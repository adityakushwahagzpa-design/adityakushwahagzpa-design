"""
Financial News Sentiment Analysis
---------------------------------
Collects recent news headlines for large Indian companies, scores how
positive or negative each headline is, and checks whether days with more
positive news coincided with better share-price moves.

Steps
  1. Fetch headlines from Google News RSS for each company.
  2. Score each headline with VADER, a sentiment model, after adding a
     finance word list (e.g. "surges", "downgrade", "penalty") so that
     market language is read correctly.
  3. Combine daily average sentiment with daily share-price returns.
  4. Report sentiment by company and the link between news and returns.

Run:  python sentiment.py
"""

import re
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import feedparser
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

OUT = Path("outputs")


def naive(idx):
    """Remove timezone info from a date index so dates line up."""
    return idx.tz_localize(None) if idx.tz is not None else idx

OUT.mkdir(exist_ok=True)

# NSE symbol -> search name used for news
COMPANIES = {
    "RELIANCE": "Reliance Industries",
    "TCS": "TCS Tata Consultancy",
    "INFY": "Infosys",
    "HDFCBANK": "HDFC Bank",
    "ICICIBANK": "ICICI Bank",
    "ITC": "ITC Ltd",
    "SBIN": "State Bank of India SBI",
    "BHARTIARTL": "Bharti Airtel",
    "TMPV": "Tata Motors Passenger Vehicles",
    "ADANIENT": "Adani Enterprises",
}

# Finance words VADER does not know well, with a score from -4 to +4
FINANCE_LEXICON = {
    "surge": 2.5, "surges": 2.5, "soar": 2.5, "soars": 2.5, "jump": 2.0, "jumps": 2.0,
    "rally": 2.0, "rallies": 2.0, "gain": 1.5, "gains": 1.5, "rise": 1.2, "rises": 1.2,
    "climbs": 1.5, "beat": 1.5, "beats": 1.5, "upgrade": 2.0, "upgrades": 2.0,
    "outperform": 1.8, "bullish": 2.0, "record": 1.2, "profit": 1.0, "dividend": 1.0,
    "buyback": 1.5, "expansion": 1.0, "order": 0.8, "wins": 1.5, "approval": 1.2,
    "plunge": -2.8, "plunges": -2.8, "slump": -2.2, "slumps": -2.2, "crash": -3.0,
    "tumble": -2.2, "tumbles": -2.2, "fall": -1.5, "falls": -1.5, "drop": -1.5,
    "drops": -1.5, "decline": -1.5, "declines": -1.5, "slips": -1.2, "miss": -1.5,
    "misses": -1.5, "downgrade": -2.0, "downgrades": -2.0, "underperform": -1.8,
    "bearish": -2.0, "loss": -1.8, "losses": -1.8, "probe": -1.8, "penalty": -2.0,
    "fine": -1.0, "fraud": -3.0, "selloff": -2.0, "sell-off": -2.0, "weak": -1.5,
    "lawsuit": -2.0, "default": -2.5, "layoffs": -2.0, "resigns": -1.2, "raid": -2.0,
}

analyser = SentimentIntensityAnalyzer()
analyser.lexicon.update(FINANCE_LEXICON)


def fetch_headlines(symbol, query):
    """Return recent headlines for one company from Google News RSS."""
    url = ("https://news.google.com/rss/search?q="
           f"{quote_plus(query + ' share')}&hl=en-IN&gl=IN&ceid=IN:en")
    feed = feedparser.parse(url)
    rows = []
    for e in feed.entries:
        title = re.sub(r"\s+-\s+[^-]+$", "", e.get("title", "")).strip()  # drop " - Source"
        title = title.replace("|", "/")  # "|" would break the markdown tables
        published = pd.to_datetime(e.get("published"), errors="coerce", utc=True)
        if title and pd.notna(published):
            rows.append({"Symbol": symbol, "Date": published.tz_convert("Asia/Kolkata").date(),
                         "Headline": title,
                         "Source": e.get("source", {}).get("title", "")})
    return rows


def label(score):
    if score > 0.05:
        return "Positive"
    if score < -0.05:
        return "Negative"
    return "Neutral"


