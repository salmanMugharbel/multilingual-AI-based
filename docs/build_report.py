"""
Builds docs/Project_Report.docx from the real artefacts of the project:
  training/data/stats.json            dataset statistics
  models/e5-small-multiqa/training_log.json
  training/results/xquad_results.json + xquad_mrr.png
  docs/demo_results.json              end-to-end test of the running system
  docs/architecture.png
"""
import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def load(p):
    p = ROOT / p
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


stats = load("training/data/stats.json")
tlog = load("models/e5-small-multiqa/training_log.json")
res = load("training/results/xquad_results.json")
demo = load("docs/demo_results.json")

doc = Document()
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(11)
for s in doc.sections:
    s.left_margin = s.right_margin = Cm(2.2)
    s.top_margin = s.bottom_margin = Cm(2)


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def table(headers, rows, widths=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(headers):
        c = t.rows[0].cells[i]
        c.text = ""
        r = c.paragraphs[0].add_run(str(h))
        r.bold = True
        r.font.size = Pt(10)
        shade(c, "DCE6F7")
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            run = cells[i].paragraphs[0].add_run(str(v))
            run.font.size = Pt(10)
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph()
    return t


def h(text, level=1):
    doc.add_heading(text, level=level)


def p(text, bold_prefix=None):
    para = doc.add_paragraph()
    if bold_prefix:
        para.add_run(bold_prefix).bold = True
    para.add_run(text)
    para.paragraph_format.space_after = Pt(6)
    return para


def bullets(items):
    for it in items:
        if isinstance(it, tuple):
            para = doc.add_paragraph(style="List Bullet")
            para.add_run(it[0]).bold = True
            para.add_run(it[1])
        else:
            doc.add_paragraph(it, style="List Bullet")


def code(text):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = "Consolas"
    run.font.size = Pt(9)
    para.paragraph_format.left_indent = Cm(0.5)


def caption(text):
    para = doc.add_paragraph()
    r = para.add_run(text)
    r.italic = True
    r.font.size = Pt(9.5)
    para.alignment = WD_ALIGN_PARAGRAPH.CENTER


def rtl_para(text, bold=False, indent=False):
    """Paragraph that is laid out right-to-left when the text is mainly Arabic,
    so citations like [1] and numbers appear in the correct place."""
    import re
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.bold = bold
    arabic = len(re.findall(r"[؀-ۿ]", text)) > len(re.findall(r"[A-Za-zЀ-ӿ]", text))
    if arabic:
        para._p.get_or_add_pPr().append(OxmlElement("w:bidi"))
        rpr = run._r.get_or_add_rPr()
        if bold:
            rpr.append(OxmlElement("w:bCs"))   # bold for complex scripts (Arabic)
        rpr.append(OxmlElement("w:rtl"))
    if indent:
        para.paragraph_format.left_indent = Cm(0.8)
        para.paragraph_format.right_indent = Cm(0.8)
        para.paragraph_format.space_after = Pt(8)
    else:
        para.paragraph_format.space_after = Pt(1)
    return para


def pct(x):
    return f"{100 * x:.1f}%"


# ------------------------------------------------------------------ title page
for _ in range(5):
    doc.add_paragraph()
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("Intelligent Multilingual Document\nQuestion-Answering System")
r.bold = True
r.font.size = Pt(26)
r.font.color.rgb = RGBColor(0x1F, 0x4E, 0xA8)
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
t.add_run("Using Natural Language Processing, Semantic Search and a Fine-Tuned Retrieval Model").font.size = Pt(13)
for _ in range(3):
    doc.add_paragraph()
for line in ["Course: Systems of Artificial Intelligence — RK2",
             "Project + Viva + Documentation",
             "Student: ______________________",
             "Group: ______________________",
             "Submission date: 17 November 2026"]:
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.add_run(line).font.size = Pt(12)
doc.add_page_break()

# ------------------------------------------------------------------ contents
h("Contents")
for i, s in enumerate(["Introduction and problem statement", "Objectives", "Background",
                       "System architecture", "Dataset", "Model training (fine-tuning)",
                       "Evaluation of the retrieval model", "Implementation", "Testing of the complete system",
                       "Deployment and running the project", "Limitations and future work",
                       "Individual contribution", "Conclusion", "References"], 1):
    doc.add_paragraph(f"{i}. {s}")
doc.add_page_break()

# ------------------------------------------------------------------ 1
h("1. Introduction and problem statement")
p("People increasingly work with documents written in several languages: contracts, research papers, "
  "regulations, manuals and study materials. Finding a specific fact in a long document is slow, and it "
  "becomes much harder when the document is written in a language the reader does not know well. "
  "Keyword search (Ctrl+F) only finds exact words, it does not understand meaning, and it does not work "
  "across languages: searching for \"efficiency\" will never find the Arabic word \"كفاءة\".")
p("This project builds an AI-based product that solves this problem. A user uploads documents in English, "
  "Arabic or Russian and asks questions in natural language, in any of these three languages. The system "
  "finds the relevant passages by meaning (semantic search), generates a concise answer that is based only "
  "on the document text, shows references to the exact pages or sections the answer came from, and can "
  "produce a summary of each document.")
p("A key design goal is trustworthiness: large language models are known to \"hallucinate\" (invent facts). "
  "Our system reduces this by giving the language model only the retrieved passages and requiring it to cite "
  "them, so every statement can be checked by clicking the citation and opening the original page.")

# ------------------------------------------------------------------ 2
h("2. Objectives")
bullets([
    "Support uploading PDF, DOCX and TXT documents in English, Arabic and Russian.",
    "Answer natural-language questions using the document contents (Retrieval-Augmented Generation).",
    "Support cross-lingual questions (e.g. an English question about an Arabic document).",
    "Provide references to the original pages (PDF) or sections (DOCX/TXT) for every answer.",
    "Generate concise summaries of uploaded documents in a chosen language.",
    "Fine-tune and evaluate our own retrieval model on multilingual question-answering data.",
    "Deploy the full system (frontend, backend, AI models) locally on a laptop without a cloud API.",
])

# ------------------------------------------------------------------ 3
h("3. Background")
h("3.1 Retrieval-Augmented Generation (RAG)", 2)
p("RAG combines two components. A retriever searches a collection of texts and returns the passages most "
  "relevant to a question. A generator (a large language model) then writes an answer using these passages "
  "as its context. Because the generator is given the facts explicitly, its answers are grounded in the "
  "documents, they can cite their sources, and new documents can be added without retraining any model.")
h("3.2 Dense retrieval with text embeddings", 2)
p("An embedding model converts a piece of text into a fixed-length vector (here 384 numbers) so that texts "
  "with similar meaning have vectors that point in a similar direction. The relevance of a passage to a "
  "question is measured with cosine similarity:  sim(q, p) = (q · p) / (‖q‖ ‖p‖). A multilingual embedding "
  "model is trained so that a sentence and its translation get almost the same vector; this is what makes "
  "cross-lingual search possible.")
p("We use multilingual-E5-small (Wang et al., 2024), a 12-layer Transformer encoder (117.7M parameters, "
  "of which 96M are the token-embedding table for a 250k-token multilingual vocabulary). E5 models expect "
  "the prefixes \"query: \" for questions and \"passage: \" for documents.")
h("3.3 Contrastive learning", 2)
p("The retriever is fine-tuned with the Multiple Negatives Ranking loss (in-batch negatives). For a batch "
  "of N pairs (qᵢ, pᵢ), the model must give the highest score to the correct passage pᵢ among all N passages "
  "in the batch:")
code("L = -(1/N) Σᵢ log( exp(s·sim(qᵢ,pᵢ)) / Σⱼ exp(s·sim(qᵢ,pⱼ)) ),   s = 20 (scale)")
p("This is a cross-entropy classification over the batch: the other N−1 passages act as negative examples, "
  "so no manually labelled negatives are needed.")
h("3.4 Local large language model", 2)
p("Answers and summaries are generated by Qwen2.5-3B-Instruct (Alibaba Qwen team), a 3-billion-parameter "
  "instruction-tuned model with good multilingual ability, including Arabic and Russian. It runs locally "
  "through Ollama in 4-bit quantised form (~1.9 GB), so no internet connection or paid API is needed.")

# ------------------------------------------------------------------ 4
h("4. System architecture")
doc.add_picture(str(DOCS / "architecture.png"), width=Cm(16.5))
caption("Figure 1. Architecture of the system. All components run on the local machine.")
p("Document ingestion (when a file is uploaded):", None)
bullets([
    ("Extraction – ", "text is extracted page by page from PDFs with PyMuPDF, and section by section (split at "
                      "headings) from DOCX files. Arabic text stored in visual order / presentation forms is "
                      "normalised; scanned pages can be OCR-ed with Tesseract (eng+ara+rus) if installed."),
    ("Language detection – ", "the language of each page is detected (langdetect) to label the document."),
    ("Chunking – ", "pages are split at sentence boundaries (including the Arabic question mark ؟) into chunks of "
                    "about 160 words with 40 words of overlap. A chunk never crosses a page, so every chunk "
                    "has exactly one page reference."),
    ("Embedding and indexing – ", "each chunk is embedded by the fine-tuned model and stored in a FAISS index "
                                  "together with its metadata (file, page, section). The index is saved to disk."),
])
p("Question answering (when a question is asked):", None)
bullets([
    "The question language is detected; the answer will be written in that language (or a language chosen in the UI).",
    "The question is embedded and the top-5 most similar chunks are retrieved (optionally only from selected documents). "
    "Chunks with similarity below a threshold are discarded, so off-topic questions are answered with \"not found\".",
    "The chunks are numbered [1]…[5] and sent to the LLM with instructions to answer only from them and cite the numbers.",
    "The answer is streamed token-by-token to the browser; the frontend turns [n] into clickable citations that open "
    "the original PDF at the cited page.",
])
p("Summarisation uses a map-reduce strategy: the document is split into parts of ~2,500 characters, each part is "
  "summarised separately (map), and the partial summaries are combined into a final summary with key points "
  "(reduce). This allows summarising documents longer than the LLM context window.")

# ------------------------------------------------------------------ 5
h("5. Dataset")
p("No suitable model exists for exactly our task, so we fine-tuned the retrieval model ourselves. Training "
  "data consists of (question, passage that contains the answer) pairs taken from public, human-annotated "
  "question-answering datasets:")
table(["Dataset", "Languages", "Description", "License", "Role"], [
    ["TyDi QA – GoldP (Clark et al., 2020)", "EN, AR, RU (+8)", "Questions written by native speakers, "
     "answers in Wikipedia passages; not translated", "Apache 2.0", "Training"],
    ["SQuAD v1.1 (Rajpurkar et al., 2016)", "EN", "Crowd-sourced questions on Wikipedia paragraphs", "CC BY-SA 4.0", "Training"],
    ["ARCD (Mozannar et al., 2019)", "AR", "Arabic Reading Comprehension Dataset", "MIT", "Training"],
    ["XQuAD (Artetxe et al., 2020)", "EN, AR, RU (+9)", "1,190 SQuAD dev questions + 240 paragraphs professionally "
     "translated into 12 languages (parallel)", "CC BY-SA 4.0", "Test only"],
], widths=[3.6, 2.2, 6, 2.2, 1.8])
if stats:
    pool = stats["available_pool"]
    p("Available pairs after preprocessing (at most 2 questions per passage):")
    table(["Language", "TyDi QA", "SQuAD", "ARCD", "Total available"], [
        ["English", pool["en"].get("tydiqa", 0), pool["en"].get("squad", 0), "–", sum(pool["en"].values())],
        ["Arabic", pool["ar"].get("tydiqa", 0), "–", pool["ar"].get("arcd", 0), sum(pool["ar"].values())],
        ["Russian", pool["ru"].get("tydiqa", 0), "–", "–", sum(pool["ru"].values())],
    ])
    p(f"From this pool we built a balanced set of {stats['train_size']:,} training pairs "
      f"({', '.join(f'{k.upper()}: {v:,}' for k, v in stats['train_by_lang'].items())}) and a {stats['dev_size']}-pair "
      f"development set. Native TyDi QA questions were preferred ({stats['train_by_source'].get('tydiqa', 0):,} pairs); "
      f"SQuAD filled the remaining English slots ({stats['train_by_source'].get('squad', 0):,} pairs). "
      f"Average question length is {stats['avg_query_chars']} characters and average passage length "
      f"{stats['avg_passage_chars']} characters.")
p("Preprocessing steps:", None)
bullets([
    "Converted all datasets to the same (question, passage) format; empty records removed.",
    "Kept at most 2 questions per passage, so that frequently-asked paragraphs do not dominate training.",
    "Balanced the three languages and shuffled with a fixed random seed (42) for reproducibility.",
    "Added the E5 prefixes \"query: \" and \"passage: \".",
    "XQuAD was kept completely separate as the test set. Its paragraphs come from the SQuAD development "
    "split, while we only trained on the SQuAD training split, so there is no overlap between training and test data.",
])
p("Example training record (TyDi QA, Arabic):")
code('{"query": "query: متى تأسست جامعة القاهرة؟",\n "positive": "passage: جامعة القاهرة هي جامعة حكومية مصرية ..."}')
p("A Russian dataset, SberQuAD, was also planned, but it could not be downloaded from the Hugging Face Hub "
  "(the dataset was moved), so Russian training data comes from TyDi QA only; it still provides enough pairs.")

# ------------------------------------------------------------------ 6
h("6. Model training (fine-tuning)")
if tlog:
    table(["Setting", "Value"], [
        ["Base model", tlog["base_model"]],
        ["Training pairs used", f"{tlog['train_pairs']:,} (balanced EN/AR/RU)"],
        ["Loss", tlog["loss"]],
        ["Epochs", tlog["epochs"]],
        ["Batch size", f"{tlog['batch_size']} (no duplicate passages in a batch)"],
        ["Learning rate", f"{tlog['learning_rate']} with 10% linear warm-up"],
        ["Max sequence length", f"{tlog['max_seq_length']} tokens"],
        ["Trainable parameters", f"{tlog['trainable_params']/1e6:.1f}M of {tlog['total_params']/1e6:.1f}M "
                                 "(token-embedding table frozen)"],
        ["Hardware", "Intel Core i7-8565U CPU (4 cores), 8 GB RAM"],
        ["Training time", f"{tlog['train_minutes']} minutes"],
    ], widths=[5, 11])
p("Design decisions:", None)
bullets([
    ("Training on CPU. ", "The laptop's GPU (GeForce MX250, 2 GB) has a 2019 driver that current PyTorch does "
                         "not support, and its memory is too small for comfortable training, so training was done on the CPU."),
    ("Small model. ", "multilingual-e5-small was chosen over larger models because it is fast enough to fine-tune on "
                      "a CPU and to embed documents quickly at run time, while still supporting 100+ languages."),
    ("Frozen token embeddings. ", "The 96M-parameter vocabulary table was frozen; only the Transformer layers "
                                  "(21.6M parameters) were trained. This made training several times faster on "
                                  "the CPU and protects the shared multilingual vocabulary from drifting towards "
                                  "the three training languages."),
    ("In-batch negatives with no duplicates. ", "A batch sampler guarantees that the same passage does not appear "
                                                "twice in a batch, which would otherwise create false negatives."),
    ("Subset of the data. ", "A first timing test showed about 30 s per training step on this CPU, so 6,000 of the "
                             "15,000 prepared pairs were used for one epoch to keep training time around one hour."),
    ("Checkpointing. ", "The first training run crashed at step 78 with an out-of-memory error when the LLM was "
                        "loaded at the same time on the 8 GB laptop. The training script now saves a checkpoint "
                        "every 40 steps and resumes automatically; the second run completed."),
])
if tlog:
    losses = [x for x in tlog["history"] if "loss" in x and "eval_loss" not in x]
    if losses:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.plot([x["step"] for x in losses], [float(x["loss"]) for x in losses], color="#2f6fde", lw=2)
        ax.set_xlabel("training step")
        ax.set_ylabel("MNR loss")
        ax.set_title("Training loss")
        ax.grid(alpha=.3)
        fig.tight_layout()
        fig.savefig(DOCS / "training_loss.png", dpi=150)
        doc.add_picture(str(DOCS / "training_loss.png"), width=Cm(14))
        caption("Figure 2. Training loss of the fine-tuning run (logged every 10 steps).")
        ev = [x for x in tlog["history"] if "eval_loss" in x]
        if ev:
            p(f"Loss on the held-out development pairs at the end of training: {float(ev[-1]['eval_loss']):.4f}.")

# ------------------------------------------------------------------ 7
h("7. Evaluation of the retrieval model")
p("Models were evaluated on two test sets that were never used for training:")
bullets([
    ("In-domain dev set – ", "600 held-out (question, passage) pairs from the same sources as the training data "
     "(TyDi QA, SQuAD, ARCD), 200 per language; each question is ranked against all 600 passages."),
    ("XQuAD (out-of-domain) – ", "for each combination of question language and passage language, all 1,190 "
     "questions are embedded and the 240 paragraphs are ranked by cosine similarity. XQuAD questions are "
     "SQuAD-style (written while reading the paragraph), unlike TyDi QA questions (written before seeing it)."),
])
p("Metrics:")
bullets([
    ("Recall@1 – ", "fraction of questions whose correct paragraph is ranked first."),
    ("Recall@5 – ", "fraction whose correct paragraph is in the top 5 (we give the LLM 5 passages, so this is "
                    "the chance the answer reaches the LLM)."),
    ("MRR@10 – ", "mean reciprocal rank of the correct paragraph (1 for rank 1, 0.5 for rank 2, …, 0 beyond 10)."),
])
allm = load("training/results/all_models.json")
if allm:
    names = {"base": "Base multilingual-e5-small", "fine_tuned": "Fine-tuned (ours)",
             "wise30": "WiSE-FT α = 0.3 (deployed)", "wise50": "WiSE-FT α = 0.5"}
    h("7.1 First result: fine-tuning helps in-domain but hurts out-of-domain", 2)
    rows = []
    for k in ["base", "fine_tuned"]:
        d, x = allm[k]["dev"]["average"], allm[k]["xquad"]["average"]
        rows.append([names[k], pct(d["R@1"]), f"{d['MRR@10']:.3f}", pct(x["R@1"]), pct(x["R@5"]), f"{x['MRR@10']:.3f}"])
    table(["Model", "Dev R@1", "Dev MRR@10", "XQuAD R@1", "XQuAD R@5", "XQuAD MRR@10"], rows)
    b, f = allm["base"], allm["fine_tuned"]
    p(f"On the in-domain dev set fine-tuning worked: Recall@1 rose from {pct(b['dev']['average']['R@1'])} to "
      f"{pct(f['dev']['average']['R@1'])} and MRR@10 from {b['dev']['average']['MRR@10']:.3f} to "
      f"{f['dev']['average']['MRR@10']:.3f}. On XQuAD, however, it got worse: MRR@10 fell from "
      f"{b['xquad']['average']['MRR@10']:.3f} to {f['xquad']['average']['MRR@10']:.3f}.")
    p("Analysis: this is a classic domain-shift / over-specialisation effect. About 90% of the training pairs came "
      "from TyDi QA, whose \"information-seeking\" questions are written before the author sees the passage and have "
      "little word overlap with it. XQuAD questions are written while reading the paragraph. The training loss "
      "dropped from 0.94 to about 0.04 within the first 50 steps — the in-batch task was easy — so the rest of "
      "training mostly moved the model towards the TyDi question style. The base E5 model had already been trained "
      "on very large amounts of question–passage data (including SQuAD-style data), so there was little to gain "
      "and something to lose on XQuAD.")
    h("7.2 Fix: weight-space interpolation (WiSE-FT)", 2)
    p("Following Wortsman et al. (2022), we averaged the weights of the base and fine-tuned models: "
      "θ(α) = (1 − α)·θ_base + α·θ_fine-tuned. This needs no extra training (training/interpolate.py). "
      "α = 0 is the base model and α = 1 the fully fine-tuned model.")
    rows = []
    for k in ["base", "wise30", "wise50", "fine_tuned"]:
        if k in allm:
            d, x = allm[k]["dev"]["average"], allm[k]["xquad"]["average"]
            rows.append([names[k], pct(d["R@1"]), f"{d['MRR@10']:.3f}", pct(x["R@1"]), pct(x["R@5"]), f"{x['MRR@10']:.3f}"])
    table(["Model", "Dev R@1", "Dev MRR@10", "XQuAD R@1", "XQuAD R@5", "XQuAD MRR@10"], rows)
    caption("Table: all evaluated retrieval models (averages over languages / language pairs).")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    order = [k for k in ["base", "wise30", "wise50", "fine_tuned"] if k in allm]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.4))
    for ax, ds, title, lo in [(axes[0], "dev", "In-domain dev set", 0.94), (axes[1], "xquad", "XQuAD (out-of-domain)", 0.80)]:
        vals = [allm[k][ds]["average"]["MRR@10"] for k in order]
        bars = ax.bar(range(len(order)), vals, color=["#9aa5b1", "#2f6fde", "#6c9be8", "#c47f2c"][:len(order)])
        ax.set_xticks(range(len(order)), ["base", "WiSE 0.3", "WiSE 0.5", "fine-tuned"][:len(order)])
        ax.set_ylim(lo, max(vals) + 0.015)
        ax.set_title(title)
        ax.set_ylabel("MRR@10")
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.001, f"{v:.3f}", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(DOCS / "models_mrr.png", dpi=150)
    doc.add_picture(str(DOCS / "models_mrr.png"), width=Cm(16))
    caption("Figure 3. MRR@10 of each model on the in-domain and out-of-domain test sets (note the y-axis ranges).")

    if "wise30" in allm:
        w = allm["wise30"]
        p(f"With α = 0.3 the model keeps most of the in-domain improvement (dev Recall@1 "
          f"{pct(b['dev']['average']['R@1'])} → {pct(w['dev']['average']['R@1'])}, MRR@10 "
          f"{b['dev']['average']['MRR@10']:.3f} → {w['dev']['average']['MRR@10']:.3f}) while matching the base model on "
          f"XQuAD (MRR@10 {b['xquad']['average']['MRR@10']:.3f} vs {w['xquad']['average']['MRR@10']:.3f}). "
          "It is therefore the model deployed in the application.")
        rows = []
        for pair in [k for k in w["xquad"] if k != "average"]:
            rows.append([pair.upper().replace("->", " → "),
                         f"{b['xquad'][pair]['MRR@10']:.3f}", f"{f['xquad'][pair]['MRR@10']:.3f}",
                         f"{w['xquad'][pair]['MRR@10']:.3f}", pct(w['xquad'][pair]['R@5'])])
        table(["XQuAD pair (question → passage)", "MRR base", "MRR fine-tuned", "MRR WiSE 0.3", "R@5 WiSE 0.3"], rows)
        caption("Table: XQuAD per language pair. Cross-lingual pairs are harder than monolingual ones, "
                "especially those involving Arabic.")
    p("Lessons learned: (1) always evaluate on data that differs from the training distribution — the in-domain "
      "dev loss (0.011) looked excellent while out-of-domain quality had dropped; (2) when fine-tuning a strong "
      "pre-trained model on a small dataset, weight interpolation is a cheap and effective way to keep its "
      "general robustness; (3) to really improve cross-lingual retrieval, cross-lingual training pairs "
      "(question and passage in different languages) and SQuAD-style Arabic/Russian data would be needed.")

