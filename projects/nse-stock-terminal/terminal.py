"""
NSE Stock Terminal
------------------
A small command-line "terminal" that prints a one-screen company snapshot
for any NSE-listed stock: price, valuation, profitability, balance sheet,
dividends and four years of revenue and profit, plus a price chart.

Run one stock:        python terminal.py TCS
Run several:          python terminal.py TCS INFY ITC
Run the watchlist:    python terminal.py          (reads watchlist.txt)

Data: Yahoo Finance via the yfinance library. Ticker symbols are NSE codes
(the script adds the ".NS" suffix for you).
"""

import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import yfinance as yf

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)
CRORE = 1e7  # 1 crore = 10 million


# ------------------------------------------------------------------
# Small helpers to format numbers safely (data can be missing)
# ------------------------------------------------------------------
def num(x):
    try:
        x = float(x)
        return None if pd.isna(x) else x
    except (TypeError, ValueError):
        return None


def fmt(x, kind="num"):
    x = num(x)
    if x is None:
        return "n/a"
    if kind == "pct":
        return f"{x:.1f}%"
    if kind == "cr":
        return f"₹{x / CRORE:,.0f} cr"
    if kind == "x":
        return f"{x:.2f}x"
    if kind == "rs":
        return f"₹{x:,.2f}"
    return f"{x:,.2f}"


def row_from_statement(stmt, names):
    """Pick the first matching row (e.g. 'Total Revenue') from a statement."""
    if stmt is None or stmt.empty:
        return None
    for n in names:
        if n in stmt.index:
            return stmt.loc[n]
    return None


# ------------------------------------------------------------------
# Core: build the snapshot for one company
# ------------------------------------------------------------------
def get_snapshot(symbol):
    t = yf.Ticker(f"{symbol}.NS")
    info = t.info or {}
    hist = t.history(period="1y", auto_adjust=True)
    if hist.empty:
        raise ValueError(f"No price data found for {symbol}")

    close = hist["Close"]
    price = num(info.get("currentPrice")) or close.iloc[-1]
    high52, low52 = close.max(), close.min()

    # Ratios we calculate ourselves where Yahoo's field can be unreliable
    div_rate = num(info.get("dividendRate"))
    div_yield = div_rate / price * 100 if div_rate else None
    roe = num(info.get("returnOnEquity"))
    margin = num(info.get("profitMargins"))
    de = num(info.get("debtToEquity"))          # Yahoo gives this as a % (e.g. 35 = 0.35x)

    snap = {
        "Symbol": symbol,
        "Company": info.get("longName") or symbol,
        "Sector": info.get("sector", "n/a"),
        "Industry": info.get("industry", "n/a"),
        "Price": price,
        "52W High": high52,
        "52W Low": low52,
        "% Below 52W High": (price / high52 - 1) * 100,
        "1Y Return %": (close.iloc[-1] / close.iloc[0] - 1) * 100,
        "Market Cap": num(info.get("marketCap")),
        "P/E": num(info.get("trailingPE")),
        "P/B": num(info.get("priceToBook")),
        "EV/EBITDA": num(info.get("enterpriseToEbitda")),
        "ROE %": roe * 100 if roe is not None else None,
        "Net Margin %": margin * 100 if margin is not None else None,
        "Debt/Equity": de / 100 if de is not None else None,
        "Dividend Yield %": div_yield,
        "Beta": num(info.get("beta")),
    }

    # Four years of revenue and net profit from the annual income statement
    stmt = t.income_stmt
    rev = row_from_statement(stmt, ["Total Revenue", "Operating Revenue"])
    ni = row_from_statement(stmt, ["Net Income", "Net Income Common Stockholders"])
    yearly = pd.DataFrame()
    if rev is not None and ni is not None:
        yearly = pd.DataFrame({"Revenue (₹ cr)": rev / CRORE, "Net Profit (₹ cr)": ni / CRORE})
        yearly.index = [pd.to_datetime(d).strftime("FY%y") if hasattr(d, "year") else str(d)
                        for d in yearly.index]
        yearly = yearly.dropna(how="all").iloc[:4][::-1].round(0)
        yearly["Net Margin %"] = (yearly["Net Profit (₹ cr)"] / yearly["Revenue (₹ cr)"] * 100).round(1)

    return snap, yearly, hist


# ------------------------------------------------------------------
# Output: terminal print, markdown file, chart
# ------------------------------------------------------------------
def print_snapshot(s, yearly):
    line = "─" * 60
    print(f"\n{line}\n {s['Company']} ({s['Symbol']})  |  {s['Sector']}\n{line}")
    print(f" Price        {fmt(s['Price'], 'rs'):>18}   1Y Return   {fmt(s['1Y Return %'], 'pct'):>9}")
    print(f" 52W High     {fmt(s['52W High'], 'rs'):>18}   52W Low     {fmt(s['52W Low'], 'rs'):>12}")
    print(f" Market Cap   {fmt(s['Market Cap'], 'cr'):>18}   Beta        {fmt(s['Beta']):>9}")
    print(f" P/E          {fmt(s['P/E'], 'x'):>18}   P/B         {fmt(s['P/B'], 'x'):>9}")
    print(f" ROE          {fmt(s['ROE %'], 'pct'):>18}   Net Margin  {fmt(s['Net Margin %'], 'pct'):>9}")
    print(f" Debt/Equity  {fmt(s['Debt/Equity'], 'x'):>18}   Div Yield   {fmt(s['Dividend Yield %'], 'pct'):>9}")
    if not yearly.empty:
        print(f"{line}\n{yearly.to_string()}")
    print(line)


