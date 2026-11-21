"""
Sharpe (1964) "Capital Asset Prices": the CAPM tested on 20 Nifty 50 stocks.

Steps
  1. Five years of monthly returns for 20 large NSE stocks and the Nifty 50 index.
  2. Time-series regression for each stock: excess return on market excess return
     -> beta, alpha (Jensen's alpha), R-squared and t-statistics.
  3. Cross-section: average excess return against beta (the security market line, SML).
     CAPM predicts a slope equal to the market risk premium and an intercept of zero.
  4. Cost of equity for each stock: Re = Rf + beta x ERP (assumptions below).
Outputs: SML chart, beta chart, betas.csv, summary.json, REPORT.md
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from data_utils import prices
from style import DARK, GREY, ROSE, WINE, plt, save

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

STOCKS = {
    "RELIANCE.NS": "Reliance", "HDFCBANK.NS": "HDFC Bank", "ICICIBANK.NS": "ICICI Bank", "INFY.NS": "Infosys",
    "TCS.NS": "TCS", "ITC.NS": "ITC", "HINDUNILVR.NS": "HUL", "LT.NS": "L&T", "SBIN.NS": "SBI",
    "BHARTIARTL.NS": "Bharti Airtel", "KOTAKBANK.NS": "Kotak Bank", "AXISBANK.NS": "Axis Bank",
    "SUNPHARMA.NS": "Sun Pharma", "MARUTI.NS": "Maruti", "TATASTEEL.NS": "Tata Steel", "NESTLEIND.NS": "Nestle",
    "ASIANPAINT.NS": "Asian Paints", "BAJFINANCE.NS": "Bajaj Finance", "ONGC.NS": "ONGC", "POWERGRID.NS": "Power Grid",
}
INDEX = "^NSEI"
RF = 0.065   # assumed annual risk-free rate (approx. 10-year G-sec yield)
ERP = 0.07   # assumed equity risk premium for India, for the cost-of-equity column only


def ols(y, x):
    """y = a + b x. Returns a, b, t_a, t_b, r2."""
    X = np.column_stack([np.ones(len(x)), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    s2 = resid @ resid / (len(y) - 2)
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    r2 = 1 - resid @ resid / ((y - y.mean()) @ (y - y.mean()))
    return coef[0], coef[1], coef[0] / se[0], coef[1] / se[1], r2


def main():
    px = prices(list(STOCKS) + [INDEX], period="5y")
    m = px.resample("ME").last().pct_change().dropna(how="all").dropna(subset=[INDEX])
    rf_m = (1 + RF) ** (1 / 12) - 1
    ex = m - rf_m
    mkt = ex[INDEX]

    rows = []
    for t, name in STOCKS.items():
        if t not in ex:
            continue
        d = pd.concat([ex[t], mkt], axis=1).dropna()
        a, b, ta, tb, r2 = ols(d[t].values, d[INDEX].values)
        rows.append({"Stock": name, "Beta": b, "t(beta)": tb, "Alpha (ann. %)": a * 12 * 100, "t(alpha)": ta,
                     "R²": r2, "Avg excess return (ann. %)": d[t].mean() * 12 * 100,
                     "Cost of equity (%)": (RF + b * ERP) * 100, "Months": len(d)})
    df = pd.DataFrame(rows).sort_values("Beta", ascending=False).reset_index(drop=True)

    # cross-sectional SML
    g0, g1, tg0, tg1, r2_sml = ols(df["Avg excess return (ann. %)"].values, df["Beta"].values)
    mkt_premium = mkt.mean() * 12 * 100

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.scatter(df["Beta"], df["Avg excess return (ann. %)"], color=WINE, s=40, zorder=3)
    for _, r in df.iterrows():
        ax.annotate(r["Stock"], (r["Beta"], r["Avg excess return (ann. %)"]), fontsize=7.5, xytext=(4, 2), textcoords="offset points")
    xs = np.linspace(0, df["Beta"].max() * 1.1, 50)
    ax.plot(xs, mkt_premium * xs, color=DARK, ls="--", lw=1.5, label=f"CAPM prediction (slope = market premium {mkt_premium:.1f}%)")
    ax.plot(xs, g0 + g1 * xs, color=ROSE, lw=2.5, label=f"Fitted line (intercept {g0:.1f}%, slope {g1:.1f}%)")
    ax.scatter([1], [mkt_premium], marker="*", s=200, color=DARK, zorder=4, label="Nifty 50")
    ax.axhline(0, color=GREY, lw=0.8)
    ax.set(xlabel="Beta vs Nifty 50", ylabel="Average excess return (% a year)", title="Security market line: CAPM prediction vs data")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_security_market_line.png")

    fig, ax = plt.subplots(figsize=(9, 5))
    d2 = df.sort_values("Beta")
    ax.barh(d2["Stock"], d2["Beta"], color=[WINE if b > 1 else ROSE for b in d2["Beta"]])
    ax.axvline(1, color=DARK, ls="--", lw=1)
    ax.set(xlabel="Beta", title="Betas vs Nifty 50 (monthly returns, five years)")
    save(fig, OUT / "chart_betas.png")

    df.round(3).to_csv(OUT / "betas.csv", index=False)
    sig_alpha = int((df["t(alpha)"].abs() > 2).sum())
    summary = {
        "period": f"{m.index[0]:%b %Y} to {m.index[-1]:%b %Y}", "stocks": len(df), "months": int(df["Months"].median()),
        "assumptions": {"risk_free_pct": RF * 100, "equity_risk_premium_pct": ERP * 100},
        "highest_beta": {df.loc[0, "Stock"]: round(df.loc[0, "Beta"], 2)},
        "lowest_beta": {df.iloc[-1]["Stock"]: round(df.iloc[-1]["Beta"], 2)},
        "median_r2": round(df["R²"].median(), 2),
        "stocks_with_significant_alpha": sig_alpha,
        "market_premium_realised_pct": round(mkt_premium, 2),
        "sml_intercept_pct": round(g0, 2), "sml_slope_pct": round(g1, 2), "sml_t_slope": round(tg1, 2), "sml_r2": round(r2_sml, 2),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    report = f"""# CAPM Report

Data: monthly returns, {summary['period']} (Yahoo Finance). Risk-free rate {RF*100:.1f}%, equity risk premium {ERP*100:.1f}% (assumptions).

## Time-series regressions

{df.drop(columns='Months').round(2).to_markdown(index=False)}

## Security market line (cross-section)

| | Value |
|:--|--:|
| Realised market premium | {mkt_premium:.2f}% |
| Fitted intercept | {g0:.2f}% (t = {tg0:.2f}) |
| Fitted slope | {g1:.2f}% (t = {tg1:.2f}) |
| R² across stocks | {r2_sml:.2f} |

Stocks with alpha significant at |t| > 2: **{sig_alpha} of {len(df)}**. Median R²: **{summary['median_r2']}**.
"""
    (OUT / "REPORT.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