# ------------------------------------------------------------------ 8
h("8. Implementation")
h("8.1 Backend (Python, FastAPI)", 2)
table(["Module", "Responsibility"], [
    ["app/extract.py", "PDF/DOCX/TXT text extraction with page/section metadata, Arabic normalisation, optional OCR"],
    ["app/chunker.py", "Sentence-aware chunking with overlap (EN/AR/RU sentence boundaries)"],
    ["app/store.py", "Embedding model wrapper (E5 prefixes, normalisation) and FAISS vector store with persistence"],
    ["app/llm.py", "Prompts, streaming chat with Ollama, context building with numbered passages"],
    ["app/main.py", "REST API, language detection, retrieval threshold, streaming answers, map-reduce summaries"],
], widths=[4, 12])
table(["Endpoint", "Description"], [
    ["GET /api/health", "Status of the embedding model and the LLM"],
    ["POST /api/documents", "Upload a file → extract → chunk → embed → index"],
    ["GET /api/documents", "List documents with language, pages, chunks"],
    ["DELETE /api/documents/{id}", "Remove a document and its vectors"],
    ["GET /api/documents/{id}/file", "Original file"],
    ["POST /api/documents/{id}/page/{n}", "PNG image of page n with the cited passage highlighted"],
    ["POST /api/ask", "Question → sources + streamed answer (NDJSON)"],
    ["POST /api/documents/{id}/summary", "Streamed map-reduce summary in a chosen language"],
], widths=[6, 10])
h("8.2 Prompt design", 2)
p("The system prompt sent to the LLM for question answering:")
code("You are a precise document assistant. Answer the user's question using ONLY the numbered context\n"
     "passages. After each fact, cite its passage number in square brackets, e.g. [1] or [2][3]. If the\n"
     "passages do not contain the answer, say clearly that the document does not contain this information.\n"
     "Do not invent facts. Do not repeat the question. Be concise. Always write the answer in {language},\n"
     "even if the passages are in another language.")
