"""
Black & Scholes (1973) "The Pricing of Options and Corporate Liabilities", applied to the Nifty 50.

  1. Black-Scholes-Merton prices and Greeks (delta, gamma, vega, theta, rho) for European calls and puts.
  2. Inputs from market data: Nifty 50 spot and 1-year historical volatility (Yahoo Finance);
     risk-free rate and dividend yield are stated assumptions.
  3. Three independent checks of the formula:
       * put-call parity
       * a Cox-Ross-Rubinstein binomial tree converging to the BS price as steps increase
       * a Monte Carlo simulation of terminal prices (with a 95% confidence interval)
  4. Implied volatility solver (Brent's method) that recovers the input volatility.
  5. A test of the model's key assumption: are Nifty daily returns normal? (skew, kurtosis, Jarque-Bera)
Outputs: four charts, option_chain.csv, summary.json, REPORT.md
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import brentq

from data_utils import prices
from style import DARK, GREY, PALE, ROSE, WINE, plt, save

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

INDEX = "^NSEI"
R = 0.065    # assumed risk-free rate (continuous approximation)
Q = 0.012    # assumed Nifty dividend yield
DAYS_TO_EXPIRY = 30


def bs(S, K, T, r, q, sigma, kind="call"):
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if kind == "call":
        price = S * np.exp(-q * T) * stats.norm.cdf(d1) - K * np.exp(-r * T) * stats.norm.cdf(d2)
        delta = np.exp(-q * T) * stats.norm.cdf(d1)
        theta = (-S * np.exp(-q * T) * stats.norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                 - r * K * np.exp(-r * T) * stats.norm.cdf(d2) + q * S * np.exp(-q * T) * stats.norm.cdf(d1))
        rho = K * T * np.exp(-r * T) * stats.norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * stats.norm.cdf(-d2) - S * np.exp(-q * T) * stats.norm.cdf(-d1)
        delta = -np.exp(-q * T) * stats.norm.cdf(-d1)
        theta = (-S * np.exp(-q * T) * stats.norm.pdf(d1) * sigma / (2 * np.sqrt(T))
                 + r * K * np.exp(-r * T) * stats.norm.cdf(-d2) - q * S * np.exp(-q * T) * stats.norm.cdf(-d1))
        rho = -K * T * np.exp(-r * T) * stats.norm.cdf(-d2)
    gamma = np.exp(-q * T) * stats.norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = S * np.exp(-q * T) * stats.norm.pdf(d1) * np.sqrt(T)
    return {"price": price, "delta": delta, "gamma": gamma, "vega_per_1pct": vega / 100,
            "theta_per_day": theta / 365, "rho_per_1pct": rho / 100}


def binomial(S, K, T, r, q, sigma, steps, kind="call"):
    dt = T / steps
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u
    p = (np.exp((r - q) * dt) - d) / (u - d)
    ST = S * u ** np.arange(steps, -1, -1) * d ** np.arange(0, steps + 1)
    v = np.maximum(ST - K, 0) if kind == "call" else np.maximum(K - ST, 0)
    disc = np.exp(-r * dt)
    for _ in range(steps):
        v = disc * (p * v[:-1] + (1 - p) * v[1:])
    return v[0]


def monte_carlo(S, K, T, r, q, sigma, n=500_000, seed=11):
    z = np.random.default_rng(seed).standard_normal(n // 2)
    z = np.concatenate([z, -z])  # antithetic variates
    ST = S * np.exp((r - q - 0.5 * sigma ** 2) * T + sigma * np.sqrt(T) * z)
    pay = np.exp(-r * T) * np.maximum(ST - K, 0)
    return pay.mean(), 1.96 * pay.std() / np.sqrt(len(pay))


def implied_vol(price, S, K, T, r, q, kind="call"):
    return brentq(lambda s: bs(S, K, T, r, q, s, kind)["price"] - price, 1e-4, 3)


def main():
    px = prices([INDEX], period="2y", min_obs=300)[INDEX].dropna()
    S = float(px.iloc[-1])
    lr = np.log(px / px.shift(1)).dropna()
    sigma = float(lr.iloc[-252:].std() * np.sqrt(252))
    T = DAYS_TO_EXPIRY / 365
    K = round(S / 50) * 50  # nearest Nifty strike (50-point steps)

    call, put = bs(S, K, T, R, Q, sigma, "call"), bs(S, K, T, R, Q, sigma, "put")
    parity_gap = call["price"] - put["price"] - (S * np.exp(-Q * T) - K * np.exp(-R * T))
    steps = [5, 10, 25, 50, 100, 250, 500, 1000]
    tree = [binomial(S, K, T, R, Q, sigma, n) for n in steps]
    mc, mc_ci = monte_carlo(S, K, T, R, Q, sigma)
    iv = implied_vol(call["price"], S, K, T, R, Q)

    strikes = np.arange(K - 1500, K + 1501, 250)
    chain = pd.DataFrame([{"Strike": k, "Call": bs(S, k, T, R, Q, sigma, "call")["price"],
                           "Put": bs(S, k, T, R, Q, sigma, "put")["price"],
                           "Call delta": bs(S, k, T, R, Q, sigma, "call")["delta"],
                           "Gamma": bs(S, k, T, R, Q, sigma, "call")["gamma"]} for k in strikes])
    chain.round(4).to_csv(OUT / "option_chain.csv", index=False)

    # normality of returns
    skew, kurt = stats.skew(lr), stats.kurtosis(lr)
    jb, jb_p = stats.jarque_bera(lr)
    big = int((np.abs((lr - lr.mean()) / lr.std()) > 3).sum())
    expected_big = len(lr) * 2 * (1 - stats.norm.cdf(3))

    # charts
    grid = np.linspace(S * 0.85, S * 1.15, 200)
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    for tdays, c in [(30, WINE), (10, ROSE), (1, GREY)]:
        ax.plot(grid, [bs(s, K, tdays / 365, R, Q, sigma)["price"] for s in grid], color=c, lw=2, label=f"Call, {tdays} days to expiry")
    ax.plot(grid, np.maximum(grid - K, 0), color=DARK, ls="--", lw=1.2, label="Payoff at expiry")
    ax.axvline(S, color=GREY, ls=":", lw=1)
    ax.set(xlabel="Nifty 50 level", ylabel="Option value (index points)", title=f"Black-Scholes call value, strike {K:,.0f}")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_call_value.png")

    fig, axes = plt.subplots(2, 2, figsize=(10, 6.5))
    for ax, g, lab in zip(axes.ravel(), ["delta", "gamma", "vega_per_1pct", "theta_per_day"],
                          ["Delta", "Gamma", "Vega (per 1% vol)", "Theta (per day)"]):
        ax.plot(grid, [bs(s, K, T, R, Q, sigma, "call")[g] for s in grid], color=WINE, lw=2, label="Call")
        ax.plot(grid, [bs(s, K, T, R, Q, sigma, "put")[g] for s in grid], color=ROSE, lw=2, label="Put")
        ax.axvline(S, color=GREY, ls=":", lw=1)
        ax.set_title(lab)
    axes[0, 0].legend(fontsize=8)
    fig.suptitle(f"Greeks against the Nifty level ({DAYS_TO_EXPIRY} days, strike {K:,.0f})", fontweight="bold")
    fig.tight_layout()
    save(fig, OUT / "chart_greeks.png")

    fig, ax = plt.subplots(figsize=(8.5, 4.3))
    ax.semilogx(steps, tree, marker="o", color=WINE, lw=2, label="Binomial tree (CRR)")
    ax.axhline(call["price"], color=DARK, ls="--", lw=1.2, label=f"Black-Scholes {call['price']:.2f}")
    ax.axhspan(mc - mc_ci, mc + mc_ci, color=PALE, alpha=0.6, label="Monte Carlo 95% interval")
    ax.set(xlabel="Tree steps (log scale)", ylabel="Call price (points)", title="Three methods, one price")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_convergence.png")

    fig, ax = plt.subplots(figsize=(8.5, 4.3))
    zs = (lr - lr.mean()) / lr.std()
    ax.hist(zs, bins=120, density=True, color=ROSE, alpha=0.8, label="Nifty daily returns (standardised)")
    xs = np.linspace(-6, 6, 300)
    ax.plot(xs, stats.norm.pdf(xs), color=WINE, lw=2, label="Normal distribution (BS assumption)")
    ax.set(xlim=(-6, 6), xlabel="Standard deviations", title="Fat tails: what Black-Scholes leaves out")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_fat_tails.png")

    summary = {
        "as_of": f"{px.index[-1]:%d %b %Y}", "spot": round(S, 2), "strike": K, "days_to_expiry": DAYS_TO_EXPIRY,
        "historical_vol_1y_pct": round(sigma * 100, 2), "assumptions": {"risk_free_pct": R * 100, "dividend_yield_pct": Q * 100},
        "call": {k: round(v, 4) for k, v in call.items()}, "put": {k: round(v, 4) for k, v in put.items()},
        "put_call_parity_gap": round(parity_gap, 10),
        "binomial_1000_steps": round(tree[-1], 4), "binomial_error_1000": round(tree[-1] - call["price"], 4),
        "monte_carlo": round(mc, 4), "monte_carlo_ci95": round(mc_ci, 4),
        "implied_vol_recovered_pct": round(iv * 100, 4),
        "returns_used_for_normality": len(lr), "skewness": round(skew, 3), "excess_kurtosis": round(kurt, 3),
        "jarque_bera": round(jb, 1), "jarque_bera_p": float(jb_p),
        "days_beyond_3_sd": big, "expected_if_normal": round(expected_big, 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    g = pd.DataFrame({"Call": call, "Put": put}).round(4)
    report = f"""# Black-Scholes Report: Nifty 50 options

As of {summary['as_of']}: Nifty 50 at **{S:,.2f}**, strike {K:,} ({DAYS_TO_EXPIRY} days), 1-year historical volatility **{sigma*100:.2f}%**.
Assumed risk-free rate {R*100:.1f}% and dividend yield {Q*100:.1f}%.

## Prices and Greeks

{g.to_markdown()}

## Checks

| Check | Result |
|:--|:--|
| Put-call parity gap | {parity_gap:.2e} points |
| Binomial tree, 1,000 steps | {tree[-1]:.4f} (error {tree[-1]-call['price']:+.4f}) |
| Monte Carlo, 500,000 paths | {mc:.4f} ± {mc_ci:.4f} |
| Implied volatility recovered | {iv*100:.4f}% (input {sigma*100:.4f}%) |

## Are returns normal? ({len(lr)} daily returns)

Skewness {skew:.3f}, excess kurtosis {kurt:.3f}, Jarque-Bera {jb:,.1f} (p = {jb_p:.2e}).
Days beyond ±3 standard deviations: **{big}**, against **{expected_big:.1f}** expected under a normal distribution.

## Strike ladder

{chain.round(2).to_markdown(index=False)}
"""
    (OUT / "REPORT.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
