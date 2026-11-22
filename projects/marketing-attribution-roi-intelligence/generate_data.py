"""Generate synthetic marketing data for a fictional Indian D2C skincare brand.

Two datasets, both with a known "true" answer so every model can be checked:

1. data/journeys.csv  - 60,000 customer journeys (Jul-Sep 2026): each touchpoint's channel and
   time, and whether the customer bought. Conversion follows a known model, so the true
   incremental conversions of each channel (what is lost if that channel is removed) are known
   and saved to data/true_incremental.csv.
2. data/weekly_mmm.csv - 156 weeks (Oct 2023-Sep 2026) of spend by paid channel and revenue,
   built from a known adstock + saturation model. True ROI per channel is saved to
   data/true_roi.csv. data/lift_tests.csv holds four experiment results (measured ROI with
   sampling error) used to calibrate the MMM.

All amounts in Rs lakh unless stated. All data is synthetic.
"""
import os

import numpy as np
import pandas as pd

SEED = int(os.environ.get("SEED", 11))
CHANNELS = ["Google Search", "Meta Ads", "YouTube", "Influencers", "Email", "Affiliate", "Direct"]
PAID = ["Google Search", "Meta Ads", "YouTube", "Influencers", "Affiliate"]
AOV_RS = 1850  # average order value, rupees

# Journey model: effect of each channel on the log-odds of buying (diminishing with repeat touches)
EFFECT = {"Google Search": 0.35, "Meta Ads": 0.40, "YouTube": 0.60, "Influencers": 0.50,
          "Email": 0.25, "Affiliate": 0.12, "Direct": 0.08}
INTERCEPT = -3.4
# Where in the journey each channel tends to appear: early (awareness) vs late (purchase intent)
EARLY = {"Google Search": 0.6, "Meta Ads": 1.6, "YouTube": 2.2, "Influencers": 1.8,
         "Email": 0.4, "Affiliate": 0.3, "Direct": 0.3}
LATE = {"Google Search": 2.4, "Meta Ads": 0.9, "YouTube": 0.3, "Influencers": 0.4,
        "Email": 1.4, "Affiliate": 1.0, "Direct": 1.6}
# Spend for Jul-Sep 2026 (Rs lakh); Email is platform cost, Direct has no media cost
JOURNEY_SPEND = {"Google Search": 9.5, "Meta Ads": 8.5, "YouTube": 7.5, "Influencers": 6.0,
                 "Email": 0.8, "Affiliate": 2.2, "Direct": 0.0}

# MMM model (weekly): revenue = base + trend + season + sum beta * hill(adstock(spend))
MMM_TRUE = {  # decay, half-saturation (Rs lakh/week of adstocked spend), max weekly revenue (Rs lakh)
    "Google Search": (0.15, 4.0, 16.0),
    "Meta Ads": (0.35, 3.5, 12.0),
    "YouTube": (0.65, 6.0, 18.0),
    "Influencers": (0.50, 3.0, 9.0),
    "Affiliate": (0.10, 1.2, 3.5),
}
WEEKLY_SPEND_MEAN = {"Google Search": 3.0, "Meta Ads": 2.6, "YouTube": 2.3, "Influencers": 1.8, "Affiliate": 0.7}


def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def log_odds(counts):
    return INTERCEPT + sum(EFFECT[c] * np.log1p(n) for c, n in counts.items())


def make_journeys(rng, n_users=60_000):
    rows, users, truth = [], [], {c: 0.0 for c in CHANNELS}
    start = pd.Timestamp("2026-07-01")
    for u in range(n_users):
        k = min(1 + rng.poisson(2.2), 10)
        t0 = start + pd.Timedelta(minutes=int(rng.integers(0, 85 * 24 * 60)))
        gaps = np.cumsum(rng.exponential(1.4, k)) - rng.exponential(1.4)  # days between touches
        chans = []
        for i in range(k):
            pos = i / max(k - 1, 1)  # 0 = first touch, 1 = last touch
            w = np.array([EARLY[c] * (1 - pos) + LATE[c] * pos for c in CHANNELS])
            chans.append(CHANNELS[rng.choice(len(CHANNELS), p=w / w.sum())])
        counts = pd.Series(chans).value_counts().to_dict()
        p = sigmoid(log_odds(counts))
        converted = rng.random() < p
        for c in counts:  # true incremental effect = drop in purchase probability without channel c
            truth[c] += p - sigmoid(log_odds({k2: v for k2, v in counts.items() if k2 != c}))
        for i, c in enumerate(chans):
            rows.append((f"U{u:05d}", i + 1, (t0 + pd.Timedelta(days=float(max(gaps[i], 0)))).floor("min"), c))
        users.append((f"U{u:05d}", int(converted), round(p, 4)))
    tp = pd.DataFrame(rows, columns=["user_id", "touch_no", "timestamp", "channel"])
    us = pd.DataFrame(users, columns=["user_id", "converted", "true_probability"])
    tp = tp.merge(us[["user_id", "converted"]], on="user_id")
    t = pd.Series(truth)
    true_df = pd.DataFrame({"channel": CHANNELS,
                            "true_incremental_conversions": t[CHANNELS].round(1).values})
    true_df["true_share"] = (true_df.true_incremental_conversions / true_df.true_incremental_conversions.sum()).round(4)
    true_df["spend_lakh"] = [JOURNEY_SPEND[c] for c in CHANNELS]
    return tp, true_df


