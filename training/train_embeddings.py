"""
Step 2 of training: fine-tune intfloat/multilingual-e5-small for retrieval.

Method: contrastive learning with MultipleNegativesRankingLoss.
For a batch of N (question, passage) pairs the model must score each question
highest against its own passage; the other N-1 passages in the batch act as
negatives ("in-batch negatives"). The NO_DUPLICATES batch sampler prevents the
same passage appearing twice in a batch (which would create false negatives).

Runs on CPU (the laptop GPU is an MX250 with 2 GB VRAM and an old driver).
"""
import argparse
import json
import time
from pathlib import Path

import torch
from datasets import Dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerTrainer,
    SentenceTransformerTrainingArguments,
    losses,
)
from sentence_transformers.training_args import BatchSamplers

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(__file__).parent / "data"
BASE = "intfloat/multilingual-e5-small"


def load_jsonl(path, limit=None):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    rows = rows[:limit] if limit else rows
    # e5 models expect these prefixes for asymmetric retrieval
    return Dataset.from_dict({
        "anchor": ["query: " + r["query"] for r in rows],
        "positive": ["passage: " + r["positive"] for r in rows],
    })


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=float, default=1)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max_seq", type=int, default=128)
    ap.add_argument("--limit", type=int, default=6000, help="use only the first N (shuffled) pairs")
    ap.add_argument("--train_word_embeddings", action="store_true",
                    help="also update the 96M-parameter word-embedding table (slow on CPU)")
    ap.add_argument("--out", default=str(ROOT / "models" / "e5-small-multiqa"))
    args = ap.parse_args()

    torch.set_num_threads(max(1, torch.get_num_threads()))
    print(f"torch threads: {torch.get_num_threads()}  cuda: {torch.cuda.is_available()}")

    model = SentenceTransformer(BASE, device="cpu")
    model.max_seq_length = args.max_seq

    # Freeze the token-embedding matrix (250k vocab x 384 = 96M of the 118M params).
    # Only the 12 transformer layers are trained: ~5x fewer trainable parameters,
    # much faster on CPU, and the shared multilingual vocabulary stays aligned.
    if not args.train_word_embeddings:
        model[0].auto_model.embeddings.word_embeddings.weight.requires_grad_(False)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print(f"trainable params: {trainable/1e6:.1f}M / {total/1e6:.1f}M")

    train_ds = load_jsonl(DATA / "train.jsonl", args.limit)
    dev_ds = load_jsonl(DATA / "dev.jsonl", 300)
    print(f"train pairs: {len(train_ds)}  dev pairs: {len(dev_ds)}")

    loss = losses.MultipleNegativesRankingLoss(model)  # scale=20, cosine similarity

    targs = SentenceTransformerTrainingArguments(
        output_dir=str(ROOT / "models" / "_checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch,
        per_device_eval_batch_size=args.batch,
        learning_rate=args.lr,
        warmup_ratio=0.1,
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        eval_strategy="epoch",
        logging_steps=10,
        save_strategy="steps",      # checkpoint so a crash (e.g. out of RAM) can resume
        save_steps=40,
        save_total_limit=1,
        report_to="none",
        use_cpu=True,
        dataloader_num_workers=0,
        seed=42,
    )

    trainer = SentenceTransformerTrainer(
        model=model, args=targs, train_dataset=train_ds, eval_dataset=dev_ds, loss=loss,
    )
    t0 = time.time()
    ckpt_dir = ROOT / "models" / "_checkpoints"
    resume = ckpt_dir.exists() and any(ckpt_dir.glob("checkpoint-*"))
    trainer.train(resume_from_checkpoint=True if resume else None)
    minutes = (time.time() - t0) / 60

    model.save(args.out)
    log = {
        "base_model": BASE,
        "train_pairs": len(train_ds),
        "epochs": args.epochs,
        "batch_size": args.batch,
        "learning_rate": args.lr,
        "max_seq_length": args.max_seq,
        "trainable_params": trainable,
        "total_params": total,
        "loss": "MultipleNegativesRankingLoss (in-batch negatives)",
        "device": "cpu",
        "train_minutes": round(minutes, 1),
        "history": trainer.state.log_history,
    }
    Path(args.out, "training_log.json").write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"saved to {args.out}  ({minutes:.1f} min)")


if __name__ == "__main__":
    main()
