"""
India Market Data Dashboard
---------------------------
Pulls free market data for Indian indices, ETFs and key macro assets,
then builds a one-page dashboard: returns, volatility, drawdowns and
correlations, with charts and an auto-written report (REPORT.md).

Run:  python dashboard.py
Data: Yahoo Finance (via the yfinance library), daily closing prices.
"""

from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # draw charts to files, no screen needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)

# ------------------------------------------------------------------
# 1. The assets we track: Yahoo Finance ticker -> (display name, group)
# ------------------------------------------------------------------
ASSETS = {
    "^NSEI":         ("Nifty 50",          "Equity Index"),
    "^BSESN":        ("Sensex",            "Equity Index"),
    "^NSEBANK":      ("Nifty Bank",        "Equity Index"),
    "^CNXIT":        ("Nifty IT",          "Equity Index"),
    "NIFTYBEES.NS":  ("Nifty BeES ETF",    "ETF"),
    "GOLDBEES.NS":   ("Gold BeES ETF",     "ETF"),
    "INR=X":         ("USD / INR",         "Currency"),
    "GC=F":          ("Gold (USD/oz)",     "Commodity"),
    "BZ=F":          ("Brent Crude (USD)", "Commodity"),
    "BTC-USD":       ("Bitcoin (USD)",     "Crypto"),
}

TRADING_DAYS = 252  # used to annualise volatility


def download_prices(tickers, period="2y"):
    """Download daily closing prices for all tickers into one table."""
    raw = yf.download(list(tickers), period=period, auto_adjust=True,
                      progress=False, group_by="column")
    prices = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    prices = prices.dropna(how="all")
    # Bitcoin trades on weekends; other markets don't. Forward-fill so every
    # asset has a value on every date, then drop rows before data starts.
    prices = prices.ffill().dropna(how="all")
    missing = [t for t in tickers if t not in prices.columns or prices[t].isna().all()]
    if missing:
        print("Warning: no data for", missing)
    return prices.drop(columns=[m for m in missing if m in prices.columns])


def period_return(series, days):
    """% change over the last `days` calendar days."""
    end = series.index[-1]
    past = series[series.index <= end - pd.Timedelta(days=days)]
    if past.empty:
        return np.nan
    return (series.iloc[-1] / past.iloc[-1] - 1) * 100


def max_drawdown(series):
    """Largest fall from a previous peak, in %."""
    running_peak = series.cummax()
    drawdown = series / running_peak - 1
    return drawdown.min() * 100


def build_summary(prices):
    """One row per asset with price, returns, volatility and drawdown."""
    last_year = prices[prices.index >= prices.index[-1] - pd.Timedelta(days=365)]
    rows = []
    for ticker in prices.columns:
        s = prices[ticker].dropna()
        s1y = last_year[ticker].dropna()
        daily = s1y.pct_change().dropna()
        name, group = ASSETS[ticker]
        rows.append({
            "Asset": name,
            "Group": group,
            "Last Price": round(s.iloc[-1], 2),
            "1M %": round(period_return(s, 30), 2),
            "3M %": round(period_return(s, 91), 2),
            "6M %": round(period_return(s, 182), 2),
            "1Y %": round(period_return(s, 365), 2),
            "Volatility 1Y %": round(daily.std() * np.sqrt(TRADING_DAYS) * 100, 2),
            "Max Drawdown 1Y %": round(max_drawdown(s1y), 2),
        })
    return pd.DataFrame(rows)


# ------------------------------------------------------------------
# 2. Charts
# ------------------------------------------------------------------
PURPLE = ["#7c3aed", "#2563eb", "#0d9488", "#db2777", "#f59e0b",
          "#ca8a04", "#64748b", "#ea580c", "#111827", "#16a34a"]


def chart_rebased(prices):
    """Growth of 100 over the last year for every asset."""
    last_year = prices[prices.index >= prices.index[-1] - pd.Timedelta(days=365)]
    rebased = last_year / last_year.iloc[0] * 100
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for i, t in enumerate(rebased.columns):
        ax.plot(rebased.index, rebased[t], label=ASSETS[t][0], color=PURPLE[i % len(PURPLE)], lw=1.6)
    ax.axhline(100, color="grey", lw=0.8, ls="--")
    ax.set_title("Growth of 100 over the last 12 months", fontsize=13, weight="bold")
    ax.set_ylabel("Value (start = 100)")
    ax.legend(ncol=2, fontsize=8, frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "chart_growth_of_100.png", dpi=150)
    plt.close(fig)


