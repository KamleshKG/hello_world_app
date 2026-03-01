"""

app.py  –  Streamlit dashboard for Outlook email NLP analysis

-------------------------------------------------------------

Run:  streamlit run app.py

spaCy model is installed automatically via pip on first launch — no manual step needed.

"""



# ── Auto-install spaCy model as a pip package (runs once, cached by pip) ──────

import subprocess, sys



def _ensure_spacy_model(model: str = "en_core_web_sm"):

    """

    Install the spaCy model as a pip package if it is not already present.

    This is the recommended production approach — the model is installed

    once into the Python environment and never needs downloading again.

    """

    try:

        import spacy

        spacy.load(model)           # already installed → done immediately

    except OSError:

        pkg = f"https://github.com/explosion/spacy-models/releases/download/{model}-3.7.1/{model}-3.7.1-py3-none-any.whl"

        print(f"[spaCy] Installing model '{model}' via pip (one-time)…")

        result = subprocess.run(

            [sys.executable, "-m", "pip", "install", pkg, "--quiet"],

            capture_output=True, text=True

        )

        if result.returncode != 0:

            # Fallback: use spacy download command

            subprocess.run(

                [sys.executable, "-m", "spacy", "download", model, "--quiet"],

                check=True

            )

        print(f"[spaCy] Model '{model}' installed successfully.")



_ensure_spacy_model()   # ← runs at import time, before Streamlit draws anything

# ──────────────────────────────────────────────────────────────────────────────



import sqlite3

import json

import re

from pathlib import Path

from collections import Counter

from io import BytesIO



import pandas as pd

import streamlit as st

import plotly.express as px

import plotly.graph_objects as go

from plotly.subplots import make_subplots

import matplotlib.pyplot as plt

import spacy



try:

    from wordcloud import WordCloud

    HAS_WC = True

except ImportError:

    HAS_WC = False



DB_PATH = "emails.db"



# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(

    page_title="📧 Outlook Mail NLP Analyser",

    page_icon="📧",

    layout="wide",

    initial_sidebar_state="expanded",

)



st.markdown("""

<style>

    .metric-card {

        background: linear-gradient(135deg,#1e3a5f,#0d6efd22);

        border-radius: 12px;

        padding: 18px;

        border-left: 4px solid #0d6efd;

    }

    .section-header {

        font-size:1.3rem; font-weight:700;

        border-bottom: 2px solid #0d6efd;

        padding-bottom:6px; margin-top:30px;

    }

    footer {visibility:hidden;}

</style>

""", unsafe_allow_html=True)



# ── Helpers ───────────────────────────────────────────────────────────────────



@st.cache_resource(show_spinner=False)

def load_spacy():

    """Load spaCy model. Model is guaranteed installed at app startup."""

    try:

        return spacy.load("en_core_web_sm"), None

    except Exception as e:

        return None, str(e)





@st.cache_data

def load_data(db_path: str = DB_PATH):

    if not Path(db_path).exists():

        return pd.DataFrame(), pd.DataFrame()

    con = sqlite3.connect(db_path)

    emails = raw = pd.DataFrame()

    try:

        emails = pd.read_sql("SELECT * FROM emails",     con)

    except Exception:

        pass

    try:

        raw    = pd.read_sql("SELECT * FROM nlp_results", con)

    except Exception:

        pass

    con.close()

    return emails, raw





def safe_json(val, default=None):

    try:

        return json.loads(val) if val else default

    except Exception:

        return default





def parse_datetime(series: pd.Series) -> pd.Series:

    return pd.to_datetime(series, errors="coerce", utc=False)





def make_wordcloud(words: list, title: str = "") -> plt.Figure:

    if not HAS_WC or not words:

        return None

    text = " ".join(words)

    wc = WordCloud(width=800, height=350, background_color="white",

                   colormap="Blues", max_words=80).generate(text)

    fig, ax = plt.subplots(figsize=(10, 4))

    ax.imshow(wc, interpolation="bilinear")

    ax.axis("off")

    if title:

        ax.set_title(title, fontsize=14, fontweight="bold")

    plt.tight_layout()

    return fig





# ── SIDEBAR ───────────────────────────────────────────────────────────────────

with st.sidebar:

    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/d/df/Microsoft_Office_Outlook_%282018%E2%80%93present%29.svg/200px-Microsoft_Office_Outlook_%282018%E2%80%93present%29.svg.png",

             width=60)

    st.title("📧 Mail NLP Analyser")

    st.markdown("---")



    # ── Run pipeline buttons ──

    st.markdown("### ⚙️ Pipeline")

    sender_input = st.text_input("Target Sender Email / Name",

                                  placeholder="someone@company.com")



    col1, col2 = st.columns(2)

    with col1:

        if st.button("📥 Scan Outlook", use_container_width=True):

            if sender_input:

                with st.spinner("Scanning Outlook…"):

                    try:

                        import outlook_scanner as os_mod

                        os_mod.TARGET_SENDER = sender_input

                        df_scan = os_mod.scan_emails(target_sender=sender_input)

                        os_mod.save_csv(df_scan)

                        os_mod.save_sqlite_raw(df_scan)

                        st.success(f"✓ {len(df_scan)} emails saved")

                        st.cache_data.clear()

                    except Exception as e:

                        st.error(str(e))

            else:

                st.warning("Enter a sender first")



    with col2:

        if st.button("🔬 Run NLP", use_container_width=True):

            status_box = st.empty()

            status_box.info("🔬 Running spaCy NLP pipeline…")

            try:

                import nlp_pipeline, importlib

                importlib.reload(nlp_pipeline)

                nlp_pipeline.run_pipeline()

                st.cache_data.clear()

                status_box.success("✅ NLP complete! Charts updated below.")

            except Exception as e:

                status_box.error(f"Error: {e}")



    st.markdown("---")



    # ── Upload CSV fallback ──

    st.markdown("### 📂 Or Upload CSV")

    uploaded = st.file_uploader("Upload emails.csv", type="csv")

    if uploaded:

        df_up = pd.read_csv(uploaded)

        con = sqlite3.connect(DB_PATH)

        df_up.to_sql("emails", con, if_exists="replace", index=False)

        con.commit(); con.close()

        st.success(f"✓ {len(df_up)} rows imported")

        st.cache_data.clear()



    st.markdown("---")

    st.markdown("**Powered by**  \n`spaCy` · `Plotly` · `Streamlit` · `SQLite`")





# ── MAIN ──────────────────────────────────────────────────────────────────────

emails_df, nlp_df = load_data()



if nlp_df.empty and emails_df.empty:

    st.info("👋 **Welcome!**  \n1. Enter a sender email in the sidebar  \n"

            "2. Click **Scan Outlook** (needs desktop Outlook)  \n"

            "3. Click **Run NLP** to enrich with spaCy  \n"

            "4. Explore the visualisations below\n\n"

            "_Or upload a CSV file directly._")

    st.stop()



# Use nlp_df if available, else emails_df for basic stats

have_nlp = not nlp_df.empty

main_df  = nlp_df if have_nlp else emails_df



# Ensure datetime

if "received_time" in main_df.columns:

    main_df["received_dt"] = parse_datetime(main_df["received_time"])





