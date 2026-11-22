"""Marketing mix model (MMM): ROI per channel from weekly spend and revenue, plus a budget optimiser.

Model:  revenue_t = base_t + sum_c beta_c * hill(adstock(spend_c, decay_c), half_c) + noise
        base_t    = intercept + trend + yearly seasonality + festive index

Fitting: the carry-over (decay) and saturation (half) of each channel are found by differential
evolution; for each candidate the linear part (base terms and non-negative betas) is solved exactly
by bounded least squares. A residual bootstrap (refit on resampled noise) gives ROI ranges.

The optimiser reallocates a fixed weekly budget across channels (each channel limited to a range
around today's spend) to maximise steady-state revenue, using the fitted response curves.
"""
import json
import os

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution, lsq_linear, minimize

from generate_data import PAID, adstock, hill

DECAY_BOUNDS = (0.0, 0.9)
HALF_BOUNDS_X = (0.2, 6.0)  # half-saturation as a multiple of the channel's mean weekly spend
NOISE_SD = 1.6  # weekly noise used to weight lift tests; re-estimated from an uncalibrated fit in main()


def base_terms(df):
    t = np.arange(len(df))
    return np.column_stack([np.ones(len(df)), t / 52, np.sin(2 * np.pi * t / 52), np.cos(2 * np.pi * t / 52),
                            df.festive_index.values])


def media_terms(df, theta):
    cols = []
    for i, c in enumerate(PAID):
        decay, half = theta[2 * i], theta[2 * i + 1] * df[c].mean()
        cols.append(hill(adstock(df[c].values, decay), half))
    return np.column_stack(cols)


def solve_linear(df, theta, y, lift=None):
    """Exact solve of base terms and betas >= 0. Each lift test adds one row pulling the channel's
    ROI (beta * sum of curve / spend, which is linear in beta) towards the measured ROI, weighted by
    its standard error relative to the weekly noise."""
    B, M = base_terms(df), media_terms(df, theta)
    X = np.hstack([B, M])
    Xa, ya = X, y
    if lift is not None and len(lift):
        sigma = NOISE_SD
        rows, targets = [], []
        for r in lift.itertuples():
            i = PAID.index(r.channel)
            row = np.zeros(X.shape[1])
            row[B.shape[1] + i] = M[:, i].sum() / df[r.channel].sum()
            w = sigma / r.std_error
            rows.append(row * w)
            targets.append(r.measured_roi * w)
        Xa, ya = np.vstack([X, rows]), np.r_[y, targets]
    lb = np.r_[np.full(B.shape[1], -np.inf), np.zeros(M.shape[1])]
    sol = lsq_linear(Xa, ya, bounds=(lb, np.inf))
    return sol.x, X @ sol.x


def fit(df, y=None, seed=0, maxiter=150, lift=None):
    y = df.revenue_lakh.values if y is None else y
    bounds = [DECAY_BOUNDS, HALF_BOUNDS_X] * len(PAID)

    def loss(theta):
        coef, pred = solve_linear(df, theta, y, lift)
        loss_ = np.mean((y - pred) ** 2)
        if lift is not None and len(lift):  # same lift penalty in the outer search
            M = media_terms(df, theta)
            nb = base_terms(df).shape[1]
            sigma2 = max(np.mean((y - pred) ** 2), 1e-6)
            for r in lift.itertuples():
                i = PAID.index(r.channel)
                roi = coef[nb + i] * M[:, i].sum() / df[r.channel].sum()
                loss_ += sigma2 * ((roi - r.measured_roi) / r.std_error) ** 2 / len(y)
        return loss_

    res = differential_evolution(loss, bounds, seed=seed, maxiter=maxiter, tol=1e-7, polish=True)
    coef, pred = solve_linear(df, res.x, y, lift)
    nb = base_terms(df).shape[1]
    params = {c: {"decay": float(res.x[2 * i]), "half": float(res.x[2 * i + 1] * df[c].mean()),
                  "beta": float(coef[nb + i])} for i, c in enumerate(PAID)}
    return {"params": params, "base_coef": coef[:nb].tolist(), "pred": pred, "theta": res.x}


def contributions(df, params, scale=1.0):
    return {c: p["beta"] * hill(adstock(df[c].values * scale, p["decay"]), p["half"]) for c, p in params.items()}


