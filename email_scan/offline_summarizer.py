"""
offline_summarizer.py
─────────────────────
Fully offline NLP intelligence engine. Zero external API calls.
Combines multiple Python libraries for summarisation + insights.

Libraries used:
  sumy          – extractive summarisation (TextRank, LSA, LexRank, Luhn)
  spaCy         – NER, keywords, POS, noun chunks
  nltk          – sentence tokenisation, frequency analysis
  collections   – frequency counting
  re / string   – text cleaning
  sklearn       – TF-IDF keyword scoring (if available)

Install:
  pip install sumy nltk scikit-learn
  python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"
"""

import re
import json
import string
from collections import Counter, defaultdict
from typing import List, Dict, Any, Optional

# ── sumy imports ──────────────────────────────────────────────────────────────
try:
    from sumy.parsers.plaintext import PlaintextParser
    from sumy.nlp.tokenizers import Tokenizer
    from sumy.summarizers.text_rank import TextRankSummarizer
    from sumy.summarizers.lsa import LsaSummarizer
    from sumy.summarizers.lex_rank import LexRankSummarizer
    from sumy.summarizers.luhn import LuhnSummarizer
    from sumy.nlp.stemmers import Stemmer
    from sumy.utils import get_stop_words
    HAS_SUMY = True
except ImportError:
    HAS_SUMY = False

# ── nltk imports ──────────────────────────────────────────────────────────────
try:
    import nltk
    try:
        nltk.data.find("tokenizers/punkt")
    except LookupError:
        nltk.download("punkt", quiet=True)
        nltk.download("punkt_tab", quiet=True)
        nltk.download("stopwords", quiet=True)
    from nltk.tokenize import sent_tokenize, word_tokenize
    from nltk.corpus import stopwords as nltk_sw
    NLTK_STOPS = set(nltk_sw.words("english"))
    HAS_NLTK = True
except Exception:
    HAS_NLTK = False
    NLTK_STOPS = set()

# ── sklearn TF-IDF ────────────────────────────────────────────────────────────
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    import numpy as np
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

LANGUAGE = "english"

# ── DevOps / IT domain knowledge ─────────────────────────────────────────────
# Used to boost scoring of technically significant sentences
DOMAIN_SIGNALS = {
    "critical":    10, "p0":        10, "urgent":      8,  "outage":     10,
    "production":   8, "incident":   8, "escalat":      8,  "resolved":    6,
    "failed":       7, "failure":    7, "error":        6,  "crash":       7,
    "memory":       5, "cpu":        5, "disk":         5,  "timeout":     6,
    "deploy":       6, "release":    6, "rollback":     7,  "hotfix":      8,
    "upgrade":      5, "migration":  5, "install":      4,  "patch":       6,
    "cve":          9, "vulnerability":9,"security":    7,  "breach":      9,
    "kubernetes":   4, "docker":     4, "jenkins":      4,  "gitlab":      4,
    "terraform":    4, "aws":        4, "helm":         4,  "argocd":      4,
    "root cause":   8, "fix":        5, "solution":     5,  "workaround":  5,
    "action":       6, "recommend":  7, "approval":     6,  "decision":    6,
    "cost":         5, "budget":     5, "saving":       4,  "invoice":     5,
    "downtime":     8, "slo":        8, "sla":          7,  "impact":      6,
}

SEVERITY_WORDS = {
    "high":   {"critical","p0","urgent","outage","breach","production down","data loss",
               "cve","vulnerability","escalat","hotfix","emergency","immediately"},
    "medium": {"failed","error","crash","timeout","incident","degraded","blocked",
               "upgrade","migration","rollback","warning","high","impact"},
    "low":    {"update","routine","maintenance","scheduled","planned","install",
               "newsletter","fyi","informational","onboarding","meeting"},
}

