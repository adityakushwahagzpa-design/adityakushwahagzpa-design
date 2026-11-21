"""Streamlit dashboard: streamlit run app.py"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

OUT = Path(__file__).parent / "outputs"
st.set_page_config(page_title="Card Fraud Detection", layout="wide")
st.title("Card Fraud Detection: anomaly detection vs machine learning")
if not (OUT / "summary.json").exists():
    st.warning("Run `python detect.py` first."); st.stop()
s = json.loads((OUT / "summary.json").read_text())
st.caption(s["data"] + " · " + s["split"]["method"])
st.dataframe(pd.DataFrame(s["results"]), use_container_width=True)
st.image(str(OUT / "chart_pr_budget.png"))
model = st.selectbox("Alert budget detail for", list(s["budget_detail"]))
st.dataframe(pd.DataFrame(s["budget_detail"][model]).T, use_container_width=True)
st.subheader("Hybrid rule: supervised model OR Isolation Forest")
st.dataframe(pd.DataFrame(s["hybrid_gb_or_iforest"]).T, use_container_width=True)