# ── TABS ──────────────────────────────────────────────────────────────────────

tabs = st.tabs([

    "🤖 AI Summaries",

    "🧭 Plain English Summary",

    "📊 Overview",

    "📅 Timeline",

    "🏷️ Named Entities",

    "🔑 Keywords & Phrases",

    "😊 Sentiment",

    "📐 Readability",

    "🗂️ Categories",

    "🔎 Email Explorer",

    "🧪 Live NLP",

])



# ──────────────────────────────────────────────────────────────────────────────

with tabs[0]:
    st.markdown('<div class="section-header">🤖 Offline AI Intelligence — No API Required</div>',
                unsafe_allow_html=True)
    st.caption("Uses sumy TextRank, LSA, TF-IDF and spaCy — 100% offline. Zero external API calls.")

    # ── auto-install offline libraries ────────────────────────────────────────
    @st.cache_resource(show_spinner=False)
    def load_offline_libs():
        import subprocess, sys
        pkgs = {"sumy": "sumy", "sklearn": "scikit-learn", "nltk": "nltk"}
        missing = []
        for imp, pip in pkgs.items():
            try:
                __import__(imp)
            except ImportError:
                missing.append(pip)
        if missing:
            subprocess.run([sys.executable, "-m", "pip", "install"] + missing + ["--quiet"], check=False)
        # ensure NLTK data
        try:
            import nltk
            for pkg, loc in [("punkt","tokenizers/punkt"),("punkt_tab","tokenizers/punkt_tab"),
                              ("stopwords","corpora/stopwords")]:
                try:    nltk.data.find(loc)
                except: nltk.download(pkg, quiet=True)
        except Exception:
            pass
        return True

    with st.spinner("⚙️ Loading offline NLP libraries (first time only)…"):
        load_offline_libs()

    try:
        import sys, os
        # Add outputs dir to path so offline_summarizer can be imported
        outputs_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else "."
        if outputs_dir not in sys.path:
            sys.path.insert(0, outputs_dir)
        import offline_summarizer as OS
        HAS_OFFLINE = True
    except Exception as oe:
        st.error(f"Could not load offline_summarizer.py: {oe}")
        HAS_OFFLINE = False

    if HAS_OFFLINE and not emails_df.empty:
        # Build merged df
        merged = emails_df.copy()
        if have_nlp and not nlp_df.empty and "message_id" in emails_df.columns and "message_id" in nlp_df.columns:
            cols = [c for c in ["message_id","sentiment_label","category","word_count",
                                 "top_keywords_json","top_entities_json"] if c in nlp_df.columns]
            merged = merged.merge(nlp_df[cols], on="message_id", how="left")

        mode = st.radio("Choose analysis mode", [
            "📋 Single email deep-dive",
            "🔍 Batch intelligence briefing",
            "💬 Ask a question",
        ], horizontal=True, key="off_mode")
        st.markdown("---")

        # ════════════════════════════════════════════════════════════════════
        if mode == "📋 Single email deep-dive":
            st.markdown("### 📧 Select an Email")
            srch = st.text_input("Search subject", "", placeholder="jenkins, L3, upgrade, CVE…", key="off_srch")
            df_s = merged[merged["subject"].str.contains(srch, case=False, na=False)] if srch else merged
            subjs = df_s["subject"].fillna("(no subject)").tolist()
            if not subjs:
                st.info("No emails match.")
            else:
                chosen = st.selectbox("Email", subjs, key="off_sel")
                row = df_s[df_s["subject"] == chosen].iloc[0]

                c1,c2,c3,c4 = st.columns(4)
                c1.markdown(f"**📅 Date**\n{str(row.get('received_time',''))[:10]}")
                c2.markdown(f"**👤 From**\n{row.get('sender_name','')}")
                c3.markdown(f"**📂 Category**\n{row.get('category','—')}")
                c4.markdown(f"**😊 Tone**\n{row.get('sentiment_label','—')}")

                with st.expander("📄 View original email"):
                    st.text(str(row.get("body",""))[:3000])

                if st.button("🔬 Analyse with Offline NLP", type="primary", key="off_btn_s"):
                    spacy_ctx = {
                        "keywords" : safe_json(row.get("top_keywords_json"), []),
                        "entities" : safe_json(row.get("top_entities_json"), []),
                        "word_count": int(row.get("word_count") or 0),
                    }
                    with st.spinner("🔬 Running TextRank + LSA + TF-IDF + domain analysis…"):
                        result = OS.analyse_single_email(
                            subject=str(row.get("subject","")),
                            body=str(row.get("body","")),
                            spacy_data=spacy_ctx
                        )

                    st.markdown("### 🔬 Offline NLP Analysis")

                    # Severity badge
                    sev_color = {"High":"#dc3545","Medium":"#fd7e14","Low":"#28a745"}.get(result["severity"],"#6c757d")
                    sev_icon  = {"High":"🔴","Medium":"🟡","Low":"🟢"}.get(result["severity"],"⚪")
                    st.markdown(f"""<div style="display:inline-block;background:{sev_color};
                        color:white;padding:4px 14px;border-radius:20px;font-weight:700;margin-bottom:16px;">
                        {sev_icon} {result["severity"]} Severity &nbsp;|&nbsp; {result["issue_type"]}
                        </div>""", unsafe_allow_html=True)

                    # Summary cards
                    cards = [
                        ("📋","WHAT HAPPENED (TextRank)","#0d6efd",
                         " ".join(result.get("key_sentences",[]))[:400] or "—"),
                        ("🔍","THE REAL PROBLEM","#fd7e14",
                         (result.get("lsa_sentences") or ["—"])[0]),
                        ("🎯","WHAT TO DO","#28a745",
                         result.get("recommendation","—")),
                        ("⚠️","RISK IF IGNORED","#dc3545",
                         result.get("risk","—")),
                        ("💡","INSIGHT","#6f42c1",
                         result.get("insight","—")),
                    ]
                    for icon, label, color, val in cards:
                        st.markdown(f"""<div style="background:#1a1a2e;border-radius:10px;
                            padding:14px 18px;border-left:4px solid {color};margin-bottom:10px;">
                            <span style="color:{color};font-weight:700;font-size:0.82rem;">
                            {icon} {label}</span><br>
                            <span style="color:white;font-size:0.97rem;">{val}</span>
                            </div>""", unsafe_allow_html=True)

                    # Actions + entities
                    col_l, col_r = st.columns(2)
                    with col_l:
                        if result.get("actions"):
                            st.markdown("**🎬 Actions Detected:**")
                            for a in result["actions"]:
                                st.markdown(f"- {a}")
                    with col_r:
                        for label, vals in [("👤 People", result.get("people",[])),
                                             ("🏢 Tools/Orgs", result.get("orgs",[])),
                                             ("💰 Money", result.get("money",[])),
                                             ("📅 Dates", result.get("dates",[]))]:
                            if vals:
                                st.markdown(f"**{label}:** {', '.join(vals)}")

                    # Library tags
                    st.markdown("---")
                    st.caption("🔬 Powered by: **sumy TextRank** (key sentences) · "
                               "**sumy LSA** (topic sentences) · "
                               "**spaCy NER** (entities) · "
                               "**Domain scorer** (severity/issue type) · "
                               "100% offline")

        # ════════════════════════════════════════════════════════════════════
        elif mode == "🔍 Batch intelligence briefing":
            st.markdown("### 🔍 Offline Intelligence Briefing — All Emails")

            cats = sorted(merged["category"].dropna().unique().tolist()) if "category" in merged.columns else []
            sel  = st.multiselect("Filter categories (blank = all)", cats, default=[], key="off_bcat")
            df_b = merged[merged["category"].isin(sel)] if sel else merged
            st.write(f"Will analyse **{len(df_b)}** emails")

            if st.button("🔬 Generate Offline Briefing", type="primary", key="off_btn_b"):
                email_list = df_b.to_dict("records")
                with st.spinner("🔬 Running TF-IDF + TextRank + pattern analysis across all emails…"):
                    brief = OS.analyse_batch(email_list)

                st.markdown("### 🤖 Intelligence Briefing")

                # Overall narrative
                st.markdown(f"""<div style="background:#1a1a2e;border-radius:12px;
                    padding:18px 22px;border-left:4px solid #0d6efd;margin-bottom:16px;">
                    <div style="color:#7eb3ff;font-weight:700;margin-bottom:6px;">🌐 OVERALL</div>
                    <div style="color:white;font-size:0.97rem;line-height:1.6;">
                    {brief.get("overall","—")}</div></div>""", unsafe_allow_html=True)

                col1, col2 = st.columns(2)

                with col1:
                    # Severity
                    sc = brief.get("severity_counts",{})
                    st.markdown(f"""<div style="background:#1a1a2e;border-radius:12px;
                        padding:16px 20px;border-left:4px solid #dc3545;margin-bottom:14px;">
                        <div style="color:#dc3545;font-weight:700;margin-bottom:6px;">🔥 SEVERITY BREAKDOWN</div>
                        <div style="color:white;">
                        🔴 High: {sc.get("High",0)} &nbsp;|&nbsp;
                        🟡 Medium: {sc.get("Medium",0)} &nbsp;|&nbsp;
                        🟢 Low: {sc.get("Low",0)}</div></div>""", unsafe_allow_html=True)

                    # Patterns
                    pats = brief.get("patterns",[])
                    if pats:
                        pat_html = "<br>".join(f"• {p}" for p in pats)
                        st.markdown(f"""<div style="background:#1a1a2e;border-radius:12px;
                            padding:16px 20px;border-left:4px solid #fd7e14;margin-bottom:14px;">
                            <div style="color:#fd7e14;font-weight:700;margin-bottom:8px;">🔄 PATTERNS DETECTED</div>
                            <div style="color:white;font-size:0.93rem;line-height:1.8;">{pat_html}</div>
                            </div>""", unsafe_allow_html=True)

                    # Recurring issues
                    rec = brief.get("recurring_issues",[])
                    if rec:
                        rec_html = "<br>".join(f"• {r}" for r in rec)
                        st.markdown(f"""<div style="background:#1a1a2e;border-radius:12px;
                            padding:16px 20px;border-left:4px solid #20c997;margin-bottom:14px;">
                            <div style="color:#20c997;font-weight:700;margin-bottom:8px;">🔁 RECURRING ISSUES</div>
                            <div style="color:white;font-size:0.93rem;line-height:1.8;">{rec_html}</div>
                            </div>""", unsafe_allow_html=True)

                with col2:
                    # Top people
                    ppl = brief.get("top_people",[])
                    if ppl:
                        ppl_html = "<br>".join(f"👤 <b>{p}</b> — {c} mentions" for p,c in ppl[:6])
                        st.markdown(f"""<div style="background:#1a1a2e;border-radius:12px;
                            padding:16px 20px;border-left:4px solid #20c997;margin-bottom:14px;">
                            <div style="color:#20c997;font-weight:700;margin-bottom:8px;">👥 KEY PEOPLE</div>
                            <div style="color:white;font-size:0.93rem;line-height:1.9;">{ppl_html}</div>
                            </div>""", unsafe_allow_html=True)

                    # Money
                    mon = brief.get("top_money",[])
                    if mon:
                        mon_html = "<br>".join(f"💰 <b>{m}</b> — {c}x" for m,c in mon)
                        st.markdown(f"""<div style="background:#1a1a2e;border-radius:12px;
                            padding:16px 20px;border-left:4px solid #28a745;margin-bottom:14px;">
                            <div style="color:#28a745;font-weight:700;margin-bottom:8px;">💰 FINANCIAL</div>
                            <div style="color:white;font-size:0.93rem;line-height:1.9;">{mon_html}</div>
                            </div>""", unsafe_allow_html=True)

                    # Recommendations
                    recs = brief.get("recommendations",[])
                    if recs:
                        rec_html = "<br><br>".join(recs)
                        st.markdown(f"""<div style="background:#1a1a2e;border-radius:12px;
                            padding:16px 20px;border-left:4px solid #6f42c1;margin-bottom:14px;">
                            <div style="color:#6f42c1;font-weight:700;margin-bottom:8px;">🎯 RECOMMENDATIONS</div>
                            <div style="color:white;font-size:0.93rem;line-height:1.7;">{rec_html}</div>
                            </div>""", unsafe_allow_html=True)

                # Key sentences (TF-IDF most important across all emails)
                top_sents = brief.get("top_sentences",[])
                if top_sents:
                    st.markdown("---")
                    st.markdown("### 📝 Most Significant Sentences (TF-IDF across all emails)")
                    st.caption("These sentences were ranked highest by TF-IDF as most informationally dense across the corpus.")
                    for i, s in enumerate(top_sents, 1):
                        st.markdown(f"**{i}.** {s}")

                # Urgent summary
                urg = brief.get("urgent_summary",[])
                if urg:
                    st.markdown("---")
                    st.markdown("### 🚨 Urgent Emails Summary (TextRank on incident emails)")
                    for s in urg:
                        st.markdown(f"- {s}")

                # Charts
                st.markdown("---")
                st.markdown("### 📊 spaCy + NLP Evidence")
                sc1,sc2,sc3 = st.columns(3)
                kw_df2 = pd.DataFrame(brief.get("top_keywords",[])[:12], columns=["Keyword","Count"])
                if not kw_df2.empty:
                    sc1.plotly_chart(px.bar(kw_df2,x="Count",y="Keyword",orientation="h",
                        title="Top Keywords",color="Count",color_continuous_scale="Blues"
                        ).update_layout(yaxis={"categoryorder":"total ascending"},height=300,showlegend=False),
                        use_container_width=True)
                ppl_df2 = pd.DataFrame(brief.get("top_people",[])[:10], columns=["Person","Mentions"])
                if not ppl_df2.empty:
                    sc2.plotly_chart(px.bar(ppl_df2,x="Mentions",y="Person",orientation="h",
                        title="Key People",color="Mentions",color_continuous_scale="Oranges"
                        ).update_layout(yaxis={"categoryorder":"total ascending"},height=300,showlegend=False),
                        use_container_width=True)
                org_df2 = pd.DataFrame(brief.get("top_orgs",[])[:10], columns=["Tool","Mentions"])
                if not org_df2.empty:
                    sc3.plotly_chart(px.bar(org_df2,x="Mentions",y="Tool",orientation="h",
                        title="Tools & Orgs",color="Mentions",color_continuous_scale="Greens"
                        ).update_layout(yaxis={"categoryorder":"total ascending"},height=300,showlegend=False),
                        use_container_width=True)

                st.caption("🔬 Powered by: **sumy TextRank** · **sumy LSA** · "
                           "**sklearn TF-IDF** · **spaCy NER** · "
                           "**Pattern matcher** · 100% offline")

        # ════════════════════════════════════════════════════════════════════
        else:  # Q&A
            st.markdown("### 💬 Ask a Question About These Emails")
            st.caption(
                "Try: *Which tool breaks most?* · *Who are the key people?* · "
                "*What are the L3 incidents?* · *What costs are mentioned?* · "
                "*What is the biggest risk?* · *Show me all hotfix emails*"
            )
            question = st.text_area("Your question", height=80,
                placeholder="Which tools keep breaking? What should I escalate?",
                key="off_qa")

            if st.button("🔬 Find Answer", type="primary", key="off_btn_qa") and question:
                email_list = merged.to_dict("records")
                with st.spinner("🔬 Searching with TF-IDF + pattern matching…"):
                    answer = OS.answer_question(question, email_list)

                st.markdown(f"""<div style="background:#1a1a2e;border-radius:12px;
                    padding:20px 24px;border-left:4px solid #0d6efd;margin-top:12px;">
                    <div style="color:#7eb3ff;font-weight:700;margin-bottom:10px;font-size:0.9rem;">
                    🔬 OFFLINE NLP ANSWER</div>
                    <div style="color:white;font-size:0.97rem;line-height:1.75;
                    white-space:pre-wrap;">{answer}</div></div>""", unsafe_allow_html=True)
                st.caption("🔬 Powered by: **TF-IDF similarity** · **spaCy NER** · "
                           "**Pattern matching** · 100% offline")

    elif emails_df.empty:
        st.warning("Upload emails CSV first (sidebar), then run NLP pipeline.")


