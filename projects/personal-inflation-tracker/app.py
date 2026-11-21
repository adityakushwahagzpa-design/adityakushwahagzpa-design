"""Streamlit app: streamlit run app.py"""
import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from ocr_receipts import DATA, ocr, parse

OUT = Path(__file__).parent / "outputs"
st.set_page_config(page_title="Personal Inflation Tracker", layout="wide")
st.title("Personal Inflation Tracker")
st.caption("Demo built on SAMPLE receipts from a fictional store. Upload your own receipt to test the OCR.")

if (OUT / "summary.json").exists():
    s = json.loads((OUT / "summary.json").read_text())
    c = st.columns(4)
    c[0].metric("My basket, YoY", f"{s['basket_yoy_latest_%']:.1f}%")
    if "cpi_food_at_home_yoy_latest_%" in s:
        c[1].metric("CPI food at home, YoY", f"{s['cpi_food_at_home_yoy_latest_%']:.1f}%")
        c[2].metric("Gap vs CPI", f"{s['gap_vs_food_cpi_latest_pts']:+.1f} pts")
    c[3].metric("Basket cost", f"${s['basket_cost_latest']:.2f}", f"{s['basket_cost_latest'] - s['basket_cost_first']:+.2f} since start")
    st.image(str(OUT / "inflation_vs_cpi.png"))
    st.subheader("Items")
    st.dataframe(pd.read_csv(OUT / "item_inflation.csv"), use_container_width=True)
    st.subheader("Monthly series")
    st.dataframe(pd.read_csv(OUT / "monthly_inflation.csv"), use_container_width=True)

st.subheader("Read a receipt")
up = st.file_uploader("Receipt image", type=["png", "jpg", "jpeg"])
if up:
    with tempfile.NamedTemporaryFile(suffix=Path(up.name).suffix) as f:
        f.write(up.read()); f.flush()
        text = ocr(f.name)
    date, rows, rejected, total = parse(text, pd.read_csv(DATA / "catalog.csv")["item"].tolist())
    st.image(up, width=320)
    st.write(f"Date: {date.date() if date is not None else 'not found'} · printed total: {total}")
    st.dataframe(pd.DataFrame(rows))
    if rejected:
        st.warning(f"{len(rejected)} lines failed the checks")
        st.dataframe(pd.DataFrame(rejected))
    with st.expander("Raw OCR text"):
        st.text(text)
