# core/templates/value_dashboard.py
import streamlit as st
from core.data_collector import get_platform_metrics, get_plugin_metrics

def show_value_dashboard(user):
    st.title("📊 DevOps Chapter Value Dashboard")

    # LAYER 1: Chapter Health
    st.header("Chapter Health & Impact")
    col1, col2, col3 = st.columns(3)
    metrics = get_platform_metrics()
    col1.metric("Platform Uptime", f"{metrics['uptime']}%", "100%")
    col2.metric("User Adoption", f"{metrics['adoption_rate']}%", "+5%")
    col3.metric("Lead Time for Changes", f"{metrics['lead_time']} days", "-2 days")

    # LAYER 2: Plugin Ecosystem
    st.header("Plugin Ecosystem Performance")
    plugin_metrics = get_plugin_metrics()
    for plugin_name, data in plugin_metrics.items():
        with st.expander(f"Plugin: {plugin_name}"):
            st.metric("Active Users", data['active_users'])
            st.metric("Monthly Value Delivered", data['value_metric'])

    # LAYER 3: Social Feedback
    st.header("Community Feedback")
    col1, col2 = st.columns(2)
    with col1:
        st.write("**Recent Feedback**")
        # Display latest feedback comments
    with col2:
        st.write("**Sentiment This Week**")
        st.metric("Avg. Rating", "4.5 / 5", "+0.2")