def save_chart(symbol, hist):
    close = hist["Close"]
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(close.index, close, color="#7c3aed", lw=1.6, label="Close")
    ax.plot(close.index, close.rolling(50).mean(), color="#3b82f6", lw=1.1, label="50-day avg")
    ax.plot(close.index, close.rolling(200).mean(), color="#f59e0b", lw=1.1, label="200-day avg")
    ax.set_title(f"{symbol}: price over the last 12 months", fontsize=13, weight="bold")
    ax.set_ylabel("₹")
    ax.legend(frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(OUT / f"{symbol}_chart.png", dpi=150)
    plt.close(fig)


def save_markdown(s, yearly):
    md = [
        f"# {s['Company']} ({s['Symbol']})",
        "",
        f"**Sector:** {s['Sector']}  |  **Industry:** {s['Industry']}  |  "
        f"**Generated:** {datetime.now():%d %b %Y}",
        "",
        "| Metric | Value | Metric | Value |",
        "|:--|--:|:--|--:|",
        f"| Price | {fmt(s['Price'], 'rs')} | 1Y Return | {fmt(s['1Y Return %'], 'pct')} |",
        f"| 52W High | {fmt(s['52W High'], 'rs')} | 52W Low | {fmt(s['52W Low'], 'rs')} |",
        f"| Market Cap | {fmt(s['Market Cap'], 'cr')} | Beta | {fmt(s['Beta'])} |",
        f"| P/E | {fmt(s['P/E'], 'x')} | P/B | {fmt(s['P/B'], 'x')} |",
        f"| EV/EBITDA | {fmt(s['EV/EBITDA'], 'x')} | ROE | {fmt(s['ROE %'], 'pct')} |",
        f"| Net Margin | {fmt(s['Net Margin %'], 'pct')} | Debt/Equity | {fmt(s['Debt/Equity'], 'x')} |",
        f"| Dividend Yield | {fmt(s['Dividend Yield %'], 'pct')} | Below 52W High | {fmt(s['% Below 52W High'], 'pct')} |",
        "",
    ]
    if not yearly.empty:
        md += ["## Revenue and Profit", "", yearly.to_markdown(), ""]
    md += [f"![Price chart]({s['Symbol']}_chart.png)", "",
           "_Data: Yahoo Finance. For learning purposes only, not investment advice._"]
    (OUT / f"{s['Symbol']}.md").write_text("\n".join(md), encoding="utf-8")


def save_comparison(snaps):
    cols = ["Company", "Sector", "Price", "1Y Return %", "Market Cap", "P/E", "P/B",
            "ROE %", "Net Margin %", "Debt/Equity", "Dividend Yield %"]
    df = pd.DataFrame(snaps)[["Symbol"] + cols]
    df["Market Cap"] = (df["Market Cap"] / CRORE).round(0)
    df = df.rename(columns={"Market Cap": "Market Cap (₹ cr)"})
    df.to_csv(OUT / "comparison.csv", index=False)
    md = ["# Watchlist Comparison", "", f"Generated {datetime.now():%d %b %Y}. "
          "Click a symbol for its full snapshot.", ""]
    show = df.copy().round(2)
    show["Symbol"] = [f"[{x}]({x}.md)" for x in show["Symbol"]]
    show["Market Cap (₹ cr)"] = [f"{v:,.0f}" if pd.notna(v) else "n/a" for v in show["Market Cap (₹ cr)"]]
    show = show.astype(object).where(show.notna(), "n/a")
    md += [show.to_markdown(index=False), "",
           "_Data: Yahoo Finance. For learning purposes only, not investment advice._"]
    (OUT / "COMPARISON.md").write_text("\n".join(md), encoding="utf-8")


def main():
    symbols = [a.upper() for a in sys.argv[1:]]
    if not symbols:
        symbols = [l.strip().upper() for l in Path("watchlist.txt").read_text().splitlines()
                   if l.strip() and not l.startswith("#")]
    snaps = []
    for sym in symbols:
        try:
            snap, yearly, hist = get_snapshot(sym)
        except Exception as e:  # keep going if one stock fails
            print(f"Skipping {sym}: {e}")
            continue
        print_snapshot(snap, yearly)
        save_chart(sym, hist)
        save_markdown(snap, yearly)
        snaps.append(snap)
    if snaps:
        save_comparison(snaps)
        print(f"\nSaved {len(snaps)} snapshots to outputs/")


if __name__ == "__main__":
    main()