def main():
    # 1. Headlines
    rows = []
    for sym, q in COMPANIES.items():
        got = fetch_headlines(sym, q)
        print(f"{sym}: {len(got)} headlines")
        rows += got
    news = pd.DataFrame(rows)
    # Same story is often syndicated with small wording changes: compare the
    # first 50 lower-case characters to drop near-duplicates.
    news["key"] = news["Headline"].str.lower().str[:50]
    news = news.drop_duplicates(["Symbol", "key"]).drop(columns="key")
    news["Date"] = pd.to_datetime(news["Date"])
    news = news[news["Date"] >= news["Date"].max() - pd.Timedelta(days=90)]

    # 2. Sentiment score per headline
    news["Sentiment"] = news["Headline"].apply(lambda h: analyser.polarity_scores(h)["compound"])
    news["Label"] = news["Sentiment"].apply(label)
    news.sort_values(["Symbol", "Date"]).to_csv(OUT / "headlines_scored.csv", index=False)

    # 3. Company-level summary
    by_co = news.groupby("Symbol").agg(
        Headlines=("Headline", "count"),
        Avg_Sentiment=("Sentiment", "mean"),
        Positive_pct=("Label", lambda x: (x == "Positive").mean() * 100),
        Negative_pct=("Label", lambda x: (x == "Negative").mean() * 100),
    ).round(3).sort_values("Avg_Sentiment", ascending=False)

    # 4. Daily returns for the same window
    start = news["Date"].min() - pd.Timedelta(days=5)
    tickers = [f"{s}.NS" for s in COMPANIES]
    px = yf.download(tickers, start=start.strftime("%Y-%m-%d"), auto_adjust=True,
                     progress=False)["Close"]
    rets = px.pct_change().mul(100)
    rets.columns = [c.replace(".NS", "") for c in rets.columns]
    rets.index = naive(pd.to_datetime(rets.index)).normalize()
    rets_long = rets.stack().rename("Return %").reset_index()
    rets_long.columns = ["Date", "Symbol", "Return %"]

    # Next trading day's return, to test whether news "leads" price
    rets_next = rets.shift(-1).stack().rename("Next Day Return %").reset_index()
    rets_next.columns = ["Date", "Symbol", "Next Day Return %"]

    daily = news.groupby(["Symbol", "Date"])["Sentiment"].mean().reset_index()
    merged = (daily.merge(rets_long, on=["Symbol", "Date"], how="inner")
                   .merge(rets_next, on=["Symbol", "Date"], how="left"))
    merged.to_csv(OUT / "daily_sentiment_vs_returns.csv", index=False)

    same_day = merged["Sentiment"].corr(merged["Return %"])
    next_day = merged["Sentiment"].corr(merged["Next Day Return %"])
    pos_days = merged[merged["Sentiment"] > 0.05]["Return %"].mean()
    neg_days = merged[merged["Sentiment"] < -0.05]["Return %"].mean()

    # 5. Charts
    fig, ax = plt.subplots(figsize=(9, 5))
    s = by_co["Avg_Sentiment"].sort_values()
    ax.barh(s.index, s.values, color=["#16a34a" if v >= 0 else "#dc2626" for v in s.values])
    ax.axvline(0, color="black", lw=0.8)
    ax.set_title("Average headline sentiment by company", fontsize=13, weight="bold")
    ax.set_xlabel("VADER compound score (-1 to +1)")
    ax.grid(axis="x", alpha=0.25)
    fig.tight_layout(); fig.savefig(OUT / "chart_sentiment_by_company.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.scatter(merged["Sentiment"], merged["Return %"], color="#7c3aed", alpha=0.55, s=22)
    fit = merged[["Sentiment", "Return %"]].dropna()
    if len(fit) > 2:
        m, c = np.polyfit(fit["Sentiment"], fit["Return %"], 1)
        xs = np.linspace(fit["Sentiment"].min(), fit["Sentiment"].max(), 50)
        ax.plot(xs, m * xs + c, color="#f59e0b", lw=1.5, label=f"Trend (corr {same_day:.2f})")
        ax.legend(frameon=False)
    ax.axhline(0, color="grey", lw=0.6); ax.axvline(0, color="grey", lw=0.6)
    ax.set_title("Daily news sentiment vs same-day share return", fontsize=13, weight="bold")
    ax.set_xlabel("Average headline sentiment that day"); ax.set_ylabel("Share return (%)")
    ax.grid(alpha=0.25)
    fig.tight_layout(); fig.savefig(OUT / "chart_sentiment_vs_return.png", dpi=150); plt.close(fig)

    mix = news["Label"].value_counts().reindex(["Positive", "Neutral", "Negative"]).fillna(0)

    # 6. Report
    top_pos = news.nlargest(5, "Sentiment")[["Symbol", "Date", "Headline", "Sentiment"]]
    top_neg = news.nsmallest(5, "Sentiment")[["Symbol", "Date", "Headline", "Sentiment"]]
    for t in (top_pos, top_neg):
        t["Date"] = t["Date"].dt.strftime("%d %b %Y")
    md = [
        "# News Sentiment Report", "",
        f"Generated {datetime.now():%d %b %Y}. {len(news)} headlines for {news['Symbol'].nunique()} companies, "
        f"{news['Date'].min():%d %b %Y} to {news['Date'].max():%d %b %Y}.", "",
        "## Key Results", "",
        f"- **Headline mix:** {int(mix['Positive'])} positive, {int(mix['Neutral'])} neutral, {int(mix['Negative'])} negative.",
        f"- **Most positive coverage:** {by_co.index[0]} (avg {by_co['Avg_Sentiment'].iloc[0]:+.2f}); "
        f"**most negative:** {by_co.index[-1]} (avg {by_co['Avg_Sentiment'].iloc[-1]:+.2f}).",
        f"- **Same-day link:** correlation between daily sentiment and that day's return = **{same_day:.2f}** "
        f"across {len(merged)} company-days.",
        f"- **Next-day link:** correlation with the following day's return = **{next_day:.2f}**.",
        f"- **Average return on positive-news days:** {pos_days:+.2f}%; on negative-news days: {neg_days:+.2f}%.",
        "",
        "## Sentiment by Company", "", by_co.to_markdown(), "",
        "![By company](chart_sentiment_by_company.png)", "",
        "![Sentiment vs return](chart_sentiment_vs_return.png)", "",
        "## Most Positive Headlines", "", top_pos.round(2).to_markdown(index=False), "",
        "## Most Negative Headlines", "", top_neg.round(2).to_markdown(index=False), "",
        "## Limitations", "",
        "- Google News RSS returns only recent headlines (about 100 per search), so the sample is small.",
        "- Headlines are often written after the price has moved, so a same-day link does not mean news caused the move.",
        "- VADER is a general-purpose model; the finance word list improves it but it can still misread context.",
        "",
        "_For learning purposes only. Not investment advice._",
    ]
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print(by_co.to_string())
    print(f"Same-day corr {same_day:.2f} | Next-day corr {next_day:.2f}")
    print("Done. See outputs/REPORT.md")


if __name__ == "__main__":
    main()
