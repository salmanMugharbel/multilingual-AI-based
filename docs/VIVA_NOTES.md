# Viva preparation — likely questions and short answers

## The idea
**Q: What problem does your product solve?**
Finding information in long documents, especially in a language you don't read well. Ctrl+F only matches exact
words and can't cross languages. My system understands meaning, works across EN/AR/RU, answers in plain language
and shows the exact page the answer came from.

**Q: What is RAG and why did you use it instead of just asking an LLM?**
Retrieval-Augmented Generation = first *retrieve* the relevant passages, then let the LLM *generate* an answer from
them. An LLM alone doesn't know my documents and may hallucinate. With RAG the answer is grounded in the document,
it can cite sources, and new documents are added instantly without retraining.

## The AI models
**Q: Which models do you use?**
1. `multilingual-e5-small` (embedding / retrieval model) — I fine-tuned it myself.
2. `Qwen2.5-3B-Instruct` via Ollama (answer + summary generation) — used pre-trained.

**Q: What is an embedding?**
A vector (384 numbers) representing the meaning of a text. Similar meaning → vectors point in a similar direction.
Relevance = cosine similarity = dot product of normalised vectors.

**Q: How can an English question find an Arabic passage?**
The multilingual model maps all languages into one shared vector space: a sentence and its translation get almost
the same vector. So the English question is close to the Arabic passage that answers it.

**Q: Why the "query:" / "passage:" prefixes?**
E5 was trained with them; they tell the model whether the text is a short question or a document passage
(asymmetric retrieval). Leaving them out lowers quality.

## Training
**Q: What exactly did you train?**
The retrieval model. Training data = (question, passage containing the answer) pairs from TyDi QA (EN/AR/RU),
SQuAD (EN) and ARCD (AR). 15,000 balanced pairs prepared, 6,000 used for training (CPU time limit).

**Q: What loss function? Explain it.**
Multiple Negatives Ranking loss. In a batch of 32 pairs, for each question the correct passage must score higher
than the 31 other passages in the batch (in-batch negatives). It's a softmax cross-entropy over the batch with
scale 20. No hand-labelled negatives needed.

**Q: Why NO_DUPLICATES batch sampler?**
If the same passage appeared twice in a batch, one copy would be treated as a negative for a question it actually
answers — a false negative that confuses training.

**Q: Why did you freeze the token embeddings?**
They are 96M of 118M parameters (250k-word multilingual vocabulary). Freezing them: (1) ~5× fewer trainable
parameters → much faster on CPU and less RAM, (2) keeps the shared multilingual vocabulary aligned, so training on
3 languages doesn't damage the others / cross-lingual ability.

**Q: Why CPU and not GPU?**
My GPU is an MX250 with 2 GB and an old 2019 driver not supported by current PyTorch. CPU training with a small model
and the freezing trick was enough.

**Q: How did you avoid testing on training data?**
Test set = XQuAD, whose paragraphs come from the SQuAD *dev* split; I trained only on SQuAD *train*. TyDi QA and ARCD
are different sources.

**Q: How do you evaluate? What are Recall@k and MRR?**
For each question, rank all candidate paragraphs by similarity.
Recall@1 = % of questions whose correct paragraph is ranked first; Recall@5 = in top 5 (we give ≤5 passages to the LLM).
MRR@10 = average of 1/rank of the correct paragraph (0 if not in top 10).
Two test sets: in-domain dev (600 held-out pairs) and XQuAD (out-of-domain, 9 language pairs).

**Q: What were your results? (KNOW THESE NUMBERS)**
| Model | Dev MRR@10 | XQuAD MRR@10 |
|---|---|---|
| Base e5-small | 0.963 | 0.865 |
| Fine-tuned | 0.977 | 0.828 |
| **WiSE-FT α=0.3 (deployed)** | **0.975** | **0.866** |

Fine-tuning helped in-domain (dev R@1 94.3% → 96.5%) but hurt out-of-domain XQuAD — domain shift: 90% of training
data was TyDi QA (questions written *before* seeing the passage), XQuAD is SQuAD-style (written *while reading*).
Loss fell to ~0.04 by step 50, so the task was easy and the model drifted to TyDi style.

