"""Streamlit app: streamlit run app.py — score one borrower with the trained model."""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

OUT = Path(__file__).parent / "outputs"
st.set_page_config(page_title="Credit Default Prediction", layout="wide")
st.title("Credit Default Prediction")

if not (OUT / "summary.json").exists():
    st.warning("Run `python model.py` first."); st.stop()
s = json.loads((OUT / "summary.json").read_text())
st.caption(s["data"])
st.dataframe(pd.DataFrame(s["models"]), use_container_width=True)
c = s["cost_based_cutoff"]
k = st.columns(4)
k[0].metric("Approval rate at cut-off", f"{c['approval_rate_%']}%")
k[1].metric("Defaulters caught", f"{c['defaulters_caught_%']}%")
k[2].metric("Default rate, approved", f"{c['default_rate_approved_%']}%")
k[3].metric("Default rate, all", f"{c['default_rate_all_%']}%")
st.image(str(OUT / "chart_roc_calibration.png"))
st.image(str(OUT / "chart_drivers_bands.png"))

st.subheader("Score a borrower")
@st.cache_resource
def train():
    from sklearn.ensemble import HistGradientBoostingClassifier
    from model import features, load
    X, y, _ = load()
    F = features(X)
    return HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, l2_regularization=1.0, random_state=42).fit(F, y), F.columns

if st.button("Load model (downloads the data set once)"):
    st.session_state["m"] = train()
if "m" in st.session_state:
    from model import COLS, features, to_score
    a, b = st.columns(2)
    limit = a.number_input("Credit limit (NT$)", 10000, 1000000, 100000, 10000)
    age = a.number_input("Age", 21, 79, 35)
    delay = a.selectbox("Months behind on latest payment", [-1, 0, 1, 2, 3, 4], index=1)
    bill = b.number_input("Latest bill", 0, 1000000, 40000, 1000)
    paid = b.number_input("Amount paid last month", 0, 1000000, 5000, 500)
    row = {c: 0.0 for c in COLS}
    row.update({"LIMIT_BAL": limit, "AGE": age, "EDUCATION": 2, "PAY_0": delay,
                **{f"BILL_AMT{i}": bill for i in range(1, 7)}, **{f"PAY_AMT{i}": paid for i in range(1, 7)}})
    m, cols = st.session_state["m"]
    p = m.predict_proba(features(pd.DataFrame([row]))[cols])[0, 1]
    st.metric("Probability of default", f"{p * 100:.1f}%", f"score {int(to_score(pd.Series([p]))[0])}")
