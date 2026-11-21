"""
Kahneman & Tversky (1979) "Prospect Theory", with the cumulative version (Tversky & Kahneman, 1992).

  1. The value function: concave for gains, convex and steeper for losses (loss aversion, lambda = 2.25).
  2. The probability weighting function: small probabilities overweighted, large ones underweighted.
  3. Certainty equivalents for classic gambles, compared with an expected-value decision maker.
  4. Application, myopic loss aversion (Benartzi & Thaler, 1995): how attractive does the Nifty 50 look
     to a prospect-theory investor who checks the portfolio every h months, versus a fixed deposit?
     Uses the empirical distribution of h-month Nifty returns since 2007.
Outputs: four charts, gambles.csv, horizons.csv, summary.json, REPORT.md
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from data_utils import prices
from style import DARK, GREY, ROSE, WINE, plt, save

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

ALPHA, BETA, LAMBDA = 0.88, 0.88, 2.25     # Tversky & Kahneman (1992) estimates
GAMMA_GAIN, GAMMA_LOSS = 0.61, 0.69
FD_RATE = 0.065                             # assumed annual fixed-deposit rate
INDEX = "^NSEI"


def v(x):
    x = np.asarray(x, float)
    return np.where(x >= 0, np.abs(x) ** ALPHA, -LAMBDA * np.abs(x) ** BETA)


def w(p, g):
    p = np.asarray(p, float)
    return p ** g / (p ** g + (1 - p) ** g) ** (1 / g)


def cpt_value(outcomes, probs):
    """Cumulative prospect theory value with rank-dependent decision weights."""
    x, p = np.asarray(outcomes, float), np.asarray(probs, float)
    o = np.argsort(x)
    x, p = x[o], p[o]
    total = 0.0
    gains = x >= 0
    # gains: decumulative from the best outcome down
    xg, pg = x[gains][::-1], p[gains][::-1]
    cum = np.cumsum(pg)
    wg = w(cum, GAMMA_GAIN) - w(np.r_[0, cum[:-1]], GAMMA_GAIN)
    total += np.sum(wg * v(xg))
    # losses: cumulative from the worst outcome up
    xl, pl = x[~gains], p[~gains]
    cum = np.cumsum(pl)
    wl = w(cum, GAMMA_LOSS) - w(np.r_[0, cum[:-1]], GAMMA_LOSS)
    total += np.sum(wl * v(xl))
    return total


def certainty_equivalent(val):
    return val ** (1 / ALPHA) if val >= 0 else -((-val) / LAMBDA) ** (1 / BETA)


GAMBLES = [
    ("50% win ₹1,000, else nothing", [1000, 0], [0.5, 0.5]),
    ("50% win ₹1,000, 50% lose ₹1,000", [1000, -1000], [0.5, 0.5]),
    ("50% win ₹2,500, 50% lose ₹1,000", [2500, -1000], [0.5, 0.5]),
    ("1% win ₹1,00,000, else nothing (lottery)", [100000, 0], [0.01, 0.99]),
    ("1% lose ₹1,00,000, else nothing (insurance case)", [-100000, 0], [0.01, 0.99]),
    ("90% lose ₹1,000, else nothing", [-1000, 0], [0.9, 0.1]),
]


def main():
    # 1-3: theory
    rows = []
    for name, x, p in GAMBLES:
        val = cpt_value(x, p)
        ce = certainty_equivalent(val)
        ev = float(np.dot(x, p))
        rows.append({"Gamble": name, "Expected value (₹)": ev, "Prospect-theory certainty equivalent (₹)": ce,
                     "Accept vs ₹0?": "Yes" if val > 0 else "No"})
    gam = pd.DataFrame(rows)
    gam.round(1).to_csv(OUT / "gambles.csv", index=False)

    xs = np.linspace(-1000, 1000, 400)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(xs, v(xs), color=WINE, lw=2.5, label=f"Prospect theory (α = {ALPHA}, λ = {LAMBDA})")
    ax.plot(xs, xs ** 1, color=GREY, ls="--", lw=1.2, label="Expected value (linear)")
    ax.axhline(0, color=DARK, lw=0.8)
    ax.axvline(0, color=DARK, lw=0.8)
    ax.set(xlabel="Gain or loss (₹)", ylabel="Subjective value", title="Losses hurt about twice as much as gains please")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_value_function.png")

    ps = np.linspace(0.001, 0.999, 400)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(ps, w(ps, GAMMA_GAIN), color=WINE, lw=2.5, label=f"Gains (γ = {GAMMA_GAIN})")
    ax.plot(ps, w(ps, GAMMA_LOSS), color=ROSE, lw=2.5, label=f"Losses (γ = {GAMMA_LOSS})")
    ax.plot(ps, ps, color=GREY, ls="--", lw=1.2, label="Objective probability")
    ax.set(xlabel="Probability", ylabel="Decision weight", title="Probability weighting")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_probability_weighting.png")

    # 4: myopic loss aversion on the Nifty 50
    px = prices([INDEX], start="2007-09-17", min_obs=1000)[INDEX].dropna()
    mp = px.resample("ME").last()
    horizons = [1, 2, 3, 6, 9, 12, 18, 24, 36, 48, 60]
    hz = []
    for h in horizons:
        r = (mp.shift(-h) / mp - 1).dropna().values * 100  # % return over h months (overlapping windows)
        fd = ((1 + FD_RATE) ** (h / 12) - 1) * 100
        val_eq = cpt_value(r, np.full(len(r), 1 / len(r)))
        val_fd = cpt_value([fd], [1.0])
        hz.append({"Horizon (months)": h, "Windows": len(r), "Mean Nifty return %": r.mean(),
                   "Share of losing windows %": (r < 0).mean() * 100, "Worst %": r.min(),
                   "FD return %": fd, "PT value: Nifty": val_eq, "PT value: FD": val_fd,
                   "PT value per year: Nifty": val_eq * 12 / h, "PT value per year: FD": val_fd * 12 / h})
    hz = pd.DataFrame(hz)
    hz.round(3).to_csv(OUT / "horizons.csv", index=False)
    # first horizon at which a prospect-theory investor prefers the Nifty
    better = hz[hz["PT value: Nifty"] > hz["PT value: FD"]]
    cross = int(better["Horizon (months)"].iloc[0]) if len(better) else None

    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.plot(hz["Horizon (months)"], hz["PT value per year: Nifty"], marker="o", color=WINE, lw=2, label="Nifty 50")
    ax.plot(hz["Horizon (months)"], hz["PT value per year: FD"], marker="s", color=GREY, lw=2, label=f"Fixed deposit at {FD_RATE*100:.1f}%")
    if cross:
        ax.axvline(cross, color=ROSE, ls=":", lw=1.5)
        ax.annotate(f"Nifty preferred from {cross} months", (cross, ax.get_ylim()[0]), xytext=(6, 10), textcoords="offset points", fontsize=8)
    ax.set(xscale="log", xticks=horizons, xticklabels=horizons, xlabel="How often the portfolio is checked (months, log scale)",
           ylabel="Prospect-theory value per year", title="Myopic loss aversion: checking often makes equities look worse")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_myopic_loss_aversion.png")

    fig, ax = plt.subplots(figsize=(8.5, 4.3))
    ax.bar([str(h) for h in hz["Horizon (months)"]], hz["Share of losing windows %"], color=ROSE)
    ax.set(xlabel="Holding period (months)", ylabel="Share of periods with a loss (%)", title="How often the Nifty 50 shows a loss")
    save(fig, OUT / "chart_loss_frequency.png")

    summary = {
        "parameters": {"alpha": ALPHA, "lambda": LAMBDA, "gamma_gain": GAMMA_GAIN, "gamma_loss": GAMMA_LOSS, "fd_rate_pct": FD_RATE * 100},
        "data": f"Nifty 50 month-end closes, {mp.index[0]:%b %Y} to {mp.index[-1]:%b %Y} (price index, dividends excluded)",
        "gambles": gam.round(1).to_dict(orient="records"),
        "loss_share_1m_pct": round(hz.loc[0, "Share of losing windows %"], 1),
        "loss_share_12m_pct": round(hz.set_index("Horizon (months)").loc[12, "Share of losing windows %"], 1),
        "loss_share_60m_pct": round(hz.set_index("Horizon (months)").loc[60, "Share of losing windows %"], 1),
        "horizon_where_nifty_beats_fd_months": cross,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    report = f"""# Prospect Theory Report

Parameters: α = β = {ALPHA}, λ = {LAMBDA}, γ⁺ = {GAMMA_GAIN}, γ⁻ = {GAMMA_LOSS} (Tversky & Kahneman, 1992).

## Classic gambles

{gam.round(1).to_markdown(index=False)}

## Myopic loss aversion on the Nifty 50

{summary['data']}. Fixed deposit assumed at {FD_RATE*100:.1f}% a year.

{hz.drop(columns=['PT value per year: Nifty', 'PT value per year: FD']).round(2).to_markdown(index=False)}

A prospect-theory investor prefers the Nifty 50 to the fixed deposit only when checking the portfolio every **{cross if cross else 'n/a'} months** or less often.
"""
    (OUT / "REPORT.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
