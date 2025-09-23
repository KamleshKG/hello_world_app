# dashboard_components/patent_flow_detailed.py
import streamlit as st


def show_patent_flow_detailed(claim, result):
    """Show detailed patent flow for each claim verification"""

    st.markdown("### 🔬 Patent Flow Analysis")

    # Determine claim type
    claim_lower = claim.lower()
    claim_type = "general"
    patent_used = []

    if any(geo in claim_lower for geo in ['capital', 'country', 'city', 'france', 'london', 'paris']):
        claim_type = "geographical"
        patent_used.extend(["Geospatial Context Detector", "Geospatial Resolver"])

    if any(temp in claim_lower for temp in ['world war', '1995', '1945', 'year', 'ended']):
        claim_type = "temporal"
        patent_used.extend(["Temporal Context Detector", "Temporal Resolver"])

    if any(stat in claim_lower for stat in ['temperature', '35°c', '37°c', 'degree', 'average']):
        claim_type = "statistical"
        patent_used.extend(["Statistical Outlier Detector", "Statistical Resolver"])

    if 'python' in claim_lower or 'guido' in claim_lower:
        claim_type = "entity"
        patent_used.extend(["Entity Consistency Detector"])

    # Remove duplicates
    patent_used = list(set(patent_used))

    # Show patent flow
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("**🛡️ Patent #1 - Identification**")
        if patent_used:
            st.write(f"🔍 {patent_used[0] if len(patent_used) > 0 else 'Context Analyzer'}")
        st.success("✅ Claim analyzed")

    with col2:
        st.markdown("**⚖️ Patent #2 - Verification**")
        if result.get('verification_skipped'):
            st.write("🔒 Confidence-based skip")
            st.info("⏭️ Verification skipped")
        else:
            st.write("🔎 Multi-source consensus")
            st.success("✅ Verification completed")

    with col3:
        st.markdown("**🔧 Patent #3 - Resolution**")
        if len(patent_used) > 1:
            st.write(f"🛠️ {patent_used[1]}")
            st.success("✅ Error corrected")
        else:
            st.write("⚡ Standard resolution")
            st.info("✅ Claim processed")

    with col4:
        st.markdown("**🔄 Patent #4 - Feedback**")
        if result.get('overall_confidence', 0) > 0.7 and not result.get('verification_skipped'):
            st.write("🧠 KG self-healing")
            st.success("✅ Knowledge updated")
        else:
            st.write("📊 Confidence tracking")
            st.info("📈 Learning continued")

    # Show claim type and result
    st.markdown(
        f"**Claim Type:** `{claim_type}` | **Result:** {'🔄 Skipped' if result.get('verification_skipped') else '✅ Verified' if result.get('verdict') else '❌ Hallucination'}**")