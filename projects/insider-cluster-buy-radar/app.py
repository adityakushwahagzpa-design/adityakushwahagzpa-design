"""
Streamlit dashboard for the insider cluster-buy radar.

Run:  streamlit run app.py   (after radar.py; set DATABASE_URL to read from PostgreSQL)
"""

import json
import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

st.set_page_config(page_title="Insider Cluster-Buy Radar", layout="wide")
st.title("Insider Cluster-Buy Radar")
st.caption("Three or more officers or directors buying their own stock on the open market within 14 days. Source: SEC Form 4 filings.")

engine = create_engine(os.environ.get("DATABASE_URL", "sqlite:///radar.db"))
try:
    clusters = pd.read_sql("SELECT * FROM clusters", engine)
    purchases = pd.read_sql("SELECT * FROM purchases", engine)
except Exception:  # no database yet: fall back to the saved CSV
    clusters, purchases = pd.read_csv("outputs/clusters.csv"), None
summary = json.load(open("outputs/summary.json"))

c1, c2, c3 = st.columns(3)
c1.metric("Clusters found", summary["clusters"])
c2.metric("Qualifying purchases", f"{summary['qualifying_purchases']:,}")
m = summary.get("1 month", {})
c3.metric("Avg 1-month return vs SPY", f"{m.get('avg_excess_return_%') or 0:+.1f} pp")

min_insiders = st.slider("Minimum insiders in a cluster", 3, 8, 3)
view = clusters[clusters["insiders"] >= min_insiders].sort_values("end", ascending=False)
st.dataframe(view, use_container_width=True)

if purchases is not None and len(view):
    t = st.selectbox("Show the individual purchases for", view["ticker"].unique())
    st.dataframe(purchases[purchases["ticker"] == t].sort_values("trans_date"), use_container_width=True)

st.image("outputs/excess_returns.png")
