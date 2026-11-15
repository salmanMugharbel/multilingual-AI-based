"""
FastAPI backend for the Multilingual Document Q&A system.

Endpoints
  GET    /api/health                    status of embedding model + Ollama
  GET    /api/documents                 list uploaded documents
  POST   /api/documents                 upload + extract + chunk + embed a file
  DELETE /api/documents/{id}            remove a document
  GET    /api/documents/{id}/file       original file (frontend opens PDF at #page=N)
  POST   /api/ask                       question -> retrieved sources + streamed answer
  POST   /api/documents/{id}/summary    streamed summary (map-reduce)

Streaming endpoints return NDJSON: one JSON object per line, e.g.
  {"type": "sources", "sources": [...]}
  {"type": "token", "text": "..."}
  {"type": "done"}
"""
import json
import time
import uuid
from collections import Counter
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from langdetect import DetectorFactory, detect
from pydantic import BaseModel

from . import llm
from .chunker import chunk_units, split_sentences
from .config import ALLOWED_EXT, EMBED_MODEL, INDEX_DIR, MAX_GAP, MIN_SCORE, ROOT, TOP_K, UPLOADS
from .extract import extract
from .store import Embedder, VectorStore

DetectorFactory.seed = 0  # deterministic language detection

app = FastAPI(title="Multilingual Document Q&A")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

print(f"Loading embedding model: {EMBED_MODEL}")
store = VectorStore(Embedder())
UNITS = INDEX_DIR / "units"
UNITS.mkdir(exist_ok=True)

# If the embedding model changed (e.g. after fine-tuning), re-embed stored documents.
for _id, _meta in store.pending_reindex.items():
    _units_file = UNITS / f"{_id}.json"
    if _units_file.exists():
        print(f"Re-indexing {_meta['filename']} with the new embedding model")
        store.add(_id, {**_meta, "summaries": _meta.get("summaries", {})},
                  chunk_units(json.loads(_units_file.read_text(encoding="utf-8"))))
store.pending_reindex = {}


def detect_lang(text: str) -> str:
    """Return 'en', 'ar', 'ru' (or 'en' as a fallback)."""
    try:
        lang = detect(text)
    except Exception:
        return "en"
    return lang if lang in ("en", "ar", "ru") else "en"


def strip_echo(text: str, question: str) -> str:
    """Remove the question if the answer starts with it (ignoring citations like [1],
    whitespace and punctuation)."""
    import re
    norm = lambda s: re.sub(r"[\W_]+", "", s).lower()
    q = norm(question)
    m = re.match(r"\s*(\[\d+\]\s*)*", text)
    prefix_cites, body = m.group(0), text[m.end():]
    if not q or not norm(body).startswith(q):
        return text
    # walk through body until we have consumed all question characters
    consumed, i = 0, 0
    while i < len(body) and consumed < len(q):
        if norm(body[i]):
            consumed += 1
        i += 1
    rest = re.sub(r"^[\s\?\؟:\-–—.,]+", "", body[i:])
    return (prefix_cites.strip() + " " + rest).strip() if prefix_cites.strip() else rest