with tabs[1]:

    st.markdown('<div class="section-header">🧭 What Do These Emails Actually Mean?</div>',

                unsafe_allow_html=True)

    st.caption("Plain-English interpretation of everything spaCy found — no technical knowledge needed.")



    if not have_nlp:

        st.warning("Run the NLP pipeline first (sidebar → Run NLP), then come back here.")

    else:

        df = main_df.copy()



        # ── helpers ───────────────────────────────────────────────────────────

        def sentiment_story(df):

            counts = df["sentiment_label"].value_counts() if "sentiment_label" in df.columns else pd.Series()

            pos = counts.get("Positive", 0); neg = counts.get("Negative", 0); neu = counts.get("Neutral", 0)

            total = len(df)

            pct_pos = round(pos/total*100) if total else 0

            pct_neg = round(neg/total*100) if total else 0

            if pct_neg >= 40:   tone = "⚠️ Predominantly **urgent or negative** — lots of problems, complaints or escalations."

            elif pct_pos >= 50: tone = "✅ Mostly **positive** — confirmations, good news, approvals."

            else:               tone = "🔵 **Neutral and professional** — mostly informational updates."

            return tone, pos, neg, neu, pct_pos, pct_neg



        def busiest_period(df):

            if "received_dt" not in df.columns: return "unknown", "unknown"

            df2 = df.dropna(subset=["received_dt"]).copy()

            df2["month"] = df2["received_dt"].dt.to_period("M").astype(str)

            df2["hour"]  = df2["received_dt"].dt.hour

            bm = df2["month"].value_counts().idxmax() if len(df2) else "unknown"

            bh = df2["hour"].value_counts().idxmax()  if len(df2) else 9

            tod = "morning" if 6<=bh<12 else ("afternoon" if 12<=bh<17 else ("evening" if 17<=bh<21 else "late night"))

            return bm, tod



        def top_people_orgs(df):

            people, orgs = Counter(), Counter()

            for _, row in df.iterrows():

                for e in safe_json(row.get("top_entities_json"), []):

                    if e.get("label") == "PERSON": people[e["text"]] += 1

                    if e.get("label") == "ORG":    orgs[e["text"]]   += 1

            return people.most_common(5), orgs.most_common(5)



        def top_money_dates(df):

            money, dates = Counter(), Counter()

            for _, row in df.iterrows():

                for e in safe_json(row.get("top_entities_json"), []):

                    if e.get("label") == "MONEY": money[e["text"]] += 1

                    if e.get("label") == "DATE":  dates[e["text"]]  += 1

            return money.most_common(5), dates.most_common(5)



        # ── compute ───────────────────────────────────────────────────────────

        total       = len(df)

        tone_str, pos, neg, neu, pct_pos, pct_neg = sentiment_story(df)

        busiest_mon, tod = busiest_period(df)

        top_people, top_orgs   = top_people_orgs(df)

        top_money,  top_dates  = top_money_dates(df)

        avg_words = int(df["word_count"].mean())    if "word_count"    in df.columns else 0

        avg_sents = int(df["sentence_count"].mean())if "sentence_count" in df.columns else 0

        cat_counts = df["category"].value_counts()  if "category" in df.columns else pd.Series()

        top_cat     = cat_counts.index[0]          if len(cat_counts) else "General"

        top_cat_pct = int(cat_counts.iloc[0]/total*100) if len(cat_counts) else 0

        all_kws: Counter = Counter()

        for _, row in df.iterrows():

            all_kws.update(safe_json(row.get("top_keywords_json"), []))

        top5_kws = [w for w, _ in all_kws.most_common(5)]

        urgent_count = len(df[df["subject"].str.contains(

            "urgent|critical|URGENT|ASAP|immediately|bug|error|fail|vulnerability",

            case=False, na=False)])

        attach_count = len(df[df["has_attachments"]==True]) if "has_attachments" in df.columns else 0



        # ── big header ────────────────────────────────────────────────────────

        st.markdown(f"""

<div style="background:linear-gradient(135deg,#0f2027,#203a43,#2c5364);

            border-radius:16px;padding:28px 32px;color:white;margin-bottom:24px;">

  <h2 style="margin:0 0 6px 0;">📬 {total} emails analysed from this sender</h2>

  <p style="font-size:1.05rem;opacity:0.8;margin:0;">

    Here is everything you need to know — no technical knowledge required.

  </p>

</div>""", unsafe_allow_html=True)



        # ── 4 story cards ─────────────────────────────────────────────────────

        r1, r2, r3, r4 = st.columns(4)

        tone_color = "#dc3545" if pct_neg>=40 else ("#28a745" if pct_pos>=50 else "#6c757d")

        tone_icon  = "⚠️"      if pct_neg>=40 else ("✅"      if pct_pos>=50 else "🔵")

        tone_label = "Urgent/Negative" if pct_neg>=40 else ("Positive" if pct_pos>=50 else "Neutral")

        wlen_label = "Very detailed"  if avg_words>200 else ("Average length" if avg_words>80 else "Short & concise")



        for col, icon, title, big, sub, color in [

            (r1, "📂", "Mostly About",   top_cat,    f"{top_cat_pct}% of all emails",        "#0d6efd"),

            (r2, tone_icon, "Overall Tone", tone_label, f"{pct_pos}% positive · {pct_neg}% negative", tone_color),

            (r3, "📝", "Email Length",   wlen_label, f"~{avg_words} words · ~{avg_sents} sentences", "#fd7e14"),

            (r4, "📅", "Most Active",    busiest_mon,f"Emails usually arrive {tod}",          "#6f42c1"),

        ]:

            with col:

                st.markdown(f"""

<div style="background:#1a1a2e;border-radius:12px;padding:18px;border-left:4px solid {color};min-height:150px;">

  <div style="font-size:2rem;">{icon}</div>

  <div style="font-size:1rem;font-weight:700;color:#7eb3ff;margin:6px 0 4px;">{title}</div>

  <div style="font-size:1.3rem;font-weight:800;color:white;">{big}</div>

  <div style="color:#aaa;font-size:0.82rem;">{sub}</div>

</div>""", unsafe_allow_html=True)



        st.markdown("<br>", unsafe_allow_html=True)



        # ── narrative + word count guide ──────────────────────────────────────

        col_a, col_b = st.columns(2)



        with col_a:

            st.markdown("### 🗣️ What is this person talking about?")

            st.markdown(tone_str)

            if top5_kws:

                st.markdown(f"The emails revolve around: **{', '.join(top5_kws)}**.")

            if urgent_count:

                st.markdown(f"🚨 **{urgent_count} emails** have urgent or critical subjects — these need immediate attention.")

            if attach_count:

                st.markdown(f"📎 **{attach_count} emails** came with attachments — likely invoices, contracts or reports.")



            st.markdown("### 🏢 Who and what gets mentioned?")

            if top_people:

                st.markdown("👤 **People:** " + ", ".join(f"**{p}**" for p,_ in top_people))

            if top_orgs:

                st.markdown("🏢 **Companies:** " + ", ".join(f"**{o}**" for o,_ in top_orgs))

            if top_money:

                st.markdown("💰 **Amounts mentioned:** " + ", ".join(f"**{m}**" for m,_ in top_money[:3]))



        with col_b:

            st.markdown("### 📖 How to read Word Count")

            st.info(f"""**Average email = ~{avg_words} words**



🟢 **Under 50 words** = Quick note or FYI. Just skim it.

🟡 **50–150 words** = Normal business email. Read it — has action points.

🔴 **150–300 words** = Detailed. Needs your decision or approval.

🔴🔴 **300+ words** = Long report. Block dedicated reading time.



→ This sender averages **{avg_words} words** — {"block time to read properly" if avg_words>150 else "quick reads, scan for action items"}.

""")

            st.markdown("### 📖 How to read Sentence Count")

            st.info(f"""**Average email = ~{avg_sents} sentences**



✅ **Few short sentences** = Clear, direct writer. Easy to act on.

⚠️ **Many long sentences** = Dense content — legal, technical or detailed.



→ {avg_sents} sentences per email = {"long flowing paragraphs — read carefully" if avg_sents>10 else "concise communicator — easy to follow"}.

""")

            st.markdown("### 📖 How to read Sentiment Score")

            st.info("""**Sentiment tells you the emotional tone:**



✅ **Positive** = Good news, thanks, approvals, confirmations.

🔵 **Neutral** = Updates, information, meeting notes.

⚠️ **Negative** = Problems, complaints, escalations, urgency.



→ Use this to **prioritise** — negative emails need faster replies.

""")



        st.markdown("<br>", unsafe_allow_html=True)



        # ── Per-email digest ──────────────────────────────────────────────────

        st.markdown("### 📋 Per-Email Plain English Digest")

        st.caption("What each email is actually trying to say — and what YOU should do about it.")



        cat_colors  = {"Finance":"#28a745","Legal":"#dc3545","HR":"#fd7e14",

                       "Technical":"#0d6efd","Sales":"#6f42c1","Meeting":"#20c997","General":"#6c757d"}

        sent_icons  = {"Positive":"✅","Negative":"⚠️","Neutral":"🔵"}



        df_disp = df.copy()

        if "received_dt" in df_disp.columns:

            df_disp = df_disp.sort_values("received_dt", ascending=False)



        # Search/filter

        f1, f2 = st.columns([3,2])

        dq = f1.text_input("🔍 Search emails", "", placeholder="invoice, meeting, budget…", key="pe_search")

        dc = f2.multiselect("Filter by Category", options=list(cat_colors.keys()), default=[], key="pe_cat")

        if dq:  df_disp = df_disp[df_disp["subject"].str.contains(dq, case=False, na=False)]

        if dc:  df_disp = df_disp[df_disp["category"].isin(dc)]



        st.write(f"Showing **{len(df_disp)}** emails")



        for _, row in df_disp.head(60).iterrows():

            cat      = row.get("category","General")

            sent_lbl = row.get("sentiment_label","Neutral")

            wc       = int(row.get("word_count", 0))

            sc       = int(row.get("sentence_count", 0))

            kws      = safe_json(row.get("top_keywords_json"), [])[:5]

            ents     = safe_json(row.get("top_entities_json"), [])

            people   = [e["text"] for e in ents if e.get("label")=="PERSON"][:3]

            money    = [e["text"] for e in ents if e.get("label")=="MONEY"][:2]

            dates_e  = [e["text"] for e in ents if e.get("label")=="DATE"][:2]

            subj     = str(row.get("subject","(no subject)"))

            recv     = str(row.get("received_time",""))[:10]

            s_icon   = sent_icons.get(sent_lbl,"🔵")



            # Plain-English action

            sl = subj.lower()

            if any(w in sl for w in ["invoice","payment","refund","budget","cost","revenue","billing","fee"]):

                action = "💰 Check if a payment or financial approval is needed"

            elif any(w in sl for w in ["urgent","critical","bug","error","fail","vulnerability","p0","asap"]):

                action = "🚨 Needs immediate attention — do not delay"

            elif any(w in sl for w in ["meeting","invite","agenda","sync","call","schedule","zoom","teams"]):

                action = "📅 Add to your calendar and prepare agenda"

            elif any(w in sl for w in ["contract","nda","agreement","legal","compliance","gdpr","clause"]):

                action = "⚖️ Review carefully — may need legal sign-off"

            elif any(w in sl for w in ["offer","onboarding","appraisal","leave","salary","hire","hr"]):

                action = "👥 HR action required — review and respond"

            elif any(w in sl for w in ["proposal","deal","closed","lead","demo","client","crm","sales"]):

                action = "💼 Sales opportunity — follow up promptly"

            elif any(w in sl for w in ["report","summary","newsletter","update","fyi","results"]):

                action = "📄 Read and file — informational update"

            else:

                action = "📄 Read and decide if action is needed"



            wc_tip = ("Very short — just a quick note." if wc<50

                      else "Standard length — one clear topic." if wc<150

                      else "Detailed — likely needs your action." if wc<300

                      else "Long email — treat like a document.")



            with st.expander(f"{s_icon} **{recv}** &nbsp; {subj[:75]}  ·  *{cat}*", expanded=False):

                d1, d2, d3, d4 = st.columns(4)

                d1.metric("Category",  cat)

                d2.metric("Tone",      sent_lbl)

                d3.metric("Words",     wc)

                d4.metric("Sentences", sc)

                st.markdown(f"**🎯 What to do:** {action}")

                if kws:    st.markdown(f"**🔑 Key topics:** {', '.join(kws)}")

                if people: st.markdown(f"**👤 People mentioned:** {', '.join(people)}")

                if money:  st.markdown(f"**💰 Money:** {', '.join(money)}")

                if dates_e:st.markdown(f"**📅 Key dates:** {', '.join(dates_e)}")

                st.caption(f"📝 {wc_tip}")



