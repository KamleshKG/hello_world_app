# 📧 Outlook Mail NLP Analyser

Scans Outlook (via COM / win32 — no IMAP required), extracts emails from a
specific sender, enriches them with **spaCy NLP**, stores everything in
**SQLite**, and visualises in a **Streamlit** dashboard.

---

## 📁 Files

| File | Purpose |
|------|---------|
| `outlook_scanner.py` | Connects to desktop Outlook via COM, scans a folder for a target sender, saves `emails.csv` + SQLite |
| `nlp_pipeline.py`    | Loads emails from SQLite, runs full spaCy NLP, writes `nlp_results` table |
| `app.py`             | Streamlit dashboard with 9 analysis tabs |
| `requirements.txt`   | Python dependencies |

---

## ⚡ Quick Start

### 1 — Install dependencies (Windows only for Outlook COM)

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
# Optional: better accuracy
python -m spacy download en_core_web_md
```

### 2 — Configure sender

Edit `outlook_scanner.py`, line ~15:

```python
TARGET_SENDER = "boss@company.com"   # email address or display name
```

### 3 — Scan Outlook

```bash
python outlook_scanner.py
```
→ Creates `emails.csv` and `emails.db`

### 4 — Run NLP enrichment

```bash
python nlp_pipeline.py
```
→ Adds `nlp_results` table to `emails.db`

### 5 — Launch dashboard

```bash
streamlit run app.py
```
Open http://localhost:8501

---

## 🔬 spaCy NLP Features Used

| Feature | Details |
|---------|---------|
| **Named Entity Recognition** | PERSON, ORG, DATE, MONEY, GPE, EVENT… |
| **Part-of-Speech tagging** | NOUN, VERB, ADJ, ADV distribution |
| **Dependency parsing** | Grammatical relations (nsubj, dobj…) |
| **Noun chunking** | Multi-word key phrases |
| **Lemmatisation** | Canonical keyword forms |
| **Stopword filtering** | Built-in spaCy stopword list |
| **Token attributes** | shape_, is_alpha, is_stop, tag_ |
| **Type-Token Ratio** | Vocabulary richness score |
| **Sentence segmentation** | Count + average length |
| **Sentiment proxy** | Positive/negative word hit ratio |
| **Domain categorisation** | Finance, Legal, HR, Technical, Sales, Meeting |

---

## 📊 Dashboard Tabs

1. **Overview** — email table + word count histogram
2. **Timeline** — daily area chart + day×hour heatmap
3. **Named Entities** — entity type bar chart + word cloud
4. **Keywords & Phrases** — top keywords, noun phrases, POS pie
5. **Sentiment** — pie, score distribution, trend over time
6. **Readability** — Flesch scores, TTR, sentence length
7. **Categories** — pie + bar + monthly trend
8. **Email Explorer** — filter + search + per-email deep-dive
9. **Live NLP Sandbox** — paste any text → instant spaCy analysis

---

## ⚙️ Notes

- **Windows only** for Outlook scanning (requires `pywin32` + desktop Outlook).
- You can **upload a CSV** directly in the sidebar if you're on Mac/Linux.
- For production use, replace the sentiment proxy with `spacy-textblob` or a
  transformer model (`en_core_web_trf`).
