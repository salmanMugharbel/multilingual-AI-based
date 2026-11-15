"""
Answer generation and summarisation with a local LLM served by Ollama.

The LLM never sees the whole document. It only receives the retrieved chunks
(numbered [1]..[k]) and is instructed to answer ONLY from them and to cite the
numbers. This "grounding" is what keeps answers tied to the real document.
"""
import json

import httpx

from .config import LLM_CTX, LLM_MODEL, OLLAMA_URL

LANG_NAMES = {"en": "English", "ar": "Arabic", "ru": "Russian"}

QA_SYSTEM = (
    "You are a precise document assistant. Answer the user's question using ONLY the "
    "numbered context passages. After each fact, cite its passage number in square brackets, "
    "e.g. [1] or [2][3]. If the passages do not contain the answer, say clearly that the "
    "document does not contain this information. Do not invent facts. Do not repeat the "
    "question. Answer in one to three complete sentences. "
    "Always write the answer in {lang}, even if the passages are in another language."
)

SUMMARY_PART = (
    "Summarise the following part of a document in 2-4 sentences in {lang}. "
    "Keep names, numbers and key facts. Output only the summary.\n\n{text}"
)

SUMMARY_FINAL = (
    "Below are summaries of consecutive parts of one document called \"{name}\". "
    "Write a concise overall summary in {lang}: one short paragraph followed by 3-6 bullet "
    "points with the key points. Output only the summary.\n\n{text}"
)


def build_context(hits):
    lines = []
    for i, h in enumerate(hits, start=1):
        where = f"page {h['page']}" if h.get("page") else (h.get("section") or "")
        lines.append(f"[{i}] ({h['filename']}, {where})\n{h['text']}")
    return "\n\n".join(lines)


async def stream_chat(messages, temperature=0.2):
    """Yield text pieces from Ollama as they are generated."""
    payload = {"model": LLM_MODEL, "messages": messages, "stream": True,
               "options": {"temperature": temperature, "num_ctx": LLM_CTX}}
    async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=5)) as client:
        async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as r:
            if r.status_code != 200:
                body = await r.aread()
                raise RuntimeError(f"Ollama error {r.status_code}: {body.decode()[:200]}")
            async for line in r.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                piece = data.get("message", {}).get("content", "")
                if piece:
                    yield piece
                if data.get("done"):
                    break


async def chat(messages, temperature=0.2):
    return "".join([p async for p in stream_chat(messages, temperature)]).strip()


def qa_messages(question, hits, lang):
    return [
        {"role": "system", "content": QA_SYSTEM.format(lang=LANG_NAMES.get(lang, "English"))},
        {"role": "user", "content": f"Context passages:\n\n{build_context(hits)}\n\nQuestion: {question}"},
    ]


async def ollama_status():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{OLLAMA_URL}/api/tags")
            names = [m["name"] for m in r.json().get("models", [])]
            return {"running": True, "model": LLM_MODEL, "model_available": LLM_MODEL in names}
    except Exception:
        return {"running": False, "model": LLM_MODEL, "model_available": False}
