"""Draws the system architecture diagram used in the report (docs/architecture.png)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

fig, ax = plt.subplots(figsize=(11, 6.2))
ax.set_xlim(0, 11)
ax.set_ylim(0, 6.2)
ax.axis("off")

C = {"fe": "#dbe7fb", "be": "#e3f4e8", "ai": "#fde9d9", "st": "#eeeaf7"}


def box(x, y, w, h, title, sub, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.12",
                                fc=color, ec="#4a5568", lw=1.2))
    ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="top", fontsize=10.5, weight="bold")
    ax.text(x + w / 2, y + h - 0.62, sub, ha="center", va="top", fontsize=8.5, color="#333", linespacing=1.35)


def arrow(x1, y1, x2, y2, label=""):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14, lw=1.3, color="#4a5568"))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, label, ha="center", fontsize=8, color="#2d3748")


box(0.2, 4.4, 2.4, 1.5, "React frontend", "upload · chat · citations\nPDF viewer · summaries", C["fe"])
box(3.4, 4.4, 2.6, 1.5, "FastAPI backend", "REST + streaming (NDJSON)\nlanguage detection", C["be"])
box(0.2, 2.2, 2.4, 1.6, "Extraction", "PyMuPDF (pages)\npython-docx (sections)\nArabic normalisation, OCR", C["be"])
box(3.4, 2.2, 2.6, 1.6, "Chunker", "~160-word chunks\n40-word overlap\npage / section metadata", C["be"])
box(6.8, 2.2, 2.0, 1.6, "Embedding model", "multilingual-e5-small\nFINE-TUNED by us\n384-dim vectors", C["ai"])
box(6.8, 0.2, 2.0, 1.5, "FAISS index", "cosine (inner product)\npersisted to disk", C["st"])
box(6.8, 4.4, 2.0, 1.5, "Retriever", "top-k passages\nscore threshold", C["be"])
box(9.2, 4.4, 1.6, 1.5, "Ollama LLM", "Qwen2.5-3B\ngrounded answer\n+ [n] citations", C["ai"])
box(9.2, 2.2, 1.6, 1.6, "Summariser", "map-reduce\nover document\nparts", C["ai"])

arrow(2.6, 5.15, 3.4, 5.15, "HTTP")
arrow(4.7, 4.4, 4.7, 3.8)
ax.text(4.8, 4.05, "upload", fontsize=8)
arrow(3.4, 3.0, 2.6, 3.0)
arrow(2.6, 2.6, 3.4, 2.6)
arrow(6.0, 3.0, 6.8, 3.0, "chunks")
arrow(7.8, 2.2, 7.8, 1.7, "")
arrow(6.0, 5.15, 6.8, 5.15, "question")
arrow(7.8, 4.4, 7.8, 3.8)
ax.text(7.9, 4.05, "embed query", fontsize=8)
arrow(8.8, 5.15, 9.2, 5.15)
arrow(10.0, 4.4, 10.0, 3.8)
# retriever <-> FAISS search path routed around the embedding box
ax.plot([8.8, 9.0, 9.0, 8.8], [4.6, 4.6, 0.95, 0.95], ls="--", color="#4a5568", lw=1.0)
ax.add_patch(FancyArrowPatch((9.0, 0.95), (8.8, 0.95), arrowstyle="-|>", mutation_scale=12, color="#4a5568"))
ax.text(9.08, 1.2, "nearest-neighbour\nsearch", fontsize=8)
ax.text(10.08, 4.05, "uses", fontsize=8)

ax.text(5.5, 6.05, "Multilingual Document Q&A — system architecture (all components run locally)",
        ha="center", fontsize=12, weight="bold")
fig.savefig(Path(__file__).parent / "architecture.png", dpi=160, bbox_inches="tight")
print("saved")
