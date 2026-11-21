"""
Portfolio Performance Analytics

Tracks a portfolio of NSE stocks and a gold ETF from a transaction list and real daily prices, and
compares it with putting the same money, on the same dates, into the Nifty 50.

Measures
  * Returns: XIRR (money-weighted), time-weighted return (TWR), annualised return
  * Risk: volatility, maximum drawdown, Sharpe and Sortino ratios, beta, alpha, tracking error
  * Diversification: weights, sector mix, effective number of holdings, correlation matrix,
    diversification ratio and each holding's share of total risk
Input: data/sample_transactions.csv (a SAMPLE portfolio; replace with your own: date, symbol, action, amount_inr)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq

ROOT = Path(__file__).parent
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
BENCH = "^NSEI"
RISK_FREE = 0.065   # approx. yield on 91-day Indian T-bills, annual


def load_prices(symbols, start):
    import yfinance as yf
    tick = [s + ".NS" for s in symbols] + [BENCH]
    px = yf.download(tick, start=start, auto_adjust=True, progress=False)["Close"]
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px.columns = [c.replace(".NS", "") for c in px.columns]
    return px.ffill().dropna(how="all")


def xirr(dates, flows):
    t = np.array([(d - dates[0]).days / 365.0 for d in dates])
    f = np.array(flows, dtype=float)
    return brentq(lambda r: np.sum(f / (1 + r) ** t), -0.99, 10)


def build(tx, px):
    """Units held per day, daily value, and daily external cash flow (money in = positive)."""
    days = px.index[px.index >= tx["date"].min()]
    units = pd.DataFrame(0.0, index=days, columns=sorted(tx["symbol"].unique()) + ["__BENCH__"])
    flow = pd.Series(0.0, index=days)
    for _, r in tx.iterrows():
        d = days[days.searchsorted(r["date"])]          # first trading day on/after the date
        sign = 1 if r["action"] == "BUY" else -1
        units.loc[d:, r["symbol"]] += sign * r["amount_inr"] / px.at[d, r["symbol"]]
        units.loc[d:, "__BENCH__"] += sign * r["amount_inr"] / px.at[d, BENCH]
        flow[d] += sign * r["amount_inr"]
    prices = px.loc[days, units.columns[:-1]].copy()
    prices["__BENCH__"] = px.loc[days, BENCH]
    value = units * prices
    return units, value, flow


def twr_returns(v, flow):
    """Daily returns that strip out deposits and withdrawals (flows land at the close)."""
    return ((v - flow) / v.shift(1) - 1).iloc[1:]


def stats(r, rb=None):
    ann = (1 + r).prod() ** (252 / len(r)) - 1
    vol = r.std() * np.sqrt(252)
    down = r[r < 0].std() * np.sqrt(252)
    curve = (1 + r).cumprod()
    out = {"annualised_return_%": ann * 100, "volatility_%": vol * 100,
           "sharpe": (ann - RISK_FREE) / vol, "sortino": (ann - RISK_FREE) / down,
           "max_drawdown_%": ((curve / curve.cummax()) - 1).min() * 100,
           "best_day_%": r.max() * 100, "worst_day_%": r.min() * 100}
    if rb is not None:
        beta = r.cov(rb) / rb.var()
        annb = (1 + rb).prod() ** (252 / len(rb)) - 1
        te = (r - rb).std() * np.sqrt(252)
        out.update({"beta": beta, "alpha_%": (ann - (RISK_FREE + beta * (annb - RISK_FREE))) * 100,
                    "tracking_error_%": te * 100, "information_ratio": (ann - annb) / te,
                    "correlation_with_nifty": r.corr(rb)})
    return {k: round(float(v), 3) for k, v in out.items()}


def diversification(value, px, sectors):
    last = value.iloc[-1].drop("__BENCH__")
    last = last[last > 1]
    w = last / last.sum()
    rets = px[w.index].pct_change().iloc[-252:].dropna()
    cov = rets.cov() * 252
    sig_p = float(np.sqrt(w @ cov @ w))
    sig_i = np.sqrt(np.diag(cov))
    risk_contrib = w * (cov @ w) / sig_p ** 2
    hold = pd.DataFrame({"value_inr": last.round(0), "weight_%": (w * 100).round(2),
                         "volatility_%": (pd.Series(sig_i, index=w.index) * 100).round(1),
                         "risk_contribution_%": (risk_contrib * 100).round(2)})
    hold["sector"] = hold.index.map(sectors).fillna("Other")
    corr = rets.corr()
    pairs = corr.where(np.triu(np.ones(corr.shape, bool), 1)).stack()
    return hold.sort_values("weight_%", ascending=False), corr, {
        "holdings": int(len(w)), "effective_holdings": round(float(1 / (w ** 2).sum()), 2),
        "diversification_ratio": round(float((w * sig_i).sum() / sig_p), 2),
        "portfolio_volatility_1y_%": round(sig_p * 100, 2),
        "avg_pairwise_correlation": round(float(pairs.mean()), 2),
        "lowest_correlation_pair": [*pairs.idxmin(), round(float(pairs.min()), 2)],
        "highest_correlation_pair": [*pairs.idxmax(), round(float(pairs.max()), 2)],
        "sector_weights_%": hold.groupby("sector")["weight_%"].sum().sort_values(ascending=False).round(1).to_dict(),
    }


def charts(total, bench, invested, r, rb, hold, corr):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.6), gridspec_kw={"width_ratios": [1.4, 1]})
    ax[0].plot(total.index, total / 1e5, color="#7c3aed", lw=1.8, label="Portfolio value")
    ax[0].plot(bench.index, bench / 1e5, color="#f59e0b", lw=1.5, label="Same cash flows into Nifty 50")
    ax[0].plot(invested.index, invested / 1e5, color="grey", lw=1.2, ls="--", label="Net amount invested")
    ax[0].set_ylabel("₹ lakh"); ax[0].legend(frameon=False, fontsize=9)
    ax[0].set_title("Portfolio value vs Nifty 50 and money invested")
    for s, col, lab in [(r, "#7c3aed", "Portfolio"), (rb, "#f59e0b", "Nifty 50")]:
        c = (1 + s).cumprod(); dd = (c / c.cummax() - 1) * 100
        ax[1].plot(dd.index, dd, color=col, lw=1.3, label=lab)
    ax[1].set_title("Drawdown from peak (%)"); ax[1].legend(frameon=False, fontsize=9)
    for a in ax:
        a.spines[["top", "right"]].set_visible(False); a.tick_params(axis="x", rotation=30, labelsize=8)
    fig.tight_layout(); fig.savefig(OUT / "chart_value_drawdown.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    h = hold.sort_values("weight_%")
    y = np.arange(len(h))
    ax[0].barh(y - 0.2, h["weight_%"], 0.4, color="#7c3aed", label="Weight %")
    ax[0].barh(y + 0.2, h["risk_contribution_%"], 0.4, color="#ef4444", label="Share of risk %")
    ax[0].set_yticks(y, h.index); ax[0].legend(frameon=False, fontsize=9)
    ax[0].set_title("Weight vs contribution to portfolio risk")
    im = ax[1].imshow(corr.values, cmap="RdYlGn_r", vmin=-0.2, vmax=1)
    ax[1].set_xticks(range(len(corr)), corr.columns, rotation=60, fontsize=8)
    ax[1].set_yticks(range(len(corr)), corr.index, fontsize=8)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax[1].text(j, i, f"{corr.values[i, j]:.2f}", ha="center", va="center", fontsize=6.5)
    ax[1].set_title("Correlation of daily returns, last 12 months")
    fig.colorbar(im, ax=ax[1], fraction=0.046)
    ax[0].spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "chart_risk_diversification.png", dpi=150); plt.close(fig)


def main():
    tx = pd.read_csv(ROOT / "data" / "sample_transactions.csv", parse_dates=["date"])
    sectors = pd.read_csv(ROOT / "data" / "sectors.csv").set_index("symbol")["sector"]
    px = load_prices(sorted(tx["symbol"].unique()), (tx["date"].min() - pd.Timedelta(days=10)).strftime("%Y-%m-%d"))
    units, value, flow = build(tx, px)
    total, bench = value.drop(columns="__BENCH__").sum(axis=1), value["__BENCH__"]
    invested = flow.cumsum()
    r, rb = twr_returns(total, flow), twr_returns(bench, flow)

    end = total.index[-1]
    cf = tx.assign(cf=np.where(tx["action"] == "BUY", -tx["amount_inr"], tx["amount_inr"]))
    dates = list(cf["date"]) + [end]
    x_port = xirr(dates, list(cf["cf"]) + [total.iloc[-1]])
    x_bench = xirr(dates, list(cf["cf"]) + [bench.iloc[-1]])
    hold, corr, div = diversification(value, px, sectors)

    calendar = pd.DataFrame({"portfolio_%": (1 + r).groupby(r.index.year).prod() - 1,
                             "nifty_%": (1 + rb).groupby(rb.index.year).prod() - 1}).mul(100).round(2)
    summary = {
        "data": "SAMPLE portfolio (illustrative transactions) valued with real NSE prices from Yahoo Finance",
        "period": [str(total.index[0].date()), str(end.date())], "transactions": int(len(tx)),
        "net_invested_inr": round(float(invested.iloc[-1])), "current_value_inr": round(float(total.iloc[-1])),
        "gain_inr": round(float(total.iloc[-1] - invested.iloc[-1])),
        "nifty_equivalent_value_inr": round(float(bench.iloc[-1])),
        "xirr_%": round(x_port * 100, 2), "nifty_xirr_same_cash_flows_%": round(x_bench * 100, 2),
        "twr_total_%": round(float(((1 + r).prod() - 1) * 100), 2), "nifty_total_return_%": round(float(((1 + rb).prod() - 1) * 100), 2),
        "portfolio": stats(r, rb), "nifty": stats(rb), "diversification": div,
        "calendar_year_returns": calendar.to_dict(orient="index"), "risk_free_rate_assumed_%": RISK_FREE * 100,
    }
    hold.to_csv(OUT / "holdings.csv")
    pd.DataFrame({"portfolio_value": total.round(0), "nifty_equivalent": bench.round(0), "net_invested": invested}).to_csv(OUT / "daily_values.csv")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    charts(total, bench, invested, r, rb, hold, corr)

    comp = pd.DataFrame({"Portfolio": summary["portfolio"], "Nifty 50": summary["nifty"]})
    md = [f"# Portfolio Performance Report — {end.date()}", "", f"> {summary['data']}.", "",
          f"Net invested ₹{summary['net_invested_inr']:,}; value ₹{summary['current_value_inr']:,}; "
          f"the same cash flows in the Nifty 50 would be worth ₹{summary['nifty_equivalent_value_inr']:,}.", "",
          f"**XIRR {summary['xirr_%']}%** vs Nifty 50 {summary['nifty_xirr_same_cash_flows_%']}% on the same cash flows.", "",
          "![Value](chart_value_drawdown.png)", "", "## Risk and return (time-weighted)", "", comp.to_markdown(), "",
          "## Calendar-year returns", "", calendar.to_markdown(), "", "## Holdings", "", hold.to_markdown(), "",
          "![Risk](chart_risk_diversification.png)", "", "_For learning purposes only, not investment advice._"]
    (OUT / "REPORT.md").write_text("\n".join(md))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
