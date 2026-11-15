"""Central configuration. Values can be overridden with environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # project root (RK2/)
STORAGE = Path(os.getenv("DOCQA_STORAGE", ROOT / "backend" / "storage"))
UPLOADS = STORAGE / "uploads"
INDEX_DIR = STORAGE / "index"

# Embedding model: our fine-tuned model if it exists, else the public base model.
# We deploy the WiSE-FT interpolation (30% fine-tuned + 70% base weights), which
# kept the in-domain gain without losing accuracy on XQuAD (see training/results).
FINE_TUNED = ROOT / "models" / "e5-small-multiqa-wise30"
BASE_EMBED = "intfloat/multilingual-e5-small"
EMBED_MODEL = os.getenv("DOCQA_EMBED_MODEL", str(FINE_TUNED) if FINE_TUNED.exists() else BASE_EMBED)

# Local LLM served by Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
LLM_MODEL = os.getenv("DOCQA_LLM", "qwen2.5:3b")
LLM_CTX = int(os.getenv("DOCQA_LLM_CTX", "4096"))

# Chunking / retrieval
CHUNK_WORDS = 160         # target chunk size in words
CHUNK_OVERLAP = 40        # words shared between neighbouring chunks
TOP_K = 5                 # chunks given to the LLM
# Calibrated on 12 on-topic vs 10 off-topic questions (EN/AR/RU) with the deployed model:
# on-topic top scores 0.62-0.92, off-topic 0.50-0.68. Below MIN_SCORE the LLM is not called;
# borderline cases are handled by the prompt ("say the document does not contain this").
MIN_SCORE = 0.60
MAX_GAP = 0.10            # drop passages scoring more than this below the best passage

ALLOWED_EXT = {".pdf", ".docx", ".txt", ".md"}

for d in (UPLOADS, INDEX_DIR):
    d.mkdir(parents=True, exist_ok=True)