def chart_returns(summary):
    """Horizontal bar chart of 1-year returns."""
    s = summary.sort_values("1Y %")
    colors = ["#16a34a" if v >= 0 else "#dc2626" for v in s["1Y %"]]
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(s["Asset"], s["1Y %"], color=colors)
    for y, v in enumerate(s["1Y %"]):
        ax.text(v, y, f" {v:.1f}%", va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.axvline(0, color="black", lw=0.8)
    ax.set_title("1-year return by asset", fontsize=13, weight="bold")
    ax.set_xlabel("Return (%)")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "chart_1y_returns.png", dpi=150)
    plt.close(fig)


def chart_correlation(prices):
    """Heatmap of daily-return correlations over the last year."""
    last_year = prices[prices.index >= prices.index[-1] - pd.Timedelta(days=365)]
    corr = last_year.pct_change().dropna().corr()
    labels = [ASSETS[t][0] for t in corr.columns]
    fig, ax = plt.subplots(figsize=(9, 7.5))
    im = ax.imshow(corr.values, cmap="PuOr", vmin=-1, vmax=1)
    ax.set_xticks(range(len(labels)), labels, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(labels)), labels, fontsize=8)
    for i in range(len(labels)):
        for j in range(len(labels)):
            ax.text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, fraction=0.046, pad=0.04)
    ax.set_title("Correlation of daily returns (last 12 months)", fontsize=13, weight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "chart_correlation.png", dpi=150)
    plt.close(fig)
    corr.index = corr.columns = labels
    return corr


def chart_drawdown(prices):
    """How far the Nifty 50 sat below its previous peak, day by day."""
    s = prices["^NSEI"].dropna()
    dd = (s / s.cummax() - 1) * 100
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.fill_between(dd.index, dd, 0, color="#7c3aed", alpha=0.45)
    ax.set_title("Nifty 50 drawdown from previous peak (2 years)", fontsize=13, weight="bold")
    ax.set_ylabel("Below peak (%)")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / "chart_nifty_drawdown.png", dpi=150)
    plt.close(fig)


# ------------------------------------------------------------------
# 3. Auto-written report
# ------------------------------------------------------------------
def write_report(summary, corr, prices):
    as_of = prices.index[-1].strftime("%d %b %Y")
    best = summary.loc[summary["1Y %"].idxmax()]
    worst = summary.loc[summary["1Y %"].idxmin()]
    calm = summary.loc[summary["Volatility 1Y %"].idxmin()]
    wild = summary.loc[summary["Volatility 1Y %"].idxmax()]

    pairs = corr.where(~np.eye(len(corr), dtype=bool)).stack()
    pairs = pairs[[a < b for a, b in pairs.index]]
    lowest_pair = pairs.idxmin()

    lines = [
        "# Market Dashboard Report",
        "",
        f"Data as of **{as_of}** (daily closing prices, Yahoo Finance). "
        f"Generated {datetime.now():%d %b %Y}.",
        "",
        "## Key Observations",
        "",
        f"- **Best 1-year performer:** {best['Asset']} at {best['1Y %']:+.1f}%.",
        f"- **Weakest 1-year performer:** {worst['Asset']} at {worst['1Y %']:+.1f}%.",
        f"- **Lowest volatility:** {calm['Asset']} ({calm['Volatility 1Y %']:.1f}% annualised); "
        f"**highest:** {wild['Asset']} ({wild['Volatility 1Y %']:.1f}%).",
        f"- **Weakest link between two assets:** {lowest_pair[0]} and {lowest_pair[1]} "
        f"(correlation {pairs.min():.2f}), the strongest diversification pair in the set.",
        "",
        "## Summary Table",
        "",
        summary.to_markdown(index=False),
        "",
        "## Charts",
        "",
        "![Growth of 100](chart_growth_of_100.png)",
        "",
        "![1-year returns](chart_1y_returns.png)",
        "",
        "![Correlation](chart_correlation.png)",
        "",
        "![Nifty drawdown](chart_nifty_drawdown.png)",
        "",
        "_For learning and portfolio purposes only. Not investment advice._",
    ]
    (OUT / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    print("Downloading prices...")
    prices = download_prices(ASSETS.keys())
    print(f"Got {len(prices)} days for {prices.shape[1]} assets.")

    summary = build_summary(prices)
    summary.to_csv(OUT / "market_summary.csv", index=False)
    print(summary.to_string(index=False))

    chart_rebased(prices)
    chart_returns(summary)
    corr = chart_correlation(prices)
    corr.round(3).to_csv(OUT / "correlation_matrix.csv")
    chart_drawdown(prices)
    write_report(summary, corr, prices)
    print("Done. See outputs/REPORT.md")


if __name__ == "__main__":
    main()
