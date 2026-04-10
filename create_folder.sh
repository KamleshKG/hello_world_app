# Create main directory
mkdir verifactai_complete
cd verifactai_complete

# Create main files
touch app.py cli_demo.py verifactai_core.py logprobs_trigger.py local_verifier.py
touch requirements.txt README.md

# Create folders
mkdir -p dashboard_components knowledge assets/patent_diagrams

# Create dashboard files
touch dashboard_components/__init__.py
touch dashboard_components/patent_flow.py
touch dashboard_components/realtime_monitor.py 
touch dashboard_components/knowledge_graph_viz.py

# Create data files
touch knowledge/local_knowledge.db
touch knowledge/verifactai_kg.db

echo "✅ Structure created!"