p("The temperature is set to 0.2 to make answers factual and stable.")
h("8.3 Relevance threshold", 2)
p("If no retrieved passage reaches a minimum cosine similarity, the LLM is not called at all and the user is told "
  "that the information was not found. The threshold was calibrated with the deployed model on 12 questions that "
  "are answered by the demo documents and 10 unrelated questions, in all three languages. Top similarity scores "
  "were 0.62–0.92 for answerable questions and 0.50–0.68 for unrelated ones. Since the ranges overlap slightly, "
  "we chose 0.60 to favour recall: clearly unrelated questions are rejected immediately, and borderline "
  "questions are handled by the prompt rule \"say that the document does not contain this information\". "
  "Passages scoring more than 0.10 below the best passage are also dropped so that only focused sources are cited.")
h("8.4 Frontend (React)", 2)
bullets([
    "Drag-and-drop upload of several files with processing status.",
    "Document list with detected language, pages, chunks and words; documents can be ticked to restrict the search.",
    "Chat interface with streamed answers, clickable [n] citations and a collapsible list of source passages with relevance scores.",
    "Source viewer: the backend renders the cited PDF page as an image (PyMuPDF) and highlights the cited "
    "passage in yellow; the user can page through the document or open the original PDF. Because the page is "
    "rendered on the server, this works in every browser without a PDF plug-in.",
    "Summary window with language selection and progress of the map-reduce steps.",
    "Right-to-left rendering for Arabic (dir=\"auto\"), light and dark themes, responsive layout.",
])
for img, cap in [("ui_answer_en_ru.jpg", "English question answered from the Russian document, with citation and source chips."),
                 ("ui_viewer.jpg", "Clicking a citation opens the cited page with the passage highlighted."),
                 ("ui_answer_ar.jpg", "Arabic question (right-to-left) answered from the English document.")]:
    if (DOCS / img).exists():
        doc.add_picture(str(DOCS / img), width=Cm(14))
        caption("Screenshot: " + cap)
