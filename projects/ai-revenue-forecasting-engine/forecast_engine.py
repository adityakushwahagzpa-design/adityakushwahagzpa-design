"""Revenue forecasting engine: three models, rolling backtest, ensemble, prediction ranges,
driver scenarios and auto-written management commentary.

Models
  1. Seasonal naive  : same weekday last year x recent year-on-year growth
  2. Holt-Winters    : damped trend + weekly seasonality (statsmodels), per product line
  3. LightGBM (ML)   : one model across product lines, learning from the calendar, festivals,
                       discounts, marketing spend and the recent revenue level
Ensemble weights are chosen on the backtest (grid search for the lowest error). Ranges (P10-P90) come from the
backtest errors (split conformal). Outputs go to outputs/.
"""
import json
import os
import warnings
import numpy as np
import pandas as pd
import lightgbm as lgb
from statsmodels.tsa.holtwinters import ExponentialSmoothing

warnings.filterwarnings("ignore")
H = 90
DRIVERS = ["diwali_window", "holi", "republic_day_sale", "independence_day_sale", "discount_pct", "marketing_lakh"]
LINES = ["Apparel", "Electronics", "Home"]
RNG = np.random.default_rng(0)


def load():
    df = pd.read_csv("data/daily_revenue.csv", parse_dates=["date"])
    plan = pd.read_csv("data/plan_q1_2026.csv", parse_dates=["date"])
    return df, plan


