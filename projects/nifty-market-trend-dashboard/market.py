"""
Nifty 50 Market Trend Dashboard

Two years of daily prices for every Nifty 50 stock and the index, turned into:
  * returns over 1 month, 3 months, 6 months, 1 year and year-to-date
  * 50-day and 200-day moving averages, golden and death crosses, RSI(14)
  * volatility and maximum drawdown
  * market breadth: share of Nifty 50 stocks above their 200-day average, over time
  * sector performance (equal weight)
Outputs: stock_metrics.csv, summary.json, REPORT.md and four charts. app.py shows it in Streamlit.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from nifty50 import INDEX, NIFTY50, yf_symbol

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)


def download():
    import yfinance as yf
    syms = [yf_symbol(s) for s in NIFTY50] + [INDEX]
    px = yf.download(syms, period="2y", auto_adjust=True, progress=False, threads=True)["Close"]
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px = px.dropna(how="all")
    px.columns = [c.replace(".NS", "") for c in px.columns]
    for s in [s for s in NIFTY50 if s not in px or px[s].dropna().shape[0] < 220]:  # retry one by one
        one = yf.download(yf_symbol(s), period="2y", auto_adjust=True, progress=False)["Close"].squeeze()
        if len(one.dropna()) >= 220:
            one.index = pd.to_datetime(one.index).tz_localize(None)
            px[s] = one
    missing = [s for s in NIFTY50 if s not in px or px[s].dropna().shape[0] < 220]
    return px.drop(columns=[m for m in missing if m in px]), missing


def rsi(series, n=14):
    d = series.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def ret(s, days):
    s = s.dropna()
    return (s.iloc[-1] / s.iloc[-days - 1] - 1) * 100 if len(s) > days else np.nan


def stock_metrics(px):
    rows = []
    year_start = px.index[px.index.year == px.index[-1].year][0]
    for sym in [c for c in px.columns if c != INDEX]:
        s = px[sym].dropna()
        ma50, ma200 = s.rolling(50).mean(), s.rolling(200).mean()
        above = (ma50 > ma200).astype(int)
        cross = above.diff().iloc[-60:]  # last ~3 months
        last1y = s.iloc[-252:]
        rows.append({
            "symbol": sym, "sector": NIFTY50.get(sym, ""), "price": round(s.iloc[-1], 2),
            "1M %": ret(s, 21), "3M %": ret(s, 63), "6M %": ret(s, 126), "1Y %": ret(s, 252),
            "YTD %": (s.iloc[-1] / s.loc[s.index >= year_start].iloc[0] - 1) * 100,
            "vs 200DMA %": (s.iloc[-1] / ma200.iloc[-1] - 1) * 100,
            "trend": "Uptrend (50DMA > 200DMA)" if ma50.iloc[-1] > ma200.iloc[-1] else "Downtrend (50DMA < 200DMA)",
            "recent cross": "Golden cross" if (cross == 1).any() else ("Death cross" if (cross == -1).any() else ""),
            "RSI 14": rsi(s).iloc[-1],
            "volatility 1Y %": s.pct_change().iloc[-252:].std() * np.sqrt(252) * 100,
            "max drawdown 1Y %": ((last1y / last1y.cummax()) - 1).min() * 100,
        })
    return pd.DataFrame(rows).round(2).sort_values("1Y %", ascending=False)


def breadth(px):
    stocks = px.drop(columns=[INDEX])
    ma200 = stocks.rolling(200).mean()
    valid = ma200.notna()
    share = ((stocks > ma200) & valid).sum(axis=1) / valid.sum(axis=1).replace(0, np.nan) * 100
    return share.dropna()


def charts(px, m, br, sectors):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    idx = px[INDEX].dropna()
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.plot(idx.index, idx, color="#1e1b4b", lw=1.6, label="Nifty 50")
    ax.plot(idx.index, idx.rolling(50).mean(), color="#7c3aed", lw=1.2, label="50-day average")
    ax.plot(idx.index, idx.rolling(200).mean(), color="#f59e0b", lw=1.2, label="200-day average")
    ax.set_title("Nifty 50 with 50-day and 200-day moving averages", fontweight="bold")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "chart_index_trend.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 4))
    ax.fill_between(br.index, br, color="#7c3aed", alpha=0.25)
    ax.plot(br.index, br, color="#7c3aed", lw=1.4)
    for y in (30, 70):
        ax.axhline(y, color="grey", ls="--", lw=0.8)
    ax.set_ylim(0, 100)
    ax.set_title("Market breadth: % of Nifty 50 stocks above their 200-day average", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "chart_breadth.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    s = sectors.sort_values()
    ax.barh(s.index, s, color=["#c62828" if v < 0 else "#2e7d32" for v in s])
    for i, v in enumerate(s):
        ax.text(v, i, f" {v:+.1f}%", va="center", ha="left" if v >= 0 else "right", fontsize=9)
    ax.axvline(0, color="black", lw=0.6)
    ax.set_title("1-year return by sector (equal weight)", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "chart_sectors.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
    top, bot = m.head(10).iloc[::-1], m.dropna(subset=["1Y %"]).tail(10)
    ax[0].barh(top["symbol"], top["1Y %"], color="#2e7d32"); ax[0].set_title("Top 10, 1-year return %")
    ax[1].barh(bot["symbol"], bot["1Y %"], color="#c62828"); ax[1].set_title("Bottom 10, 1-year return %")
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "chart_leaders_laggards.png", dpi=150); plt.close(fig)


def main():
    px, missing = download()
    m = stock_metrics(px)
    br = breadth(px)
    sectors = m.groupby("sector")["1Y %"].mean().round(2)
    idx = px[INDEX].dropna()
    ma50, ma200 = idx.rolling(50).mean().iloc[-1], idx.rolling(200).mean().iloc[-1]
    summary = {
        "as_of": str(px.index[-1].date()), "stocks_analysed": int(len(m)), "symbols_not_found": missing,
        "nifty_level": round(float(idx.iloc[-1]), 1),
        "nifty_returns_%": {k: round(float(ret(idx, d)), 2) for k, d in [("1M", 21), ("3M", 63), ("6M", 126), ("1Y", 252)]},
        "nifty_vs_200dma_%": round(float((idx.iloc[-1] / ma200 - 1) * 100), 2),
        "nifty_trend": "uptrend" if ma50 > ma200 else "downtrend",
        "breadth_above_200dma_%": round(float(br.iloc[-1]), 1),
        "breadth_1y_range_%": [round(float(br.iloc[-252:].min()), 1), round(float(br.iloc[-252:].max()), 1)],
        "stocks_in_uptrend": int((m["trend"].str.startswith("Up")).sum()),
        "golden_crosses_last_3m": m.loc[m["recent cross"] == "Golden cross", "symbol"].tolist(),
        "death_crosses_last_3m": m.loc[m["recent cross"] == "Death cross", "symbol"].tolist(),
        "overbought_rsi_70": m.loc[m["RSI 14"] > 70, "symbol"].tolist(),
        "oversold_rsi_30": m.loc[m["RSI 14"] < 30, "symbol"].tolist(),
        "best_1y": m.head(3)[["symbol", "1Y %"]].values.tolist(),
        "worst_1y": m.dropna(subset=["1Y %"]).tail(3)[["symbol", "1Y %"]].values.tolist(),
        "sector_1y_%": sectors.sort_values(ascending=False).to_dict(),
        "share_beating_index_1y_%": round(float((m["1Y %"] > ret(idx, 252)).mean() * 100), 1),
    }
    m.to_csv(OUT / "stock_metrics.csv", index=False)
    br.rename("pct_above_200dma").to_csv(OUT / "breadth.csv")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    charts(px, m, br, sectors)
    cols = ["symbol", "sector", "price", "1M %", "1Y %", "vs 200DMA %", "RSI 14", "trend", "recent cross"]
    md = [f"# Nifty 50 Market Trend Report — {summary['as_of']}", "",
          f"Nifty 50 at {summary['nifty_level']:,}: {summary['nifty_trend']}, {summary['nifty_vs_200dma_%']:+.1f}% vs its 200-day average. "
          f"{summary['breadth_above_200dma_%']}% of stocks trade above their 200-day average; "
          f"{summary['stocks_in_uptrend']} of {summary['stocks_analysed']} are in an uptrend.", "",
          "![Index](chart_index_trend.png)", "", "![Breadth](chart_breadth.png)", "",
          "## All stocks (sorted by 1-year return)", "", m[cols].to_markdown(index=False), "",
          "![Sectors](chart_sectors.png)", "", "![Leaders](chart_leaders_laggards.png)", "",
          "_Data: Yahoo Finance via yfinance. For learning purposes only, not investment advice._"]
    (OUT / "REPORT.md").write_text("\n".join(md))
    print(json.dumps(summary, indent=2, default=float))


if __name__ == "__main__":
    main()
