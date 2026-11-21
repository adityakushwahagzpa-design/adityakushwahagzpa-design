"""
Fama (1970) "Efficient Capital Markets": weak-form efficiency tests on the Nifty 50.

If prices follow a random walk, past returns should not predict future returns. Tests:
  1. Autocorrelation of daily returns at lags 1 to 10, with the Ljung-Box Q test.
  2. Lo-MacKinlay (1988) variance ratio test at 2, 5, 10 and 20 days (heteroskedasticity-robust z).
  3. Wald-Wolfowitz runs test on the signs of daily returns.
  4. A trading rule: 50/200-day moving-average crossover vs buy-and-hold, after 0.10% cost per trade.
Each test runs on the full sample and on three sub-periods to see whether results are stable.
Outputs: three charts, summary.json, REPORT.md
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from data_utils import prices
from style import DARK, GREY, ROSE, WINE, plt, save

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

INDEX = "^NSEI"
COST = 0.001  # 0.10% per switch


def autocorr(r, lags=10):
    r = r - r.mean()
    acf = np.array([np.sum(r[k:] * r[:-k]) / np.sum(r * r) for k in range(1, lags + 1)])
    n = len(r)
    q = n * (n + 2) * np.sum(acf ** 2 / (n - np.arange(1, lags + 1)))
    return acf, q, 1 - stats.chi2.cdf(q, lags)


def variance_ratio(logp, q):
    """Lo-MacKinlay variance ratio with heteroskedasticity-consistent z statistic."""
    r = np.diff(logp)
    n = len(r)
    mu = r.mean()
    s1 = np.sum((r - mu) ** 2) / (n - 1)
    rq = logp[q:] - logp[:-q]
    m = q * (n - q + 1) * (1 - q / n)
    sq = np.sum((rq - q * mu) ** 2) / m
    vr = sq / s1
    dev = (r - mu) ** 2
    theta = 0.0
    for j in range(1, q):
        delta = np.sum(dev[j:] * dev[:-j]) / np.sum(dev) ** 2 * n
        theta += (2 * (q - j) / q) ** 2 * delta
    z = np.sqrt(n) * (vr - 1) / np.sqrt(theta)
    return vr, z, 2 * (1 - stats.norm.cdf(abs(z)))


def runs_test(r):
    s = np.sign(r[r != 0])
    n1, n2 = np.sum(s > 0), np.sum(s < 0)
    runs = 1 + np.sum(s[1:] != s[:-1])
    mean = 2 * n1 * n2 / (n1 + n2) + 1
    var = 2 * n1 * n2 * (2 * n1 * n2 - n1 - n2) / ((n1 + n2) ** 2 * (n1 + n2 - 1))
    z = (runs - mean) / np.sqrt(var)
    return int(runs), round(mean, 1), z, 2 * (1 - stats.norm.cdf(abs(z)))


def ma_strategy(p):
    ma50, ma200 = p.rolling(50).mean(), p.rolling(200).mean()
    signal = (ma50 > ma200).astype(int).shift(1)  # trade the day after the signal
    r = p.pct_change()
    trades = signal.diff().abs().fillna(0)
    strat = signal * r - trades * COST
    d = pd.DataFrame({"Buy and hold": r, "50/200 MA crossover": strat}).iloc[200:].dropna()
    return d, int(trades.iloc[200:].sum())


def perf(r):
    g = (1 + r).cumprod()
    yrs = len(r) / 252
    return {"CAGR %": (g.iloc[-1] ** (1 / yrs) - 1) * 100, "Volatility %": r.std() * np.sqrt(252) * 100,
            "Sharpe (rf=0)": r.mean() / r.std() * np.sqrt(252), "Max drawdown %": ((g / g.cummax()) - 1).min() * 100}


def battery(p):
    lp = np.log(p.values)
    r = np.diff(lp)
    acf, q, qp = autocorr(r)
    vrs = {k: variance_ratio(lp, k) for k in (2, 5, 10, 20)}
    runs = runs_test(r)
    return acf, q, qp, vrs, runs


def main():
    px = prices([INDEX], start="2007-09-17", min_obs=1000)[INDEX].dropna()
    acf, q, qp, vrs, runs = battery(px)
    n = len(px) - 1
    band = 1.96 / np.sqrt(n)

    cuts = np.array_split(px.index, 3)
    sub = []
    for c in cuts:
        p = px.loc[c[0]:c[-1]]
        a, qq, qqp, v, ru = battery(p)
        sub.append({"Period": f"{c[0]:%Y}–{c[-1]:%Y}", "Lag-1 autocorr": a[0], "Ljung-Box p": qqp,
                    "VR(5)": v[5][0], "VR(5) p": v[5][2], "Runs test p": ru[3]})
    sub = pd.DataFrame(sub)

    d, n_trades = ma_strategy(px)
    perf_df = pd.DataFrame({k: perf(d[k]) for k in d}).T

    fig, ax = plt.subplots(figsize=(8.5, 4.3))
    ax.bar(range(1, 11), acf, color=[WINE if abs(a) > band else ROSE for a in acf])
    ax.axhline(band, color=DARK, ls="--", lw=1)
    ax.axhline(-band, color=DARK, ls="--", lw=1, label="95% band for a random walk")
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set(xlabel="Lag (trading days)", ylabel="Autocorrelation", xticks=range(1, 11),
           title="Do yesterday's Nifty returns predict today's?")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_autocorrelation.png")

    fig, ax = plt.subplots(figsize=(8.5, 4.3))
    ks = list(vrs)
    ax.bar([str(k) for k in ks], [vrs[k][0] for k in ks], color=[WINE if vrs[k][2] < 0.05 else ROSE for k in ks])
    ax.axhline(1, color=DARK, ls="--", lw=1.2, label="Random walk: VR = 1")
    for i, k in enumerate(ks):
        ax.text(i, vrs[k][0] + 0.01, f"p={vrs[k][2]:.2f}", ha="center", fontsize=8)
    ax.set(xlabel="Holding period q (days)", ylabel="Variance ratio", title="Variance ratio test (Lo-MacKinlay)")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_variance_ratio.png")

    fig, ax = plt.subplots(figsize=(9, 4.5))
    g = (1 + d).cumprod() * 100
    ax.plot(g.index, g["Buy and hold"], color=GREY, lw=1.6, label="Buy and hold")
    ax.plot(g.index, g["50/200 MA crossover"], color=WINE, lw=2, label="50/200 MA crossover (after costs)")
    ax.set(ylabel="Value of ₹100", title="Can a simple trend rule beat the Nifty 50?")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_trading_rule.png")

    sig_lags = [int(i + 1) for i, a in enumerate(acf) if abs(a) > band]
    summary = {
        "period": f"{px.index[0]:%d %b %Y} to {px.index[-1]:%d %b %Y}", "observations": n,
        "lag1_autocorrelation": round(acf[0], 4), "significant_lags": sig_lags,
        "ljung_box_Q10": round(q, 2), "ljung_box_p": round(qp, 4),
        "variance_ratios": {str(k): {"VR": round(v[0], 3), "z": round(v[1], 2), "p": round(v[2], 4)} for k, v in vrs.items()},
        "runs": {"observed": runs[0], "expected": runs[1], "z": round(runs[2], 2), "p": round(runs[3], 4)},
        "ma_rule_trades": n_trades,
        "performance": perf_df.round(2).to_dict(orient="index"),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    vr_df = pd.DataFrame({f"q = {k}": {"Variance ratio": v[0], "z (robust)": v[1], "p-value": v[2]} for k, v in vrs.items()}).T
    report = f"""# Market Efficiency Report: Nifty 50

Data: daily closes, {summary['period']} ({n:,} returns, Yahoo Finance).

## 1. Autocorrelation

Lag-1 autocorrelation **{acf[0]:.4f}**; 95% band for a random walk ±{band:.4f}. Lags outside the band: {sig_lags or 'none'}.
Ljung-Box Q(10) = {q:.2f}, p = {qp:.4f}.

## 2. Variance ratios

{vr_df.round(4).to_markdown()}

## 3. Runs test

Observed runs {runs[0]:,} vs {runs[1]:,} expected; z = {runs[2]:.2f}, p = {runs[3]:.4f}.

## 4. Sub-periods

{sub.round(4).to_markdown(index=False)}

## 5. Trading rule (after {COST*100:.2f}% per trade, {n_trades} switches)

{perf_df.round(2).to_markdown()}
"""
    (OUT / "REPORT.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
