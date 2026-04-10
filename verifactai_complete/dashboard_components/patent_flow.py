# dashboard_components/patent_flow.py
import streamlit as st


def show_patent_flow():
    st.markdown("### 🔬 Patent-Protected Verification Pipeline")

    # Get session state to show dynamic progress
    kg_has_content = False
    try:
        import sqlite3
        conn = sqlite3.connect('knowledge/verifactai_kg.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM verified_facts")
        fact_count = cursor.fetchone()[0]
        conn.close()
        kg_has_content = fact_count > 0
    except:
        pass

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("**🛡️ Identification Patents**")
        st.write("- Contextual Discontinuity Detector")
        st.write("- Temporal-Context Detector")
        st.write("- Statistical Outlier Detector")
        progress = 100 if kg_has_content else 25
        st.progress(progress)

    with col2:
        st.markdown("**⚖️ Multi-Source Verification**")
        st.write("- Weighted Consensus Algorithm")
        st.write("- Progressive Verification")
        st.write("- Confidence Scoring")
        progress = 100 if kg_has_content else 50
        st.progress(progress)

    with col3:
        st.markdown("**🔧 Resolution Patents**")
        st.write("- Geospatial Resolver")
        st.write("- Temporal Resolver")
        st.write("- Numerical Resolver")
        progress = 100 if kg_has_content else 75
        st.progress(progress)

    with col4:
        st.markdown("**🔄 Self-Healing Loop**")
        st.write("- Knowledge Graph Update")
        st.write("- Continuous Learning")
        st.write("- Performance Optimization")
        progress = 100 if kg_has_content else 25
        st.progress(progress)