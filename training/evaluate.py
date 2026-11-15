"""
Step 3 of training: compare the base model and the fine-tuned model on XQuAD.

For every (question language -> passage language) pair among EN/AR/RU we embed
the 1190 questions and the 240 paragraphs, rank paragraphs by cosine
similarity and compute:
  Recall@1, Recall@5  - is the correct paragraph in the top 1 / top 5?
  MRR@10              - mean reciprocal rank of the correct paragraph.
Cross-lingual pairs (e.g. question in English, document in Arabic) are exactly
the situation our document-QA system must handle.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / "data"
LANGS = ["en", "ar", "ru"]


def metrics(q_emb, p_emb, gold):
    scores = q_emb @ p_emb.T
    order = np.argsort(-scores, axis=1)
    ranks = np.array([np.where(order[i] == g)[0][0] + 1 for i, g in enumerate(gold)])
    return {
        "R@1": float(np.mean(ranks <= 1)),
        "R@5": float(np.mean(ranks <= 5)),
        "MRR@10": float(np.mean(np.where(ranks <= 10, 1.0 / ranks, 0.0))),
    }


def evaluate(model_name, test):
    model = SentenceTransformer(model_name, device="cpu")
    model.max_seq_length = 256
    enc = lambda texts, pfx: model.encode([pfx + t for t in texts], batch_size=64,
                                          normalize_embeddings=True, show_progress_bar=False)
    q = {l: enc(test[l]["questions"], "query: ") for l in LANGS}
    p = {l: enc(test[l]["contexts"], "passage: ") for l in LANGS}
    res = {}
    for ql in LANGS:
        for pl in LANGS:
            # gold paragraph index is the same across languages (XQuAD is parallel)
            res[f"{ql}->{pl}"] = metrics(q[ql], p[pl], test[ql]["gold"])
            print(f"  {ql}->{pl}: " + "  ".join(f"{k}={v:.3f}" for k, v in res[f"{ql}->{pl}"].items()))
    res["average"] = {k: float(np.mean([v[k] for n, v in res.items()])) for k in ["R@1", "R@5", "MRR@10"]}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="intfloat/multilingual-e5-small")
    ap.add_argument("--tuned", default=str(ROOT / "models" / "e5-small-multiqa"))
    args = ap.parse_args()

    test = json.load(open(DATA / "xquad_test.json", encoding="utf-8"))
    out = {}
    for tag, name in [("base", args.base), ("fine_tuned", args.tuned)]:
        if tag == "fine_tuned" and not Path(name).exists():
            print("fine-tuned model not found, skipping")
            continue
        print(f"== {tag}: {name}")
        out[tag] = evaluate(name, test)

    res_dir = ROOT / "training" / "results"
    res_dir.mkdir(exist_ok=True)
    (res_dir / "xquad_results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    if len(out) == 2:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        pairs = [k for k in out["base"] if k != "average"]
        x = np.arange(len(pairs))
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(x - 0.2, [out["base"][k]["MRR@10"] for k in pairs], 0.4, label="base e5-small", color="#9aa5b1")
        ax.bar(x + 0.2, [out["fine_tuned"][k]["MRR@10"] for k in pairs], 0.4, label="fine-tuned", color="#2f6fde")
        ax.set_xticks(x, pairs)
        ax.set_ylabel("MRR@10")
        ax.set_ylim(0, 1)
        ax.set_title("XQuAD retrieval (question lang -> passage lang)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(res_dir / "xquad_mrr.png", dpi=150)
        print("\nAverage:", {t: out[t]["average"] for t in out})


if __name__ == "__main__":
    main()