# ──────────────────────────────────────────────────────────────────────────────

# TAB 0 – OVERVIEW

# ──────────────────────────────────────────────────────────────────────────────

with tabs[2]:

    st.markdown('<div class="section-header">📊 Email Overview</div>',

                unsafe_allow_html=True)



    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Total Emails", len(main_df))

    if have_nlp:

        c2.metric("Avg Word Count", int(main_df["word_count"].mean()) if "word_count" in main_df else "—")

        c3.metric("Avg Sentences",  int(main_df["sentence_count"].mean()) if "sentence_count" in main_df else "—")

        if "sentiment_label" in main_df.columns:

            sent_mode = main_df["sentiment_label"].mode()[0]

            c4.metric("Dominant Sentiment", sent_mode)

        if "category" in main_df.columns:

            top_cat = main_df["category"].mode()[0]

            c5.metric("Top Category", top_cat)



    if not emails_df.empty:

        st.markdown('<div class="section-header">Raw Email Table</div>',

                    unsafe_allow_html=True)

        show_cols = [c for c in ["received_time","sender_name","sender_email","subject",

                                  "body_length","has_attachments"] if c in emails_df.columns]

        st.dataframe(emails_df[show_cols].head(200), use_container_width=True)



    # Word count distribution

    if have_nlp and "word_count" in nlp_df.columns:

        fig = px.histogram(nlp_df, x="word_count", nbins=30,

                           title="Email Body Word Count Distribution",

                           color_discrete_sequence=["#0d6efd"])

        fig.update_layout(bargap=0.1)

        st.plotly_chart(fig, use_container_width=True)





