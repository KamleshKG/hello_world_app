"""
nlp_pipeline.py
---------------
Runs comprehensive spaCy NLP analysis on emails stored in emails.csv / SQLite.
Enriches the database with:
  • Named Entity Recognition (NER)
  • Part-of-Speech frequency
  • Noun chunks (key phrases)
  • Sentence count / readability
  • Token stats (word count, unique words, TTR)
  • Top keywords (TF via spaCy)
  • Dependency parse summary
  • Sentiment proxy (positive/negative word ratio)
  • Category tagging (Finance, Legal, HR, Tech …)

Requirements:
    pip install spacy pandas sqlite3 textstat
    python -m spacy download en_core_web_sm
    # For better accuracy (optional):
    python -m spacy download en_core_web_md
"""

import sqlite3
import json
import re
import pandas as pd
import spacy
from collections import Counter
from typing import List, Dict, Any

try:
    import textstat
    HAS_TEXTSTAT = True
except ImportError:
    HAS_TEXTSTAT = False

DB_PATH   = "emails.db"
SPACY_MODEL = "en_core_web_sm"   # upgrade to en_core_web_md for better accuracy

# ── Domain keyword sets for category tagging ──────────────────────────────────
CATEGORY_KEYWORDS = {
    "Finance"   : {"invoice","payment","budget","revenue","cost","profit","loss",
                   "billing","price","finance","bank","transaction","refund","fee"},
    "Legal"     : {"contract","agreement","terms","clause","liability","compliance",
                   "legal","law","regulation","policy","rights","dispute","court"},
    "HR"        : {"leave","vacation","hiring","employee","onboarding","salary",
                   "performance","appraisal","hr","payroll","benefits","training"},
    "Technical" : {"bug","deploy","api","server","database","code","release",
                   "feature","sprint","pull","request","error","fix","build"},
    "Sales"     : {"proposal","lead","client","customer","deal","opportunity",
                   "demo","quote","pipeline","conversion","crm","sales"},
    "Meeting"   : {"meeting","call","schedule","agenda","minutes","invite",
                   "calendar","zoom","teams","sync","standup"},
}

# ── Sentiment word lists (lightweight proxy – no extra model needed) ───────────
POSITIVE_WORDS = {
    "great","good","excellent","thanks","thank","appreciate","happy","pleased",
    "wonderful","fantastic","perfect","success","successful","approved","resolved",
    "confirm","confirmed","achieved","completed","well","enjoy","helpful"
}
NEGATIVE_WORDS = {
    "issue","problem","error","fail","failed","failure","bug","delay","delayed",
    "wrong","bad","poor","sorry","unfortunately","urgent","critical","broken",
    "complaint","concern","reject","rejected","cancel","cancelled","overdue"
}


def load_nlp():
    try:
        nlp = spacy.load(SPACY_MODEL)
        print(f"[✓] Loaded spaCy model: {SPACY_MODEL}")
        return nlp
    except OSError:
        print(f"[!] Model '{SPACY_MODEL}' not found. Run:")
        print(f"    python -m spacy download {SPACY_MODEL}")
        raise


