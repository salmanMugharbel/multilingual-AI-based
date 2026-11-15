"""
Split extracted units (pages / sections) into overlapping chunks.

We split on sentence boundaries (., !, ?, Arabic '؟' and '۔', newlines) and pack
sentences into chunks of ~CHUNK_WORDS words. Neighbouring chunks share
~CHUNK_OVERLAP words so an answer that crosses a boundary is not lost.
Chunks never cross pages, so every chunk has exactly one page reference.
"""
import re

from .config import CHUNK_OVERLAP, CHUNK_WORDS

_SENT = re.compile(r"(?<=[.!?؟۔])\s+|\n+")


def split_sentences(text: str):
    return [s.strip() for s in _SENT.split(text) if s and s.strip()]


def chunk_units(units):
    chunks = []
    for u in units:
        sents = split_sentences(u["text"])
        cur, cur_words, fresh = [], 0, False   # fresh = has sentences not yet emitted
        for s in sents:
            w = len(s.split())
            if cur and fresh and cur_words + w > CHUNK_WORDS:
                chunks.append({**_meta(u), "text": " ".join(cur)})
                fresh = False
                # keep the tail of the previous chunk as overlap
                tail, tw = [], 0
                for prev in reversed(cur):
                    tw += len(prev.split())
                    tail.insert(0, prev)
                    if tw >= CHUNK_OVERLAP:
                        break
                cur, cur_words = tail, tw
            cur.append(s)
            cur_words += w
            fresh = True
        if cur and fresh:   # skip a last chunk that would only repeat the overlap
            chunks.append({**_meta(u), "text": " ".join(cur)})
    return chunks


def _meta(u):
    return {"page": u["page"], "section": u["section"]}