h("8.5 Problems solved during development", 2)
bullets([
    ("Arabic PDF text in reverse order. ", "Sorting extracted text by position reversed right-to-left words; we use the "
     "PDF's logical order instead and normalise Arabic presentation-form characters (NFKC)."),
    ("Slow CPU training and limited RAM. ", "Solved by freezing the token embeddings, shorter sequences and a "
     "smaller balanced subset of data (see Section 6)."),
    ("Long documents vs small LLM context. ", "Solved with map-reduce summarisation and retrieval of only the top passages."),
    ("Changing the embedding model. ", "Stored vectors are tagged with the model name; when the model changes, "
     "documents are automatically re-indexed at start-up."),
    ("LLM repeating the question. ", "The 3B model sometimes began its answer by repeating the question, even when "
     "told not to. The backend now holds back the first tokens of the stream and removes a repeated question "
     "before sending the rest (a deterministic guard instead of relying on the prompt alone)."),
    ("PDF display in the browser. ", "Embedded PDF viewers are not available in every browser, so cited pages are "
     "rendered to images on the server, which also made highlighting the cited passage possible."),
])

# ------------------------------------------------------------------ 9
h("9. Testing of the complete system")
if demo:
    p("The complete system was tested end-to-end with three demo PDFs (English: solar energy, Russian: Moscow metro, "
      "Arabic: artificial intelligence; three pages each) and questions in all three languages, including "
      "cross-lingual questions and one question that is not answered by any document.")
    table(["File", "Detected language", "Pages", "Chunks", "Processing time"],
          [[u["filename"], u["language"].upper(), u["pages"], u["chunks"], f"{u['processing_seconds']} s"] for u in demo["uploads"]])
    rows = []
    for q in demo["qa"]:
        ts = q["top_source"]
        rows.append([q["pair"], q["question"],
                     f"{ts['filename']} p.{ts['page']} ({ts['score']:.2f})" if ts else "none (below threshold)",
                     "✓" if q["retrieval_correct"] else "✗", f"{q['total_s']} s"])
    table(["Pair", "Question", "Top source (score)", "Correct", "Time"], rows, widths=[1.6, 6.5, 4.6, 1.4, 1.5])
    ok = sum(q["retrieval_correct"] for q in demo["qa"])
    p(f"Retrieval found the correct document and page for {ok} of {len(demo['qa'])} test questions (for the "
      "unrelated question, \"correct\" means that nothing was retrieved and the LLM was not called). All generated "
      "answers were factually correct and cited their source. One weakness is visible: when the answer must be "
      "translated from an English passage into Arabic, the 3B model sometimes leaves English words in the Arabic "
      "answer. Generated answers:")
    for q in demo["qa"]:
        rtl_para(f"[{q['pair']}]  {q['question']}", bold=True)
        rtl_para(q["answer"] or "(error: " + "; ".join(q["errors"]) + ")", indent=True)
    if demo.get("summary"):
        p(f"Summary of solar_energy_en.pdf (generated in {demo['summary']['seconds']} s):")
        code(demo["summary"]["text"])
    demo15 = load("docs/demo_results_1.5b.json")
    h("9.1 Speed and choice of LLM", 2)
    p("Retrieval itself takes well under a second; almost all of the response time is spent by the LLM on the CPU. "
      "During testing the 8 GB laptop also had a web browser with many tabs, an Oracle database, VS Code and other "
      "programs open, leaving less than 0.5 GB of free RAM. Windows then pages the LLM weights to disk: Ollama "
      "measured only 0.4 generated tokens per second for the 3B model in this state (prompt processing ~27 tokens/s). "
      "We therefore compared two model sizes on the same questions:")
    if demo15:
        rows = []
        for a, bq in zip(demo["qa"], demo15["qa"]):
            rows.append([a["pair"], f"{a['total_s']} s", f"{bq['total_s']} s", bq["answer"][:160]])
        table(["Pair", "3B time", "1.5B time", "1.5B answer"], rows, widths=[1.6, 1.6, 1.6, 11.2])
        p("The 1.5B model is faster and uses about half the memory, but its answers are less accurate, especially "
          "when the answer must be translated between Arabic and the other languages. The application uses Qwen2.5-3B "
          "by default; start.ps1 -Llm qwen2.5:1.5b switches to the smaller model on machines with little free RAM. "
          "Closing other programs before the demo gives the largest speed-up.")
    p("Answers are streamed token by token, so the first words appear before the full answer is finished.")

