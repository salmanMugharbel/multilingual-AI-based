"""
Step 1 of training: build the multilingual (question, passage) training set
and the cross-lingual test set.

Training sources (human-labelled QA datasets):
  * TyDi QA GoldP  - English, Arabic, Russian (native-speaker questions)
  * SberQuAD       - Russian
  * ARCD           - Arabic
  * SQuAD v1.1     - English
Test source (never used for training):
  * XQuAD          - the same 1190 questions / 240 paragraphs in EN, AR, RU
                     (paragraphs come from the SQuAD *dev* set, so there is no
                     overlap with the SQuAD *train* split used for training).

Output (training/data/):
  train.jsonl      {"query", "positive", "lang", "source"}
  dev.jsonl        small held-out slice of the training mix (for monitoring)
  xquad_test.json  parallel test set {lang: {"questions": [...], "contexts": [...]}}
  stats.json       dataset statistics used in the report
"""
import json
import random
from collections import Counter, defaultdict
from pathlib import Path

from datasets import load_dataset

random.seed(42)
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)

# How many pairs we keep per language (CPU-friendly budget).
PER_LANG = 5000
MAX_Q_PER_CONTEXT = 2  # avoid many questions about the same paragraph


def from_squad_like(rows, lang, source):
    """Convert SQuAD-format rows (question/context) into training pairs."""
    per_ctx = defaultdict(int)
    out = []
    for r in rows:
        ctx = r["context"].strip()
        q = r["question"].strip()
        if not ctx or not q or per_ctx[ctx] >= MAX_Q_PER_CONTEXT:
            continue
        per_ctx[ctx] += 1
        out.append({"query": q, "positive": ctx, "lang": lang, "source": source})
    return out


def load_tydi():
    """TyDi QA GoldP; ids start with the language name, e.g. 'arabic-123...'."""
    ds = load_dataset("google-research-datasets/tydiqa", "secondary_task", split="train")
    by_lang = {"en": [], "ar": [], "ru": []}
    prefix = {"english": "en", "arabic": "ar", "russian": "ru"}
    for r in ds:
        lang = prefix.get(r["id"].split("-")[0])
        if lang:
            by_lang[lang].append(r)
    return {l: from_squad_like(rows, l, "tydiqa") for l, rows in by_lang.items()}


def try_load(name, *args, **kw):
    try:
        return load_dataset(name, *args, **kw)
    except Exception as e:  # dataset moved / unavailable -> skip, report it
        print(f"  ! could not load {name}: {type(e).__name__}: {str(e)[:120]}")
        return None


def main():
    pools = {"en": [], "ar": [], "ru": []}

    print("Loading TyDi QA GoldP ...")
    for lang, pairs in load_tydi().items():
        pools[lang] += pairs
        print(f"  tydiqa {lang}: {len(pairs)}")

    print("Loading SQuAD v1.1 (en) ...")
    squad = try_load("rajpurkar/squad", split="train")
    if squad is not None:
        pools["en"] += from_squad_like(squad, "en", "squad")

    print("Loading SberQuAD (ru) ...")
    sber = try_load("kuznetsoff/sberquad", split="train") or try_load("sberquad", split="train")
    if sber is not None:
        pools["ru"] += from_squad_like(sber, "ru", "sberquad")

    print("Loading ARCD (ar) ...")
    arcd = try_load("hsseinmz/arcd", split="train")
    if arcd is not None:
        pools["ar"] += from_squad_like(arcd, "ar", "arcd")

    # Native TyDi pairs first (highest quality), then fill up with the others.
    train, dev = [], []
    for lang, pairs in pools.items():
        tydi = [p for p in pairs if p["source"] == "tydiqa"]
        other = [p for p in pairs if p["source"] != "tydiqa"]
        random.shuffle(tydi)
        random.shuffle(other)
        chosen = (tydi + other)[: PER_LANG + 200]
        random.shuffle(chosen)
        dev += chosen[:200]
        train += chosen[200:]
    random.shuffle(train)

    with open(OUT / "train.jsonl", "w", encoding="utf-8") as f:
        for p in train:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(OUT / "dev.jsonl", "w", encoding="utf-8") as f:
        for p in dev:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    print("Loading XQuAD test set (en/ar/ru) ...")
    test = {}
    for lang in ["en", "ar", "ru"]:
        x = load_dataset("google/xquad", f"xquad.{lang}", split="validation")
        contexts = list(dict.fromkeys(r["context"] for r in x))  # keep order, unique
        ctx_index = {c: i for i, c in enumerate(contexts)}
        test[lang] = {
            "ids": [r["id"] for r in x],
            "questions": [r["question"] for r in x],
            "gold": [ctx_index[r["context"]] for r in x],
            "contexts": contexts,
        }
    with open(OUT / "xquad_test.json", "w", encoding="utf-8") as f:
        json.dump(test, f, ensure_ascii=False)

    stats = {
        "available_pool": {l: dict(Counter(p["source"] for p in ps)) for l, ps in pools.items()},
        "train_size": len(train),
        "dev_size": len(dev),
        "train_by_lang": dict(Counter(p["lang"] for p in train)),
        "train_by_source": dict(Counter(p["source"] for p in train)),
        "avg_query_chars": round(sum(len(p["query"]) for p in train) / len(train), 1),
        "avg_passage_chars": round(sum(len(p["positive"]) for p in train) / len(train), 1),
        "xquad": {l: {"questions": len(t["questions"]), "contexts": len(t["contexts"])} for l, t in test.items()},
    }
    with open(OUT / "stats.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
