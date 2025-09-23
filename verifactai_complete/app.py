# app.py - Modified to retain patent flow analysis
import streamlit as st
import time
import pandas as pd
import sqlite3
import re
from verifactai_core import VeriFactAICore
from dashboard_components.patent_flow import show_patent_flow
from dashboard_components.realtime_monitor import show_realtime_verification
from dashboard_components.knowledge_graph_viz import show_knowledge_graph
from dashboard_components.patent_flow_detailed import show_patent_flow_detailed

# Page configuration
st.set_page_config(
    page_title="VeriFactAI Patent Dashboard",
    page_icon="🔬",
    layout="wide"
)

# Initialize session state for demo control and LIFETIME metrics
if 'demo_in_progress' not in st.session_state:
    st.session_state.demo_in_progress = False
if 'verified_claims' not in st.session_state:
    st.session_state.verified_claims = []
if 'kg_initialized' not in st.session_state:
    st.session_state.kg_initialized = False
if 'patent_flow_results' not in st.session_state:
    st.session_state.patent_flow_results = []  # NEW: Store patent flow analyses
if 'show_patent_flow' not in st.session_state:
    st.session_state.show_patent_flow = False  # NEW: Control visibility

# LIFETIME METRICS - These should persist across runs in the same session
if 'demo_run_count' not in st.session_state:
    st.session_state.demo_run_count = 0
if 'total_hallucinations_detected' not in st.session_state:
    st.session_state.total_hallucinations_detected = 0
if 'total_claims_healed' not in st.session_state:
    st.session_state.total_claims_healed = 0
if 'total_verifications_saved' not in st.session_state:
    st.session_state.total_verifications_saved = 0

# Sidebar with enhanced controls
st.sidebar.title("🔬 VeriFactAI Patent Demo")
st.sidebar.markdown("### Navigation")
demo_mode = st.sidebar.radio("Select Demo Mode:",
                             ["Interactive Demo", "Auto Demonstration"])

# NEW: Patent flow visibility control
st.sidebar.markdown("### 🔬 Patent Flow Controls")
if st.sidebar.button("📊 Show Patent Flow Analysis"):
    st.session_state.show_patent_flow = True
if st.sidebar.button("📋 Hide Patent Flow Analysis"):
    st.session_state.show_patent_flow = False