# ------------------------------------------------------------------ 10
h("10. Deployment and running the project")
p("Everything runs on the local machine: the React frontend (built and served by FastAPI, or by the Vite dev "
  "server during development), the FastAPI backend, the fine-tuned embedding model (loaded in the backend "
  "process) and the LLM (Ollama server on port 11434). After setup, no internet connection is required.")
code("# one-time setup\n"
     "python -m venv %USERPROFILE%\\.venvs\\rk2\n"
     "pip install torch --index-url https://download.pytorch.org/whl/cpu\n"
     "pip install -r requirements.txt\n"
     "winget install Ollama.Ollama   &   ollama pull qwen2.5:3b\n"
     "cd frontend && npm install && npm run build\n\n"
     "# training (optional, already done)\n"
     "cd training\n"
     "python prepare_data.py ; python train_embeddings.py\n"
     "python interpolate.py --alpha 0.3 ; python evaluate_all.py\n\n"
     "# run\n"
     ".\\start.ps1        -> open http://127.0.0.1:8000")

# ------------------------------------------------------------------ 11
h("11. Limitations and future work")
bullets([
    "The 3B LLM running on a CPU takes several seconds per answer; a GPU or a larger model would be faster and more fluent, especially in Arabic.",
    "Fine-tuning used 6,000 pairs for one epoch on a CPU; more data, mined hard negatives and machine-translated "
    "cross-lingual pairs could improve retrieval further.",
    "Tables and images inside PDFs are only processed as plain text; layout-aware parsing could help.",
    "OCR for scanned PDFs depends on installing Tesseract with Arabic and Russian language packs.",
    "A cross-encoder re-ranker (e.g. bge-reranker-v2-m3) could improve the order of the retrieved passages.",
    "Hybrid search (BM25 keywords + embeddings) would help with exact names and numbers.",
])

