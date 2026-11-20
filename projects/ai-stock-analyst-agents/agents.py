"""
Stock Analyst Agents
--------------------
A team of four rule-based "analyst agents" reviews each stock from a
different angle, explains its reasoning, and a portfolio manager combines
their scores into one overall view.

    Value agent      -> is the stock cheap or expensive versus its peers?
    Quality agent    -> is the business profitable with a sound balance sheet?
    Momentum agent   -> is the price trend working for or against it?
    Risk agent       -> how volatile is it and how deep were its falls?

Every agent returns a score from -1 (negative) to +1 (positive) and a list
of plain-English reasons, so each decision can be traced and explained.
No machine learning or LLM is used: the rules are transparent on purpose.

Run:  python agents.py
Data: Yahoo Finance via yfinance (Nifty 50 constituents listed below).
"""

from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf

OUT = Path("outputs")


def naive(idx):
    """Remove timezone info from a date index so dates line up."""
    return idx.tz_localize(None) if idx.tz is not None else idx

OUT.mkdir(exist_ok=True)

UNIVERSE = ["RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "ITC",
            "LT", "HINDUNILVR", "SBIN", "BHARTIARTL", "MARUTI", "SUNPHARMA"]
BENCHMARK = "^NSEI"   # Nifty 50
TRADING_DAYS = 252

# How much each agent counts in the final view (must add up to 1)
WEIGHTS = {"Value": 0.30, "Quality": 0.30, "Momentum": 0.20, "Risk": 0.20}


# ------------------------------------------------------------------
# Data collection
# ------------------------------------------------------------------
def load_stock(symbol, bench_returns):
    """Collect the facts every agent needs for one stock."""
    t = yf.Ticker(f"{symbol}.NS")
    info = t.info or {}
    close = t.history(period="1y", auto_adjust=True)["Close"].dropna()
    close.index = naive(close.index)
    if len(close) < 200:
        raise ValueError("not enough price history")

    daily = close.pct_change().dropna()
    joined = pd.concat([daily, bench_returns], axis=1, join="inner").dropna()
    beta = joined.cov().iloc[0, 1] / joined.iloc[:, 1].var()

    def get(key, scale=1.0):
        v = info.get(key)
        return float(v) * scale if v is not None and not pd.isna(v) else None

    return {
        "Symbol": symbol,
        "Company": info.get("shortName") or symbol,
        "Sector": info.get("sector", "n/a"),
        "P/E": get("trailingPE"),
        "P/B": get("priceToBook"),
        "ROE %": get("returnOnEquity", 100),
        "Net Margin %": get("profitMargins", 100),
        "Debt/Equity": get("debtToEquity", 0.01),      # Yahoo reports D/E as %
        "Price": close.iloc[-1],
        "50 DMA": close.rolling(50).mean().iloc[-1],
        "200 DMA": close.rolling(200).mean().iloc[-1],
        "6M Return %": (close.iloc[-1] / close.iloc[-126] - 1) * 100,
        "Volatility %": daily.std() * np.sqrt(TRADING_DAYS) * 100,
        "Max Drawdown %": (close / close.cummax() - 1).min() * 100,
        "Beta": beta,
    }


# ------------------------------------------------------------------
# The agents
# ------------------------------------------------------------------
class Agent:
    name = "Agent"

    def analyse(self, s, peers):
        """Return (score between -1 and +1, list of reasons)."""
        raise NotImplementedError

    @staticmethod
    def combine(points):
        points = [p for p in points if p is not None]
        return float(np.clip(np.mean(points), -1, 1)) if points else 0.0


class ValueAgent(Agent):
    """Compares P/E and P/B with the median of the peer group."""
    name = "Value"

    def analyse(self, s, peers):
        points, reasons = [], []
        for metric in ["P/E", "P/B"]:
            v, med = s[metric], peers[metric].median()
            if v is None or pd.isna(med) or v <= 0:
                reasons.append(f"{metric} not available")
                continue
            ratio = v / med
            if ratio < 0.8:
                points.append(1); reasons.append(f"{metric} {v:.1f} is {(1-ratio)*100:.0f}% below peer median {med:.1f}")
            elif ratio > 1.2:
                points.append(-1); reasons.append(f"{metric} {v:.1f} is {(ratio-1)*100:.0f}% above peer median {med:.1f}")
            else:
                points.append(0); reasons.append(f"{metric} {v:.1f} is close to peer median {med:.1f}")
        return self.combine(points), reasons


class QualityAgent(Agent):
    """Checks return on equity, profit margin and leverage."""
    name = "Quality"

    def analyse(self, s, peers):
        points, reasons = [], []
        roe = s["ROE %"]
        if roe is not None:
            p = 1 if roe > 15 else (-1 if roe < 8 else 0)
            points.append(p); reasons.append(f"ROE {roe:.1f}% ({'strong' if p > 0 else 'weak' if p < 0 else 'moderate'})")
        m = s["Net Margin %"]
        if m is not None:
            p = 1 if m > 15 else (-1 if m < 5 else 0)
            points.append(p); reasons.append(f"Net margin {m:.1f}% ({'high' if p > 0 else 'thin' if p < 0 else 'average'})")
        de = s["Debt/Equity"]
        if s["Sector"] == "Financial Services":
            reasons.append("Debt/Equity skipped: borrowing is the raw material of a bank or lender")
        elif de is not None:
            p = 1 if de < 0.5 else (-1 if de > 1.5 else 0)
            points.append(p); reasons.append(f"Debt/Equity {de:.2f}x ({'low' if p > 0 else 'high' if p < 0 else 'manageable'})")
        return self.combine(points), reasons


