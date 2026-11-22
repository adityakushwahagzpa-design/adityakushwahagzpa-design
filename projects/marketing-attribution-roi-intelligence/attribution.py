"""Multi-touch attribution: six models compared against the known true incremental effect.

Models
  last_touch, first_touch, linear      - simple rules
  time_decay                           - credit halves every 7 days before the purchase
  position_based                       - 40% first, 40% last, 20% split over the middle
  markov                               - removal effect in a first-order Markov chain of journeys
  shapley                              - Shapley values over channel coalitions
  ml_counterfactual                    - LightGBM purchase model; each channel's credit is the drop in
                                         predicted purchases when its touches are removed

Outputs: outputs/attribution_comparison.csv (conversions credited per channel per model, with the
true share and each model's error) and outputs/attribution_roi.csv (revenue per Rs of spend).
"""
import itertools
import json
import math
import os
from collections import defaultdict

import numpy as np
import pandas as pd

from generate_data import AOV_RS, CHANNELS

MODELS = ["last_touch", "first_touch", "linear", "time_decay", "position_based", "markov", "shapley",
          "ml_counterfactual"]
HALF_LIFE_DAYS = 7


def load_journeys(path="data/journeys.csv"):
    tp = pd.read_csv(path, parse_dates=["timestamp"]).sort_values(["user_id", "touch_no"])
    g = tp.groupby("user_id")
    paths = g.channel.apply(list)
    times = g.timestamp.apply(list)
    conv = g.converted.first()
    return pd.DataFrame({"path": paths, "times": times, "converted": conv})


# --------------------------------------------------------------------- rule-based
def rule_weights(path, times, model):
    k = len(path)
    if model == "last_touch":
        w = np.eye(k)[-1]
    elif model == "first_touch":
        w = np.eye(k)[0]
    elif model == "linear":
        w = np.full(k, 1 / k)
    elif model == "time_decay":
        age = np.array([(times[-1] - t).total_seconds() / 86400 for t in times])
        w = 0.5 ** (age / HALF_LIFE_DAYS)
        w = w / w.sum()
    elif model == "position_based":
        if k == 1:
            w = np.array([1.0])
        elif k == 2:
            w = np.array([0.5, 0.5])
        else:
            w = np.full(k, 0.2 / (k - 2))
            w[0] = w[-1] = 0.4
    else:
        raise ValueError(model)
    return w


def rule_attribution(j, model):
    credit = defaultdict(float)
    for path, times in zip(j.path[j.converted == 1], j.times[j.converted == 1]):
        for c, w in zip(path, rule_weights(path, times, model)):
            credit[c] += w
    return credit


# --------------------------------------------------------------------- Markov
def markov_transitions(j):
    counts = defaultdict(lambda: defaultdict(float))
    for path, conv in zip(j.path, j.converted):
        states = ["start"] + path + ["conv" if conv else "null"]
        for a, b in zip(states[:-1], states[1:]):
            counts[a][b] += 1
    return {a: {b: n / sum(d.values()) for b, n in d.items()} for a, d in counts.items()}


def conversion_prob(trans, removed=None):
    """P(reach 'conv' from 'start'), solving the absorbing chain as a linear system."""
    states = [s for s in trans if s != removed]
    idx = {s: i for i, s in enumerate(states)}
    A = np.eye(len(states))
    b = np.zeros(len(states))
    for s in states:
        for t, p in trans[s].items():
            if t == "conv":
                b[idx[s]] += p
            elif t == "null" or t == removed:
                continue  # removed channel sends the journey to null
            else:
                A[idx[s], idx[t]] -= p
    return np.linalg.solve(A, b)[idx["start"]]


def markov_attribution(j):
    trans = markov_transitions(j)
    base = conversion_prob(trans)
    removal = {c: 1 - conversion_prob(trans, removed=c) / base for c in CHANNELS if c in trans}
    total = sum(removal.values())
    n_conv = int(j.converted.sum())
    return {c: n_conv * r / total for c, r in removal.items()}, removal


# --------------------------------------------------------------------- Shapley
def shapley_attribution(j):
    """Shapley values with v(S) = conversions from journeys whose channel set is a subset of S."""
    conv_by_set = defaultdict(float)
    for path, conv in zip(j.path, j.converted):
        if conv:
            conv_by_set[frozenset(path)] += 1
    n = len(CHANNELS)
    v = {}
    for r in range(n + 1):
        for S in itertools.combinations(CHANNELS, r):
            fs = frozenset(S)
            v[fs] = sum(cnt for T, cnt in conv_by_set.items() if T <= fs)
    phi = {}
    for c in CHANNELS:
        others = [x for x in CHANNELS if x != c]
        val = 0.0
        for r in range(n):
            wgt = math.factorial(r) * math.factorial(n - r - 1) / math.factorial(n)
            for S in itertools.combinations(others, r):
                fs = frozenset(S)
                val += wgt * (v[fs | {c}] - v[fs])
        phi[c] = val
    return phi