# ------------------------------------------------------------------ features for the ML model
def base_features(d):
    f = pd.DataFrame(index=d.index)
    f["line"] = pd.Categorical(d.product_line, categories=LINES)
    f["dow"] = d.date.dt.dayofweek
    f["month"] = d.date.dt.month
    doy = d.date.dt.dayofyear
    f["doy_sin"], f["doy_cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
    for c in DRIVERS[:-1]:
        f[c] = d[c].values
    f["log_marketing"] = np.log1p(d.marketing_lakh.values)
    return f


def level_at(series, end_date, window=28):
    s = series.loc[:end_date].tail(window)
    return s.mean()


def ml_train_rows(df, end):
    """One row per (line, day) up to `end`; the revenue level is measured `gap` days earlier,
    with gap drawn at random from 1-90 so the model learns to forecast up to 90 days ahead."""
    d = df[df.date <= end].copy()
    rows = []
    for line, g in d.groupby("product_line"):
        g = g.sort_values("date").reset_index(drop=True)
        rev = g.revenue_lakh.values
        fest = g.diwali_window.values
        csum, fsum = np.concatenate([[0], np.cumsum(rev)]), np.concatenate([[0], np.cumsum(fest)])
        gap = RNG.integers(1, H + 1, len(g))
        e = np.arange(len(g)) - gap + 1  # level window ends the day before (i - gap + 1)
        s = e - 28
        ok = s >= 0
        g = g[ok].copy()
        e, s, gp = e[ok], s[ok], gap[ok]
        g["level"] = (csum[e] - csum[s]) / 28
        g["level_fest"] = (fsum[e] - fsum[s]) / 28
        g["gap"] = gp
        rows.append(g)
    t = pd.concat(rows).reset_index(drop=True)
    X = base_features(t)
    X["gap"], X["level_fest"] = t.gap.values, t.level_fest.values
    y = np.log(t.revenue_lakh.values / t.level.values)
    return X, y


def ml_future_rows(df, fut, origin):
    f = fut.copy()
    lv, lf = {}, {}
    for line, g in df[df.date <= origin].groupby("product_line"):
        g = g.set_index("date")
        lv[line] = level_at(g.revenue_lakh, origin)
        lf[line] = level_at(g.diwali_window, origin)
    X = base_features(f)
    X["gap"] = (f.date - origin).dt.days.values
    X["level_fest"] = f.product_line.map(lf).values
    return X, f.product_line.map(lv).values


def fit_ml(X, y):
    m = lgb.LGBMRegressor(n_estimators=600, learning_rate=0.03, num_leaves=31, min_child_samples=20,
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.9, verbose=-1, random_state=0)
    m.fit(X, y, categorical_feature=["line"])
    return m


# ------------------------------------------------------------------ the three models
def forecast_all(df, fut, origin):
    """fut: rows (date, product_line, drivers) to forecast. Returns fut with one column per model."""
    out = fut.copy()
    # seasonal naive with growth
    sn = []
    for _, r in fut.iterrows():
        g = df[df.product_line == r.product_line].set_index("date").revenue_lakh
        last = g.loc[r.date - pd.Timedelta(days=364)]
        recent = g.loc[origin - pd.Timedelta(days=89):origin].sum()
        prior = g.loc[origin - pd.Timedelta(days=364 + 89):origin - pd.Timedelta(days=364)].sum()
        sn.append(last * recent / prior)
    out["seasonal_naive"] = sn
    # Holt-Winters per line
    hw = np.zeros(len(fut))
    for line in LINES:
        g = df[(df.product_line == line) & (df.date <= origin)].set_index("date").revenue_lakh.asfreq("D")
        model = ExponentialSmoothing(np.log(g), trend="add", damped_trend=True, seasonal="add", seasonal_periods=7).fit()
        mask = (fut.product_line == line).values
        steps = (fut.date[mask] - origin).dt.days.values
        fc = np.exp(model.forecast(steps.max()))
        hw[mask] = fc.values[steps - 1]
    out["holt_winters"] = hw
    # LightGBM
    X, y = ml_train_rows(df, origin)
    m = fit_ml(X, y)
    Xf, lvl = ml_future_rows(df, fut, origin)
    out["lightgbm"] = np.exp(m.predict(Xf)) * lvl
    return out, m, Xf, lvl


MODELS = ["seasonal_naive", "holt_winters", "lightgbm"]


def wape(a, f):
    return float(np.abs(a - f).sum() / a.sum())


def main():
    df, plan = load()
    os.makedirs("outputs", exist_ok=True)

    # ---------------- rolling backtest: forecast Q2, Q3 and Q4 2025 from the end of the prior quarter
    origins = [pd.Timestamp("2025-03-31"), pd.Timestamp("2025-06-30"), pd.Timestamp("2025-09-30")]
    bt = []
    for o in origins:
        fut = df[(df.date > o) & (df.date <= o + pd.Timedelta(days=H))]
        res, *_ = forecast_all(df[df.date <= o], fut, o)
        res["origin"] = o
        bt.append(res)
        print("backtest done", o.date())
    bt = pd.concat(bt).reset_index(drop=True)
    # ensemble weights: grid search (steps of 0.05, summing to 1) for the lowest backtest WAPE
    best = (9, None)
    for a in np.arange(0, 1.0001, 0.05):
        for b in np.arange(0, 1.0001 - a, 0.05):
            c = 1 - a - b
            e = wape(bt.revenue_lakh, a * bt.seasonal_naive + b * bt.holt_winters + c * bt.lightgbm)
            if e < best[0] - 1e-9:
                best = (e, (a, b, c))
    w = dict(zip(MODELS, [round(float(x), 2) for x in best[1]]))
    bt["ensemble"] = sum(bt[m] * w[m] for m in MODELS)
    allm = MODELS + ["ensemble"]
    rows = []
    for m in allm:
        q = bt.groupby(["origin", "product_line"])[["revenue_lakh", m]].sum()
        rows.append(dict(model=m, daily_wape=round(wape(bt.revenue_lakh, bt[m]), 4),
                         quarterly_total_error=round(float((q[m] / q.revenue_lakh - 1).abs().mean()), 4),
                         bias=round(float(bt[m].sum() / bt.revenue_lakh.sum() - 1), 4),
                         weight=w.get(m, 1.0)))
    bt_scores = pd.DataFrame(rows)
    bt_quarter = bt.assign(quarter=bt.origin.map({origins[0]: "Q2 2025", origins[1]: "Q3 2025", origins[2]: "Q4 2025"})) \
        .groupby("quarter")[["revenue_lakh"] + allm].sum().div(100).round(2).rename(columns={"revenue_lakh": "actual"})
    # ---------------- conformal ranges from backtest errors
    bt["ratio"] = bt.revenue_lakh / bt.ensemble
    d_lo, d_hi = bt.ratio.quantile([0.10, 0.90])
    bt["month"] = bt.date.dt.to_period("M")
    mr = bt.groupby(["month", "product_line"]).apply(lambda g: g.revenue_lakh.sum() / g.ensemble.sum())
    m_lo, m_hi = mr.quantile([0.10, 0.90])

    # ---------------- final forecast for Q1 2026
    origin = pd.Timestamp("2025-12-31")
    fut = pd.concat([plan.assign(product_line=l) for l in LINES]).reset_index(drop=True)
    fc, model, Xf, lvl = forecast_all(df, fut, origin)
    fc["ensemble"] = sum(fc[m] * w[m] for m in MODELS)
    fc["p10"], fc["p90"] = fc.ensemble * d_lo, fc.ensemble * d_hi
    fc["month"] = fc.date.dt.to_period("M").astype(str)
    monthly = fc.groupby(["month", "product_line"]).ensemble.sum().unstack()
    q1_25 = df[(df.date >= "2025-01-01") & (df.date <= "2025-03-31")]
    last_year = q1_25.groupby([q1_25.date.dt.month, "product_line"]).revenue_lakh.sum().unstack()
    monthly_tbl = []
    for i, mth in enumerate(monthly.index):
        for line in LINES:
            p50 = monthly.loc[mth, line]
            ly = last_year.loc[i + 1, line]
            monthly_tbl.append(dict(month=mth, product_line=line, p10=p50 * m_lo, p50=p50, p90=p50 * m_hi,
                                    last_year=ly, yoy=p50 / ly - 1))
    monthly_tbl = pd.DataFrame(monthly_tbl)

    # ---------------- scenarios (LightGBM component re-run with changed drivers)
    def scenario(change):
        p = fut.copy()
        change(p)
        Xs, lv = ml_future_rows(df, p, origin)
        ml = np.exp(model.predict(Xs)) * lv
        ens = fc.seasonal_naive * w["seasonal_naive"] + fc.holt_winters * w["holt_winters"] + ml * w["lightgbm"]
        return float(ens.sum())
    base_total = float(fc.ensemble.sum())

    def mk(f):
        def g(p):
            p["marketing_lakh"] = p["marketing_lakh"] * f
        return g

    def no_rd(p):
        rd = p.republic_day_sale > 0
        p.loc[rd, "discount_pct"] = 0.05
        p.loc[rd, "republic_day_sale"] = 0.0
        p.loc[rd, "marketing_lakh"] = p.loc[rd, "marketing_lakh"] / 1.8

    def deeper(p):
        p["discount_pct"] = p["discount_pct"] + 0.03

    scen = pd.DataFrame([dict(scenario=n, q1_revenue_crore=round(scenario(f) / 100, 2)) for n, f in
                         [("Marketing spend -20%", mk(0.8)), ("Marketing spend +20%", mk(1.2)),
                          ("Skip Republic Day sale", no_rd), ("All discounts +3 points", deeper)]])
    scen.insert(1, "base_case_crore", round(base_total / 100, 2))
    scen["change_crore"] = (scen.q1_revenue_crore - scen.base_case_crore).round(2)
    scen["change_pct"] = (scen.q1_revenue_crore / scen.base_case_crore - 1).round(4)

    # ---------------- driver importance (mean |SHAP| from LightGBM on the Q1 rows)
    contrib = model.predict(Xf, pred_contrib=True)[:, :-1]
    imp = pd.Series(np.abs(contrib).mean(0), index=Xf.columns).sort_values(ascending=False)
    imp = (imp / imp.sum()).round(4)

    # ---------------- save
    fc.to_csv("outputs/forecast_q1_2026_daily.csv", index=False)
    monthly_tbl.round(2).to_csv("outputs/forecast_q1_2026_monthly.csv", index=False)
    bt.drop(columns=["month"]).to_csv("outputs/backtest_daily.csv", index=False)
    bt_scores.to_csv("outputs/backtest_scores.csv", index=False)
    bt_quarter.to_csv("outputs/backtest_by_quarter.csv")
    scen.to_csv("outputs/scenarios.csv", index=False)
    imp.to_csv("outputs/driver_importance.csv", header=["share"])
    q1_total, q1_ly = base_total / 100, q1_25.revenue_lakh.sum() / 100
    summary = dict(q1_2026_forecast_crore=round(q1_total, 2), q1_2026_p10_crore=round(q1_total * m_lo, 2),
                   q1_2026_p90_crore=round(q1_total * m_hi, 2), q1_2025_actual_crore=round(q1_ly, 2),
                   yoy_growth=round(q1_total / q1_ly - 1, 4), weights=w,
                   backtest={r.model: dict(daily_wape=r.daily_wape, quarterly_total_error=r.quarterly_total_error, bias=r.bias)
                             for r in bt_scores.itertuples()},
                   daily_range=[round(float(d_lo), 3), round(float(d_hi), 3)],
                   monthly_range=[round(float(m_lo), 3), round(float(m_hi), 3)])
    json.dump(summary, open("outputs/summary.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))
    print(bt_scores.to_string(index=False))
    print(bt_quarter.to_string())
    print(scen.to_string(index=False))
    print(imp.head(8).to_string())


if __name__ == "__main__":
    main()