ACTION_PATTERNS = [
    (r"please\s+\w+",                    "Action requested"),
    (r"(must|need to|should|require)\s+\w+", "Action required"),
    (r"(approve|sign.?off|decision|authoris)", "Needs approval/decision"),
    (r"(by\s+\w+day|due\s+date|deadline|before\s+\w+)", "Has a deadline"),
    (r"(schedule|calendar|invite|meeting)", "Calendar action"),
    (r"(upgrade|patch|install|deploy)",   "Technical action needed"),
    (r"(review|check|verify|confirm)",    "Review required"),
    (r"(escalat|p0|critical|urgent)",     "Immediate escalation needed"),
    (r"(invoice|payment|budget|cost)",    "Financial action"),
]


# ─────────────────────────────────────────────────────────────────────────────
# CORE: Extractive Summariser
# ─────────────────────────────────────────────────────────────────────────────

def _clean(text: str) -> str:
    text = re.sub(r"http\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def summarise_sumy(text: str, n_sentences: int = 4,
                   method: str = "textrank") -> List[str]:
    """Extractive summary using sumy. Returns list of key sentences."""
    if not HAS_SUMY or not text.strip():
        return []
    try:
        parser    = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
        stemmer   = Stemmer(LANGUAGE)
        stops     = get_stop_words(LANGUAGE)
        summarizers = {
            "textrank": TextRankSummarizer(stemmer),
            "lsa":      LsaSummarizer(stemmer),
            "lexrank":  LexRankSummarizer(stemmer),
            "luhn":     LuhnSummarizer(stemmer),
        }
        summ = summarizers.get(method, TextRankSummarizer(stemmer))
        summ.stop_words = stops
        sentences = summ(parser.document, n_sentences)
        return [str(s) for s in sentences]
    except Exception:
        return []


def summarise_tfidf(texts: List[str], query_text: str,
                    n_sentences: int = 4) -> List[str]:
    """
    TF-IDF sentence ranking across a corpus.
    Scores each sentence by its TF-IDF similarity to the query.
    """
    if not HAS_SKLEARN or not texts:
        return []
    try:
        all_sents = []
        for t in texts:
            sents = sent_tokenize(t) if HAS_NLTK else t.split(". ")
            all_sents.extend(sents)

        if len(all_sents) < 2:
            return all_sents[:n_sentences]

        vec = TfidfVectorizer(stop_words="english", max_features=500,
                              ngram_range=(1, 2))
        tfidf = vec.fit_transform(all_sents + [query_text])
        query_vec  = tfidf[-1]
        sent_vecs  = tfidf[:-1]

        scores = (sent_vecs * query_vec.T).toarray().flatten()
        top_idx = scores.argsort()[::-1][:n_sentences]
        top_idx_sorted = sorted(top_idx)
        return [all_sents[i] for i in top_idx_sorted if scores[i] > 0]
    except Exception:
        return []


def domain_score_sentences(text: str, n: int = 5) -> List[str]:
    """
    Score sentences by domain-specific keyword importance.
    Returns top-n highest scoring sentences.
    """
    sents = sent_tokenize(text) if HAS_NLTK else text.split(". ")
    scored = []
    for s in sents:
        score = 0
        sl = s.lower()
        for kw, weight in DOMAIN_SIGNALS.items():
            if kw in sl:
                score += weight
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for sc, s in scored[:n] if sc > 0]