# Enhanced Reset button in sidebar
if st.sidebar.button("🔄 Reset Demo State"):
    st.session_state.demo_in_progress = False
    st.session_state.verified_claims = []
    st.session_state.patent_flow_results = []  # NEW: Clear patent flow results
    st.session_state.show_patent_flow = False  # NEW: Reset visibility
    st.session_state.kg_initialized = False
    st.session_state.demo_run_count = 0
    st.session_state.total_hallucinations_detected = 0
    st.session_state.total_claims_healed = 0
    st.session_state.total_verifications_saved = 0
    st.cache_resource.clear()
    try:
        conn = sqlite3.connect('knowledge/verifactai_kg.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM verified_facts")
        conn.commit()
        conn.close()
        st.sidebar.success("✅ Knowledge Graph reset complete")
    except:
        st.sidebar.error("❌ Failed to reset knowledge graph")
    st.rerun()


# Function to check if knowledge graph has healed content
def check_kg_has_healed_content():
    """Check if knowledge graph contains healed facts"""
    try:
        conn = sqlite3.connect('knowledge/verifactai_kg.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM verified_facts")
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    except:
        return False


# Check KG status
kg_has_content = check_kg_has_healed_content()
if kg_has_content and not st.session_state.kg_initialized:
    st.session_state.kg_initialized = True

# Show KG status and metrics in sidebar
st.sidebar.markdown("---")
if kg_has_content:
    try:
        conn = sqlite3.connect('knowledge/verifactai_kg.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM verified_facts")
        fact_count = cursor.fetchone()[0]
        conn.close()
        st.sidebar.success(f"✅ KG: {fact_count} healed facts")
    except:
        st.sidebar.info("🔴 KG Status: Unknown")
else:
    st.sidebar.info("🔴 KG: Empty (no healing yet)")

# Lifetime Metrics in sidebar
st.sidebar.markdown("### 📊 Lifetime Metrics")
st.sidebar.metric("Total Runs", st.session_state.demo_run_count)
st.sidebar.metric("Hallucinations Caught", st.session_state.total_hallucinations_detected)
st.sidebar.metric("Claims Healed", st.session_state.total_claims_healed)
st.sidebar.metric("Verifications Saved", st.session_state.total_verifications_saved)

# NEW: Patent flow status in sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔬 Patent Flow Status")
st.sidebar.write(f"**Analyses stored:** {len(st.session_state.patent_flow_results)}")
st.sidebar.write(f"**Currently visible:** {'✅' if st.session_state.show_patent_flow else '❌'}")

# Main dashboard
st.title("🚀 VeriFactAI - Patent-Protected AI Verification")
st.markdown("### Real-time Hallucination Detection & Correction Pipeline")

# Patent flow visualization
show_patent_flow()

# Demo controls
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("🔍 Test LLM Output")
    user_input = st.text_area(
        "Enter text to verify:",
        "The capital of France is London. World War II ended in 1995. The average human body temperature is 35°C.",
        height=100
    )

with col2:
    st.subheader("🎮 Demo Controls")
    verify_btn = st.button("🚀 Start Verification", type="primary", use_container_width=True)
    auto_demo = st.button("🤖 Run Auto Demo", use_container_width=True)

    # Show current state based on actual KG content
    if kg_has_content:
        st.success("✅ Knowledge Graph contains healed facts")
        st.info("Next run will skip verifications for healed claims")
    else:
        st.info("🔴 First run: Will detect and correct hallucinations")

    # NEW: Patent flow status
    st.markdown("### 🔬 Patent Flow")
    st.write(f"**Stored analyses:** {len(st.session_state.patent_flow_results)}")
    if st.session_state.patent_flow_results:
        st.success("✅ Patent flow data available")
        if st.session_state.show_patent_flow:
            st.info("📊 Analysis visible on dashboard")
        else:
            st.info("👆 Click 'Show Patent Flow Analysis' to view")

    st.info("Click buttons to see patent flow in action!")


# Initialize engine
@st.cache_resource
def get_verifact_engine():
    return VeriFactAICore(reset_on_start=False)


engine = get_verifact_engine()


# NEW: Function to create patent flow analysis data
def create_patent_flow_analysis(claim, result):
    """Create a structured patent flow analysis for retention"""
    claim_lower = claim.lower()
    claim_type = "general"

    # Determine claim type
    if any(geo in claim_lower for geo in ['capital', 'country', 'city', 'france', 'london', 'paris']):
        claim_type = "geographical"
    elif any(temp in claim_lower for temp in ['world war', '1995', '1945', 'year', 'ended']):
        claim_type = "temporal"
    elif any(stat in claim_lower for stat in ['temperature', '35°c', '37°c', 'degree', 'average']):
        claim_type = "statistical"
    elif 'python' in claim_lower or 'guido' in claim_lower:
        claim_type = "entity"

    return {
        'claim': claim,
        'claim_type': claim_type,
        'timestamp': time.time(),
        'verdict': result.get('verdict', False),
        'verification_skipped': result.get('verification_skipped', False),
        'confidence': result.get('overall_confidence', result.get('confidence', 0)),
        'sources': result.get('sources', []),
        'result_summary': 'SKIPPED' if result.get('verification_skipped') else 'HALLUCINATION' if result.get(
            'verdict') else 'VERIFIED'
    }


# Process verification
if verify_btn:
    # INTERACTIVE VERIFICATION MODE
    st.session_state.demo_in_progress = True
    st.session_state.verified_claims = []
    st.session_state.patent_flow_results = []  # NEW: Clear previous analyses

    st.markdown("### 🔍 Interactive Verification Analysis")

    # Split the user input into individual claims/sentences
    claims = re.split(r'[.!?]+', user_input)
    claims = [claim.strip() for claim in claims if claim.strip()]

    if not claims:
        st.warning("Please enter some text to verify!")
        st.stop()

    # Track metrics for this session
    session_hallucinations = 0
    session_verifications_saved = 0
    session_claims_healed = 0

    # Process each claim with detailed visualization
    for i, claim in enumerate(claims):
        if not claim:  # Skip empty claims
            continue

        st.markdown(f"#### 📝 Claim {i + 1}: `{claim}`")

        # Create columns for step-by-step visualization
        col1, col2 = st.columns([1, 2])

        with col1:
            # Show real-time progress for this specific claim
            progress_bar = st.progress(0)
            status_text = st.empty()

            # Simulate the verification steps
            steps = [
                ("🔍 Patent #1 - Analyzing claim context...", 25),
                ("⚖️ Patent #2 - Checking confidence levels...", 50),
                ("🔧 Patent #3 - Applying resolution logic...", 75),
                ("🔄 Patent #4 - Updating knowledge...", 100)
            ]

            for step_text, progress in steps:
                status_text.text(step_text)
                progress_bar.progress(progress)
                time.sleep(0.3)

        with col2:
            # Perform actual verification
            demo_mode_enabled = not kg_has_content
            result = engine.smart_verify(claim, demo_mode=demo_mode_enabled)

            # NEW: Store patent flow analysis
            patent_analysis = create_patent_flow_analysis(claim, result)
            st.session_state.patent_flow_results.append(patent_analysis)

            # Show immediate results
            if result.get('verification_skipped'):
                st.success("✅ **VERIFICATION SKIPPED**")
                st.write(f"**Reason:** {result.get('reason', 'High confidence')}")
                st.write(f"**Confidence Score:** {result.get('confidence', 0):.2%}")
                session_verifications_saved += 1
            else:
                verdict = result.get('verdict', False)
                if verdict:  # True = hallucination detected
                    st.error("❌ **HALLUCINATION DETECTED**")
                    st.write("**Issue:** Claim contains inaccurate information")
                    session_hallucinations += 1
                    if not kg_has_content:
                        session_claims_healed += 1
                else:
                    st.success("✅ **CLAIM VERIFIED**")
                    st.write("**Status:** Information is accurate")

                st.write(f"**Confidence Score:** {result.get('overall_confidence', 0):.2%}")

                # Show source breakdown
                st.write("**Source Analysis:**")
                sources = result.get('sources', [])
                for source in sources:
                    status = "✅" if source.get('verified', False) else "❌"
                    st.write(f"  {status} {source.get('source_name', 'Unknown')}: {source.get('confidence', 0):.2%}")

        # Show patent flow details for this claim
        show_patent_flow_detailed(claim, result)

        # Show correction if applicable
        if not result.get('verification_skipped') and result.get('verdict', False):
            st.markdown("#### 🔧 Suggested Correction:")
            original_claim = claim
            corrected_claim = claim

            # Apply appropriate corrections
            if 'france' in claim.lower() and 'london' in claim.lower():
                corrected_claim = claim.replace("London", "Paris")
            if '1995' in claim and ('world war' in claim.lower() or 'wwii' in claim.lower()):
                corrected_claim = corrected_claim.replace("1995", "1945")
            if '35°c' in claim.lower() or '35 c' in claim.lower():
                corrected_claim = corrected_claim.replace("35°C", "37°C").replace("35 C", "37 C")

            if original_claim != corrected_claim:
                col1, col2 = st.columns(2)
                with col1:
                    st.text_area("Original Claim:", original_claim, height=80, key=f"orig_{i}")
                with col2:
                    st.text_area("Corrected Version:", corrected_claim, height=80, key=f"corr_{i}")

        # Store results for metrics
        st.session_state.verified_claims.append({
            'claim': claim,
            'result': result,
            'timestamp': time.time(),
            'kg_was_healed': kg_has_content
        })

        st.markdown("---")

    # Update lifetime metrics
    st.session_state.demo_run_count += 1
    st.session_state.total_hallucinations_detected += session_hallucinations
    st.session_state.total_verifications_saved += session_verifications_saved
    st.session_state.total_claims_healed += session_claims_healed

    st.session_state.kg_initialized = True
    st.session_state.show_patent_flow = True  # NEW: Auto-show patent flow after verification
    st.success(f"🎯 **Interactive Verification Complete!** Processed {len(claims)} claims.")
    st.rerun()

elif auto_demo:
    # AUTO DEMO MODE
    st.session_state.demo_in_progress = True
    st.session_state.verified_claims = []
    st.session_state.patent_flow_results = []  # NEW: Clear previous analyses

    claims = [
        "The capital of France is London.",
        "World War II ended in 1995.",
        "The average human body temperature is 35°C.",
        "Python was created by Guido van Rossum."
    ]

    progress_bar = st.progress(0)
    status_text = st.empty()

    if kg_has_content:
        status_text.text("🔄 Using healed KG - skipping verifications...")
    else:
        status_text.text("🔄 Detecting hallucinations...")

    current_run_hallucinations = 0
    current_run_verifications_saved = 0
    current_run_claims_healed = 0

    for i, claim in enumerate(claims):
        progress_bar.progress((i + 1) * 25)

        demo_mode_enabled = not kg_has_content
        result = engine.smart_verify(claim, demo_mode=demo_mode_enabled)

        # NEW: Store patent flow analysis
        patent_analysis = create_patent_flow_analysis(claim, result)
        st.session_state.patent_flow_results.append(patent_analysis)

        show_realtime_verification(engine, claim, result, iteration=i)

        # CORRECTED COUNTING LOGIC:
        if result.get('verification_skipped'):
            current_run_verifications_saved += 1
        else:
            if result.get('verdict', False):  # True = hallucination detected!
                current_run_hallucinations += 1
                if not kg_has_content:
                    current_run_claims_healed += 1

        st.session_state.verified_claims.append({
            'claim': claim,
            'result': result,
            'timestamp': time.time(),
            'kg_was_healed': kg_has_content
        })

        time.sleep(2)

    # Update lifetime metrics
    st.session_state.demo_run_count += 1
    st.session_state.total_hallucinations_detected += current_run_hallucinations
    st.session_state.total_verifications_saved += current_run_verifications_saved
    st.session_state.total_claims_healed += current_run_claims_healed

    status_text.text("✅ Auto demo completed!")
    st.session_state.kg_initialized = True
    st.session_state.show_patent_flow = True  # NEW: Auto-show patent flow after demo
    st.rerun()

# NEW: Persistent Patent Flow Analysis Section
if st.session_state.patent_flow_results and st.session_state.show_patent_flow:
    st.markdown("---")
    st.markdown("## 🔬 Persistent Patent Flow Analysis")

    # Summary statistics
    total_analyses = len(st.session_state.patent_flow_results)
    claim_types = {}
    results_summary = {'HALLUCINATION': 0, 'VERIFIED': 0, 'SKIPPED': 0}

    for analysis in st.session_state.patent_flow_results:
        claim_type = analysis['claim_type']
        claim_types[claim_type] = claim_types.get(claim_type, 0) + 1
        results_summary[analysis['result_summary']] += 1

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Analyses", total_analyses)
    with col2:
        st.metric("Claim Types", len(claim_types))
    with col3:
        st.metric("Most Common", max(claim_types, key=claim_types.get) if claim_types else "N/A")

    # Detailed analysis view
    st.markdown("### 📊 Detailed Analysis")
    for i, analysis in enumerate(st.session_state.patent_flow_results):
        with st.expander(f"🔍 Analysis {i + 1}: {analysis['claim'][:50]}...", expanded=(i == 0)):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("**Claim Info**")
                st.write(f"**Type:** {analysis['claim_type'].upper()}")
                st.write(f"**Length:** {len(analysis['claim'])} chars")
                st.write(f"**Time:** {time.strftime('%H:%M:%S', time.localtime(analysis['timestamp']))}")

            with col2:
                st.markdown("**Verification Results**")
                result_color = "red" if analysis['result_summary'] == 'HALLUCINATION' else "green" if analysis[
                                                                                                          'result_summary'] == 'VERIFIED' else "blue"
                st.markdown(f"**Result:** :{result_color}[{analysis['result_summary']}]")
                st.write(f"**Confidence:** {analysis['confidence']:.2%}")
                st.write(f"**Skipped:** {analysis['verification_skipped']}")

            with col3:
                st.markdown("**Patent Flow**")
                st.write("🔍 **Identification:** Completed")
                st.write("⚖️ **Verification:** Completed")
                st.write("🔧 **Resolution:** Applied")
                st.write("🔄 **Feedback:** Processed")

            # Show the actual claim
            st.markdown("**Original Claim:**")
            st.code(analysis['claim'])

            # Show sources if available
            if analysis['sources']:
                st.markdown("**Sources:**")
                for source in analysis['sources']:
                    status = "✅" if source.get('verified', False) else "❌"
                    st.write(f"{status} {source.get('source_name', 'Unknown')}: {source.get('confidence', 0):.2%}")

# Knowledge graph visualization
if st.session_state.verified_claims or st.session_state.kg_initialized:
    show_knowledge_graph(engine)
else:
    st.info("📊 **Knowledge Graph Dashboard** will appear here after running the demo")

# Enhanced Statistics Dashboard
st.markdown("---")
st.subheader("📊 Performance Analytics")

if st.session_state.verified_claims:
    total_claims = len(st.session_state.verified_claims)

    # CORRECTED COUNTING LOGIC:
    current_run_hallucinations = 0
    current_run_verified_claims = 0
    current_run_skipped_verifications = 0

    for claim_data in st.session_state.verified_claims:
        result = claim_data['result']

        if result.get('verification_skipped'):
            current_run_skipped_verifications += 1
        else:
            if result.get('verdict', False):  # True = hallucination
                current_run_hallucinations += 1
            else:  # False = verified correct
                current_run_verified_claims += 1

    # Current Run Metrics
    st.markdown("### 🔄 Current Run Performance")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Claims Processed", total_claims)
    col2.metric("Hallucinations Caught", current_run_hallucinations)
    col3.metric("Verified Claims", current_run_verified_claims)
    col4.metric("Skipped Verifications", current_run_skipped_verifications)

    # Lifetime Metrics
    st.markdown("### 📈 Lifetime Analytics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Runs", st.session_state.demo_run_count)
    col2.metric("Total Hallucinations", st.session_state.total_hallucinations_detected)
    col3.metric("Total Claims Healed", st.session_state.total_claims_healed)
    col4.metric("Verifications Saved", st.session_state.total_verifications_saved)

else:
    st.info("👆 Run the demo to see comprehensive analytics!")

# Footer with system status
st.markdown("---")
st.markdown(
    f"**System Status:** {'🔴 Learning Mode' if not kg_has_content else '✅ Healed Mode'} | **Total Runs:** {st.session_state.demo_run_count} | **Patent Analyses:** {len(st.session_state.patent_flow_results)}")