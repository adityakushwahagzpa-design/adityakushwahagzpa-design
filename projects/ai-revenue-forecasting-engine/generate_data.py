"""Simulate three years of daily revenue for a fictional Indian D2C retailer, plus the
Q1 2026 marketing and promotion plan that the forecast will use.

Product lines: Apparel, Electronics, Home. Revenue depends on trend, weekday and yearly
seasonality, Indian festivals (Diwali, Holi, Republic Day and Independence Day sales),
planned discounts and marketing spend (with diminishing returns), plus noise.
An 8% Electronics price rise in April 2025 shifts the level.
Outputs: data/daily_revenue.csv (2023-2025 actuals), data/plan_q1_2026.csv (drivers only)
"""
import os
import numpy as np
import pandas as pd

SEED = int(os.environ.get("SEED", 7))
DIWALI = ["2023-11-12", "2024-11-01", "2025-10-20", "2026-11-08"]
HOLI = ["2023-03-08", "2024-03-25", "2025-03-14", "2026-03-04"]
LINES = {"Apparel": dict(base=21.0, growth=0.16, diwali=1.9, week=[0.95, 0.92, 0.93, 0.97, 1.05, 1.13, 1.05], mkt=0.10, elast=1.6),
         "Electronics": dict(base=34.0, growth=0.11, diwali=2.4, week=[0.97, 0.95, 0.96, 0.98, 1.02, 1.08, 1.04], mkt=0.08, elast=2.2),
         "Home": dict(base=12.0, growth=0.20, diwali=1.6, week=[0.96, 0.95, 0.96, 0.98, 1.02, 1.08, 1.05], mkt=0.07, elast=1.2)}


def calendar(dates):
    d = pd.DataFrame(index=dates)
    d["diwali_window"] = 0.0
    for x in DIWALI:
        gap = (dates - pd.Timestamp(x)).days
        d["diwali_window"] = np.maximum(d["diwali_window"], np.where((gap >= -10) & (gap <= 2), np.exp(-np.abs(gap + 2) / 4), 0))
    d["holi"] = 0.0
    for x in HOLI:
        gap = (dates - pd.Timestamp(x)).days
        d["holi"] = np.maximum(d["holi"], np.where((gap >= -4) & (gap <= 0), 1.0, 0))
    md = dates.strftime("%m-%d")
    d["republic_day_sale"] = np.isin(md, ["01-24", "01-25", "01-26"]).astype(float)
    d["independence_day_sale"] = np.isin(md, ["08-13", "08-14", "08-15"]).astype(float)
    return d


def drivers(dates, rng):
    cal = calendar(dates)
    # planned discount: higher during sales, light weekend promos
    disc = 0.05 + 0.03 * (dates.dayofweek >= 5)
    disc = disc + 0.12 * cal.republic_day_sale + 0.12 * cal.independence_day_sale + 0.15 * (cal.diwali_window > 0.2) + 0.06 * cal.holi
    # marketing spend (Rs lakh a day): budget grows over time, spikes before sales
    t = (dates - dates[0]).days.values if len(dates) else np.array([])
    mkt = 4.0 * (1 + 0.18 * (dates.year - 2023)) * (1 + 0.15 * np.sin(2 * np.pi * dates.dayofyear / 365.25))
    mkt = mkt * (1 + 1.2 * cal.diwali_window + 0.8 * (cal.republic_day_sale + cal.independence_day_sale) + 0.4 * cal.holi)
    mkt = mkt * rng.lognormal(0, 0.10, len(dates))
    out = cal.copy()
    out["discount_pct"] = np.round(disc, 3)
    out["marketing_lakh"] = np.round(mkt, 2)
    return out


def revenue(dates, drv, rng):
    rows = []
    years = (dates - pd.Timestamp("2023-01-01")).days / 365.25
    for line, p in LINES.items():
        trend = (1 + p["growth"]) ** years
        week = np.array(p["week"])[dates.dayofweek]
        yearly = 1 + 0.08 * np.sin(2 * np.pi * (dates.dayofyear - 80) / 365.25)
        if line == "Apparel":
            yearly = yearly * (1 + 0.10 * np.cos(2 * np.pi * (dates.dayofyear - 15) / 365.25))  # winter wear
        fest = 1 + (p["diwali"] - 1) * drv.diwali_window + 0.25 * drv.holi * (line == "Apparel") \
            + 0.35 * drv.republic_day_sale + 0.35 * drv.independence_day_sale
        promo = 1 + p["elast"] * (drv.discount_pct - 0.05) - 0.5 * (drv.discount_pct - 0.05)  # volume lift net of price cut
        mkt = 1 + p["mkt"] * np.log1p(drv.marketing_lakh / 4.0)
        price_rise = np.where((line == "Electronics") & (dates >= "2025-04-01"), 1.05, 1.0)
        noise = rng.lognormal(0, 0.07, len(dates))
        rev = p["base"] * trend * week * yearly * fest * promo * mkt * price_rise * noise
        rows.append(pd.DataFrame({"date": dates, "product_line": line, "revenue_lakh": np.round(rev, 2)}))
    return pd.concat(rows)


def main():
    rng = np.random.default_rng(SEED)
    hist = pd.date_range("2023-01-01", "2025-12-31", freq="D")
    fut = pd.date_range("2026-01-01", "2026-03-31", freq="D")
    drv_all = drivers(hist.append(fut), rng)
    rev = revenue(hist, drv_all.loc[hist], rng)
    d = drv_all.reset_index().rename(columns={"index": "date"})
    os.makedirs("data", exist_ok=True)
    rev.merge(d, on="date").to_csv("data/daily_revenue.csv", index=False)
    d[d.date >= "2026-01-01"].to_csv("data/plan_q1_2026.csv", index=False)
    by_year = rev.groupby(rev.date.dt.year).revenue_lakh.sum() / 100
    print("Revenue by year (Rs crore):", by_year.round(1).to_dict())


if __name__ == "__main__":
    main()
