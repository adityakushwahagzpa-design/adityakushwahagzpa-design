"""Streamlit dashboard: streamlit run app.py"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from market import rsi
from nifty50 import NIFTY50, yf_symbol

OUT = Path(__file__).parent / "outputs"
st.set_page_config(page_title="Nifty 50 Market Trend Dashboard", layout="wide")
st.title("Nifty 50 Market Trend Dashboard")

if (OUT / "summary.json").exists():
    s = json.loads((OUT / "summary.json").read_text())
    c = st.columns(4)
    c[0].metric("Nifty 50", f"{s['nifty_level']:,}", f"{s['nifty_returns_%']['1M']:+.1f}% (1M)")
    c[1].metric("1-year return", f"{s['nifty_returns_%']['1Y']:+.1f}%")
    c[2].metric("Stocks above 200-day avg", f"{s['breadth_above_200dma_%']}%")
    c[3].metric("Stocks in uptrend", f"{s['stocks_in_uptrend']} / {s['stocks_analysed']}")
    st.caption(f"As of {s['as_of']}")
    tab1, tab2, tab3 = st.tabs(["Market", "All stocks", "Stock chart"])
    with tab1:
        st.image(str(OUT / "chart_index_trend.png"))
        st.image(str(OUT / "chart_breadth.png"))
        st.image(str(OUT / "chart_sectors.png"))
    with tab2:
        m = pd.read_csv(OUT / "stock_metrics.csv")
        sector = st.multiselect("Sector", sorted(m["sector"].unique()))
        st.dataframe(m[m["sector"].isin(sector)] if sector else m, use_container_width=True)
    with tab3:
        import yfinance as yf
        sym = st.selectbox("Stock", sorted(NIFTY50))
        p = yf.download(yf_symbol(sym), period="2y", auto_adjust=True, progress=False)["Close"].squeeze()
        df = pd.DataFrame({"Price": p, "50-day avg": p.rolling(50).mean(), "200-day avg": p.rolling(200).mean()})
        st.line_chart(df)
        st.line_chart(rsi(p).rename("RSI 14"))
else:
    st.warning("Run `python market.py` first.")
