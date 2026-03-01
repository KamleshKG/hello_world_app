"""
app.py  –  Streamlit dashboard for Outlook email NLP analysis
-------------------------------------------------------------
Run:  streamlit run app.py

Requirements:
    pip install streamlit pandas plotly spacy sqlite3 wordcloud matplotlib pillow
    python -m spacy download en_core_web_sm
"""

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

@st.cache_resource
def load_spacy():
    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        return None


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
            with st.spinner("Running spaCy NLP…"):
                try:
                    import nlp_pipeline
                    nlp_pipeline.run_pipeline()
                    st.success("✓ NLP complete")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(str(e))

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
# TAB 0 – OVERVIEW
# ──────────────────────────────────────────────────────────────────────────────
with tabs[0]:
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
with tabs[1]:
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
with tabs[2]:
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
with tabs[3]:
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
with tabs[4]:
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
with tabs[5]:
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
with tabs[6]:
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
with tabs[7]:
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
with tabs[8]:
    st.markdown('<div class="section-header">🧪 Live spaCy NLP Sandbox</div>',
                unsafe_allow_html=True)
    st.markdown("Paste any text below to instantly see spaCy NLP results.")

    sample = ("The meeting with John Smith from Acme Corp. is confirmed for "
              "Monday at 10am. Please review the attached invoice for $5,000 "
              "and send payment by Friday to avoid late fees.")
    user_text = st.text_area("Input Text", value=sample, height=150)

    if st.button("🔬 Analyse with spaCy", type="primary"):
        nlp = load_spacy()
        if nlp is None:
            st.error("spaCy model not found. Run: python -m spacy download en_core_web_sm")
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
