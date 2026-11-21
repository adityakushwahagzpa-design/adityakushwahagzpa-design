"""
Fama & French (1993) "Common Risk Factors in the Returns on Stocks and Bonds".

  1. Monthly Fama-French three factors (Mkt-RF, SMB, HML) from Kenneth French's data library.
  2. Eight US equity ETFs that tilt in known directions (large/small, value/growth, tech).
  3. For each ETF: CAPM regression vs three-factor regression, with loadings, t-statistics,
     alphas and R-squared. The test: do SMB and HML loadings match each fund's style,
     and does the three-factor model explain more of the variation than the CAPM?
  4. Long-run cumulative returns of the three factors, showing the size and value premia over time.
Outputs: three charts, regressions.csv, summary.json, REPORT.md
"""
import io
import json
import os
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from data_utils import OFFLINE, prices
from style import DARK, GREY, ROSE, WINE, plt, save

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

FF_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
ETFS = {
    "SPY": "S&P 500 (large blend)", "IWM": "Russell 2000 (small blend)", "IWD": "Russell 1000 Value",
    "IWF": "Russell 1000 Growth", "IWN": "Russell 2000 Value", "IWO": "Russell 2000 Growth",
    "QQQ": "Nasdaq-100 (large tech growth)", "RSP": "S&P 500 Equal Weight",
}
START = "2004-01-01"


