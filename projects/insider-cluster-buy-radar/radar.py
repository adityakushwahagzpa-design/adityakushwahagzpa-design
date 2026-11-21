"""
Insider Cluster-Buy Radar
-------------------------
Finds companies where several executives or directors bought their own
company's stock on the open market within a short window: a "cluster buy".
One insider buying can mean anything; three or more buying together is a
stronger signal that the people who know the business think it is cheap.

Steps
  1. Download SEC's quarterly Form 4 data sets (every insider trade filed).
  2. Keep open-market purchases (transaction code "P") by officers and
     directors worth at least $25,000.
  3. Flag a cluster when 3+ different insiders buy within 14 days.
  4. Save purchases and clusters to a database (PostgreSQL if DATABASE_URL
     is set, otherwise a local SQLite file).
  5. Measure what happened next: stock return after 1 week, 1 month and
     3 months, compared with the S&P 500 (SPY).

Run:  SEC_USER_AGENT="Your Name your-contact" python radar.py
      (SEC asks every automated request to identify itself)
Data: SEC EDGAR insider transactions data sets (Forms 3, 4, 5), yfinance prices.
"""

import io
import json
import os
import zipfile
from datetime import timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import requests
import yfinance as yf
from sqlalchemy import create_engine

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)

QUARTERS = ["2025q1", "2025q2", "2025q3", "2025q4", "2026q1", "2026q2", "2026q3"]
MIN_VALUE = 25_000      # ignore token purchases
MIN_INSIDERS = 3        # distinct insiders needed for a cluster
WINDOW_DAYS = 14
HORIZONS = {"1 week": 5, "1 month": 21, "3 months": 63}  # trading days
HEADERS = {"User-Agent": os.environ.get("SEC_USER_AGENT") or "Insider Radar Research Project research@example.org"}
LOADED = []
URL = "https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"


def load_quarter(q):
    """Download one quarter and return purchases joined to issuer and insider details."""
    r = requests.get(URL.format(q=q), headers=HEADERS, timeout=120)
    if r.status_code != 200:
        print(f"{q}: not available ({r.status_code})")
        return pd.DataFrame()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    read = lambda name: pd.read_csv(z.open(name), sep="\t", dtype=str, low_memory=False)
    sub = read("SUBMISSION.tsv")[["ACCESSION_NUMBER", "FILING_DATE", "ISSUERCIK", "ISSUERNAME", "ISSUERTRADINGSYMBOL", "DOCUMENT_TYPE"]]
    own = read("REPORTINGOWNER.tsv")[["ACCESSION_NUMBER", "RPTOWNERCIK", "RPTOWNERNAME", "RPTOWNER_RELATIONSHIP", "RPTOWNER_TITLE"]]
    trn = read("NONDERIV_TRANS.tsv")[["ACCESSION_NUMBER", "TRANS_DATE", "TRANS_CODE", "TRANS_SHARES",
                                      "TRANS_PRICEPERSHARE", "TRANS_ACQUIRED_DISP_CD"]]
    trn = trn[(trn["TRANS_CODE"] == "P") & (trn["TRANS_ACQUIRED_DISP_CD"] == "A")]
    df = trn.merge(sub, on="ACCESSION_NUMBER").merge(own, on="ACCESSION_NUMBER")
    LOADED.append(q)
    print(f"{q}: {len(df):,} open-market purchase lines")
    return df


def clean(df):
    df = df[df["DOCUMENT_TYPE"].isin(["4", "4/A"])].copy()
    df["trans_date"] = pd.to_datetime(df["TRANS_DATE"], format="mixed", errors="coerce")
    df["shares"] = pd.to_numeric(df["TRANS_SHARES"], errors="coerce")
    df["price"] = pd.to_numeric(df["TRANS_PRICEPERSHARE"], errors="coerce")
    df["value"] = df["shares"] * df["price"]
    rel = df["RPTOWNER_RELATIONSHIP"].fillna("")
    df = df[rel.str.contains("Director|Officer", case=False)]  # insiders who run or oversee the company
    df = df[(df["value"] >= MIN_VALUE) & df["trans_date"].notna() & df["ISSUERTRADINGSYMBOL"].notna()]
    df["ticker"] = df["ISSUERTRADINGSYMBOL"].str.upper().str.strip()
    df = df[df["ticker"].str.fullmatch(r"[A-Z.]{1,6}") & ~df["ticker"].isin(["NONE", "NA", "N.A", "NULL"])]
    # One row per insider per day per company (a filing can split a purchase into many lines)
    out = (df.groupby(["ticker", "ISSUERNAME", "RPTOWNERCIK", "RPTOWNERNAME", "RPTOWNER_TITLE", "trans_date"], dropna=False)
             .agg(shares=("shares", "sum"), value=("value", "sum")).reset_index())
    out.columns = ["ticker", "company", "insider_cik", "insider", "title", "trans_date", "shares", "value"]
    return out.sort_values(["ticker", "trans_date"])


def find_clusters(p):
    """A cluster = 3+ distinct insiders buying the same stock within 14 days."""
    clusters = []
    for ticker, g in p.groupby("ticker"):
        g = g.sort_values("trans_date").reset_index(drop=True)
        used_until = pd.Timestamp.min
        for start in g["trans_date"]:
            if start <= used_until:
                continue
            win = g[(g["trans_date"] >= start) & (g["trans_date"] <= start + timedelta(days=WINDOW_DAYS))]
            if win["insider_cik"].nunique() >= MIN_INSIDERS:
                end = win["trans_date"].max()
                who = win["insider"].str.title() + " (" + win["title"].fillna("Director").str.title() + ")"
                clusters.append({"ticker": ticker, "company": win["company"].iloc[0], "start": start.date(), "end": end.date(),
                                 "insiders": win["insider_cik"].nunique(), "total_value": round(win["value"].sum()),
                                 "who": "; ".join(sorted(set(who)))[:300]})
                used_until = end
    return pd.DataFrame(clusters)