# ─────────────────────────────────────────────────────────────────────────────
# SINGLE EMAIL ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def analyse_single_email(subject: str, body: str,
                          spacy_data: Dict = None) -> Dict[str, Any]:
    """
    Full offline analysis of one email.
    Returns structured intelligence dict.
    """
    spacy_data = spacy_data or {}
    full_text  = f"{subject}. {body}"
    clean_text = _clean(full_text)

    # ── 1. Extractive summary (TextRank) ──────────────────────────────────────
    summary_sents = summarise_sumy(clean_text, n_sentences=3, method="textrank")
    if not summary_sents:
        # Fallback: domain-scored sentences
        summary_sents = domain_score_sentences(clean_text, n=3)
    if not summary_sents and HAS_NLTK:
        # Last fallback: first 2 sentences
        summary_sents = sent_tokenize(clean_text)[:2]

    # ── 2. Key sentence (LSA — different angle from TextRank) ─────────────────
    lsa_sents = summarise_sumy(clean_text, n_sentences=2, method="lsa")

    # ── 3. Severity detection ─────────────────────────────────────────────────
    text_lower = clean_text.lower()
    severity = "Low"
    for word in SEVERITY_WORDS["high"]:
        if word in text_lower:
            severity = "High"; break
    if severity != "High":
        for word in SEVERITY_WORDS["medium"]:
            if word in text_lower:
                severity = "Medium"; break

    # ── 4. Action detection ───────────────────────────────────────────────────
    actions_found = []
    for pattern, label in ACTION_PATTERNS:
        if re.search(pattern, text_lower):
            actions_found.append(label)
    actions_found = list(dict.fromkeys(actions_found))  # dedupe preserve order

    # ── 5. spaCy enrichment ───────────────────────────────────────────────────
    keywords = spacy_data.get("keywords", [])[:10]
    entities = spacy_data.get("entities", [])
    people   = [e["text"] for e in entities if e.get("label") == "PERSON"][:5]
    orgs     = [e["text"] for e in entities if e.get("label") == "ORG"][:5]
    money    = [e["text"] for e in entities if e.get("label") == "MONEY"][:3]
    dates    = [e["text"] for e in entities if e.get("label") == "DATE"][:3]

    # ── 6. Issue type classification ──────────────────────────────────────────
    issue_type = _classify_issue(subject, text_lower)

    # ── 7. What-to-do recommendation ─────────────────────────────────────────
    recommendation = _build_recommendation(issue_type, severity, actions_found,
                                            money, dates, people)

    # ── 8. Risk statement ─────────────────────────────────────────────────────
    risk = _build_risk(severity, issue_type, text_lower)

    # ── 9. Insight (pattern-based) ────────────────────────────────────────────
    insight = _build_insight(subject, text_lower, keywords, spacy_data)

    return {
        "summary"       : " ".join(summary_sents),
        "key_sentences" : summary_sents,
        "lsa_sentences" : lsa_sents,
        "severity"      : severity,
        "issue_type"    : issue_type,
        "actions"       : actions_found,
        "recommendation": recommendation,
        "risk"          : risk,
        "insight"       : insight,
        "people"        : people,
        "orgs"          : orgs,
        "money"         : money,
        "dates"         : dates,
        "keywords"      : keywords,
    }


def _classify_issue(subject: str, text_lower: str) -> str:
    sl = subject.lower()
    rules = [
        (["p0","critical","production down","outage","hotfix"],        "🚨 Production Incident"),
        (["cve","vulnerability","security","breach","patch"],           "🔒 Security Issue"),
        (["upgrade","migration","version","lts"],                       "⬆️ Upgrade / Migration"),
        (["install","setup","deploy new","new tool"],                   "🔧 New Installation"),
        (["maintenance","cleanup","patch","routine","ssl","cert"],      "🛠️ Maintenance"),
        (["release","v4.","v3.","sprint","go/no-go","hotfix release"],  "🚀 Release"),
        (["invoice","payment","cost","budget","refund","billing"],      "💰 Financial"),
        (["meeting","invite","agenda","sync","calendar","minutes"],     "📅 Meeting"),
        (["contract","nda","legal","compliance","gdpr","agreement"],    "⚖️ Legal / Compliance"),
        (["offer","appraisal","leave","hire","onboard","salary"],       "👥 HR"),
        (["l1","l2","l3","l4","ticket","escalat","tkt-"],               "🎫 Support Ticket"),
        (["terraform","aws","kubernetes","k8s","eks","docker"],         "☁️ Infrastructure"),
        (["jenkins","pipeline","cicd","ci/cd","build","argocd"],        "🔄 CI/CD"),
    ]
    for keywords, label in rules:
        for kw in keywords:
            if kw in sl or kw in text_lower[:300]:
                return label
    return "📄 General Update"