def ndjson(obj) -> str:
    return json.dumps(obj, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- status
@app.get("/api/health")
async def health():
    return {
        "embedding_model": Path(EMBED_MODEL).name,
        "fine_tuned": Path(EMBED_MODEL).exists(),
        "documents": len(store.docs),
        "chunks": len(store.chunks),
        "llm": await llm.ollama_status(),
    }


# ---------------------------------------------------------------- documents
@app.get("/api/documents")
def list_documents():
    return sorted(store.docs.values(), key=lambda d: d["uploaded_at"], reverse=True)


@app.post("/api/documents")
async def upload(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported file type {ext}. Use PDF, DOCX or TXT.")
    doc_id = uuid.uuid4().hex[:12]
    path = UPLOADS / f"{doc_id}{ext}"
    path.write_bytes(await file.read())

    t0 = time.time()
    try:
        units = extract(path)
    except Exception as e:
        path.unlink(missing_ok=True)
        raise HTTPException(400, f"Could not read the file: {e}")
    if not units:
        path.unlink(missing_ok=True)
        raise HTTPException(400, "No text found in the document (scanned PDF without OCR?).")

    chunks = chunk_units(units)
    # dominant language of the document, detected per unit
    langs = Counter(detect_lang(u["text"][:1000]) for u in units)
    meta = {
        "id": doc_id,
        "filename": file.filename,
        "ext": ext,
        "pages": max((u["page"] or 0) for u in units) or None,
        "sections": len(units),
        "chunks": len(chunks),
        "language": langs.most_common(1)[0][0],
        "languages": dict(langs),
        "words": sum(len(u["text"].split()) for u in units),
        "uploaded_at": time.time(),
        "summaries": {},
    }
    (UNITS / f"{doc_id}.json").write_text(json.dumps(units, ensure_ascii=False), encoding="utf-8")
    store.add(doc_id, meta, chunks)
    meta["processing_seconds"] = round(time.time() - t0, 2)
    return meta


@app.delete("/api/documents/{doc_id}")
def delete(doc_id: str):
    meta = store.docs.get(doc_id)
    if not meta:
        raise HTTPException(404, "Document not found")
    store.delete(doc_id)
    (UPLOADS / f"{doc_id}{meta['ext']}").unlink(missing_ok=True)
    (UNITS / f"{doc_id}.json").unlink(missing_ok=True)
    return {"deleted": doc_id}


@app.get("/api/documents/{doc_id}/file")
def get_file(doc_id: str):
    meta = store.docs.get(doc_id)
    if not meta:
        raise HTTPException(404, "Document not found")
    return FileResponse(UPLOADS / f"{doc_id}{meta['ext']}", filename=meta["filename"],
                        content_disposition_type="inline")


class PageRequest(BaseModel):
    highlight: str | None = None


@app.post("/api/documents/{doc_id}/page/{page_no}")
def page_image(doc_id: str, page_no: int, req: PageRequest):
    """Render one PDF page as PNG and highlight the cited passage on it.
    Works in every browser (no PDF plugin needed)."""
    import pymupdf
    from fastapi.responses import Response

    meta = store.docs.get(doc_id)
    if not meta or meta["ext"] != ".pdf":
        raise HTTPException(404, "PDF not found")
    with pymupdf.open(UPLOADS / f"{doc_id}.pdf") as pdf:
        if not 1 <= page_no <= len(pdf):
            raise HTTPException(404, "Page out of range")
        page = pdf[page_no - 1]
        if req.highlight:
            # search sentence by sentence (shorter strings match more reliably across line breaks)
            for sent in split_sentences(req.highlight):
                words = sent.split()
                for i in range(0, len(words), 8):
                    piece = " ".join(words[i:i + 8])
                    if len(piece) < 4:
                        continue
                    quads = page.search_for(piece, quads=True)
                    if quads:
                        page.add_highlight_annot(quads).update()
        png = page.get_pixmap(dpi=110, annots=True).tobytes("png")
    return Response(png, media_type="image/png", headers={"X-Page-Count": str(meta["pages"] or 1)})


# ---------------------------------------------------------------- Q&A
class AskRequest(BaseModel):
    question: str
    doc_ids: list[str] | None = None
    top_k: int = TOP_K
    answer_lang: str | None = None   # None = same language as the question


@app.post("/api/ask")
async def ask(req: AskRequest):
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Empty question")
    lang = req.answer_lang or detect_lang(question)
    t0 = time.time()
    hits = store.search(question, k=req.top_k, doc_ids=req.doc_ids or None)
    retrieval_ms = round((time.time() - t0) * 1000)
    best = hits[0]["score"] if hits else 0
    relevant = [h for h in hits if h["score"] >= MIN_SCORE and h["score"] >= best - MAX_GAP]

    async def gen():
        yield ndjson({"type": "sources", "lang": lang, "retrieval_ms": retrieval_ms,
                      "sources": [{"n": i + 1, "doc_id": h["doc_id"], "filename": h["filename"],
                                   "page": h["page"], "section": h["section"],
                                   "score": round(h["score"], 3), "text": h["text"]}
                                  for i, h in enumerate(relevant)]})
        if not relevant:
            msg = {"en": "I could not find relevant information in the uploaded documents.",
                   "ar": "لم أتمكن من العثور على معلومات ذات صلة في المستندات المرفوعة.",
                   "ru": "Я не нашёл подходящей информации в загруженных документах."}[lang]
            yield ndjson({"type": "token", "text": msg})
        else:
            try:
                # Small LLMs sometimes start by repeating the question. Hold back the first
                # tokens; if they echo the question, strip that prefix before streaming.
                held, released = "", False
                async for piece in llm.stream_chat(llm.qa_messages(question, relevant, lang)):
                    if released:
                        yield ndjson({"type": "token", "text": piece})
                        continue
                    held += piece
                    if len(held) >= len(question) + 8:
                        released = True
                        yield ndjson({"type": "token", "text": strip_echo(held, question)})
                if not released and held:
                    yield ndjson({"type": "token", "text": strip_echo(held, question)})
            except Exception as e:
                yield ndjson({"type": "error", "message": f"LLM unavailable: {e}. Is Ollama running?"})
        yield ndjson({"type": "done", "total_ms": round((time.time() - t0) * 1000)})

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# ---------------------------------------------------------------- summary
class SummaryRequest(BaseModel):
    lang: str | None = None   # None = document language


def split_parts(units, max_chars=2500, max_parts=8):
    parts, buf = [], ""
    for u in units:
        for para in u["text"].split("\n\n"):
            if len(buf) + len(para) > max_chars and buf:
                parts.append(buf)
                buf = ""
            buf += para[:max_chars] + "\n\n"
    if buf.strip():
        parts.append(buf)
    if len(parts) > max_parts:  # long document: sample parts evenly across it
        step = len(parts) / max_parts
        parts = [parts[int(i * step)] for i in range(max_parts)]
    return parts


@app.post("/api/documents/{doc_id}/summary")
async def summary(doc_id: str, req: SummaryRequest):
    meta = store.docs.get(doc_id)
    if not meta:
        raise HTTPException(404, "Document not found")
    lang = req.lang or meta["language"]
    lang_name = llm.LANG_NAMES.get(lang, "English")

    async def gen():
        cached = meta.get("summaries", {}).get(lang)
        if cached:
            yield ndjson({"type": "token", "text": cached})
            yield ndjson({"type": "done", "cached": True})
            return
        units = json.loads((UNITS / f"{doc_id}.json").read_text(encoding="utf-8"))
        parts = split_parts(units)
        try:
            if len(parts) == 1:
                final_input = parts[0]
            else:
                # MAP: summarise each part separately
                partials = []
                for i, p in enumerate(parts, 1):
                    yield ndjson({"type": "progress", "step": i, "total": len(parts)})
                    partials.append(await llm.chat([{"role": "user", "content":
                                                     llm.SUMMARY_PART.format(lang=lang_name, text=p)}]))
                final_input = "\n\n".join(f"Part {i}: {s}" for i, s in enumerate(partials, 1))
            # REDUCE: combine into the final summary (streamed)
            yield ndjson({"type": "progress", "step": "final"})
            out = ""
            async for piece in llm.stream_chat([{"role": "user", "content": llm.SUMMARY_FINAL.format(
                    name=meta["filename"], lang=lang_name, text=final_input)}], temperature=0.3):
                out += piece
                yield ndjson({"type": "token", "text": piece})
            meta.setdefault("summaries", {})[lang] = out.strip()
            store._save()
        except Exception as e:
            yield ndjson({"type": "error", "message": f"LLM unavailable: {e}. Is Ollama running?"})
        yield ndjson({"type": "done"})

    return StreamingResponse(gen(), media_type="application/x-ndjson")


# ---------------------------------------------------------------- frontend (production build)
@app.middleware("http")
async def no_cache_html(request, call_next):
    # index.html must never be cached, otherwise a rebuilt frontend is not picked up
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="frontend")