def roi_table(df, params):
    rows = []
    for c, p in params.items():
        spend = df[c].sum()
        contrib = p["beta"] * hill(adstock(df[c].values, p["decay"]), p["half"])
        bumped = p["beta"] * hill(adstock(df[c].values * 1.01, p["decay"]), p["half"])
        rows.append({"channel": c, "spend_lakh": round(spend, 1), "revenue_lakh": round(contrib.sum(), 1),
                     "roi": round(contrib.sum() / spend, 2),
                     "marginal_roi": round((bumped.sum() - contrib.sum()) / (0.01 * spend), 2),
                     "decay": round(p["decay"], 2), "half_saturation": round(p["half"], 2)})
    return pd.DataFrame(rows)


def _boot_one(args):
    df, ystar, b, lift = args
    r = fit(df, ystar, seed=b + 10, maxiter=60, lift=lift)
    return roi_table(df, r["params"]).set_index("channel")[["roi", "marginal_roi"]]


def bootstrap(df, fitres, n=20, seed=1, lift=None):
    """Refit on y* = fitted + resampled residuals (and redrawn lift results); returns ROI draws per channel."""
    from multiprocessing import Pool
    rng = np.random.default_rng(seed)
    y, pred = df.revenue_lakh.values, fitres["pred"]
    resid = y - pred
    jobs = []
    for b in range(n):
        lb = None
        if lift is not None:  # lift tests have sampling error too: redraw each measured ROI
            lb = lift.copy()
            lb["measured_roi"] = lift.measured_roi + rng.normal(0, 1, len(lift)) * lift.std_error
        jobs.append((df, pred + rng.choice(resid, len(resid), replace=True), b, lb))
    with Pool(min(os.cpu_count() or 1, 8)) as pool:
        draws = pool.map(_boot_one, jobs)
    return pd.concat(draws, keys=range(n))


# --------------------------------------------------------------------- budget
def weekly_revenue(spend, params):
    """Steady-state weekly revenue from constant weekly spend per channel."""
    return sum(params[c]["beta"] * hill(s / (1 - params[c]["decay"]), params[c]["half"])
               for c, s in zip(PAID, spend))


def optimise_budget(params, current, total=None, min_change=-0.5, max_change=0.5, locked=()):
    """Best weekly split of `total` with each channel within [1+min_change, 1+max_change] x current."""
    current = np.array([current[c] for c in PAID], float)
    total = current.sum() if total is None else total
    bounds = []
    for c, s in zip(PAID, current):
        bounds.append((s, s) if c in locked else (max(0.0, s * (1 + min_change)), s * (1 + max_change)))
    lo, hi = sum(b[0] for b in bounds), sum(b[1] for b in bounds)
    if not lo - 1e-9 <= total <= hi + 1e-9:
        raise ValueError(f"total {total:.2f} is outside what the limits allow ({lo:.2f} to {hi:.2f})")
    x0 = np.clip(current * total / current.sum(), [b[0] for b in bounds], [b[1] for b in bounds])
    res = minimize(lambda x: -weekly_revenue(x, params), x0, method="SLSQP", bounds=bounds,
                   constraints=[{"type": "eq", "fun": lambda x: x.sum() - total}],
                   options={"maxiter": 500, "ftol": 1e-10})
    best = res.x
    return {
        "total_weekly_budget_lakh": round(float(total), 3),
        "current_weekly_revenue_lakh": round(float(weekly_revenue(current, params)), 3),
        "optimised_weekly_revenue_lakh": round(float(weekly_revenue(best, params)), 3),
        "uplift_pct": round(float(weekly_revenue(best, params) / weekly_revenue(current * total / current.sum(), params) - 1) * 100, 2),
        "allocation": [{"channel": c, "current_lakh": round(float(s0), 3), "optimised_lakh": round(float(s1), 3),
                        "change_pct": round(float(s1 / s0 - 1) * 100, 1) if s0 else None}
                       for c, s0, s1 in zip(PAID, current, best)],
    }


def current_weekly_spend(df, weeks=13):
    return df[PAID].tail(weeks).mean().to_dict()


def true_weekly_revenue(spend):
    """Weekly revenue under the TRUE response curves (only possible because the data is simulated)."""
    from generate_data import MMM_TRUE
    return sum(MMM_TRUE[c][2] * hill(s / (1 - MMM_TRUE[c][0]), MMM_TRUE[c][1]) for c, s in zip(PAID, spend))