def _build_recommendation(issue_type, severity, actions, money, dates, people):
    recs = []
    if "Incident" in issue_type or severity == "High":
        recs.append("Act immediately — do not delay response")
    if "Approval" in str(actions) or "decision" in str(actions).lower():
        recs.append("Your decision or sign-off is explicitly required")
    if "deadline" in str(actions).lower() and dates:
        recs.append(f"Note the deadline: {', '.join(dates[:2])}")
    if money:
        recs.append(f"Review financial impact: {', '.join(money[:2])}")
    if "Security" in issue_type:
        recs.append("Coordinate with security team — do not defer CVE patches")
    if "Release" in issue_type:
        recs.append("Confirm Go/No-Go status and ensure on-call engineer is ready")
    if "Upgrade" in issue_type:
        recs.append("Verify staging validation is complete before production")
    if "Meeting" in issue_type:
        recs.append("Accept/decline calendar invite and review pre-reads if attached")
    if not recs:
        recs.append("Read and file — reply if action is expected from you")
    return " · ".join(recs[:3])


def _build_risk(severity, issue_type, text_lower):
    if severity == "High":
        if "Incident" in issue_type:
            return "High — ongoing production impact. Customer-facing services may be degraded right now."
        if "Security" in issue_type:
            return "High — unpatched CVEs can be exploited. Each hour of delay increases exposure."
        return "High — immediate action required. Escalation or service disruption likely if ignored."
    if severity == "Medium":
        if "Upgrade" in issue_type:
            return "Medium — delayed upgrades accumulate technical debt and may cause compatibility issues."
        if "Release" in issue_type:
            return "Medium — release blocking issues could push the go-live date."
        return "Medium — this will become a bigger problem if not addressed within 1-2 days."
    return "Low — informational. No immediate consequence, but worth tracking."


def _build_insight(subject, text_lower, keywords, spacy_data):
    insights = []
    wc = spacy_data.get("word_count", 0)

    # Length insight
    if wc > 400:
        insights.append("This is a very long technical email — it likely documents a complex incident or architecture decision worth archiving.")
    elif wc < 60:
        insights.append("Short email — likely a status ping or quick update. Look for the action item buried in it.")

    # Pattern insights from content
    if "root cause" in text_lower:
        insights.append("Root cause was identified — check if a preventive action was assigned to stop recurrence.")
    if "recurring" in text_lower or "again" in text_lower or "third time" in text_lower:
        insights.append("This problem appears to be recurring — a permanent fix or automation is overdue.")
    if "workaround" in text_lower and "permanent" not in text_lower:
        insights.append("A workaround was applied but no permanent fix mentioned — technical debt is accumulating.")
    if "manual" in text_lower:
        insights.append("Manual process detected — this is an automation opportunity to reduce toil.")
    if "vendor" in text_lower or "aws support" in text_lower:
        insights.append("Vendor dependency identified — track the support case and have a mitigation plan if vendor is slow.")
    if "approval" in text_lower or "sign-off" in text_lower:
        insights.append("Blocked on human approval — delayed responses here directly delay engineering work.")
    if "disk" in text_lower and ("full" in text_lower or "100%" in text_lower):
        insights.append("Disk full issue — implement monitoring alerts at 80% to prevent recurrence.")
    if "certificate" in text_lower or "ssl" in text_lower or "cert" in text_lower:
        insights.append("Certificate management — consider automating renewal with cert-manager to eliminate manual work.")
    if "lesson" in text_lower or "post.mortem" in text_lower or "retro" in text_lower:
        insights.append("Post-mortem or lessons learned present — ensure action items are tracked in Jira/backlog.")
    if not insights:
        kw_str = ", ".join(keywords[:3]) if keywords else "various topics"
        insights.append(f"Email covers {kw_str}. Review for any implicit requests or dependencies on your team.")

    return insights[0]  # Return most relevant single insight


