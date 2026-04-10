# dashboard_components/knowledge_graph_viz.py
import streamlit as st
import pandas as pd
import sqlite3


def show_knowledge_graph(engine):
    st.markdown("### 🧠 Self-Healing Knowledge Graph (Patent #4)")

    try:
        # Get actual data from knowledge graph
        conn = sqlite3.connect('knowledge/verifactai_kg.db')
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM verified_facts")
        fact_count = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(confidence) FROM verified_facts")
        avg_confidence = cursor.fetchone()[0] or 0

        # Get recent facts with timestamps
        cursor.execute("SELECT claim, confidence, timestamp FROM verified_facts ORDER BY timestamp DESC LIMIT 10")
        recent_facts = cursor.fetchall()

        conn.close()

        # Only show graph if there's data
        if fact_count > 0:
            # Create growth data based on actual facts
            growth_data = {
                "Metric": ["Healed Facts", "Average Confidence"],
                "Value": [fact_count, avg_confidence * 100]  # Convert to percentage
            }

            df = pd.DataFrame(growth_data)

            col1, col2 = st.columns(2)

            with col1:
                st.metric("Total Facts Learned", fact_count)
                st.bar_chart(df[df['Metric'] == 'Healed Facts'].set_index("Metric")["Value"])

            with col2:
                st.metric("Average Confidence", f"{avg_confidence:.1%}")
                st.bar_chart(df[df['Metric'] == 'Average Confidence'].set_index("Metric")["Value"])

            # Show recent learning
            st.markdown("**📚 Recently Learned Facts:**")
            for claim, confidence, timestamp in recent_facts:
                st.write(f"🔹 {claim} ({confidence:.1%} confidence)")
        else:
            st.info("📊 Knowledge Graph is empty. Run the demo to see self-healing in action!")

    except Exception as e:
        st.info("📊 Knowledge Graph not yet initialized. Run the demo to start learning!")