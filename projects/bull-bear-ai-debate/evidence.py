"""
Evidence pack builder for the bull vs bear debate.

For each ticker it collects, from primary sources only:
  * Latest 10-K from SEC EDGAR: Item 1A (Risk Factors) and Item 7 (MD&A) text
  * XBRL company facts: revenue, operating income, net income, cash from operations (last 4 fiscal years)
  * Market data from yfinance: 1-year return vs SPY, volatility, max drawdown, valuation multiples

Every evidence line gets an ID ([R1] risk, [M1] MD&A, [F1] financials, [P1] price) so the
debating agents must cite what they use, and the judge can check it.
"""
import json
import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)
HEADERS = {"User-Agent": os.environ.get("SEC_USER_AGENT") or "Bull Bear Debate Research Project research@example.org"}
TICKERS = os.environ.get("TICKERS", "NVDA,TSLA,JPM").split(",")

RISK_WORDS = ["could", "may", "adversely", "decline", "competition", "regulation", "depend", "loss", "litigation",
              "supply", "customers", "tariff", "export", "credit", "cyber", "interest rate", "concentration"]
MDA_WORDS = ["increase", "decrease", "grew", "growth", "declined", "primarily", "driven", "margin", "compared",
             "billion", "million", "%", "percent"]


def get(url, **kw):
    for attempt in range(3):
        r = requests.get(url, headers=HEADERS, timeout=60, **kw)
        if r.status_code == 200:
            return r
        time.sleep(2 + attempt * 3)
    r.raise_for_status()


def cik_for(ticker):
    data = get("https://www.sec.gov/files/company_tickers.json").json()
    for row in data.values():
        if row["ticker"].upper() == ticker.upper():
            return int(row["cik_str"]), row["title"]
    raise ValueError(f"{ticker} not found in SEC ticker list")


def latest_10k(cik):
    sub = get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").json()
    rec = pd.DataFrame(sub["filings"]["recent"])
    k = rec[rec["form"] == "10-K"].iloc[0]
    acc = k["accessionNumber"].replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{k['primaryDocument']}"
    return url, k["filingDate"], k["reportDate"]


def filing_text(url):
    soup = BeautifulSoup(get(url).content, "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    text = soup.get_text(" ")
    text = re.sub(r"\xa0|&#160;", " ", text)
    return re.sub(r"\s+", " ", text)


def section(text, start_pat, end_pat):
    """Longest span between a start heading and the next end heading (skips the table of contents)."""
    best = ""
    for m in re.finditer(start_pat, text, re.I):
        e = re.search(end_pat, text[m.end():], re.I)
        chunk = text[m.end(): m.end() + e.start()] if e else text[m.end(): m.end() + 200_000]
        if len(chunk) > len(best):
            best = chunk
    return best.strip()


def pick_sentences(text, words, n, prefix):
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if 15 <= len(s.split()) <= 60]
    scored = []
    seen = set()
    for i, s in enumerate(sents):
        key = s[:60].lower()
        if key in seen:
            continue
        seen.add(key)
        low = s.lower()
        score = sum(w in low for w in words) + (1.5 if re.search(r"\d", s) else 0)
        scored.append((score, i, s))
    top = sorted(scored, key=lambda x: (-x[0], x[1]))[:n]
    top = sorted(top, key=lambda x: x[1])  # keep filing order
    return [f"[{prefix}{j + 1}] {s}" for j, (_, _, s) in enumerate(top)]


def xbrl_financials(cik):
    facts = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json").json()["facts"].get("us-gaap", {})
    concepts = {
        "Revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
        "Operating income": ["OperatingIncomeLoss"],
        "Net income": ["NetIncomeLoss"],
        "Cash from operations": ["NetCashProvidedByUsedInOperatingActivities"],
    }
    table = {}
    for label, names in concepts.items():
        best = None
        for n in names:
            units = facts.get(n, {}).get("units", {}).get("USD")
            if not units:
                continue
            df = pd.DataFrame(units)
            df = df[(df["form"] == "10-K") & (df["fp"] == "FY") & df["frame"].fillna("").str.match(r"^CY\d{4}$")]
            if df.empty:
                continue
            s = df.drop_duplicates("frame", keep="last").set_index("frame")["val"].sort_index().tail(4)
            if best is None or s.index.max() > best.index.max():
                best = s
        if best is not None:
            table[label] = best / 1e9
    return pd.DataFrame(table).round(2)


def market_metrics(ticker):
    import yfinance as yf
    px = yf.download([ticker, "SPY"], period="1y", auto_adjust=True, progress=False)["Close"].dropna()
    r = px.pct_change().dropna()
    stock = px[ticker]
    m = {
        "1y return %": round((stock.iloc[-1] / stock.iloc[0] - 1) * 100, 1),
        "SPY 1y return %": round((px["SPY"].iloc[-1] / px["SPY"].iloc[0] - 1) * 100, 1),
        "annualised volatility %": round(r[ticker].std() * np.sqrt(252) * 100, 1),
        "max drawdown %": round(((stock / stock.cummax()) - 1).min() * 100, 1),
        "beta vs SPY": round(r[ticker].cov(r["SPY"]) / r["SPY"].var(), 2),
        "last price": round(float(stock.iloc[-1]), 2), "as of": str(px.index[-1].date()),
    }
    try:
        info = yf.Ticker(ticker).info
        for k, lab in [("trailingPE", "trailing P/E"), ("forwardPE", "forward P/E"), ("priceToSalesTrailing12Months", "P/S"),
                       ("marketCap", "market cap $bn")]:
            v = info.get(k)
            if v:
                m[lab] = round(v / 1e9, 1) if k == "marketCap" else round(v, 1)
    except Exception:
        pass
    return m