**Q: What is WiSE-FT / weight interpolation?**
θ = 0.7·θ_base + 0.3·θ_fine-tuned — average the weights of the two models (Wortsman et al., 2022). No extra training.
Keeps most of the fine-tuning gain (dev 0.963 → 0.975) and the base model's robustness (XQuAD 0.865 → 0.866).
Works because both models start from the same pre-trained weights, so they lie in the same "basin" of the loss.

**Q: Isn't a negative result bad?**
It's an honest finding: in-domain dev loss looked excellent (0.011) while out-of-domain quality dropped. Lesson:
always test on data different from training. I diagnosed it and fixed it with interpolation.

**Q: How long did training take?**
56 minutes on CPU, 188 steps, 6,000 pairs, batch 32. First run crashed (out of RAM) at step 78 because the LLM was
loaded at the same time → added checkpointing every 40 steps.

## Pipeline details
**Q: How do you split documents?**
Per page (PDF) or per heading section (DOCX); then sentence-aware chunks of ~160 words with 40-word overlap so an
answer crossing a boundary isn't lost. A chunk never crosses a page → every chunk has one exact page reference.

**Q: What is FAISS?**
Facebook's library for vector similarity search. I use `IndexFlatIP` (exact inner-product search); with normalised
vectors that equals cosine similarity. Exact search is milliseconds for thousands of chunks.

**Q: How do you prevent hallucination?**
(1) LLM only sees retrieved passages, (2) prompt says "answer ONLY from the passages, cite [n], say if not found",
(3) temperature 0.2, (4) a similarity threshold (0.60, calibrated on 12 on-topic vs 10 off-topic questions) — if
nothing relevant is retrieved the LLM isn't called at all, (5) citations open the page with the passage highlighted.

**Q: Why is it slow?**
Retrieval takes <0.5 s. The LLM runs on the CPU; with 8 GB RAM and other apps open, Windows pages the model to disk
(measured 0.4 tokens/s). The 1.5B model is 5–10× faster but answers worse. Close other programs before the demo.

**Q: How do summaries work for long documents?**
Map-reduce: split into ~2,500-character parts, summarise each part (map), then combine the part summaries into one
final summary with key points (reduce). Needed because the 3B model's context window is limited.

**Q: How do you know the language of the question?**
`langdetect` library; the answer is written in the question's language unless the user picks another one.

**Q: What problem with Arabic PDFs did you solve?**
Sorting extracted text by x-position reversed right-to-left word order; I keep the PDF's logical order. Some PDFs
store Arabic as "presentation forms" in visual order — I normalise them with Unicode NFKC and restore the order.

## Deployment
**Q: Does it need the internet?**
No — after setup everything runs locally: React frontend, FastAPI backend, embedding model inside the backend,
LLM in the local Ollama server (port 11434).

**Q: Limitations?**
CPU-only LLM is slow (seconds per answer); 3B model is weaker in Arabic than big models; tables/images are treated
as plain text; OCR requires Tesseract. Future: re-ranker, hybrid BM25 + vector search, GPU, more training data.

## Demo script (5 minutes)
0. BEFORE: close Brave/Chrome tabs you don't need, Oracle DB, VS Code, Telegram (frees RAM → much faster answers).
   Ask one warm-up question before the examiner arrives (loads the LLM into memory).
1. `.\start.ps1` → open http://127.0.0.1:8000 — show both status pills green.
2. Upload the 3 sample PDFs (EN, RU, AR) — point out detected language + chunks.
3. Ask in English about the Russian doc: *"Which metro station won a prize at the 1939 World's Fair?"* → click the
   citation → PDF opens at page 2.
4. Ask in Arabic about the English doc: *"كم انخفضت تكلفة الألواح الشمسية بين عامي 2010 و2020؟"*
5. Ask something not in the documents → "not found" (no hallucination).
6. Click **Summary** on a document, switch summary language to Russian.
7. Show `docs/models_mrr.png` and explain base vs fine-tuned vs WiSE-FT.
