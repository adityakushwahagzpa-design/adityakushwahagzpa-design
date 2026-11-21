"""
Markowitz (1952) "Portfolio Selection" applied to ten Nifty 50 stocks.

Steps
  1. Five years of daily prices for ten large NSE stocks from different sectors.
  2. Annualised expected returns and the covariance matrix.
  3. The long-only efficient frontier (quadratic optimisation) and 20,000 random portfolios.
  4. Minimum-variance and maximum-Sharpe portfolios.
  5. Out-of-sample check: weights estimated on the first four years, held for the last year,
     compared with an equal-weight portfolio and the Nifty 50 index.
Outputs: frontier chart, weights chart, out-of-sample chart, weights.csv, summary.json, REPORT.md
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from data_utils import prices
from style import DARK, GREY, PALE, ROSE, WINE, plt, save

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

STOCKS = {
    "RELIANCE.NS": "Reliance", "HDFCBANK.NS": "HDFC Bank", "INFY.NS": "Infosys", "TCS.NS": "TCS",
    "ITC.NS": "ITC", "HINDUNILVR.NS": "HUL", "LT.NS": "L&T", "SUNPHARMA.NS": "Sun Pharma",
    "MARUTI.NS": "Maruti", "BHARTIARTL.NS": "Bharti Airtel",
}
INDEX = "^NSEI"
RF = 0.065   # assumed annual risk-free rate (approx. 10-year G-sec yield); change if needed
DAYS = 252


def stats(w, mu, cov):
    r = w @ mu
    v = np.sqrt(w @ cov @ w)
    return r, v, (r - RF) / v


def optimise(mu, cov, target=None, objective="vol"):
    n = len(mu)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    if target is not None:
        cons.append({"type": "eq", "fun": lambda w: w @ mu - target})
    f = (lambda w: np.sqrt(w @ cov @ w)) if objective == "vol" else (lambda w: -stats(w, mu, cov)[2])
    res = minimize(f, np.full(n, 1 / n), bounds=[(0, 1)] * n, constraints=cons, method="SLSQP")
    return res.x


def frontier(mu, cov, points=40):
    wmin = optimise(mu, cov)
    lo = wmin @ mu
    out = []
    for t in np.linspace(lo, mu.max() * 0.999, points):
        w = optimise(mu, cov, target=t)
        out.append(stats(w, mu, cov)[:2])
    return np.array(out)


def main():
    px = prices(list(STOCKS) + [INDEX], period="5y")
    px = px.dropna()
    names = [STOCKS[t] for t in STOCKS if t in px]
    rets = np.log(px / px.shift(1)).dropna()
    stock_rets = rets[[t for t in STOCKS if t in px]]
    stock_rets.columns = names

    mu = stock_rets.mean().values * DAYS
    cov = stock_rets.cov().values * DAYS
    vol = np.sqrt(np.diag(cov))

    # random portfolios
    rng = np.random.default_rng(7)
    W = rng.dirichlet(np.ones(len(mu)), 20000)
    pr = W @ mu
    pv = np.sqrt(np.einsum("ij,jk,ik->i", W, cov, W))
    ps = (pr - RF) / pv

    front = frontier(mu, cov)
    w_min = optimise(mu, cov)
    w_tan = optimise(mu, cov, objective="sharpe")
    w_eq = np.full(len(mu), 1 / len(mu))
    s_min, s_tan, s_eq = stats(w_min, mu, cov), stats(w_tan, mu, cov), stats(w_eq, mu, cov)

    # diversification: average stock volatility vs equal-weight portfolio volatility
    avg_vol = vol.mean()

    # chart 1: frontier
    fig, ax = plt.subplots(figsize=(9, 6))
    sc = ax.scatter(pv * 100, pr * 100, c=ps, s=3, cmap="RdPu", alpha=0.5)
    fig.colorbar(sc, ax=ax, label="Sharpe ratio")
    ax.plot(front[:, 1] * 100, front[:, 0] * 100, color=WINE, lw=2.5, label="Efficient frontier (long-only)")
    ax.scatter(vol * 100, mu * 100, color=DARK, s=25, zorder=3)
    for n, x, y in zip(names, vol * 100, mu * 100):
        ax.annotate(n, (x, y), fontsize=8, xytext=(4, 2), textcoords="offset points")
    xs = np.linspace(0, max(vol) * 100, 50)
    ax.plot(xs, RF * 100 + s_tan[2] * xs, ls="--", color=ROSE, label="Capital market line")
    for (r, v, _), lab, m in [(s_min, "Minimum variance", "s"), (s_tan, "Maximum Sharpe", "*"), (s_eq, "Equal weight", "D")]:
        ax.scatter(v * 100, r * 100, marker=m, s=160, color=WINE if lab != "Equal weight" else GREY,
                   edgecolor="white", zorder=4, label=lab)
    ax.set(xlabel="Annualised volatility (%)", ylabel="Annualised return (%)",
           title="Efficient frontier: ten Nifty 50 stocks, last five years")
    ax.legend(loc="lower right", fontsize=8)
    save(fig, OUT / "chart_efficient_frontier.png")

    # chart 2: weights
    wdf = pd.DataFrame({"Minimum variance": w_min, "Maximum Sharpe": w_tan, "Equal weight": w_eq}, index=names)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    (wdf * 100).plot.bar(ax=ax, color=[WINE, ROSE, GREY], width=0.8)
    ax.set(ylabel="Weight (%)", title="Portfolio weights", xlabel="")
    plt.xticks(rotation=35, ha="right")
    save(fig, OUT / "chart_weights.png")
    (wdf.round(4) * 100).to_csv(OUT / "weights.csv")

    # out-of-sample: fit on all but last year, hold last year
    split = rets.index[-DAYS]
    train, test = stock_rets[stock_rets.index < split], stock_rets[stock_rets.index >= split]
    mu_t, cov_t = train.mean().values * DAYS, train.cov().values * DAYS
    oos_w = {"Minimum variance": optimise(mu_t, cov_t), "Maximum Sharpe": optimise(mu_t, cov_t, objective="sharpe"),
             "Equal weight": w_eq}
    simple_test = np.exp(test) - 1
    growth = {k: (1 + simple_test @ w).cumprod() for k, w in oos_w.items()}  # daily rebalanced
    growth["Nifty 50"] = (1 + (np.exp(rets.loc[rets.index >= split, INDEX]) - 1)).cumprod()
    gdf = pd.DataFrame(growth)
    oos = {}
    for k in gdf:
        dr = gdf[k].pct_change().fillna(gdf[k].iloc[0] - 1)
        oos[k] = {"return_pct": round((gdf[k].iloc[-1] - 1) * 100, 2),
                  "volatility_pct": round(dr.std() * np.sqrt(DAYS) * 100, 2),
                  "max_drawdown_pct": round(((gdf[k] / gdf[k].cummax()) - 1).min() * 100, 2)}

    fig, ax = plt.subplots(figsize=(9, 4.5))
    for k, c in zip(gdf, [WINE, ROSE, GREY, DARK]):
        ax.plot(gdf.index, gdf[k] * 100, label=k, color=c, lw=2 if k != "Nifty 50" else 1.5,
                ls="-" if k != "Nifty 50" else "--")
    ax.set(ylabel="Value of ₹100", title=f"Out-of-sample test: weights from earlier data, held from {split:%d %b %Y}")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_out_of_sample.png")

    summary = {
        "period": f"{px.index[0]:%d %b %Y} to {px.index[-1]:%d %b %Y}",
        "stocks": len(names), "risk_free_assumption_pct": RF * 100,
        "average_stock_volatility_pct": round(avg_vol * 100, 2),
        "equal_weight_volatility_pct": round(s_eq[1] * 100, 2),
        "min_variance": {"return_pct": round(s_min[0] * 100, 2), "volatility_pct": round(s_min[1] * 100, 2), "sharpe": round(s_min[2], 2)},
        "max_sharpe": {"return_pct": round(s_tan[0] * 100, 2), "volatility_pct": round(s_tan[1] * 100, 2), "sharpe": round(s_tan[2], 2)},
        "equal_weight": {"return_pct": round(s_eq[0] * 100, 2), "volatility_pct": round(s_eq[1] * 100, 2), "sharpe": round(s_eq[2], 2)},
        "max_sharpe_top_holdings": {k: round(v * 100, 1) for k, v in sorted(zip(names, w_tan), key=lambda x: -x[1])[:4] if v > 0.005},
        "stocks_with_zero_weight_in_max_sharpe": int((w_tan < 0.005).sum()),
        "out_of_sample_from": f"{split:%d %b %Y}", "out_of_sample": oos,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))

    t = pd.DataFrame({k: summary[k] for k in ["min_variance", "max_sharpe", "equal_weight"]}).T
    o = pd.DataFrame(oos).T
    report = f"""# Efficient Frontier Report

Data: daily adjusted prices, {summary['period']} (Yahoo Finance). Risk-free rate assumed at {RF*100:.1f}%.

## In-sample portfolios (full period)

{t.to_markdown()}

Average volatility of a single stock: **{summary['average_stock_volatility_pct']}%**. Volatility of an equal-weight mix of the same ten: **{summary['equal_weight_volatility_pct']}%**.

## Weights (%)

{(wdf * 100).round(1).to_markdown()}

## Out-of-sample year (weights from earlier data, held from {summary['out_of_sample_from']})

{o.to_markdown()}
"""
    (OUT / "REPORT.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
