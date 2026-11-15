"""
Evaluate several embedding models on two test sets:
  * XQuAD (out-of-domain, parallel, 9 monolingual + cross-lingual pairs)
  * in-domain dev set: 600 held-out pairs from the training distribution
    (TyDi QA / SQuAD / ARCD), 200 per language, each question ranked against
    all 600 dev passages.
Results -> training/results/all_models.json
"""
import json
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

from evaluate import LANGS, metrics

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / "data"


def run(name):
    m = SentenceTransformer(name, device="cpu")
    m.max_seq_length = 256
    enc = lambda t, pfx: m.encode([pfx + x for x in t], batch_size=64, normalize_embeddings=True)

    # in-domain dev
    dev = [json.loads(l) for l in open(DATA / "dev.jsonl", encoding="utf-8")]
    passages = list(dict.fromkeys(d["positive"] for d in dev))
    pidx = {p: i for i, p in enumerate(passages)}
    P = enc(passages, "passage: ")
    out = {"dev": {}}
    for lang in LANGS:
        sub = [d for d in dev if d["lang"] == lang]
        out["dev"][lang] = metrics(enc([d["query"] for d in sub], "query: "), P, [pidx[d["positive"]] for d in sub])
    out["dev"]["average"] = {k: float(np.mean([out["dev"][l][k] for l in LANGS])) for k in ["R@1", "R@5", "MRR@10"]}

    # XQuAD
    test = json.load(open(DATA / "xquad_test.json", encoding="utf-8"))
    q = {l: enc(test[l]["questions"], "query: ") for l in LANGS}
    p = {l: enc(test[l]["contexts"], "passage: ") for l in LANGS}
    out["xquad"] = {f"{a}->{b}": metrics(q[a], p[b], test[a]["gold"]) for a in LANGS for b in LANGS}
    pairs = list(out["xquad"])
    out["xquad"]["average"] = {k: float(np.mean([out["xquad"][x][k] for x in pairs])) for k in ["R@1", "R@5", "MRR@10"]}
    return out


if __name__ == "__main__":
    models = {
        "base": "intfloat/multilingual-e5-small",
        "fine_tuned": str(ROOT / "models" / "e5-small-multiqa"),
    }
    for p in sorted((ROOT / "models").glob("e5-small-multiqa-wise*")):
        models[p.name.replace("e5-small-multiqa-", "")] = str(p)
    for extra in sys.argv[1:]:
        models[Path(extra).name] = extra
    res = {}
    for tag, name in models.items():
        res[tag] = run(name)
        print(f"{tag:12s} dev MRR={res[tag]['dev']['average']['MRR@10']:.4f} R@1={res[tag]['dev']['average']['R@1']:.4f} | "
              f"xquad MRR={res[tag]['xquad']['average']['MRR@10']:.4f} R@1={res[tag]['xquad']['average']['R@1']:.4f}", flush=True)
    (ROOT / "training" / "results" / "all_models.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
