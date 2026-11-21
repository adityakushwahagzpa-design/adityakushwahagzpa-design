"""Streamlit app: streamlit run app.py  (set ANTHROPIC_API_KEY to run live debates)"""
import json
import os

import streamlit as st

from evidence import OUT, as_prompt_text, build

st.set_page_config(page_title="Bull vs Bear AI Debate", layout="wide")
st.title("Bull vs Bear AI Debate")
st.caption("Evidence: latest 10-K (SEC EDGAR), SEC XBRL financials and yfinance market data. Agents must cite evidence IDs.")

ticker = st.text_input("US ticker", "NVDA").upper().strip()
col1, col2 = st.columns(2)
if col1.button("Build evidence pack"):
    with st.spinner("Reading the 10-K and market data..."):
        build(ticker)
path = OUT / f"{ticker}_evidence.json"
if path.exists():
    pack = json.loads(path.read_text())
    st.markdown(f"**{pack['company']}** — 10-K filed {pack['10k_filed']} · [filing]({pack['10k_url']})")
    with st.expander("Evidence pack"):
        st.text(as_prompt_text(pack))
    if col2.button("Run debate", disabled=not os.environ.get("ANTHROPIC_API_KEY")):
        import anthropic
        from debate import run_debate
        with st.spinner("Bull and bear are arguing..."):
            run_debate(anthropic.Anthropic(), ticker)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.info("Set ANTHROPIC_API_KEY to run the agents.")
    if (OUT / f"{ticker}_debate.md").exists():
        v = json.loads((OUT / f"{ticker}_verdict.json").read_text())
        c = st.columns(4)
        c[0].metric("Verdict", str(v.get("verdict")).upper())
        c[1].metric("Confidence", f"{v.get('confidence')}%")
        c[2].metric("Bull score", v.get("bull_score"))
        c[3].metric("Bear score", v.get("bear_score"))
        st.markdown((OUT / f"{ticker}_debate.md").read_text())