# ─────────────────────────────────────────────────────────────────────────────
# BATCH ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

def analyse_batch(emails: List[Dict]) -> Dict[str, Any]:
    """
    Analyse a collection of emails and produce an intelligence briefing.
    emails: list of dicts with keys: subject, body, category, sentiment_label,
                                      received_time, top_keywords_json, top_entities_json
    """
    if not emails:
        return {}

    # ── Aggregate spaCy data ──────────────────────────────────────────────────
    all_kws:    Counter = Counter()
    all_people: Counter = Counter()
    all_orgs:   Counter = Counter()
    all_money:  Counter = Counter()
    all_dates:  Counter = Counter()

    for em in emails:
        kws  = json.loads(em.get("top_keywords_json") or "[]")
        ents = json.loads(em.get("top_entities_json") or "[]")
        all_kws.update(kws)
        for e in ents:
            lbl, txt = e.get("label",""), e.get("text","")
            if lbl == "PERSON": all_people[txt] += 1
            if lbl == "ORG":    all_orgs[txt]   += 1
            if lbl == "MONEY":  all_money[txt]  += 1
            if lbl == "DATE":   all_dates[txt]  += 1

    # ── Severity distribution ─────────────────────────────────────────────────
    severity_counts = Counter()
    issue_types     = Counter()
    for em in emails:
        text = f"{em.get('subject','')} {em.get('body','')[:500]}"
        sl   = text.lower()
        sev  = "Low"
        for w in SEVERITY_WORDS["high"]:
            if w in sl: sev = "High"; break
        if sev != "High":
            for w in SEVERITY_WORDS["medium"]:
                if w in sl: sev = "Medium"; break
        severity_counts[sev] += 1
        issue_types[_classify_issue(em.get("subject",""), sl)] += 1

    # ── Top sentences across ALL emails (TF-IDF) ──────────────────────────────
    all_bodies  = [em.get("body","")[:1000] for em in emails]
    query_terms = " ".join(w for w, _ in all_kws.most_common(10))
    top_corpus_sents = summarise_tfidf(all_bodies, query_terms, n_sentences=5)

    # ── TextRank on concatenated urgent emails ─────────────────────────────────
    urgent_text = " ".join(
        em.get("body","")[:500]
        for em in emails
        if any(w in (em.get("subject","") + em.get("body",""))[:300].lower()
               for w in ["critical","urgent","p0","incident","escalat","failed","error"])
    )
    urgent_summary = summarise_sumy(urgent_text, n_sentences=3) if urgent_text else []

    # ── Pattern detection across corpus ───────────────────────────────────────
    patterns = _detect_patterns(emails, all_kws, all_orgs)

    # ── Recurring problems ────────────────────────────────────────────────────
    recurring = _find_recurring_issues(emails)

    # ── Sentiment breakdown ───────────────────────────────────────────────────
    sent_counts = Counter(em.get("sentiment_label","Neutral") for em in emails)

    # ── Overall narrative ─────────────────────────────────────────────────────
    overall = _build_overall_narrative(emails, severity_counts, issue_types,
                                        all_kws, all_people, sent_counts)

    # ── Recommendations ───────────────────────────────────────────────────────
    recommendations = _build_batch_recommendations(
        severity_counts, issue_types, recurring, all_orgs, patterns, emails)

    return {
        "overall"           : overall,
        "top_sentences"     : top_corpus_sents,
        "urgent_summary"    : urgent_summary,
        "patterns"          : patterns,
        "recurring_issues"  : recurring,
        "severity_counts"   : dict(severity_counts),
        "issue_types"       : dict(issue_types.most_common(8)),
        "top_keywords"      : all_kws.most_common(20),
        "top_people"        : all_people.most_common(10),
        "top_orgs"          : all_orgs.most_common(10),
        "top_money"         : all_money.most_common(5),
        "recommendations"   : recommendations,
        "total_emails"      : len(emails),
        "sentiment_counts"  : dict(sent_counts),
    }


