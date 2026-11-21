"""
Personal basket inflation from OCR'd receipts, compared with official US CPI.

  * Fixed-basket (Laspeyres) index: base-month quantities x each month's prices
  * Missing item-months (OCR could not read the line) are filled with the last known price
  * Year-over-year inflation for the basket, each category and each item
  * Official benchmark: BLS CPI-U Food at home, US city average, not seasonally adjusted (CUUR0000SAF11)
"""
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).parent
OUT = ROOT / "outputs"
BLS_SERIES = {"CUUR0000SAF11": "CPI food at home", "CUUR0000SA0": "CPI all items"}


def fetch_cpi(start_year, end_year):
    key = os.environ.get("BLS_API_KEY")
    url = f"https://api.bls.gov/publicAPI/{'v2' if key else 'v1'}/timeseries/data/"
    body = {"seriesid": list(BLS_SERIES), "startyear": str(start_year), "endyear": str(end_year)}
    if key:
        body["registrationkey"] = key
    j = requests.post(url, json=body, timeout=60).json()
    if j.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(j.get("message"))
    frames = []
    for s in j["Results"]["series"]:
        d = pd.DataFrame(s["data"])
        d = d[d["period"].str.match(r"M(0[1-9]|1[0-2])")]
        d["month"] = pd.to_datetime(d["year"] + "-" + d["period"].str[1:] + "-01")
        frames.append(d.set_index("month")["value"].astype(float).rename(BLS_SERIES[s["seriesID"]]))
    return pd.concat(frames, axis=1).sort_index()


def main():
    items = pd.read_csv(OUT / "ocr_line_items.csv", parse_dates=["date"])
    items["month"] = items["date"].dt.to_period("M").dt.to_timestamp()
    prices = items.pivot_table(index="month", columns="item", values="unit_price", aggfunc="mean").sort_index()
    filled = int(prices.isna().sum().sum())
    prices = prices.ffill().bfill()
    base_qty = items[items["month"] == prices.index[0]].groupby("item")["qty"].first()
    base_qty = base_qty.reindex(prices.columns).fillna(items.groupby("item")["qty"].median())
    cats = items.drop_duplicates("item").set_index("item")["category"]

    cost = prices.mul(base_qty, axis=1)
    basket = cost.sum(axis=1)
    index = 100 * basket / basket.iloc[0]
    yoy = (basket / basket.shift(12) - 1) * 100
    cat_cost = cost.T.groupby(cats).sum().T
    cat_yoy = (cat_cost / cat_cost.shift(12) - 1) * 100
    item_yoy = (prices / prices.shift(12) - 1) * 100
    weights = (cost.iloc[0] / cost.iloc[0].sum() * 100).round(1)

    try:
        cpi = fetch_cpi(prices.index[0].year - 1, prices.index[-1].year)
        cpi_yoy = (cpi / cpi.shift(12) - 1) * 100
        cpi_note = "BLS API"
    except Exception as e:
        cpi, cpi_yoy, cpi_note = pd.DataFrame(), pd.DataFrame(), f"BLS unavailable: {e}"
    print(cpi_note)

    table = pd.DataFrame({"basket cost $": basket.round(2), "basket index": index.round(1), "basket YoY %": yoy.round(2)})
    if not cpi_yoy.empty:
        table = table.join(cpi_yoy.round(2).add_suffix(" YoY %"), how="left")
    table.index = table.index.strftime("%Y-%m")
    table.to_csv(OUT / "monthly_inflation.csv")
    latest = prices.index[-1]
    item_table = pd.DataFrame({"category": cats, "weight %": weights, "price first month $": prices.iloc[0],
                               "price latest $": prices.iloc[-1], "YoY latest %": item_yoy.iloc[-1].round(1),
                               "change since start %": ((prices.iloc[-1] / prices.iloc[0] - 1) * 100).round(1)})
    item_table = item_table.sort_values("YoY latest %", ascending=False)
    item_table.to_csv(OUT / "item_inflation.csv")

    yoy_valid = yoy.dropna()
    summary = {
        "data": "SAMPLE receipts (fictional store) read by Tesseract OCR; CPI from BLS",
        "months": [str(prices.index[0].date()), str(latest.date())], "items_tracked": int(prices.shape[1]),
        "item_months_filled_forward": filled,
        "basket_cost_first": round(float(basket.iloc[0]), 2), "basket_cost_latest": round(float(basket.iloc[-1]), 2),
        "basket_yoy_latest_%": round(float(yoy.iloc[-1]), 2),
        "basket_yoy_avg_last12_%": round(float(yoy_valid.tail(12).mean()), 2),
        "category_yoy_latest_%": cat_yoy.iloc[-1].round(2).to_dict(),
        "top_item_inflation": item_table["YoY latest %"].head(3).to_dict(),
        "falling_items": item_table[item_table["YoY latest %"] < 0]["YoY latest %"].to_dict(),
        "cpi_source": cpi_note,
    }
    if not cpi_yoy.empty:
        common = yoy_valid.index.intersection(cpi_yoy.dropna().index)
        f = cpi_yoy.loc[common, "CPI food at home"]
        summary.update({
            "cpi_food_at_home_yoy_latest_%": round(float(f.iloc[-1]), 2), "cpi_latest_month": str(common[-1].date()),
            "cpi_all_items_yoy_latest_%": round(float(cpi_yoy.loc[common[-1], "CPI all items"]), 2),
            "gap_vs_food_cpi_latest_pts": round(float(yoy.loc[common[-1]] - f.iloc[-1]), 2),
            "avg_gap_vs_food_cpi_pts": round(float((yoy.loc[common] - f).mean()), 2),
            "months_compared": int(len(common)),
        })
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    chart(yoy, cpi_yoy, item_table)
    print(json.dumps(summary, indent=2, default=float))


def chart(yoy, cpi_yoy, item_table):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.3, 1]})
    y = yoy.dropna()
    ax[0].plot(y.index, y, marker="o", lw=2, color="#6a1b9a", label="My basket (sample receipts)")
    if not cpi_yoy.empty:
        c = cpi_yoy.loc[y.index.min():y.index.max()]
        ax[0].plot(c.index, c["CPI food at home"], marker="s", lw=2, color="#ef6c00", label="CPI food at home (BLS)")
        ax[0].plot(c.index, c["CPI all items"], lw=1.5, ls="--", color="#757575", label="CPI all items (BLS)")
    ax[0].axhline(0, color="black", lw=0.6)
    ax[0].set_title("Year-over-year inflation (%)")
    ax[0].legend(frameon=False, fontsize=9)
    ax[0].tick_params(axis="x", rotation=30, labelsize=8)
    it = item_table["YoY latest %"].sort_values()
    ax[1].barh(it.index, it, color=["#2e7d32" if v < 0 else "#c62828" for v in it])
    ax[1].axvline(0, color="black", lw=0.6)
    ax[1].set_title("Item price change, latest month vs a year ago (%)")
    ax[1].tick_params(axis="y", labelsize=8)
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Personal inflation tracker — SAMPLE receipt data vs official CPI", fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "inflation_vs_cpi.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