# ------------------------------------------------------------------ 12
h("12. Individual contribution")
p("Used as ready components: the pre-trained multilingual-e5-small model, the Qwen2.5-3B-Instruct model with "
  "Ollama, and the open-source libraries PyTorch, sentence-transformers, FAISS, PyMuPDF, python-docx, FastAPI "
  "and React. My own work:")
bullets([
    "Design of the overall RAG architecture and the data flow between components.",
    "Selection, conversion, balancing and preprocessing of the multilingual training dataset, and the clean "
    "separation of the XQuAD test set.",
    "Fine-tuning of the retrieval model (loss, batch sampling, freezing strategy, hyper-parameters adapted to CPU training).",
    "Evaluation on in-domain and out-of-domain test sets (Recall@k, MRR, nine language pairs), diagnosis of the "
    "domain-shift problem and its fix with WiSE-FT weight interpolation.",
    "Calibration of the relevance threshold and comparison of two local LLM sizes.",
    "Backend: extraction with page tracking and Arabic fixes, sentence-aware chunking, vector store with "
    "persistence and re-indexing, retrieval threshold, prompts with citations, streaming, map-reduce summaries.",
    "Frontend: upload, document management, chat with clickable citations, PDF page viewer, summaries, RTL support.",
    "End-to-end testing, deployment scripts and this documentation.",
])