def load_factors():
    if OFFLINE:
        idx = pd.period_range("1990-01", pd.Timestamp.today().strftime("%Y-%m"), freq="M")
        rng = np.random.default_rng(3)
        return pd.DataFrame({"Mkt-RF": rng.normal(0.6, 4.4, len(idx)), "SMB": rng.normal(0.1, 3, len(idx)),
                             "HML": rng.normal(0.1, 3, len(idx)), "RF": np.full(len(idx), 0.2)}, index=idx)
    import urllib.request
    raw = urllib.request.urlopen(urllib.request.Request(FF_URL, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read()
    txt = zipfile.ZipFile(io.BytesIO(raw)).read(zipfile.ZipFile(io.BytesIO(raw)).namelist()[0]).decode("latin-1")
    lines = txt.splitlines()
    start = next(i for i, l in enumerate(lines) if l.strip().startswith(",Mkt-RF"))
    rows = []
    for l in lines[start + 1:]:
        parts = [p.strip() for p in l.split(",")]
        if len(parts) < 5 or not parts[0].isdigit() or len(parts[0]) != 6:
            break  # monthly block ends where the annual block starts
        rows.append(parts[:5])
    df = pd.DataFrame(rows, columns=["date", "Mkt-RF", "SMB", "HML", "RF"])
    df.index = pd.PeriodIndex(pd.to_datetime(df.pop("date"), format="%Y%m"), freq="M")
    return df.astype(float)  # percent per month


def ols(y, X):
    X = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    s2 = e @ e / (len(y) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    r2 = 1 - e @ e / ((y - y.mean()) @ (y - y.mean()))
    adj = 1 - (1 - r2) * (len(y) - 1) / (len(y) - X.shape[1])
    return b, b / se, r2, adj


def main():
    ff = load_factors()
    px = prices(list(ETFS), start=START, min_obs=600)
    m = px.resample("ME").last().pct_change().dropna(how="all") * 100
    m.index = m.index.to_period("M")
    data = m.join(ff, how="inner")

    rows = []
    for t, name in ETFS.items():
        if t not in data:
            continue
        d = data[[t, "Mkt-RF", "SMB", "HML", "RF"]].dropna()
        y = d[t] - d["RF"]
        b1, t1, r2_1, _ = ols(y.values, d[["Mkt-RF"]].values)
        b3, t3, r2_3, adj3 = ols(y.values, d[["Mkt-RF", "SMB", "HML"]].values)
        rows.append({"ETF": t, "Style": name, "Months": len(d),
                     "CAPM beta": b1[1], "CAPM alpha (%/yr)": b1[0] * 12, "CAPM R²": r2_1,
                     "FF3 market": b3[1], "FF3 SMB": b3[2], "t(SMB)": t3[2], "FF3 HML": b3[3], "t(HML)": t3[3],
                     "FF3 alpha (%/yr)": b3[0] * 12, "t(alpha)": t3[0], "FF3 R²": r2_3})
    reg = pd.DataFrame(rows)
    reg.round(3).to_csv(OUT / "regressions.csv", index=False)

    # chart: loadings map
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.axhline(0, color=GREY, lw=0.8)
    ax.axvline(0, color=GREY, lw=0.8)
    ax.scatter(reg["FF3 SMB"], reg["FF3 HML"], s=120, color=WINE, zorder=3)
    for _, r in reg.iterrows():
        ax.annotate(f"{r['ETF']}\n{r['Style']}", (r["FF3 SMB"], r["FF3 HML"]), fontsize=7.5, xytext=(6, -4), textcoords="offset points")
    ax.set(xlabel="SMB loading (← large   small →)", ylabel="HML loading (← growth   value →)",
           title="Fama-French style map of eight ETFs")
    for x, y, lab in [(0.95, 0.95, "Small value"), (0.05, 0.95, "Large value"), (0.95, 0.05, "Small growth"), (0.05, 0.05, "Large growth")]:
        ax.text(x, y, lab, transform=ax.transAxes, ha="right" if x > 0.5 else "left", va="top" if y > 0.5 else "bottom",
                color=ROSE, fontsize=9, fontweight="bold")
    save(fig, OUT / "chart_style_map.png")

    fig, ax = plt.subplots(figsize=(9, 4.5))
    xi = np.arange(len(reg))
    ax.bar(xi - 0.2, reg["CAPM R²"], 0.4, color=GREY, label="CAPM")
    ax.bar(xi + 0.2, reg["FF3 R²"], 0.4, color=WINE, label="Fama-French 3-factor")
    ax.set(xticks=xi, xticklabels=reg["ETF"], ylabel="R²", ylim=(0, 1.05), title="How much of each fund's return the models explain")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_r2_comparison.png")

    f = ff.loc["1990-01":]
    cum = (1 + f[["Mkt-RF", "SMB", "HML"]] / 100).cumprod()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for c, col in zip(cum, [DARK, ROSE, WINE]):
        ax.plot(cum.index.to_timestamp(), cum[c], label=c, color=col, lw=2)
    ax.set(yscale="log", ylabel="Growth of $1 (log scale)", title="The three factors since 1990 (US, Kenneth French data library)")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_factor_returns.png")

    ann = lambda s: ((1 + s / 100).prod() ** (12 / len(s)) - 1) * 100
    since07 = f.loc["2007-01":]
    pre07 = f.loc[:"2006-12"]
    summary = {
        "sample": f"{data.index[0]} to {data.index[-1]}", "factor_data_last_month": str(ff.index[-1]),
        "avg_capm_r2": round(reg["CAPM R²"].mean(), 3), "avg_ff3_r2": round(reg["FF3 R²"].mean(), 3),
        "loadings": reg.set_index("ETF")[["FF3 SMB", "FF3 HML", "FF3 alpha (%/yr)", "t(alpha)"]].round(2).to_dict(orient="index"),
        "significant_ff3_alphas": int((reg["t(alpha)"].abs() > 2).sum()),
        "hml_annual_1990_2006_pct": round(ann(pre07["HML"]), 2), "hml_annual_2007_on_pct": round(ann(since07["HML"]), 2),
        "smb_annual_1990_2006_pct": round(ann(pre07["SMB"]), 2), "smb_annual_2007_on_pct": round(ann(since07["SMB"]), 2),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    report = f"""# Fama-French Three-Factor Report

Monthly data, {summary['sample']}. Factors: Kenneth French data library (latest month {summary['factor_data_last_month']}). ETF prices: Yahoo Finance.

## Regressions (excess returns, % per month)

{reg.drop(columns=['Months']).round(2).to_markdown(index=False)}

Average R²: CAPM **{summary['avg_capm_r2']}**, three-factor **{summary['avg_ff3_r2']}**. Funds with a three-factor alpha significant at |t| > 2: **{summary['significant_ff3_alphas']} of {len(reg)}**.

## Factor premia (annualised)

| Factor | 1990–2006 | 2007 onwards |
|:--|--:|--:|
| SMB (small minus big) | {summary['smb_annual_1990_2006_pct']}% | {summary['smb_annual_2007_on_pct']}% |
| HML (value minus growth) | {summary['hml_annual_1990_2006_pct']}% | {summary['hml_annual_2007_on_pct']}% |
"""
    (OUT / "REPORT.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