# ──────────────────────────────────────────────────────────────────────────────

# TAB 1 – TIMELINE

# ──────────────────────────────────────────────────────────────────────────────

with tabs[3]:

    st.markdown('<div class="section-header">📅 Email Timeline</div>',

                unsafe_allow_html=True)



    if "received_dt" in main_df.columns and main_df["received_dt"].notna().any():

        df_t = main_df.dropna(subset=["received_dt"]).copy()

        df_t["date"] = df_t["received_dt"].dt.date



        # Daily count

        daily = df_t.groupby("date").size().reset_index(name="count")

        fig = px.area(daily, x="date", y="count",

                      title="Emails Received Per Day",

                      color_discrete_sequence=["#0d6efd"])

        st.plotly_chart(fig, use_container_width=True)



        # Hour of day heatmap

        df_t["hour"] = df_t["received_dt"].dt.hour

        df_t["dow"]  = df_t["received_dt"].dt.day_name()

        dow_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

        pivot = df_t.groupby(["dow","hour"]).size().unstack(fill_value=0)

        pivot = pivot.reindex([d for d in dow_order if d in pivot.index])



        fig2 = px.imshow(pivot, aspect="auto", color_continuous_scale="Blues",

                         title="Email Activity Heatmap (Day × Hour)")

        st.plotly_chart(fig2, use_container_width=True)

    else:

        st.info("No datetime data available.")





