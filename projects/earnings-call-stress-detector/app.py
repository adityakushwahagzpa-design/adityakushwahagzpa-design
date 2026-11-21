"""Streamlit dashboard: streamlit run app.py"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

OUT = Path(__file__).parent / "outputs"
st.set_page_config(page_title="Earnings Call Stress Detector", layout="wide")
st.title("Earnings Call Stress Detector")

if not (OUT / "call_scores.csv").exists():
    st.warning("Run `python stress.py` first.")
    st.stop()

s = pd.read_csv(OUT / "call_scores.csv", parse_dates=["call_time"])
summary = json.loads((OUT / "summary.json").read_text())
c = st.columns(4)
c[0].metric("Calls scored", summary["calls_scored"])
c[1].metric("Companies", summary["companies"])
c[2].metric("Q5 minus Q1 reaction", f"{summary['q5_minus_q1_abnormal']:+.2f}%")
c[3].metric("Calls where Q&A is less positive", f"{summary['share_calls_qa_less_positive']}%")
st.image(str(OUT / "stress_quintiles.png"))

st.subheader("Look up a company")
sym = st.selectbox("Ticker", sorted(s["symbol"].unique()))
st.dataframe(s[s["symbol"] == sym].sort_values("call_time"), use_container_width=True)

st.subheader("All calls, most stressed first")
st.dataframe(s.sort_values("stress_index", ascending=False), use_container_width=True)

st.subheader("Score your own Q&A text")
text = st.text_area("Paste executive answers from a call")
if st.button("Score") and text:
    from stress import lexicon_rates, load_finbert, sentences
    import numpy as np
    unc, eva, n = lexicon_rates(text)
    tone = load_finbert()(sentences(text, 60, np.random.default_rng(0)))
    st.write({"FinBERT tone (-1 to +1)": round(tone, 3), "uncertainty words per 1k": round(unc, 1),
              "evasive phrases per 1k": round(eva, 2), "words": n})
