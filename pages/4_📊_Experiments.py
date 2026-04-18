"""
Vault-AI — Experiments Dashboard
MLflow experiment tracking viewer.
"""

import streamlit as st
from components import render_sidebar

st.set_page_config(page_title="Experiments", page_icon="📊", layout="wide")
render_sidebar("experiments")

st.title("📊 ML Experiment Tracking")
st.markdown("Live MLflow metrics from your Vault-AI pipeline runs.")

try:
    from services.experiment_tracker import ExperimentTracker
    tracker = ExperimentTracker()
    summary = tracker.get_metrics_summary()
    all_runs = tracker.get_all_experiments_runs()

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Runs", summary.get("total_runs", 0))
    col2.metric("Total Uploads", summary.get("total_uploads", 0))
    col3.metric("Total Queries", summary.get("total_queries", 0))
    col4.metric("Entities Detected", summary.get("total_entities_detected", 0))

    st.divider()

    # Tabs for each experiment
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔄 Pipeline Runs",
        "🧠 Embedding Comparison", 
        "🔒 Privacy-Utility",
        "🎯 PII Detection",
        "🔍 Retrieval Quality"
    ])

    with tab1:
        st.subheader("Pipeline Runs")
        runs = all_runs.get("pipeline", [])
        if runs:
            import pandas as pd
            df = pd.DataFrame([{
                "Run": r["run_name"],
                "Operation": r["params"].get("operation", ""),
                "Document": r["params"].get("document", ""),
                "PII Entities": r["metrics"].get("pii_entities_detected", ""),
                "Processing Time (s)": r["metrics"].get("processing_time_sec", ""),
                "Chunks": r["metrics"].get("num_chunks", ""),
            } for r in runs])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No pipeline runs yet. Upload a document to start tracking!")

    with tab2:
        st.subheader("Embedding Model Comparison")
        runs = all_runs.get("embedding", [])
        if runs:
            import pandas as pd
            df = pd.DataFrame([{
                "Model": r["params"].get("model_name", ""),
                "Top-1 Similarity": r["metrics"].get("top1_similarity", ""),
                "Mean Similarity": r["metrics"].get("mean_similarity", ""),
                "Embed Time (s)": r["metrics"].get("embedding_time_sec", ""),
            } for r in runs])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No embedding experiments yet.")

    with tab3:
        st.subheader("Privacy-Utility Tradeoff (Epsilon vs Similarity)")
        runs = all_runs.get("privacy", [])
        if runs:
            import pandas as pd
            import plotly.express as px
            df = pd.DataFrame([{
                "Epsilon": r["metrics"].get("epsilon", ""),
                "Similarity Before Noise": r["metrics"].get("similarity_before_noise", ""),
                "Similarity After Noise": r["metrics"].get("similarity_after_noise", ""),
                "Utility Drop": r["metrics"].get("utility_drop", ""),
            } for r in runs])
            st.dataframe(df, use_container_width=True)
            if len(df) > 1:
                fig = px.line(df, x="Epsilon", y="Similarity After Noise",
                             title="Privacy Budget vs Retrieval Quality")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No privacy-utility experiments yet.")

    with tab4:
        st.subheader("PII Detection Confidence")
        runs = all_runs.get("pii", [])
        if runs:
            import pandas as pd
            df = pd.DataFrame([{
                "Document": r["params"].get("document", ""),
                "Entities Detected": r["metrics"].get("entities_detected", ""),
                "Avg Confidence": r["metrics"].get("avg_confidence", ""),
                "High Conf Count": r["metrics"].get("high_conf_count", ""),
                "Low Conf Count": r["metrics"].get("low_conf_count", ""),
                "Processing Time (s)": r["metrics"].get("processing_time_sec", ""),
            } for r in runs])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No PII detection experiments yet.")

    with tab5:
        st.subheader("Retrieval Quality")
        runs = all_runs.get("retrieval", [])
        if runs:
            import pandas as pd
            df = pd.DataFrame([{
                "Query": r["params"].get("query", ""),
                "Top-1 Similarity": r["metrics"].get("top1_similarity", ""),
                "Mean Similarity": r["metrics"].get("mean_similarity", ""),
                "Precision@K": r["metrics"].get("precision_at_k", ""),
                "Latency (s)": r["metrics"].get("latency_sec", ""),
            } for r in runs])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No retrieval experiments yet.")

except Exception as e:
    st.error(f"Could not load experiments: {e}")
    st.info("Run the app and upload a document to start tracking experiments!")