# ──────────────────────────────────────────────────────────────────────────────

# TAB 2 – NAMED ENTITIES

# ──────────────────────────────────────────────────────────────────────────────

with tabs[4]:

    st.markdown('<div class="section-header">🏷️ Named Entity Recognition (NER)</div>',

                unsafe_allow_html=True)



    if have_nlp and "entity_types_json" in nlp_df.columns:

        # Aggregate entity type counts across all emails

        ent_type_agg: Counter = Counter()

        ent_text_agg: Counter = Counter()



        for _, row in nlp_df.iterrows():

            etype = safe_json(row.get("entity_types_json"), {})

            ent_type_agg.update(etype)

            for e in safe_json(row.get("top_entities_json"), []):

                ent_text_agg[e.get("text","")] += 1



        col1, col2 = st.columns(2)



        with col1:

            df_et = pd.DataFrame(ent_type_agg.most_common(15),

                                  columns=["Entity Type", "Count"])

            fig = px.bar(df_et, x="Count", y="Entity Type", orientation="h",

                         title="Top Entity Types (all emails)",

                         color="Count", color_continuous_scale="Blues")

            fig.update_layout(yaxis={"categoryorder":"total ascending"})

            st.plotly_chart(fig, use_container_width=True)



        with col2:

            df_ev = pd.DataFrame(ent_text_agg.most_common(20),

                                  columns=["Entity", "Freq"])

            fig2 = px.bar(df_ev, x="Freq", y="Entity", orientation="h",

                          title="Most Frequent Entities",

                          color="Freq", color_continuous_scale="Oranges")

            fig2.update_layout(yaxis={"categoryorder":"total ascending"})

            st.plotly_chart(fig2, use_container_width=True)



        # WordCloud of entity texts

        if HAS_WC:

            wc_fig = make_wordcloud(list(ent_text_agg.elements()),

                                    "Entity Word Cloud")

            if wc_fig:

                st.pyplot(wc_fig)

    else:

        st.info("Run NLP pipeline to see NER results.")





# ──────────────────────────────────────────────────────────────────────────────

# TAB 3 – KEYWORDS & PHRASES

# ──────────────────────────────────────────────────────────────────────────────

with tabs[5]:

    st.markdown('<div class="section-header">🔑 Keywords & Noun Phrases</div>',

                unsafe_allow_html=True)



    if have_nlp and "top_keywords_json" in nlp_df.columns:

        kw_agg: Counter = Counter()

        ch_agg: Counter = Counter()

        pos_agg: Counter = Counter()



        for _, row in nlp_df.iterrows():

            kw_agg.update(safe_json(row.get("top_keywords_json"), []))

            ch_agg.update(safe_json(row.get("top_chunks_json"), []))

            pos_agg.update(safe_json(row.get("pos_dist_json"), {}))



        col1, col2 = st.columns(2)



        with col1:

            df_kw = pd.DataFrame(kw_agg.most_common(25), columns=["Keyword","Freq"])

            fig = px.bar(df_kw, x="Freq", y="Keyword", orientation="h",

                         title="Top Keywords (lemmatised, no stopwords)",

                         color="Freq", color_continuous_scale="Viridis")

            fig.update_layout(yaxis={"categoryorder":"total ascending"}, height=500)

            st.plotly_chart(fig, use_container_width=True)



        with col2:

            df_ch = pd.DataFrame(ch_agg.most_common(20), columns=["Noun Chunk","Freq"])

            fig2 = px.bar(df_ch, x="Freq", y="Noun Chunk", orientation="h",

                          title="Top Noun Phrases (2+ words)",

                          color="Freq", color_continuous_scale="Tealgrn")

            fig2.update_layout(yaxis={"categoryorder":"total ascending"}, height=500)

            st.plotly_chart(fig2, use_container_width=True)



        # POS distribution pie

        df_pos = pd.DataFrame(pos_agg.most_common(), columns=["POS","Count"])

        fig3 = px.pie(df_pos, names="POS", values="Count",

                      title="Part-of-Speech Distribution (all emails)",

                      color_discrete_sequence=px.colors.qualitative.Pastel)

        st.plotly_chart(fig3, use_container_width=True)



        # Keyword wordcloud

        if HAS_WC:

            wc_fig = make_wordcloud(list(kw_agg.elements()), "Keyword Word Cloud")

            if wc_fig:

                st.pyplot(wc_fig)

    else:

        st.info("Run NLP pipeline to see keyword results.")





