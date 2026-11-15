"""
Vector store: embeddings + metadata for every chunk of every document.

* Embeddings are L2-normalised, so inner product == cosine similarity.
* A FAISS IndexFlatIP (exact search) holds all chunk vectors. For a student
  project with thousands of chunks exact search takes milliseconds.
* Everything is persisted to backend/storage/index so documents survive a restart.
"""
import json
import threading

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from .config import EMBED_MODEL, INDEX_DIR


class Embedder:
    def __init__(self, name=EMBED_MODEL):
        self.name = name
        self.model = SentenceTransformer(name, device="cpu")
        self.model.max_seq_length = 256
        self.dim = self.model.get_sentence_embedding_dimension()

    # e5 models are trained with "query: " / "passage: " prefixes
    def passages(self, texts):
        return self.model.encode(["passage: " + t for t in texts], batch_size=32,
                                 normalize_embeddings=True, convert_to_numpy=True).astype("float32")

    def query(self, text):
        return self.model.encode(["query: " + text], normalize_embeddings=True,
                                 convert_to_numpy=True).astype("float32")


class VectorStore:
    def __init__(self, embedder: Embedder):
        self.emb = embedder
        self.lock = threading.Lock()
        self.docs = {}       # doc_id -> metadata
        self.chunks = []     # list of {doc_id, page, section, text}
        self.vectors = np.zeros((0, embedder.dim), dtype="float32")
        self.pending_reindex = {}
        self._load()

    # ---------- persistence ----------
    def _load(self):
        meta = INDEX_DIR / "meta.json"
        vecs = INDEX_DIR / "vectors.npy"
        if meta.exists() and vecs.exists():
            data = json.loads(meta.read_text(encoding="utf-8"))
            if data.get("embed_model") == self.emb.name:
                self.docs, self.chunks = data["docs"], data["chunks"]
                self.vectors = np.load(vecs)
            else:  # embedding model changed -> old vectors are incompatible, re-index later
                self.pending_reindex = data["docs"]
        self._rebuild()

    def _save(self):
        (INDEX_DIR / "meta.json").write_text(json.dumps(
            {"embed_model": self.emb.name, "docs": self.docs, "chunks": self.chunks},
            ensure_ascii=False), encoding="utf-8")
        np.save(INDEX_DIR / "vectors.npy", self.vectors)

    def _rebuild(self):
        self.index = faiss.IndexFlatIP(self.emb.dim)
        if len(self.vectors):
            self.index.add(self.vectors)

    # ---------- operations ----------
    def add(self, doc_id, meta, chunks):
        vecs = self.emb.passages([c["text"] for c in chunks])
        with self.lock:
            self.docs[doc_id] = meta
            self.chunks += [{**c, "doc_id": doc_id} for c in chunks]
            self.vectors = np.vstack([self.vectors, vecs])
            self.index.add(vecs)
            self._save()

    def delete(self, doc_id):
        with self.lock:
            keep = [i for i, c in enumerate(self.chunks) if c["doc_id"] != doc_id]
            self.chunks = [self.chunks[i] for i in keep]
            self.vectors = self.vectors[keep] if keep else np.zeros((0, self.emb.dim), "float32")
            self.docs.pop(doc_id, None)
            self._rebuild()
            self._save()

    def doc_chunks(self, doc_id):
        return [c for c in self.chunks if c["doc_id"] == doc_id]

    def search(self, question, k=5, doc_ids=None):
        if not len(self.chunks):
            return []
        q = self.emb.query(question)
        # search wider when filtering by document, then filter
        n = len(self.chunks) if doc_ids else min(k * 4, len(self.chunks))
        scores, idx = self.index.search(q, n)
        hits = []
        for s, i in zip(scores[0], idx[0]):
            if i < 0:
                continue
            c = self.chunks[i]
            if doc_ids and c["doc_id"] not in doc_ids:
                continue
            hits.append({**c, "score": float(s), "filename": self.docs[c["doc_id"]]["filename"]})
            if len(hits) >= k:
                break
        return hits