def _detect_patterns(emails, all_kws, all_orgs):
    patterns = []
    total = len(emails)
    if total == 0:
        return patterns

    # Pattern 1: High negative ratio
    neg = sum(1 for e in emails if e.get("sentiment_label") == "Negative")
    if neg / total > 0.4:
        patterns.append(
            f"⚠️ {neg}/{total} emails are negative/urgent in tone — "
            "this person is handling a disproportionate number of incidents. "
            "Consider load balancing or adding automation."
        )

    # Pattern 2: Recurring tool mentions
    for tool, count in all_orgs.most_common(5):
        if count >= max(3, total * 0.2):
            patterns.append(
                f"🔄 '{tool}' appears in {count} emails — "
                "this tool is either heavily used or a recurring problem source. "
                "Investigate if it needs dedicated attention or upgrade."
            )

    # Pattern 3: Manual work signals
    manual_count = sum(
        1 for e in emails
        if re.search(r"\bmanual(ly)?\b|\bhand.?craft|\bscript\s+ran\b|ran manually",
                     (e.get("body","") or "").lower())
    )
    if manual_count >= 2:
        patterns.append(
            f"🤖 {manual_count} emails mention manual processes — "
            "significant automation opportunity exists to reduce toil and human error risk."
        )

    # Pattern 4: Certificate / disk / cleanup recurring
    for signal, label in [
        (r"disk\s+(full|usage|space|cleanup)", "disk space management"),
        (r"ssl|certificate|cert\s+expir",      "SSL certificate management"),
        (r"backup|restore|recovery",           "backup and recovery"),
    ]:
        matches = sum(
            1 for e in emails
            if re.search(signal, (e.get("body","") or "").lower())
        )
        if matches >= 2:
            patterns.append(
                f"📋 {label.title()} appears in {matches} emails — "
                "this is likely a recurring operational task that could be automated."
            )

    # Pattern 5: Long emails (complexity indicator)
    long_emails = sum(1 for e in emails if int(e.get("word_count") or 0) > 300)
    if long_emails > total * 0.3:
        patterns.append(
            f"📝 {long_emails}/{total} emails are long (300+ words) — "
            "this person is dealing with complex, multi-system problems regularly. "
            "Ensure sufficient senior engineering support."
        )

    return patterns[:5]


def _find_recurring_issues(emails) -> List[str]:
    """Find subjects/topics that appear multiple times."""
    topic_counter: Counter = Counter()
    for em in emails:
        subj = (em.get("subject") or "").lower()
        # Strip ticket numbers and normalise
        subj_clean = re.sub(r"\[.*?\]|\d+\.\d+|\bv\d+\b|#\w+", "", subj).strip()
        # Extract core topic (first 4 meaningful words)
        words = [w for w in subj_clean.split() if len(w) > 3
                 and w not in {"with","from","this","that","have","been","will",
                                "after","before","during","using","your","their"}]
        if words:
            topic = " ".join(words[:3])
            topic_counter[topic] += 1

    return [
        f"'{topic}' — mentioned {count} times across emails"
        for topic, count in topic_counter.most_common(5)
        if count >= 2
    ]


