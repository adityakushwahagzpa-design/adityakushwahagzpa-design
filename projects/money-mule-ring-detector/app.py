"""
Streamlit dashboard for the money mule ring detector.

Run:  streamlit run app.py   (after generate_data.py and detect.py)
"""

import json

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Money Mule Ring Detector", layout="wide")
st.title("Money Mule Ring Detector")
st.caption("Synthetic transaction data. Every account is invented; labels exist only to measure the detector.")

metrics = json.load(open("outputs/metrics.json"))
feat = pd.read_csv("outputs/account_features.csv")
rings = pd.read_csv("outputs/detected_rings.csv")
tx = pd.read_csv("data/transactions.csv")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Accounts scored", f"{metrics['accounts_scored']:,}")
c2.metric("Rings detected", metrics["rings_detected"])
c3.metric("Rule recall", f"{metrics['rules_on_test_set']['recall']:.0%}")
c4.metric("Rule precision", f"{metrics['rules_on_test_set']['precision']:.0%}")

st.subheader("Detected rings")
st.dataframe(rings, use_container_width=True)

ring = st.selectbox("Inspect a ring", rings["ring"])
members = rings.set_index("ring").loc[ring, "members"].split()
sub_tx = tx[tx["src"].isin(members) | tx["dst"].isin(members)]
G = nx.from_pandas_edgelist(sub_tx, "src", "dst", edge_attr="amount", create_using=nx.DiGraph)
fig, ax = plt.subplots(figsize=(8, 5))
pos = nx.spring_layout(G, seed=3)
nx.draw_networkx(G, pos, ax=ax, node_color=["#7c3aed" if n in members else "#cbd5e1" for n in G],
                 node_size=[300 if n in members else 80 for n in G], with_labels=False, arrowsize=8, edge_color="#94a3b8")
ax.axis("off")
st.pyplot(fig)
st.dataframe(feat[feat["account_id"].isin(members)].round(3), use_container_width=True)

st.subheader("Riskiest accounts by rule score")
st.dataframe(feat.sort_values("rule_score", ascending=False).head(25).round(3), use_container_width=True)
