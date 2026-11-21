"""
Modigliani & Miller (1958, 1963) "The Cost of Capital, Corporation Finance and the Theory of Investment".

A worked model of one firm at debt-to-equity ratios from 0 to 3:
  * Proposition I   (no tax):   V_L = V_U, so leverage does not change firm value
  * Proposition II  (no tax):   cost of equity rises linearly with D/E; WACC stays flat
  * With corporate tax (1963):  V_L = V_U + t*D, so debt adds a tax shield
  * Trade-off extension:        expected financial distress costs offset the tax shield,
                                which gives an interior optimal debt level
Inputs are illustrative and set in the INPUTS block. The tax rate is India's 25.17% concessional
corporate rate (Section 115BAA, including surcharge and cess).
Outputs: three charts, table.csv, summary.json, REPORT.md
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from style import DARK, GREY, ROSE, WINE, plt, save

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

INPUTS = {
    "ebit_cr": 1000.0,          # operating profit, ₹ crore per year, perpetual
    "r_unlevered": 0.12,        # cost of capital of the all-equity firm
    "r_debt": 0.085,            # cost of debt (assumed constant)
    "tax": 0.2517,              # India corporate tax under Section 115BAA
    "distress_cost_share": 0.25,  # value lost if the firm falls into distress (share of unlevered value)
}


def model(de_grid, p):
    ebit, ru, rd, t = p["ebit_cr"], p["r_unlevered"], p["r_debt"], p["tax"]
    rows = []
    vu_notax = ebit / ru
    vu_tax = ebit * (1 - t) / ru
    for de in de_grid:
        dv = de / (1 + de)
        # no tax: V_L = V_U, D = dv * V
        v0 = vu_notax
        re0 = ru + (ru - rd) * de
        wacc0 = dv * rd + (1 - dv) * re0
        # with tax (MM 1963): V_L = V_U + tD, with D = dv*V_L  ->  V_L = V_U / (1 - t*dv)
        v1 = vu_tax / (1 - t * dv)
        d1 = dv * v1
        re1 = ru + (ru - rd) * (1 - t) * de
        wacc1 = dv * rd * (1 - t) + (1 - dv) * re1
        # trade-off: probability of distress rises with leverage (logistic in D/V)
        prob = 1 / (1 + np.exp(-12 * (dv - 0.6)))
        pv_distress = prob * p["distress_cost_share"] * vu_tax
        v2 = v1 - pv_distress
        rows.append({"D/E": de, "D/V": dv, "V_no_tax": v0, "Re_no_tax": re0, "WACC_no_tax": wacc0,
                     "V_tax": v1, "debt_tax": d1, "tax_shield": t * d1, "Re_tax": re1, "WACC_tax": wacc1,
                     "p_distress": prob, "PV_distress": pv_distress, "V_tradeoff": v2})
    return pd.DataFrame(rows)


def main():
    p = INPUTS
    grid = np.round(np.linspace(0, 3, 61), 3)
    df = model(grid, p)
    best = df.loc[df["V_tradeoff"].idxmax()]
    vu_tax = df.loc[0, "V_tax"]

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    ax.plot(df["D/E"], df["V_no_tax"], color=GREY, lw=2, label="MM I, no tax: value unchanged")
    ax.plot(df["D/E"], df["V_tax"], color=WINE, lw=2, label="MM with tax: V_U + tD")
    ax.plot(df["D/E"], df["V_tradeoff"], color=ROSE, lw=2.5, label="Trade-off: tax shield minus distress costs")
    ax.axvline(best["D/E"], color=DARK, ls=":", lw=1)
    ax.annotate(f"Optimum D/E ≈ {best['D/E']:.2f}\nValue ₹{best['V_tradeoff']:,.0f} cr", (best["D/E"], best["V_tradeoff"]),
                xytext=(10, -40), textcoords="offset points", fontsize=8)
    ax.set(xlabel="Debt-to-equity ratio", ylabel="Firm value (₹ crore)", title="Firm value and leverage")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_firm_value.png")

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.3), sharey=True)
    for ax, sfx, ttl in [(axes[0], "no_tax", "No tax (MM 1958)"), (axes[1], "tax", "With corporate tax (MM 1963)")]:
        ax.plot(df["D/E"], df[f"Re_{sfx}"] * 100, color=WINE, lw=2, label="Cost of equity")
        ax.plot(df["D/E"], df[f"WACC_{sfx}"] * 100, color=ROSE, lw=2.5, label="WACC")
        ax.axhline(p["r_debt"] * 100, color=GREY, ls="--", lw=1.2, label="Cost of debt (pre-tax)")
        ax.set(title=ttl, xlabel="Debt-to-equity ratio")
        ax.legend(fontsize=8)
    axes[0].set_ylabel("Rate (%)")
    fig.suptitle("Proposition II: equity gets riskier as debt rises", fontweight="bold")
    save(fig, OUT / "chart_cost_of_capital.png")

    fig, ax = plt.subplots(figsize=(8.5, 4.3))
    ax.plot(df["D/E"], df["tax_shield"], color=WINE, lw=2, label="PV of tax shield (tD)")
    ax.plot(df["D/E"], df["PV_distress"], color=ROSE, lw=2, label="PV of expected distress costs")
    ax.fill_between(df["D/E"], df["tax_shield"] - df["PV_distress"], 0, color=WINE, alpha=0.08)
    ax.set(xlabel="Debt-to-equity ratio", ylabel="₹ crore", title="Trade-off: benefit and cost of debt")
    ax.legend(fontsize=8)
    save(fig, OUT / "chart_tradeoff.png")

    df.round(4).to_csv(OUT / "table.csv", index=False)
    pick = df[df["D/E"].isin([0, 0.5, 1, 2])].set_index("D/E")
    summary = {
        "inputs": p,
        "unlevered_value_no_tax_cr": round(df.loc[0, "V_no_tax"], 1),
        "unlevered_value_with_tax_cr": round(vu_tax, 1),
        "wacc_no_tax_range_pct": [round(df["WACC_no_tax"].min() * 100, 3), round(df["WACC_no_tax"].max() * 100, 3)],
        "cost_of_equity_no_tax_at_DE_1_pct": round(pick.loc[1, "Re_no_tax"] * 100, 2),
        "cost_of_equity_tax_at_DE_1_pct": round(pick.loc[1, "Re_tax"] * 100, 2),
        "wacc_tax_at_DE_1_pct": round(pick.loc[1, "WACC_tax"] * 100, 2),
        "value_gain_from_tax_shield_at_DE_1_pct": round((pick.loc[1, "V_tax"] / vu_tax - 1) * 100, 2),
        "optimal_DE_tradeoff": round(best["D/E"], 2), "optimal_DV_tradeoff_pct": round(best["D/V"] * 100, 1),
        "value_at_optimum_cr": round(best["V_tradeoff"], 1),
        "gain_vs_all_equity_pct": round((best["V_tradeoff"] / vu_tax - 1) * 100, 2),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    cols = {"V_no_tax": "Value, no tax (₹ cr)", "Re_no_tax": "Re, no tax", "WACC_no_tax": "WACC, no tax",
            "V_tax": "Value, tax (₹ cr)", "Re_tax": "Re, tax", "WACC_tax": "WACC, tax", "V_tradeoff": "Value, trade-off (₹ cr)"}
    show = pick[list(cols)].rename(columns=cols)
    for c in show:
        show[c] = show[c].map(lambda x: f"{x*100:.2f}%" if x < 1 else f"{x:,.0f}")
    report = f"""# Capital Structure Report (Modigliani & Miller)

Inputs: EBIT ₹{p['ebit_cr']:,.0f} crore a year, unlevered cost of capital {p['r_unlevered']*100:.1f}%, cost of debt {p['r_debt']*100:.1f}%, tax {p['tax']*100:.2f}%, distress cost {p['distress_cost_share']*100:.0f}% of firm value.

{show.to_markdown()}

- **No tax:** WACC stays at {summary['wacc_no_tax_range_pct'][0]}% at every debt level, so value is unchanged (₹{summary['unlevered_value_no_tax_cr']:,.0f} crore).
- **With tax:** at D/E = 1 the tax shield lifts value by {summary['value_gain_from_tax_shield_at_DE_1_pct']}% and WACC falls to {summary['wacc_tax_at_DE_1_pct']}%.
- **Trade-off:** value peaks at D/E ≈ {summary['optimal_DE_tradeoff']} (debt {summary['optimal_DV_tradeoff_pct']}% of firm value), {summary['gain_vs_all_equity_pct']}% above the all-equity firm.
"""
    (OUT / "REPORT.md").write_text(report)
    print(report)


if __name__ == "__main__":
    main()