def _build_overall_narrative(emails, severity_counts, issue_types,
                               all_kws, all_people, sent_counts) -> str:
    total   = len(emails)
    high    = severity_counts.get("High", 0)
    med     = severity_counts.get("Medium", 0)
    top_cat = issue_types.most_common(1)[0][0] if issue_types else "General"
    top_kw  = ", ".join(w for w, _ in all_kws.most_common(5))
    top_ppl = ", ".join(p for p, _ in all_people.most_common(3))
    neg_pct = round(sent_counts.get("Negative", 0) / total * 100) if total else 0

    narrative = (
        f"Across {total} emails, this person's work is predominantly in "
        f"**{top_cat}**, covering themes of {top_kw}. "
    )
    if high > 0:
        narrative += (
            f"**{high} high-severity issues** were raised, indicating active incident load. "
        )
    if neg_pct > 35:
        narrative += (
            f"With {neg_pct}% of emails carrying a negative/urgent tone, "
            "this individual is under significant operational pressure. "
        )
    if top_ppl:
        narrative += f"Key collaborators include: {top_ppl}."
    return narrative


def _build_batch_recommendations(severity_counts, issue_types, recurring,
                                   all_orgs, patterns, emails) -> List[str]:
    recs = []
    total = len(emails)

    if severity_counts.get("High", 0) > 2:
        recs.append(
            "🚨 Multiple high-severity incidents detected — conduct a reliability review "
            "and identify if there are common root causes that can be permanently fixed."
        )

    top_tools = [o for o, c in all_orgs.most_common(3)]
    if top_tools:
        recs.append(
            f"🔧 Focus reliability investment on: {', '.join(top_tools)} — "
            "these appear most frequently and likely drive the most operational toil."
        )

    if recurring:
        recs.append(
            "🔄 Recurring issues detected — create runbooks and automate responses "
            "for the most frequent problems to reduce manual intervention time."
        )

    manual_emails = sum(
        1 for e in emails
        if "manual" in (e.get("body","") or "").lower()
    )
    if manual_emails >= 2:
        recs.append(
            f"🤖 {manual_emails} emails mention manual processes — "
            "prioritise automation in the next sprint to reduce toil and human error."
        )

    if severity_counts.get("High", 0) / max(total, 1) > 0.3:
        recs.append(
            "📊 Over 30% of emails are high-severity — "
            "consider implementing better monitoring and alerting to catch issues "
            "earlier and reduce the blast radius of incidents."
        )

    if not recs:
        recs.append(
            "✅ Operations appear relatively stable. "
            "Continue monitoring and focus on planned upgrades and automation."
        )

    return recs[:4]


# ─────────────────────────────────────────────────────────────────────────────
# Q&A  — offline question answering over email corpus
# ─────────────────────────────────────────────────────────────────────────────