def add_returns(cl):
    """Return after each horizon from the first close after the cluster ends, vs SPY."""
    if cl.empty:
        return cl
    tickers = sorted(set(cl["ticker"])) + ["SPY"]
    px = yf.download(tickers, start=str(pd.to_datetime(cl["start"]).min().date()), auto_adjust=True,
                     progress=False, threads=False)["Close"]
    for name, n in HORIZONS.items():
        rets, excess = [], []
        for r in cl.itertuples():
            if r.ticker not in px.columns:
                rets.append(None); excess.append(None); continue
            s, m = px[r.ticker].dropna(), px["SPY"].dropna()
            after = s[s.index > pd.Timestamp(r.end)]
            if len(after) <= n:
                rets.append(None); excess.append(None); continue
            t0, t1 = after.index[0], after.index[n]
            ret = after.iloc[n] / after.iloc[0] - 1
            mret = m.asof(t1) / m.asof(t0) - 1
            rets.append(round(ret * 100, 2)); excess.append(round((ret - mret) * 100, 2))
        cl[f"return {name} %"] = rets
        cl[f"vs SPY {name} %"] = excess
    return cl


def main():
    raw = pd.concat([load_quarter(q) for q in QUARTERS], ignore_index=True)
    purchases = clean(raw)
    clusters = add_returns(find_clusters(purchases))
    print(f"{len(purchases):,} qualifying purchases, {len(clusters)} clusters")

    engine = create_engine(os.environ.get("DATABASE_URL", "sqlite:///radar.db"))
    purchases.to_sql("purchases", engine, if_exists="replace", index=False)
    clusters.to_sql("clusters", engine, if_exists="replace", index=False)
    top_sql = pd.read_sql("SELECT ticker, COUNT(*) AS clusters, SUM(total_value) AS total_value FROM clusters "
                          "GROUP BY ticker ORDER BY SUM(total_value) DESC LIMIT 10", engine)  # proves the DB round trip

    clusters.sort_values("end", ascending=False).to_csv(OUT / "clusters.csv", index=False)
    summary = {"quarters": LOADED, "qualifying_purchases": int(len(purchases)),
               "companies_with_purchases": int(purchases["ticker"].nunique()), "clusters": int(len(clusters)),
               "database": engine.dialect.name}
    for name in HORIZONS:
        col = f"vs SPY {name} %"
        v = clusters[col].dropna() if col in clusters else pd.Series(dtype=float)
        summary[name] = {"clusters_measured": int(len(v)), "avg_excess_return_%": round(v.mean(), 2) if len(v) else None,
                         "median_excess_return_%": round(v.median(), 2) if len(v) else None,
                         "share_beating_spy_%": round((v > 0).mean() * 100, 1) if len(v) else None}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    names = [h for h in HORIZONS if summary[h]["clusters_measured"]]
    if names:
        fig, ax = plt.subplots(figsize=(8, 4.5))
        xs = range(len(names))
        avg = [summary[h]["avg_excess_return_%"] for h in names]
        med = [summary[h]["median_excess_return_%"] for h in names]
        ax.bar([x - 0.18 for x in xs], avg, 0.36, label="Average", color="#7c3aed")
        ax.bar([x + 0.18 for x in xs], med, 0.36, label="Median", color="#c4b5fd")
        for x, a, m in zip(xs, avg, med):
            ax.text(x - 0.18, a, f"{a:+.1f}%", ha="center", va="bottom" if a >= 0 else "top", fontsize=9)
            ax.text(x + 0.18, m, f"{m:+.1f}%", ha="center", va="bottom" if m >= 0 else "top", fontsize=9)
        ax.axhline(0, color="black", lw=0.8)
        ax.set_xticks(list(xs), [f"{h}\n(n={summary[h]['clusters_measured']})" for h in names])
        ax.set_ylabel("Return vs S&P 500 (percentage points)")
        ax.set_title("Stock return after an insider cluster buy, relative to SPY", weight="bold")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(OUT / "excess_returns.png", dpi=140)

    recent = clusters.sort_values("end", ascending=False).head(15)
    md = ["# Latest Insider Cluster Buys", "",
          f"{len(clusters)} clusters found in {', '.join(LOADED)} ({len(purchases):,} qualifying purchases). "
          f"Rule: {MIN_INSIDERS}+ officers or directors, open-market buys of ${MIN_VALUE:,}+, within {WINDOW_DAYS} days.", "",
          recent[["ticker", "company", "start", "end", "insiders", "total_value"]].to_markdown(index=False, floatfmt=",.0f", intfmt=","), "",
          "## Top companies by cluster value (queried from the database)", "", top_sql.to_markdown(index=False, floatfmt=",.0f"), "",
          "![Excess returns](excess_returns.png)", "",
          "_Data: SEC EDGAR insider transactions data sets; prices from Yahoo Finance. Not investment advice._"]
    (OUT / "ALERTS.md").write_text("\n".join(md))


if __name__ == "__main__":
    main()
