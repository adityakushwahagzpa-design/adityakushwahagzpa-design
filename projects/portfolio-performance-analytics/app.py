"""Streamlit dashboard: streamlit run app.py"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

OUT = Path(__file__).parent / "outputs"
st.set_page_config(page_title="Portfolio Performance Analytics", layout="wide")
st.title("Portfolio Performance Analytics")
if not (OUT / "summary.json").exists():
    st.warning("Run `python tracker.py` first."); st.stop()
s = json.loads((OUT / "summary.json").read_text())
st.caption(s["data"] + f" · {s['period'][0]} to {s['period'][1]}")
c = st.columns(5)
c[0].metric("Net invested", f"₹{s['net_invested_inr']:,}")
c[1].metric("Current value", f"₹{s['current_value_inr']:,}", f"₹{s['gain_inr']:,}")
c[2].metric("XIRR", f"{s['xirr_%']}%", f"{s['xirr_%'] - s['nifty_xirr_same_cash_flows_%']:+.2f} pts vs Nifty")
c[3].metric("Sharpe ratio", s["portfolio"]["sharpe"], f"Nifty {s['nifty']['sharpe']}")
c[4].metric("Max drawdown", f"{s['portfolio']['max_drawdown_%']:.1f}%", f"Nifty {s['nifty']['max_drawdown_%']:.1f}%", delta_color="off")
d = pd.read_csv(OUT / "daily_values.csv", index_col=0, parse_dates=True)
st.line_chart(d)
st.subheader("Risk and return")
st.dataframe(pd.DataFrame({"Portfolio": s["portfolio"], "Nifty 50": s["nifty"]}), use_container_width=True)
st.subheader("Holdings")
st.dataframe(pd.read_csv(OUT / "holdings.csv"), use_container_width=True)
st.image(str(OUT / "chart_risk_diversification.png"))
