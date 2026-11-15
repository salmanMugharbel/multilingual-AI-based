"""
Text extraction. Every extractor returns a list of "units":
    {"page": int | None, "section": str | None, "text": str}
so that each answer can point back to a page (PDF) or section (DOCX/TXT).
"""
import re
import unicodedata
from pathlib import Path

import pymupdf  # PyMuPDF
from docx import Document


_PRES_FORMS = re.compile(r"[ﭐ-﷿ﹰ-﻿]")


def _fix_arabic(text: str) -> str:
    """Some PDFs store Arabic as 'presentation forms' in visual (left-to-right)
    order. NFKC maps the glyph forms back to normal letters and, for lines that
    were stored visually, we reverse the word order to restore logical order."""
    if not _PRES_FORMS.search(text):
        return text
    lines = []
    for line in text.split("\n"):
        visual = bool(_PRES_FORMS.search(line))
        line = unicodedata.normalize("NFKC", line)
        if visual:
            line = " ".join(w[::-1] if not re.search(r"\d", w) else w for w in reversed(line.split()))
        lines.append(line)
    return "\n".join(lines)


def _clean(text: str) -> str:
    text = _fix_arabic(text)
    text = text.replace("­", "")                 # soft hyphens
    text = re.sub(r"-\n(\w)", r"\1", text)            # re-join hyphenated line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf(path: Path):
    units = []
    with pymupdf.open(path) as doc:
        for i, page in enumerate(doc, start=1):
            # NOTE: no sort=True - sorting by x-position reverses Arabic (RTL) word order
            text = page.get_text("text")
            if len(text.strip()) < 20:
                text = _ocr_page(page) or text      # scanned page -> try OCR
            text = _clean(text)
            if text:
                units.append({"page": i, "section": None, "text": text})
    return units


def _ocr_page(page):
    """OCR via Tesseract if it is installed (optional). Languages: eng+ara+rus."""
    try:
        tp = page.get_textpage_ocr(language="eng+ara+rus", dpi=200, full=True)
        return page.get_text("text", textpage=tp)
    except Exception:
        return None


def extract_docx(path: Path):
    """DOCX has no fixed pages, so we split by headings into sections."""
    doc = Document(path)
    units, title, buf = [], "Introduction", []
    n = 0

    def flush():
        nonlocal n
        if buf:
            n += 1
            units.append({"page": None, "section": f"§{n} {title}"[:80], "text": _clean("\n".join(buf))})

    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        if p.style is not None and p.style.name.lower().startswith(("heading", "title")):
            flush()
            title, buf = t, [t]
        else:
            buf.append(t)
    flush()
    for ti, table in enumerate(doc.tables, start=1):
        rows = [" | ".join(c.text.strip() for c in r.cells) for r in table.rows]
        units.append({"page": None, "section": f"Table {ti}", "text": _clean("\n".join(rows))})
    return [u for u in units if u["text"]]


def extract_txt(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    parts = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    # group paragraphs into sections of ~300 words
    units, buf, words = [], [], 0
    for p in parts:
        buf.append(p)
        words += len(p.split())
        if words >= 300:
            units.append({"page": None, "section": f"Part {len(units)+1}", "text": _clean("\n\n".join(buf))})
            buf, words = [], 0
    if buf:
        units.append({"page": None, "section": f"Part {len(units)+1}", "text": _clean("\n\n".join(buf))})
    return units


def extract(path: Path):
    ext = path.suffix.lower()
    if ext == ".pdf":
        return extract_pdf(path)
    if ext == ".docx":
        return extract_docx(path)
    return extract_txt(path)
