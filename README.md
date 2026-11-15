# DocQA — Intelligent Multilingual Document Question-Answering

**Author:** Salman Mugharbel — Systems of Artificial Intelligence, RK2 project

Upload documents in **English, Arabic or Russian**, ask questions in any of these
languages, and get answers generated only from the document text, with
**clickable page references** and **document summaries**. Everything runs locally.

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite |
| Backend | Python FastAPI |
| Retrieval model | `multilingual-e5-small`, **fine-tuned by us** on 6k EN/AR/RU QA pairs + WiSE-FT interpolation |
| Vector index | FAISS (exact cosine search) |
| Generator | Qwen2.5-3B-Instruct running locally in Ollama |
| Extraction | PyMuPDF (PDF, page numbers), python-docx (DOCX sections), optional Tesseract OCR |

## Project structure
```
backend/app/        FastAPI app: extract.py, chunker.py, store.py, llm.py, main.py
frontend/src/       React UI
training/           prepare_data.py, train_embeddings.py, evaluate.py, results/
models/             fine-tuned embedding model (created by training)
sample_docs/        demo documents in EN / RU / AR
docs/               project report
start.ps1           one-command launcher
```

## Setup (once)
```powershell
python -m venv $env:USERPROFILE\.venvs\rk2
$py = "$env:USERPROFILE\.venvs\rk2\Scripts\python.exe"
& $py -m pip install torch --index-url https://download.pytorch.org/whl/cpu
& $py -m pip install -r requirements.txt
winget install Ollama.Ollama
ollama pull qwen2.5:3b
cd frontend; npm install; npm run build; cd ..
```

## Train the retrieval model
The trained models are **not stored in this repository** (each is ~470 MB, above GitHub's
file limit). Run the steps below once (~1 hour on a laptop CPU) to create
`models/e5-small-multiqa` and `models/e5-small-multiqa-wise30`. Without them, the app
automatically falls back to the public base model `intfloat/multilingual-e5-small`.
```powershell
cd training
& $py prepare_data.py           # downloads TyDi QA, SQuAD, ARCD, XQuAD -> data/
& $py train_embeddings.py       # fine-tunes e5-small on CPU (~1 h) -> ../models/e5-small-multiqa
& $py interpolate.py --alpha 0.3 # WiSE-FT weight averaging -> ../models/e5-small-multiqa-wise30 (deployed)
& $py evaluate_all.py           # base / fine-tuned / WiSE on dev + XQuAD -> results/all_models.json
```

| Model | In-domain dev MRR@10 | XQuAD MRR@10 |
|---|---|---|
| base multilingual-e5-small | 0.963 | 0.865 |
| fine-tuned | 0.977 | 0.828 |
| **WiSE-FT α=0.3 (deployed)** | **0.975** | **0.866** |

## Run
```powershell
.\start.ps1
```
Open <http://127.0.0.1:8000>. For UI development with hot reload, run the backend
and `cd frontend; npm run dev`, then open <http://localhost:5173>.

**Speed tip (8 GB RAM):** close other heavy programs (browser tabs, Oracle DB, VS Code) before the
demo — if RAM is full, Windows pages the LLM to disk and answers take 1–2 minutes instead of seconds.
`.\start.ps1 -Llm qwen2.5:1.5b` uses a smaller, faster (but less accurate) model.

End-to-end test (backend must be running): `& $py tests\run_demo.py`
Report: `& $py docs\build_report.py` → `docs/Project_Report.docx` · Viva notes: `docs/VIVA_NOTES.md`
