"""Streamlit app: streamlit run app.py"""
from pathlib import Path

import pandas as pd
import streamlit as st

OUT = Path(__file__).parent / "outputs"
st.set_page_config(page_title="Financial Statement Analyzer", layout="wide")
st.title("Financial Statement Analyzer")
st.caption("12 Indian companies · annual statements from Yahoo Finance · ₹ crore")
if not (OUT / "ratio_comparison.csv").exists():
    st.warning("Run `python analyzer.py` first."); st.stop()
comp = pd.read_csv(OUT / "ratio_comparison.csv", index_col=0)
st.dataframe(comp, use_container_width=True)
st.image(str(OUT / "chart_profitability_growth.png"))
sym = st.selectbox("Company detail", comp.index)
st.dataframe(pd.read_csv(OUT / f"{sym}_statements_ratios.csv", index_col=0), use_container_width=True)
st.download_button("Download Excel workbook", (OUT / "Financial_Statement_Analysis.xlsx").read_bytes(),
                   "Financial_Statement_Analysis.xlsx")