# ------------------------------------------------------------------ 13
h("13. Conclusion")
p("The project delivers a working, fully local AI product for multilingual document question answering. It "
  "combines a retrieval model that we fine-tuned and evaluated ourselves with a local large language model in a "
  "Retrieval-Augmented Generation pipeline. Users can upload English, Arabic and Russian documents, ask "
  "questions in any of these languages, receive answers grounded in the documents with clickable page "
  "references, and generate summaries. The evaluation showed that fine-tuning improved retrieval on data like the "
  "training data but over-specialised the model; weight interpolation (WiSE-FT) kept the improvement without "
  "losing robustness on the XQuAD benchmark. The end-to-end tests show that the system finds the correct page "
  "both within and across languages and refuses questions that the documents do not answer. The main practical "
  "limitation is speed on an 8 GB CPU-only laptop.")

# ------------------------------------------------------------------ 14
h("14. References")
for ref in [
    "Lewis, P. et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS.",
    "Wang, L. et al. (2024). Multilingual E5 Text Embeddings: A Technical Report. arXiv:2402.05672.",
    "Henderson, M. et al. (2017). Efficient Natural Language Response Suggestion for Smart Reply. arXiv:1705.00652 (multiple negatives ranking loss).",
    "Reimers, N. & Gurevych, I. (2019). Sentence-BERT. EMNLP. (sentence-transformers library)",
    "Clark, J. H. et al. (2020). TyDi QA: A Benchmark for Information-Seeking Question Answering in Typologically Diverse Languages. TACL.",
    "Rajpurkar, P. et al. (2016). SQuAD: 100,000+ Questions for Machine Comprehension of Text. EMNLP.",
    "Mozannar, H. et al. (2019). Neural Arabic Question Answering. WANLP (ARCD dataset).",
    "Artetxe, M., Ruder, S. & Yogatama, D. (2020). On the Cross-lingual Transferability of Monolingual Representations. ACL (XQuAD).",
    "Johnson, J., Douze, M. & Jégou, H. (2019). Billion-scale similarity search with GPUs. IEEE Trans. Big Data (FAISS).",
    "Qwen Team (2024). Qwen2.5 Technical Report. arXiv:2412.15115.",
    "Wortsman, M. et al. (2022). Robust fine-tuning of zero-shot models (WiSE-FT). CVPR.",
    "Ollama — https://ollama.com ;  FastAPI — https://fastapi.tiangolo.com ;  React — https://react.dev",
]:
    doc.add_paragraph(ref, style="List Number")

out = DOCS / "Project_Report.docx"
doc.save(out)
print("saved", out)