def answer_question(question: str, emails: List[Dict]) -> str:
    """
    Offline Q&A using TF-IDF similarity to find most relevant emails,
    then extract key sentences from them.
    """
    if not emails:
        return "No emails loaded."

    q_lower = question.lower()

    # ── Direct pattern matching for common questions ──────────────────────────
    # "which tool breaks most" → org frequency
    if re.search(r"(tool|system|service).*(break|fail|problem|issue|incident)", q_lower) or \
       re.search(r"(break|fail|problem|incident).*(tool|system|service)", q_lower):
        all_orgs: Counter = Counter()
        for em in emails:
            for e in json.loads(em.get("top_entities_json") or "[]"):
                if e.get("label") == "ORG":
                    all_orgs[e["text"]] += 1
        top = all_orgs.most_common(5)
        if top:
            lines = [f"**{o}** — mentioned in {c} emails" for o, c in top]
            return ("Based on spaCy named entity frequency across all emails, "
                    "these tools/systems appear most often:\n\n" +
                    "\n".join(lines) +
                    "\n\nHigh mention frequency in a DevOps context correlates "
                    "with either heavy use or recurring problems.")

    # "who is involved / key people"
    if re.search(r"(who|people|person|team|engineer|contact)", q_lower):
        all_people: Counter = Counter()
        for em in emails:
            for e in json.loads(em.get("top_entities_json") or "[]"):
                if e.get("label") == "PERSON":
                    all_people[e["text"]] += 1
        top = all_people.most_common(8)
        if top:
            lines = [f"**{p}** — mentioned {c} times" for p, c in top]
            return ("Key people identified by spaCy across all emails:\n\n" +
                    "\n".join(lines))

    # "cost / money / financial"
    if re.search(r"(cost|money|financial|budget|price|spend|saving|\$|₹|invoice)", q_lower):
        all_money: Counter = Counter()
        for em in emails:
            for e in json.loads(em.get("top_entities_json") or "[]"):
                if e.get("label") == "MONEY":
                    all_money[e["text"]] += 1
        top = all_money.most_common(8)
        if top:
            lines = [f"**{m}** — appears {c} time(s)" for m, c in top]
            return ("Financial amounts detected across all emails:\n\n" +
                    "\n".join(lines))

    # "l3 incidents / l1 tickets / hotfix" → filter and summarise
    level_match = re.search(r"\b(l1|l2|l3|l4|hotfix|release|upgrade|install|maintenance)\b", q_lower)
    if level_match:
        keyword = level_match.group(1)
        relevant = [em for em in emails
                    if keyword in (em.get("subject","") + em.get("body","")).lower()[:200]]
        if relevant:
            summaries = []
            for em in relevant[:5]:
                sents = domain_score_sentences(
                    f"{em.get('subject','')} {em.get('body','')}",
                    n=2
                )
                summaries.append(f"**{em.get('subject','')}**\n" +
                                  (sents[0] if sents else em.get("body","")[:150]))
            return (f"Found {len(relevant)} emails matching '{keyword}':\n\n" +
                    "\n\n---\n\n".join(summaries[:4]))

    # "biggest risk / what to escalate / priority"
    if re.search(r"(risk|escalat|priorit|urgent|critical|danger|worst)", q_lower):
        high_emails = []
        for em in emails:
            text = f"{em.get('subject','')} {em.get('body','')[:500]}"
            for w in SEVERITY_WORDS["high"]:
                if w in text.lower():
                    high_emails.append(em)
                    break
        if high_emails:
            result = f"**{len(high_emails)} high-severity emails found:**\n\n"
            for em in high_emails[:6]:
                result += f"🚨 **{em.get('received_time','')[:10]}** — {em.get('subject','')}\n"
            return result

    # ── Fallback: TF-IDF similarity search ────────────────────────────────────
    if HAS_SKLEARN:
        bodies = [f"{em.get('subject','')} {em.get('body','')[:500]}" for em in emails]
        try:
            vec = TfidfVectorizer(stop_words="english", max_features=300)
            tfidf = vec.fit_transform(bodies + [question])
            q_vec = tfidf[-1]
            scores = (tfidf[:-1] * q_vec.T).toarray().flatten()
            top_idx = scores.argsort()[::-1][:3]
            result = "**Most relevant emails based on your question:**\n\n"
            for idx in top_idx:
                if scores[idx] > 0.01:
                    em = emails[idx]
                    sents = domain_score_sentences(
                        f"{em.get('subject','')} {em.get('body','')}",
                        n=2
                    )
                    snippet = sents[0] if sents else (em.get("body","")[:200])
                    result += (f"**{em.get('received_time','')[:10]}** — "
                               f"{em.get('subject','')}\n{snippet}\n\n")
            return result if "**" in result else "No closely matching emails found for your question."
        except Exception as e:
            return f"Search error: {e}"

    return ("Question understood. For best results, try asking about: "
            "tools/systems, people, costs/money, specific ticket levels (L1-L4), "
            "risks, or recurring issues.")


# ── Ensure NLTK data is available ─────────────────────────────────────────────
def ensure_nltk():
    try:
        import nltk
        for pkg in ["punkt", "punkt_tab", "stopwords"]:
            try:
                nltk.data.find(f"tokenizers/{pkg}" if "punkt" in pkg else f"corpora/{pkg}")
            except LookupError:
                nltk.download(pkg, quiet=True)
    except Exception:
        pass


ensure_nltk()