def adstock(x, decay):
    """Geometric carry-over: a_t = x_t + decay * a_(t-1)."""
    from scipy.signal import lfilter
    return lfilter([1.0], [1.0, -decay], np.asarray(x, float))


def hill(x, half):
    return x / (x + half)


def make_mmm(rng, weeks=156):
    dates = pd.date_range("2023-10-02", periods=weeks, freq="W-MON")
    df = pd.DataFrame({"week": dates})
    t = np.arange(weeks)
    # festive weeks: Diwali season (Oct-Nov) and end-of-season sales
    festive = df.week.dt.month.isin([10, 11]).astype(float) * (1 + 0.5 * (df.week.dt.month == 10))
    df["festive_index"] = festive.round(2)
    for c, m in WEEKLY_SPEND_MEAN.items():
        flight = np.where(rng.random(weeks) < 0.15, 0.1, 1.0)  # dark weeks between campaign flights
        lift = 1 + 0.6 * festive.values
        df[c] = np.round(m * flight * lift * rng.lognormal(0, 0.6, weeks), 3)
    base = 22 + 0.06 * t + 2.5 * np.sin(2 * np.pi * t / 52) + 9 * festive.values
    contrib = {}
    for c, (decay, half, beta) in MMM_TRUE.items():
        contrib[c] = beta * hill(adstock(df[c].values, decay), half)
    df["revenue_lakh"] = np.round(base + sum(contrib.values()) + rng.normal(0, 1.6, weeks), 2)
    roi = []
    for c in PAID:
        decay, half, beta = MMM_TRUE[c]
        spend = df[c].sum()
        # marginal ROI: extra revenue from 1% more spend every week, per extra rupee
        bumped = beta * hill(adstock(df[c].values * 1.01, decay), half)
        mroi = (bumped.sum() - contrib[c].sum()) / (0.01 * spend)
        roi.append((c, round(spend, 1), round(contrib[c].sum(), 1), round(contrib[c].sum() / spend, 2), round(mroi, 2),
                    decay, half))
    true_roi = pd.DataFrame(roi, columns=["channel", "spend_lakh", "true_revenue_lakh", "true_roi", "true_marginal_roi",
                                          "true_decay", "true_half_saturation"])
    return df, true_roi


LIFT_TESTS = {  # experiments run on four channels; measured ROI has sampling error
    "YouTube": ("Geo-lift test, 12 test vs 12 control cities", "2025-08-04", "2025-09-14"),
    "Meta Ads": ("Conversion-lift test, 10% holdout audience", "2026-02-02", "2026-03-15"),
    "Influencers": ("Holdout test, campaign paused in 8 cities", "2026-05-04", "2026-06-14"),
    "Google Search": ("Brand + generic search holdout, ads paused in 10 cities", "2025-11-24", "2026-01-04"),
}


def make_lift_tests(rng, true_roi):
    rows = []
    for c, (design, start, end) in LIFT_TESTS.items():
        t = float(true_roi.set_index("channel").loc[c, "true_roi"])
        rows.append((c, design, start, end, round(t * (1 + rng.normal(0, 0.08)), 2), round(0.12 * t, 2)))
    return pd.DataFrame(rows, columns=["channel", "design", "start", "end", "measured_roi", "std_error"])


def main():
    rng = np.random.default_rng(SEED)
    os.makedirs("data", exist_ok=True)
    tp, true_df = make_journeys(rng)
    tp.to_csv("data/journeys.csv", index=False)
    true_df.to_csv("data/true_incremental.csv", index=False)
    mmm, true_roi = make_mmm(rng)
    mmm.to_csv("data/weekly_mmm.csv", index=False)
    true_roi.to_csv("data/true_roi.csv", index=False)
    make_lift_tests(rng, true_roi).to_csv("data/lift_tests.csv", index=False)
    users = tp.drop_duplicates("user_id")
    print(f"journeys: {users.shape[0]:,} users, {len(tp):,} touchpoints, {users.converted.sum():,} conversions "
          f"({users.converted.mean():.1%})")
    print(true_df.to_string(index=False))
    print(true_roi.to_string(index=False))
    print(f"weekly revenue: Rs {mmm.revenue_lakh.sum() / 100:.1f} crore over {len(mmm)} weeks")


if __name__ == "__main__":
    main()