# ──────────────────────────────────────────────────────────────────────────────

# TAB 4 – SENTIMENT

# ──────────────────────────────────────────────────────────────────────────────

with tabs[6]:

    st.markdown('<div class="section-header">😊 Sentiment Analysis</div>',

                unsafe_allow_html=True)



    if have_nlp and "sentiment_label" in nlp_df.columns:

        col1, col2 = st.columns(2)



        with col1:

            sent_counts = nlp_df["sentiment_label"].value_counts().reset_index()

            sent_counts.columns = ["Sentiment", "Count"]

            fig = px.pie(sent_counts, names="Sentiment", values="Count",

                         title="Sentiment Distribution",

                         color="Sentiment",

                         color_discrete_map={"Positive":"#28a745",

                                              "Negative":"#dc3545",

                                              "Neutral" :"#6c757d"})

            st.plotly_chart(fig, use_container_width=True)



        with col2:

            fig2 = px.histogram(nlp_df, x="sentiment_score", nbins=30,

                                title="Sentiment Score Distribution",

                                color_discrete_sequence=["#0d6efd"])

            fig2.add_vline(x=0, line_dash="dash", line_color="gray")

            st.plotly_chart(fig2, use_container_width=True)



        # Sentiment over time

        if "received_dt" in nlp_df.columns and nlp_df["received_dt"].notna().any():

            df_st = nlp_df.dropna(subset=["received_dt"]).copy()

            df_st["date"] = df_st["received_dt"].dt.date

            daily_sent = df_st.groupby("date")["sentiment_score"].mean().reset_index()

            fig3 = px.line(daily_sent, x="date", y="sentiment_score",

                           title="Average Sentiment Score Over Time",

                           color_discrete_sequence=["#0d6efd"])

            fig3.add_hline(y=0, line_dash="dash", line_color="gray")

            st.plotly_chart(fig3, use_container_width=True)



        # Positive vs Negative word hits

        if "positive_hits" in nlp_df.columns:

            df_pn = nlp_df[["subject","positive_hits","negative_hits"]].head(40)

            fig4 = go.Figure()

            fig4.add_trace(go.Bar(x=df_pn.index, y=df_pn["positive_hits"],

                                   name="Positive", marker_color="#28a745"))

            fig4.add_trace(go.Bar(x=df_pn.index, y=-df_pn["negative_hits"],

                                   name="Negative", marker_color="#dc3545"))

            fig4.update_layout(barmode="relative",

                               title="Positive vs Negative Word Hits (first 40 emails)",

                               xaxis_title="Email Index",

                               yaxis_title="Word Count")

            st.plotly_chart(fig4, use_container_width=True)

    else:

        st.info("Run NLP pipeline to see sentiment results.")





# ──────────────────────────────────────────────────────────────────────────────

# TAB 5 – READABILITY

# ──────────────────────────────────────────────────────────────────────────────

with tabs[7]:

    st.markdown('<div class="section-header">📐 Readability & Text Stats</div>',

                unsafe_allow_html=True)



    if have_nlp and "word_count" in nlp_df.columns:

        col1, col2, col3 = st.columns(3)



        col1.metric("Avg Word Count",        f"{nlp_df['word_count'].mean():.0f}")

        col2.metric("Avg Sentences / Email", f"{nlp_df['sentence_count'].mean():.1f}")

        col3.metric("Avg Type-Token Ratio",  f"{nlp_df['type_token_ratio'].mean():.3f}")



        fig = make_subplots(rows=1, cols=2,

                            subplot_titles=["Avg Sentence Length","Type-Token Ratio"])

        fig.add_trace(go.Histogram(x=nlp_df["avg_sentence_len"],

                                    name="Avg Sent Len",

                                    marker_color="#0d6efd"), row=1, col=1)

        fig.add_trace(go.Histogram(x=nlp_df["type_token_ratio"],

                                    name="TTR",

                                    marker_color="#fd7e14"), row=1, col=2)

        fig.update_layout(showlegend=False, title_text="Text Complexity Metrics")

        st.plotly_chart(fig, use_container_width=True)



        # Readability scores if available

        if "readability_json" in nlp_df.columns:

            rd_rows = []

            for _, row in nlp_df.iterrows():

                rd = safe_json(row.get("readability_json"), {})

                if rd:

                    rd["subject"] = row.get("subject","")[:40]

                    rd_rows.append(rd)

            if rd_rows:

                df_rd = pd.DataFrame(rd_rows)

                if "flesch_reading_ease" in df_rd.columns:

                    fig2 = px.scatter(df_rd, x="flesch_reading_ease",

                                      y="flesch_kincaid_grade",

                                      hover_name="subject",

                                      title="Flesch Reading Ease vs Kincaid Grade",

                                      color="flesch_reading_ease",

                                      color_continuous_scale="RdYlGn")

                    st.plotly_chart(fig2, use_container_width=True)

    else:

        st.info("Run NLP pipeline to see readability metrics.")





# ──────────────────────────────────────────────────────────────────────────────

# TAB 6 – CATEGORIES

# ──────────────────────────────────────────────────────────────────────────────

with tabs[8]:

    st.markdown('<div class="section-header">🗂️ Email Categories</div>',

                unsafe_allow_html=True)



    if have_nlp and "category" in nlp_df.columns:

        col1, col2 = st.columns(2)



        with col1:

            cat_counts = nlp_df["category"].value_counts().reset_index()

            cat_counts.columns = ["Category","Count"]

            fig = px.pie(cat_counts, names="Category", values="Count",

                         title="Category Distribution",

                         color_discrete_sequence=px.colors.qualitative.Set3)

            st.plotly_chart(fig, use_container_width=True)



        with col2:

            fig2 = px.bar(cat_counts, x="Category", y="Count",

                          title="Email Count by Category",

                          color="Category",

                          color_discrete_sequence=px.colors.qualitative.Set3)

            st.plotly_chart(fig2, use_container_width=True)



        if "received_dt" in nlp_df.columns and nlp_df["received_dt"].notna().any():

            df_c = nlp_df.dropna(subset=["received_dt"]).copy()

            df_c["month"] = df_c["received_dt"].dt.to_period("M").astype(str)

            monthly_cat = df_c.groupby(["month","category"]).size().reset_index(name="count")

            fig3 = px.area(monthly_cat, x="month", y="count",

                           color="category", title="Category Trend Over Time")

            st.plotly_chart(fig3, use_container_width=True)

    else:

        st.info("Run NLP pipeline to see category classifications.")