def main(n_boot=20):
    global NOISE_SD
    os.makedirs("outputs", exist_ok=True)
    df = pd.read_csv("data/weekly_mmm.csv", parse_dates=["week"])
    lift = pd.read_csv("data/lift_tests.csv")
    truth = pd.read_csv("data/true_roi.csv")
    y = df.revenue_lakh.values

    raw = fit(df)
    NOISE_SD = float(np.std(y - raw["pred"]))
    fr = fit(df, lift=lift)
    r2 = 1 - np.sum((y - fr["pred"]) ** 2) / np.sum((y - y.mean()) ** 2)
    mape = np.mean(np.abs(y - fr["pred"]) / y) * 100

    roi = roi_table(df, fr["params"])
    boot = bootstrap(df, fr, n=n_boot, lift=lift)
    q = boot.groupby(level=1).quantile([0.1, 0.9]).unstack()
    roi["roi_p10"] = roi.channel.map(q[("roi", 0.1)]).round(2)
    roi["roi_p90"] = roi.channel.map(q[("roi", 0.9)]).round(2)
    roi["roi_uncalibrated"] = roi.channel.map(roi_table(df, raw["params"]).set_index("channel").roi)
    roi["lift_test_roi"] = roi.channel.map(lift.set_index("channel").measured_roi)
    roi = roi.merge(truth[["channel", "true_roi", "true_marginal_roi"]], on="channel")
    roi.to_csv("outputs/mmm_roi.csv", index=False)

    contrib = contributions(df, fr["params"])
    decomp = pd.DataFrame({"week": df.week, "revenue_lakh": y, "fitted_lakh": fr["pred"].round(2),
                           **{c: v.round(2) for c, v in contrib.items()}})
    decomp["base_lakh"] = (decomp.fitted_lakh - decomp[PAID].sum(axis=1)).round(2)
    decomp.to_csv("outputs/mmm_decomposition.csv", index=False)

    cur = current_weekly_spend(df)
    plan = optimise_budget(fr["params"], cur, min_change=-0.4, max_change=0.4)
    cur_v = np.array([cur[c] for c in PAID])
    new_v = np.array([a["optimised_lakh"] for a in plan["allocation"]])
    plan["true_uplift_pct"] = round(float(true_weekly_revenue(new_v) / true_weekly_revenue(cur_v) - 1) * 100, 2)
    from generate_data import MMM_TRUE
    true_params = {c: {"decay": d, "half": h, "beta": b} for c, (d, h, b) in MMM_TRUE.items()}
    best = optimise_budget(true_params, cur, min_change=-0.4, max_change=0.4)
    plan["best_possible_uplift_pct"] = best["uplift_pct"]
    plan["best_possible_allocation"] = {a["channel"]: a["change_pct"] for a in best["allocation"]}
    pd.DataFrame(plan["allocation"]).to_csv("outputs/budget_optimisation.csv", index=False)

    json.dump({"params": fr["params"], "base_coef": fr["base_coef"], "noise_sd": NOISE_SD},
              open("outputs/mmm_params.json", "w"), indent=2)
    summary = {
        "weeks": len(df), "revenue_crore": round(y.sum() / 100, 2),
        "media_spend_crore": round(df[PAID].sum().sum() / 100, 2),
        "media_revenue_share_pct": round(sum(v.sum() for v in contrib.values()) / y.sum() * 100, 1),
        "fit_r2": round(r2, 3), "fit_mape_pct": round(mape, 2),
        "roi_mae_uncalibrated": round(float((roi.roi_uncalibrated - roi.true_roi).abs().mean()), 2),
        "roi_mae_calibrated": round(float((roi.roi - roi.true_roi).abs().mean()), 2),
        "roi_truth_inside_p10_p90": int(((roi.true_roi >= roi.roi_p10) & (roi.true_roi <= roi.roi_p90)).sum()),
        "lift_tests": lift.channel.tolist(),
        "budget": plan,
    }
    json.dump(summary, open("outputs/mmm_summary.json", "w"), indent=2)
    print(roi.to_string(index=False))
    print(json.dumps({k: v for k, v in summary.items() if k != "budget"}, indent=1))
    print(pd.DataFrame(plan["allocation"]).to_string(index=False))
    print("model uplift", plan["uplift_pct"], "% | true uplift", plan["true_uplift_pct"], "% | best possible",
          plan["best_possible_uplift_pct"], "%", plan["best_possible_allocation"])


if __name__ == "__main__":
    main()
