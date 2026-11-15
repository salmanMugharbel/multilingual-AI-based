"""
WiSE-FT style weight interpolation (Wortsman et al., 2022, "Robust fine-tuning of zero-shot models").

    theta(alpha) = (1 - alpha) * theta_base + alpha * theta_finetuned

alpha = 0 is the base model, alpha = 1 the fine-tuned model. Interpolating keeps
part of the task adaptation while recovering the robustness of the base model on
data that differs from the training distribution.
"""
import argparse
from pathlib import Path

import torch
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, required=True)
    ap.add_argument("--base", default="intfloat/multilingual-e5-small")
    ap.add_argument("--tuned", default=str(ROOT / "models" / "e5-small-multiqa"))
    args = ap.parse_args()

    base = SentenceTransformer(args.base, device="cpu")
    tuned = SentenceTransformer(args.tuned, device="cpu")
    tuned_sd = tuned.state_dict()
    with torch.no_grad():
        merged = {k: (1 - args.alpha) * v + args.alpha * tuned_sd[k] if v.is_floating_point() else v
                  for k, v in base.state_dict().items()}
    base.load_state_dict(merged)
    out = ROOT / "models" / f"e5-small-multiqa-wise{int(args.alpha * 100)}"
    base.save(str(out))
    print("saved", out)


if __name__ == "__main__":
    main()