def get_sentiment(tokens_lower: List[str]) -> Dict[str, Any]:
    pos = sum(1 for t in tokens_lower if t in POSITIVE_WORDS)
    neg = sum(1 for t in tokens_lower if t in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        label, score = "Neutral", 0.0
    elif pos > neg:
        label, score = "Positive", round(pos / total, 3)
    else:
        label, score = "Negative", round(-neg / total, 3)
    return {"sentiment_label": label, "sentiment_score": score,
            "positive_hits": pos, "negative_hits": neg}


def get_category(tokens_lower: List[str]) -> str:
    token_set = set(tokens_lower)
    scores = {cat: len(kws & token_set) for cat, kws in CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "General"


def analyse_text(text: str, nlp) -> Dict[str, Any]:
    """Full spaCy analysis of a single text blob."""
    doc = nlp(text[:100_000])   # cap to avoid memory issues

    # ── Basic token stats ──────────────────────────────────────────────────────
    tokens_alpha  = [t.text.lower() for t in doc if t.is_alpha]
    tokens_no_stop= [t.text.lower() for t in doc if t.is_alpha and not t.is_stop]
    word_count    = len(tokens_alpha)
    unique_words  = len(set(tokens_alpha))
    ttr           = round(unique_words / word_count, 3) if word_count else 0.0

    # ── Sentences ──────────────────────────────────────────────────────────────
    sentences     = list(doc.sents)
    sent_count    = len(sentences)
    avg_sent_len  = round(word_count / sent_count, 1) if sent_count else 0

    # ── Named Entities ─────────────────────────────────────────────────────────
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    ent_counter = Counter(label for _, label in entities)
    top_entities = [{"text": t, "label": l} for t, l in
                    Counter(e[0] for e in entities).most_common(20)]

    # ── POS distribution ───────────────────────────────────────────────────────
    pos_dist = dict(Counter(t.pos_ for t in doc if t.is_alpha))

    # ── Noun chunks (key phrases) ──────────────────────────────────────────────
    chunks = [chunk.text.lower() for chunk in doc.noun_chunks
              if len(chunk.text.split()) >= 2]
    top_chunks = [c for c, _ in Counter(chunks).most_common(15)]

    # ── Top keywords (lemmatised, no stopwords) ────────────────────────────────
    keywords = [t.lemma_.lower() for t in doc
                if t.is_alpha and not t.is_stop and len(t.text) > 2]
    top_keywords = [w for w, _ in Counter(keywords).most_common(20)]

    # ── Dependency relations ───────────────────────────────────────────────────
    dep_dist = dict(Counter(t.dep_ for t in doc if t.dep_ != ""))

    # ── Readability ────────────────────────────────────────────────────────────
    readability = {}
    if HAS_TEXTSTAT and word_count > 10:
        readability = {
            "flesch_reading_ease"  : textstat.flesch_reading_ease(text),
            "flesch_kincaid_grade" : textstat.flesch_kincaid_grade(text),
            "smog_index"           : textstat.smog_index(text),
        }

    # ── Sentiment & Category ──────────────────────────────────────────────────
    sentiment = get_sentiment(tokens_alpha)
    category  = get_category(tokens_no_stop)

    return {
        "word_count"       : word_count,
        "unique_words"     : unique_words,
        "type_token_ratio" : ttr,
        "sentence_count"   : sent_count,
        "avg_sentence_len" : avg_sent_len,
        "entity_types_json": json.dumps(dict(ent_counter)),
        "top_entities_json": json.dumps(top_entities),
        "pos_dist_json"    : json.dumps(pos_dist),
        "top_keywords_json": json.dumps(top_keywords),
        "top_chunks_json"  : json.dumps(top_chunks),
        "dep_dist_json"    : json.dumps(dep_dist),
        "readability_json" : json.dumps(readability),
        **sentiment,
        "category"         : category,
    }


def analyse_subject(subject: str, nlp) -> Dict[str, Any]:
    """Lightweight NLP on subject line only."""
    doc = nlp(subject or "")
    subj_entities = [(ent.text, ent.label_) for ent in doc.ents]
    subj_keywords = [t.lemma_.lower() for t in doc
                     if t.is_alpha and not t.is_stop]
    return {
        "subject_entities_json": json.dumps(subj_entities),
        "subject_keywords_json": json.dumps(subj_keywords),
    }


def run_pipeline(db_path: str = DB_PATH):
    """Load emails from SQLite, analyse, write nlp_results table."""
    nlp = load_nlp()

    con = sqlite3.connect(db_path)
    df  = pd.read_sql("SELECT * FROM emails", con)
    print(f"[+] Analysing {len(df)} emails with spaCy…")

    results = []
    for i, row in df.iterrows():
        print(f"   [{i+1}/{len(df)}] {str(row.get('subject',''))[:50]}")
        combined_text = f"{row.get('subject','')} {row.get('body','')}"

        nlp_row = {
            "message_id"    : row.get("message_id", ""),
            "subject"       : row.get("subject", ""),
            "sender_email"  : row.get("sender_email", ""),
            "sender_name"   : row.get("sender_name", ""),
            "received_time" : row.get("received_time", ""),
        }
        nlp_row.update(analyse_text(row.get("body", ""), nlp))
        nlp_row.update(analyse_subject(row.get("subject", ""), nlp))
        results.append(nlp_row)

    nlp_df = pd.DataFrame(results)
    nlp_df.to_sql("nlp_results", con, if_exists="replace", index=False)
    con.commit()
    con.close()
    print(f"\n[✓] NLP enrichment complete → nlp_results table in {db_path}")
    print(f"[→] Next step: run  streamlit run app.py")


if __name__ == "__main__":
    run_pipeline()