class MomentumAgent(Agent):
    """Looks at moving averages and performance versus the Nifty."""
    name = "Momentum"

    def __init__(self, bench_6m):
        self.bench_6m = bench_6m

    def analyse(self, s, peers):
        points, reasons = [], []
        above = s["Price"] > s["200 DMA"]
        points.append(1 if above else -1)
        reasons.append(f"Price {'above' if above else 'below'} its 200-day average")
        golden = s["50 DMA"] > s["200 DMA"]
        points.append(1 if golden else -1)
        reasons.append(f"50-day average {'above' if golden else 'below'} 200-day average")
        beat = s["6M Return %"] > self.bench_6m
        points.append(1 if beat else -1)
        reasons.append(f"6M return {s['6M Return %']:+.1f}% vs Nifty {self.bench_6m:+.1f}%")
        return self.combine(points), reasons


class RiskAgent(Agent):
    """Rewards low volatility, shallow drawdowns and low beta."""
    name = "Risk"

    def analyse(self, s, peers):
        points, reasons = [], []
        v = s["Volatility %"]
        points.append(1 if v < 22 else (-1 if v > 32 else 0))
        reasons.append(f"Annual volatility {v:.1f}%")
        dd = s["Max Drawdown %"]
        points.append(1 if dd > -15 else (-1 if dd < -30 else 0))
        reasons.append(f"Worst fall from peak {dd:.1f}%")
        b = s["Beta"]
        points.append(1 if b < 0.8 else (-1 if b > 1.2 else 0))
        reasons.append(f"Beta vs Nifty {b:.2f}")
        return self.combine(points), reasons


class PortfolioManager:
    """Weights the four agent scores into one overall view."""

    def decide(self, scores):
        total = sum(scores[k] * w for k, w in WEIGHTS.items())
        if total >= 0.25:
            view = "Positive"
        elif total <= -0.25:
            view = "Negative"
        else:
            view = "Neutral"
        return round(total, 2), view


# ------------------------------------------------------------------
# Run the team over the universe
# ------------------------------------------------------------------
def main():
    bench = yf.Ticker(BENCHMARK).history(period="1y", auto_adjust=True)["Close"].dropna()
    bench.index = naive(bench.index)
    bench_returns = bench.pct_change().dropna().rename("bench")
    bench_6m = (bench.iloc[-1] / bench.iloc[-126] - 1) * 100

    stocks = []
    for sym in UNIVERSE:
        try:
            stocks.append(load_stock(sym, bench_returns))
            print(f"Loaded {sym}")
        except Exception as e:
            print(f"Skipping {sym}: {e}")
    peers = pd.DataFrame(stocks)

    agents = [ValueAgent(), QualityAgent(), MomentumAgent(bench_6m), RiskAgent()]
    pm = PortfolioManager()

    rows, notes = [], []
    for s in stocks:
        scores, block = {}, [f"### {s['Company']} ({s['Symbol']})", ""]
        for a in agents:
            score, reasons = a.analyse(s, peers)
            scores[a.name] = round(score, 2)
            block.append(f"- **{a.name} agent ({score:+.2f}):** " + "; ".join(reasons))
        total, view = pm.decide(scores)
        block += [f"- **Portfolio manager:** weighted score {total:+.2f} → **{view}**", ""]
        notes += block
        rows.append({"Symbol": s["Symbol"], "Company": s["Company"], **scores,
                     "Overall": total, "View": view})

    card = pd.DataFrame(rows).sort_values("Overall", ascending=False)
    card.to_csv(OUT / "scorecard.csv", index=False)
    peers.round(2).to_csv(OUT / "stock_data.csv", index=False)
    print(card.to_string(index=False))

    # Heatmap of agent scores
    mat = card.set_index("Symbol")[list(WEIGHTS) + ["Overall"]]
    fig, ax = plt.subplots(figsize=(8, 0.5 * len(mat) + 1.5))
    im = ax.imshow(mat.values, cmap="PuOr", vmin=-1, vmax=1, aspect="auto")
    ax.set_xticks(range(mat.shape[1]), mat.columns)
    ax.set_yticks(range(len(mat)), mat.index)
    for i in range(mat.shape[0]):
        for j in range(mat.shape[1]):
            ax.text(j, i, f"{mat.values[i, j]:+.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, fraction=0.04, pad=0.03)
    ax.set_title("Agent scores by stock (-1 negative, +1 positive)", fontsize=12, weight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "agent_scores_heatmap.png", dpi=150)
    plt.close(fig)

    counts = card["View"].value_counts()
    md = ["# Analyst Agents Scorecard", "",
          f"Generated {datetime.now():%d %b %Y}. Universe: {len(card)} Nifty 50 stocks. "
          f"Weights: " + ", ".join(f"{k} {int(v*100)}%" for k, v in WEIGHTS.items()) + ".", "",
          f"**Positive:** {counts.get('Positive', 0)}  |  **Neutral:** {counts.get('Neutral', 0)}  |  "
          f"**Negative:** {counts.get('Negative', 0)}", "",
          card.to_markdown(index=False), "",
          "![Heatmap](agent_scores_heatmap.png)", "",
          "## Agent Reasoning", ""] + notes + [
          "_Rule-based screening for learning purposes only. Not investment advice._"]
    (OUT / "SCORECARD.md").write_text("\n".join(md), encoding="utf-8")
    print("Done. See outputs/SCORECARD.md")


if __name__ == "__main__":
    main()
