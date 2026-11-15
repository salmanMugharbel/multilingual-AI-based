"""
End-to-end test against the running backend (http://127.0.0.1:8000).
Uploads the sample documents, asks monolingual and cross-lingual questions,
requests a summary and saves everything to docs/demo_results.json.
"""
import json
import sys
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000/api"
ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ["solar_energy_en.pdf", "moscow_metro_ru.pdf", "ai_ar.pdf"]

QUESTIONS = [
    ("EN→EN", "What efficiency do commercial silicon solar panels reach?", "solar_energy_en.pdf", 2),
    ("RU→RU", "Когда был открыт Московский метрополитен?", "moscow_metro_ru.pdf", 1),
    ("AR→AR", "من صاغ مصطلح الذكاء الاصطناعي ومتى؟", "ai_ar.pdf", 1),
    ("EN→RU", "Which metro station won a prize at the 1939 World's Fair in New York?", "moscow_metro_ru.pdf", 2),
    ("AR→EN", "كم انخفضت تكلفة الألواح الشمسية بين عامي 2010 و2020؟", "solar_energy_en.pdf", 2),
    ("RU→AR", "Почему арабский язык сложен для обработки?", "ai_ar.pdf", 3),
    ("EN→none", "What is the population of Australia?", None, None),
]


def stream(url, body):
    events = []
    with httpx.stream("POST", url, json=body, timeout=900) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line.strip():
                events.append(json.loads(line))
    return events


def main():
    c = httpx.Client(timeout=300)
    print("health:", c.get(f"{API}/health").json())
    # clean start
    for d in c.get(f"{API}/documents").json():
        c.delete(f"{API}/documents/{d['id']}")
    docs = {}
    for name in SAMPLES:
        with open(ROOT / "sample_docs" / name, "rb") as f:
            meta = c.post(f"{API}/documents", files={"file": (name, f)}).json()
        docs[name] = meta
        print(f"uploaded {name}: lang={meta['language']} pages={meta['pages']} chunks={meta['chunks']} "
              f"in {meta['processing_seconds']}s")

    results = {"uploads": list(docs.values()), "qa": [], "summary": None}
    for tag, q, exp_doc, exp_page in QUESTIONS:
        t0 = time.time()
        ev = stream(f"{API}/ask", {"question": q})
        src = next(e for e in ev if e["type"] == "sources")
        answer = "".join(e["text"] for e in ev if e["type"] == "token")
        errors = [e["message"] for e in ev if e["type"] == "error"]
        top = src["sources"][0] if src["sources"] else None
        correct = (top is None) if exp_doc is None else bool(top and top["filename"] == exp_doc and top["page"] == exp_page)
        item = {
            "pair": tag, "question": q, "answer": answer.strip(), "errors": errors,
            "detected_lang": src["lang"], "retrieval_ms": src["retrieval_ms"],
            "total_s": round(time.time() - t0, 1),
            "top_source": top and {k: top[k] for k in ("filename", "page", "score")},
            "expected": exp_doc and {"filename": exp_doc, "page": exp_page},
            "retrieval_correct": correct,
        }
        results["qa"].append(item)
        print(f"\n[{tag}] {q}\n  top: {item['top_source']}  correct={correct}  {item['total_s']}s\n  -> {answer.strip()[:300]}")
        if errors:
            print("  ERRORS:", errors)

    t0 = time.time()
    ev = stream(f"{API}/documents/{docs['solar_energy_en.pdf']['id']}/summary", {"lang": "en"})
    results["summary"] = {"doc": "solar_energy_en.pdf", "lang": "en",
                          "text": "".join(e["text"] for e in ev if e["type"] == "token").strip(),
                          "seconds": round(time.time() - t0, 1)}
    print("\nSUMMARY:", results["summary"]["text"][:500])

    results["llm"] = c.get(f"{API}/health").json()["llm"]["model"]
    out = ROOT / "docs" / (sys.argv[1] if len(sys.argv) > 1 else "demo_results.json")
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nsaved", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