# ──────────────────────────────────────────────────────────────────────────────

# TAB 7 – EMAIL EXPLORER

# ──────────────────────────────────────────────────────────────────────────────

with tabs[9]:

    st.markdown('<div class="section-header">🔎 Individual Email Explorer</div>',

                unsafe_allow_html=True)



    if not main_df.empty:

        # Filter controls

        fc1, fc2, fc3 = st.columns([3, 2, 2])

        search_q   = fc1.text_input("Search subject / body", "")

        sent_filter = fc2.multiselect("Sentiment",

                                       options=["Positive","Negative","Neutral"],

                                       default=[]) if "sentiment_label" in main_df.columns else []

        cat_filter  = fc3.multiselect("Category",

                                       options=main_df["category"].unique().tolist()

                                       if "category" in main_df.columns else [],

                                       default=[])



        fdf = main_df.copy()

        if search_q:

            mask = fdf.get("subject","").str.contains(search_q, case=False, na=False)

            fdf = fdf[mask]

        if sent_filter and "sentiment_label" in fdf.columns:

            fdf = fdf[fdf["sentiment_label"].isin(sent_filter)]

        if cat_filter and "category" in fdf.columns:

            fdf = fdf[fdf["category"].isin(cat_filter)]



        st.write(f"**{len(fdf)} emails** match your filters")



        display_cols = [c for c in ["received_time","subject","word_count",

                                     "sentence_count","sentiment_label",

                                     "sentiment_score","category","type_token_ratio"]

                        if c in fdf.columns]

        st.dataframe(fdf[display_cols].head(100), use_container_width=True)



        # Drill into one email

        st.markdown("---")

        st.subheader("🔬 Deep-dive: Select an email")



        subjects = fdf["subject"].fillna("(no subject)").tolist()[:50]

        if subjects:

            selected = st.selectbox("Email", subjects)

            sel_row  = fdf[fdf["subject"] == selected].iloc[0] if len(fdf) else None



            if sel_row is not None:

                st.markdown(f"**Subject:** {sel_row.get('subject','')}")

                st.markdown(f"**Sender:** {sel_row.get('sender_name','')} "

                            f"<{sel_row.get('sender_email','')}>")

                st.markdown(f"**Received:** {sel_row.get('received_time','')}")



                if have_nlp:

                    m1, m2, m3, m4 = st.columns(4)

                    m1.metric("Words",       sel_row.get("word_count","—"))

                    m2.metric("Sentences",   sel_row.get("sentence_count","—"))

                    m3.metric("Sentiment",   sel_row.get("sentiment_label","—"))

                    m4.metric("Category",    sel_row.get("category","—"))



                    kws = safe_json(sel_row.get("top_keywords_json"), [])

                    if kws:

                        st.markdown(f"**Top Keywords:** {', '.join(kws[:15])}")



                    ents = safe_json(sel_row.get("top_entities_json"), [])

                    if ents:

                        ent_df = pd.DataFrame(ents)

                        st.markdown("**Named Entities:**")

                        st.dataframe(ent_df, use_container_width=True)



                if not emails_df.empty:

                    body_row = emails_df[emails_df["subject"] == selected]

                    if not body_row.empty:

                        with st.expander("📄 Full Email Body"):

                            st.text(body_row.iloc[0].get("body","")[:3000])

    else:

        st.info("No data loaded.")





# ──────────────────────────────────────────────────────────────────────────────

# TAB 8 – LIVE NLP

# ──────────────────────────────────────────────────────────────────────────────

with tabs[10]:

    st.markdown('<div class="section-header">🧪 Live spaCy NLP Sandbox</div>',

                unsafe_allow_html=True)

    st.markdown("Paste any text below to instantly see spaCy NLP results.")



    sample = ("The meeting with John Smith from Acme Corp. is confirmed for "

              "Monday at 10am. Please review the attached invoice for $5,000 "

              "and send payment by Friday to avoid late fees.")

    user_text = st.text_area("Input Text", value=sample, height=150)



    if st.button("🔬 Analyse with spaCy", type="primary"):

        with st.spinner("Loading spaCy model (auto-downloading if needed)…"):

            nlp, nlp_err = load_spacy()

        if nlp is None:

            st.error(f"Could not load spaCy model. Try running:\n"

                     f"  python -m spacy download en_core_web_sm\n\nDetail: {nlp_err}")

        else:

            doc = nlp(user_text)

            col1, col2 = st.columns(2)



            with col1:

                st.subheader("🏷️ Named Entities")

                ents_data = [{"Text": e.text, "Label": e.label_,

                               "Description": spacy.explain(e.label_) or ""}

                             for e in doc.ents]

                if ents_data:

                    st.dataframe(pd.DataFrame(ents_data), use_container_width=True)

                else:

                    st.write("No entities found.")



            with col2:

                st.subheader("🔑 Keywords")

                kws = [t.lemma_.lower() for t in doc

                       if t.is_alpha and not t.is_stop and len(t.text)>2]

                kw_df = pd.DataFrame(Counter(kws).most_common(15),

                                      columns=["Keyword","Freq"])

                fig = px.bar(kw_df, x="Freq", y="Keyword", orientation="h",

                             color="Freq", color_continuous_scale="Blues")

                fig.update_layout(yaxis={"categoryorder":"total ascending"}, height=350)

                st.plotly_chart(fig, use_container_width=True)



            st.subheader("📝 Token Details")

            token_rows = []

            for tok in doc[:60]:

                token_rows.append({

                    "Token"   : tok.text,

                    "Lemma"   : tok.lemma_,

                    "POS"     : tok.pos_,

                    "Tag"     : tok.tag_,

                    "Dep"     : tok.dep_,

                    "Shape"   : tok.shape_,

                    "Alpha"   : tok.is_alpha,

                    "Stopword": tok.is_stop,

                })

            st.dataframe(pd.DataFrame(token_rows), use_container_width=True)



            st.subheader("📊 POS Distribution")

            pos_c = Counter(t.pos_ for t in doc if t.is_alpha)

            pos_df = pd.DataFrame(pos_c.most_common(), columns=["POS","Count"])

            fig2 = px.pie(pos_df, names="POS", values="Count",

                          color_discrete_sequence=px.colors.qualitative.Pastel)

            st.plotly_chart(fig2, use_container_width=True)



            st.subheader("🔗 Noun Chunks")

            chunks = [chunk.text for chunk in doc.noun_chunks]

            st.write(", ".join(chunks) if chunks else "None found")



            st.subheader("📄 Sentences")

            for i, s in enumerate(doc.sents, 1):

                st.markdown(f"**{i}.** {s.text}")



st.markdown("---")

st.caption("📧 Outlook Mail NLP Analyser | spaCy + Streamlit + SQLite | Built with ❤️")