# --------------------------------------------------------------------- ML counterfactual
def features(paths):
    """Touches per channel and journey length; order is left out because it does not drive buying."""
    X = np.zeros((len(paths), len(CHANNELS) + 1))
    col = {c: i for i, c in enumerate(CHANNELS)}
    for r, p in enumerate(paths):
        for c in p:
            X[r, col[c]] += 1
        X[r, -1] = len(p)
    return X


def fit_purchase_model(j, seed=0):
    import lightgbm as lgb
    X, y = features(j.path), j.converted.values
    model = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=200,
                               subsample=0.8, subsample_freq=1, reg_lambda=5.0, random_state=seed, verbose=-1,
                               monotone_constraints=[1] * len(CHANNELS) + [0])
    model.fit(X, y)
    return model


def ml_counterfactual_attribution(j, model=None):
    """Sum over ALL journeys of P(buy | journey) - P(buy | journey without channel c), scaled to conversions."""
    model = model or fit_purchase_model(j)
    X = features(j.path)
    p_all = model.predict_proba(X)[:, 1]
    drop = {}
    for i, c in enumerate(CHANNELS):
        Xc = X.copy()
        Xc[:, -1] -= Xc[:, i]
        Xc[:, i] = 0
        drop[c] = float((p_all - model.predict_proba(Xc)[:, 1]).clip(min=0).sum())
    total = sum(drop.values())
    n_conv = int(j.converted.sum())
    return {c: n_conv * d / total for c, d in drop.items()}, model


# --------------------------------------------------------------------- compare
def run_all(j):
    res = {m: rule_attribution(j, m) for m in MODELS[:5]}
    res["markov"], removal = markov_attribution(j)
    res["shapley"] = shapley_attribution(j)
    res["ml_counterfactual"], _ = ml_counterfactual_attribution(j)
    df = pd.DataFrame({m: [res[m].get(c, 0.0) for c in CHANNELS] for m in MODELS}, index=CHANNELS)
    return df, removal


def compare(df, truth):
    share = df / df.sum()
    t = truth.set_index("channel").true_share.reindex(CHANNELS)
    err = (share.sub(t, axis=0)).abs().mean() * 100  # mean absolute error, percentage points
    return share, t, err


def main():
    os.makedirs("outputs", exist_ok=True)
    j = load_journeys()
    truth = pd.read_csv("data/true_incremental.csv")
    df, removal = run_all(j)
    share, t, err = compare(df, truth)

    out = df.round(1)
    out.insert(0, "true_share_pct", (t * 100).round(1))
    for m in MODELS:
        out[f"{m}_share_pct"] = (share[m] * 100).round(1)
    out.index.name = "channel"
    out.to_csv("outputs/attribution_comparison.csv")

    spend = truth.set_index("channel").spend_lakh.reindex(CHANNELS)
    revenue = df * AOV_RS / 1e5  # Rs lakh
    true_rev = t * df["linear"].sum() * AOV_RS / 1e5  # true incremental share of all sales, for ROI
    roi = revenue.div(spend.replace(0, np.nan), axis=0).round(2)
    roi.insert(0, "true_roi", (true_rev / spend.replace(0, np.nan)).round(2))
    roi.insert(0, "spend_lakh", spend)
    roi.index.name = "channel"
    roi.to_csv("outputs/attribution_roi.csv")

    summary = {
        "users": int(len(j)), "touchpoints": int(j.path.str.len().sum()), "conversions": int(j.converted.sum()),
        "conversion_rate_pct": round(j.converted.mean() * 100, 2),
        "revenue_lakh": round(j.converted.sum() * AOV_RS / 1e5, 1),
        "error_pp": {m: round(float(err[m]), 2) for m in MODELS},
        "best_model": err.idxmin(),
        "markov_removal_effect_pct": {c: round(r * 100, 1) for c, r in removal.items()},
    }
    json.dump(summary, open("outputs/attribution_summary.json", "w"), indent=2)
    print(out[["true_share_pct"] + [f"{m}_share_pct" for m in MODELS]].to_string())
    print("\nMean absolute error vs true share (pp):", summary["error_pp"])
    print(roi.to_string())


if __name__ == "__main__":
    main()