def build(ticker):
    cik, name = cik_for(ticker)
    url, filed, period = latest_10k(cik)
    text = filing_text(url)
    risk = section(text, r"item\s*1a\.?\s*[-–—:]?\s*risk\s+factors", r"item\s*1b\.?|item\s*1c\.?|item\s*2\.?\s*[-–—:]?\s*properties")
    mda = section(text, r"item\s*7\.?\s*[-–—:]?\s*management['’]?s\s+discussion", r"item\s*7a\.?|item\s*8\.?\s*[-–—:]?\s*financial\s+statements")
    fin = xbrl_financials(cik)
    mkt = market_metrics(ticker)

    fin_lines = []
    for j, (year, row) in enumerate(fin.iterrows()):
        vals = ", ".join(f"{k} ${v:,.2f}bn" for k, v in row.dropna().items())
        fin_lines.append(f"[F{j + 1}] FY{year[2:]}: {vals}")
    pack = {
        "ticker": ticker, "company": name, "cik": cik, "10k_url": url, "10k_filed": filed, "period": period,
        "risk_section_words": len(risk.split()), "mda_section_words": len(mda.split()),
        "risk_evidence": pick_sentences(risk, RISK_WORDS, 12, "R"),
        "mda_evidence": pick_sentences(mda, MDA_WORDS, 12, "M"),
        "financials": fin_lines,
        "market": [f"[P{j + 1}] {k}: {v}" for j, (k, v) in enumerate(mkt.items())],
        "market_raw": mkt, "financials_raw": fin.reset_index().rename(columns={"index": "frame"}).to_dict(orient="records"),
    }
    (OUT / f"{ticker}_evidence.json").write_text(json.dumps(pack, indent=2))
    print(f"{ticker}: 10-K filed {filed}, risk {pack['risk_section_words']:,} words, MD&A {pack['mda_section_words']:,} words, "
          f"{len(pack['risk_evidence'])} risk + {len(pack['mda_evidence'])} MD&A lines")
    return pack


def as_prompt_text(pack):
    parts = [f"COMPANY: {pack['company']} ({pack['ticker']}), 10-K for period {pack['period']} filed {pack['10k_filed']}",
             "\nRISK FACTORS (Item 1A excerpts):", *pack["risk_evidence"],
             "\nMANAGEMENT DISCUSSION (Item 7 excerpts):", *pack["mda_evidence"],
             "\nFINANCIALS (SEC XBRL, USD billions):", *pack["financials"],
             "\nMARKET DATA (yfinance):", *pack["market"]]
    return "\n".join(parts)


def scorecard(packs):
    """One chart comparing the evidence the agents see for each ticker."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = []
    for p in packs:
        fin = pd.DataFrame(p["financials_raw"]).set_index("frame")
        rev = fin.get("Revenue", pd.Series(dtype=float)).dropna()
        ni = fin.get("Net income", pd.Series(dtype=float)).dropna()
        rows.append({"ticker": p["ticker"],
                     "Revenue growth, latest FY %": (rev.iloc[-1] / rev.iloc[-2] - 1) * 100 if len(rev) > 1 else np.nan,
                     "Net margin, latest FY %": ni.iloc[-1] / rev.iloc[-1] * 100 if len(rev) and len(ni) else np.nan,
                     "1y return vs SPY, pts": p["market_raw"]["1y return %"] - p["market_raw"]["SPY 1y return %"],
                     "Volatility %": p["market_raw"]["annualised volatility %"],
                     "Risk factors (k words)": p["risk_section_words"] / 1000})
    df = pd.DataFrame(rows).set_index("ticker").round(1)
    df.to_csv(OUT / "evidence_scorecard.csv")
    fig, axes = plt.subplots(1, len(df.columns), figsize=(16, 3.8))
    for ax, col in zip(axes, df.columns):
        vals = df[col]
        ax.bar(vals.index, vals, color=["#2e7d32" if v >= 0 else "#c62828" for v in vals.fillna(0)])
        ax.set_title(col, fontsize=10)
        ax.axhline(0, color="black", lw=0.6)
        ax.spines[["top", "right"]].set_visible(False)
        for i, v in enumerate(vals):
            if pd.notna(v):
                ax.text(i, v, f"{v:,.1f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
    fig.suptitle("Evidence scorecard given to the bull and bear agents (SEC 10-K, XBRL, yfinance)", fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "evidence_scorecard.png", dpi=150)
    plt.close(fig)
    print(df.to_string())


if __name__ == "__main__":
    packs = []
    for t in TICKERS:
        try:
            packs.append(build(t.strip()))
        except Exception as e:
            print(f"{t}: failed ({e})")
    if packs:
        scorecard(packs)
