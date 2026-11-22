"""Charts, Excel pack and a rule-based budget memo from the attribution and MMM outputs."""
import json

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from attribution import MODELS
from generate_data import PAID, hill

LABEL = {"last_touch": "Last touch", "first_touch": "First touch", "linear": "Linear", "time_decay": "Time decay",
         "position_based": "Position based", "markov": "Markov", "shapley": "Shapley",
         "ml_counterfactual": "ML counterfactual"}
PALETTE = ["#2a6f97", "#c44536", "#6a994e", "#8d6a9f", "#e09f3e", "#468faf", "#7f7f7f"]


def chart_attribution(a, s):
    models = ["last_touch", "first_touch", "linear", "markov", "shapley", "ml_counterfactual"]
    chans = list(a.index)
    fig, ax = plt.subplots(figsize=(11, 4.6))
    w = 0.12
    x = np.arange(len(chans))
    for i, m in enumerate(models):
        ax.bar(x + (i - 2.5) * w, a[f"{m}_share_pct"], w, label=f"{LABEL[m]} (error {s['error_pp'][m]:.1f} pp)",
               color=PALETTE[i], alpha=0.9)
    ax.scatter(x, a.true_share_pct, marker="D", s=55, color="black", zorder=5, label="True incremental share")
    ax.set_xticks(x, chans)
    ax.set_ylabel("Share of conversions credited, %")
    ax.set_title("Who gets credit for a sale? Six attribution models vs the true incremental share")
    ax.legend(fontsize=8, ncol=2, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("outputs/attribution_vs_truth.png", dpi=150)
    plt.close(fig)


def chart_roi(r):
    fig, ax = plt.subplots(figsize=(9, 4.4))
    x = np.arange(len(r))
    ax.bar(x - 0.2, r.roi, 0.4, color="#2a6f97", label="Average ROI (calibrated MMM)")
    ax.errorbar(x - 0.2, r.roi, yerr=[r.roi - r.roi_p10, r.roi_p90 - r.roi], fmt="none", ecolor="#222", capsize=4)
    ax.bar(x + 0.2, r.marginal_roi, 0.4, color="#e09f3e", label="Marginal ROI (next rupee)")
    ax.scatter(x - 0.2, r.true_roi, marker="D", color="black", zorder=5, label="True average ROI")
    ax.scatter(x[r.lift_test_roi.notna()] - 0.2, r.lift_test_roi.dropna(), marker="x", s=60, color="#c44536", zorder=6,
               label="Lift-test result")
    ax.axhline(1, color="#888", lw=0.8, ls="--")
    ax.set_xticks(x, r.channel)
    ax.set_ylabel("Revenue per Rs 1 of spend")
    ax.set_title("Return on ad spend by channel (bars: P10-P90 range from bootstrap)")
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("outputs/channel_roi.png", dpi=150)
    plt.close(fig)


def chart_curves(params, current, plan):
    fig, ax = plt.subplots(figsize=(9, 4.4))
    opt = {a["channel"]: a["optimised_lakh"] for a in plan["allocation"]}
    for i, c in enumerate(PAID):
        p = params[c]
        s = np.linspace(0, current[c] * 2.2, 100)
        rev = p["beta"] * hill(s / (1 - p["decay"]), p["half"])
        ax.plot(s, rev, color=PALETTE[i], label=c)
        for val, mk in ((current[c], "o"), (opt[c], "*")):
            ax.plot(val, p["beta"] * hill(val / (1 - p["decay"]), p["half"]), mk, color=PALETTE[i], ms=8 if mk == "o" else 13)
    ax.set_xlabel("Weekly spend, Rs lakh")
    ax.set_ylabel("Weekly revenue driven, Rs lakh")
    ax.set_title("Response curves: today's spend (circle) vs optimised spend (star)")
    ax.legend(fontsize=8, frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig("outputs/response_curves.png", dpi=150)
    plt.close(fig)


def write_excel(a, att_roi, r, plan, ms, s):
    wb = Workbook()
    head = Font(bold=True, color="FFFFFF", name="Arial")
    fill = PatternFill("solid", fgColor="1F3864")
    thin = Border(bottom=Side(style="thin", color="BFBFBF"))
    blue = Font(color="0000FF", name="Arial")
    base = Font(name="Arial")

    def table(ws, df, start_row=3, fmt=None):
        for j, col in enumerate(df.columns, 1):
            cl = ws.cell(row=start_row, column=j, value=col)
            cl.font, cl.fill, cl.alignment = head, fill, Alignment(wrap_text=True, vertical="center")
        for i, row in enumerate(df.itertuples(index=False), start_row + 1):
            for j, v in enumerate(row, 1):
                cl = ws.cell(row=i, column=j, value=None if (isinstance(v, float) and np.isnan(v)) else v)
                cl.font, cl.border = base, thin
                if fmt and df.columns[j - 1] in fmt:
                    cl.number_format = fmt[df.columns[j - 1]]
        for j in range(1, len(df.columns) + 1):
            ws.column_dimensions[get_column_letter(j)].width = 16 if j > 1 else 18
        ws.row_dimensions[start_row].height = 32

    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Marketing Attribution & ROI Intelligence: fictional D2C skincare brand (synthetic data)"
    ws["A1"].font = Font(bold=True, size=13, name="Arial")
    rows = [("Journeys analysed (Jul-Sep 2026)", s["users"]), ("Conversions", s["conversions"]),
            ("Most accurate attribution model", LABEL[s["best_model"]]),
            ("Its error vs true share, pp", s["error_pp"][s["best_model"]]),
            ("Last-touch error vs true share, pp", s["error_pp"]["last_touch"]),
            ("MMM weeks", ms["weeks"]), ("MMM fit R²", ms["fit_r2"]),
            ("ROI error, uncalibrated MMM", ms["roi_mae_uncalibrated"]), ("ROI error, calibrated MMM", ms["roi_mae_calibrated"]),
            ("Optimised budget: revenue uplift (model), %", plan["uplift_pct"]),
            ("Optimised budget: revenue uplift (true curves), %", plan["true_uplift_pct"])]
    for i, (k, v) in enumerate(rows, 3):
        ws.cell(row=i, column=1, value=k).font = base
        ws.cell(row=i, column=2, value=v).font = base
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 20
    ws.cell(row=16, column=1, value="All figures are produced by the Python scripts in this folder; data is synthetic.").font = Font(italic=True, name="Arial")

    ws = wb.create_sheet("Attribution")
    ws["A1"] = "Share of conversions credited by each model (%), vs true incremental share"
    ws["A1"].font = Font(bold=True, name="Arial")
    cols = ["true_share_pct"] + [f"{m}_share_pct" for m in MODELS]
    t = a[cols].reset_index().rename(columns={"index": "channel", **{f"{m}_share_pct": LABEL[m] for m in MODELS},
                                              "true_share_pct": "True share"})
    table(ws, t, fmt={c: "0.0" for c in t.columns[1:]})
    n = len(t) + 4
    ws.cell(row=n, column=1, value="Error vs truth, pp").font = Font(bold=True, name="Arial")
    for j in range(3, len(t.columns) + 1):  # mean absolute error, as a live formula
        col = get_column_letter(j)
        ws.cell(row=n, column=j, value=f"=SUMPRODUCT(ABS({col}4:{col}{n - 1}-$B$4:$B${n - 1}))/ROWS({col}4:{col}{n - 1})").number_format = "0.00"

    ws = wb.create_sheet("Attribution ROI")
    ws["A1"] = "Revenue per Rs 1 of spend, Jul-Sep 2026, by attribution model (AOV Rs 1,850)"
    ws["A1"].font = Font(bold=True, name="Arial")
    t = att_roi.reset_index().rename(columns={**LABEL, "spend_lakh": "Spend (Rs lakh)", "true_roi": "True ROI"})
    table(ws, t, fmt={c: "0.00" for c in t.columns[1:]})

    ws = wb.create_sheet("Channel ROI (MMM)")
    ws["A1"] = "Marketing mix model, 156 weeks, calibrated with lift tests"
    ws["A1"].font = Font(bold=True, name="Arial")
    t = r[["channel", "spend_lakh", "revenue_lakh", "roi", "roi_p10", "roi_p90", "marginal_roi", "roi_uncalibrated",
           "lift_test_roi", "true_roi", "true_marginal_roi"]].copy()
    table(ws, t, fmt={c: "0.00" for c in t.columns[3:]} | {"spend_lakh": "#,##0.0", "revenue_lakh": "#,##0.0"})
    last = len(t) + 3
    ws.cell(row=last + 1, column=1, value="Total").font = Font(bold=True, name="Arial")
    ws.cell(row=last + 1, column=2, value=f"=SUM(B4:B{last})").number_format = "#,##0.0"
    ws.cell(row=last + 1, column=3, value=f"=SUM(C4:C{last})").number_format = "#,##0.0"
    ws.cell(row=last + 1, column=4, value=f"=C{last + 1}/B{last + 1}").number_format = "0.00"

    ws = wb.create_sheet("Budget Plan")
    ws["A1"] = "Weekly budget: today (last 13 weeks) vs optimised (each channel within ±40%)"
    ws["A1"].font = Font(bold=True, name="Arial")
    for j, h in enumerate(["Channel", "Today (Rs lakh/week)", "Optimised (Rs lakh/week)", "Change %"], 1):
        cl = ws.cell(row=3, column=j, value=h)
        cl.font, cl.fill, cl.alignment = head, fill, Alignment(wrap_text=True)
    for i, al in enumerate(plan["allocation"], 4):
        ws.cell(row=i, column=1, value=al["channel"]).font = base
        c1 = ws.cell(row=i, column=2, value=al["current_lakh"])
        c2 = ws.cell(row=i, column=3, value=al["optimised_lakh"])
        c1.font = c2.font = blue
        c1.number_format = c2.number_format = "0.000"
        ws.cell(row=i, column=4, value=f"=IF(B{i}=0,0,C{i}/B{i}-1)").number_format = "0.0%"
    e = 3 + len(plan["allocation"])
    ws.cell(row=e + 1, column=1, value="Total").font = Font(bold=True, name="Arial")
    for col in "BC":
        ws[f"{col}{e + 1}"] = f"=SUM({col}4:{col}{e})"
        ws[f"{col}{e + 1}"].number_format = "0.000"
    ws.cell(row=e + 3, column=1, value="Blue cells are optimiser outputs; change them to test another split.").font = Font(italic=True, name="Arial")
    for col, wd in zip("ABCD", (18, 20, 22, 12)):
        ws.column_dimensions[col].width = wd
    wb.save("outputs/marketing_roi_pack.xlsx")


def write_memo(a, r, plan, ms, s):
    best = LABEL[s["best_model"]]
    lt = a["last_touch_share_pct"]
    ml = a[f"{s['best_model']}_share_pct"]
    over = (lt - a.true_share_pct).idxmax()
    under = (lt - a.true_share_pct).idxmin()
    alloc = sorted(plan["allocation"], key=lambda x: -x["change_pct"])
    up = [f"{x['channel']} ({x['change_pct']:+.0f}%)" for x in alloc if x["change_pct"] > 1]
    down = [f"{x['channel']} ({x['change_pct']:+.0f}%)" for x in alloc if x["change_pct"] < -1]
    top = r.sort_values("marginal_roi", ascending=False).iloc[0]
    uncal = [c for c in r.channel if pd.isna(r.set_index("channel").loc[c, "lift_test_roi"])]
    text = f"""# Marketing Budget Memo (rule-based)

*Written by report.py from the model outputs. `python ai_analyst.py --memo` has Claude write this memo using the
same numbers through tool calls.*

## Recommendation
Move budget towards {', '.join(up) or 'no channel'} and away from {', '.join(down) or 'no channel'}, keeping the
total weekly spend the same. The response curves put the gain at **{plan['uplift_pct']:.1f}% more media-driven
revenue** for the same money; checked against the true curves (possible because the data is simulated) the gain is
{plan['true_uplift_pct']:.1f}%.

## Why
- **Last-touch reporting misleads.** It gives {over} {lt[over]:.1f}% of the credit against a true incremental share
  of {a.true_share_pct[over]:.1f}%, and gives {under} only {lt[under]:.1f}% against a true {a.true_share_pct[under]:.1f}%.
  The {best} model is closest to the truth (error {s['error_pp'][s['best_model']]:.1f} pp vs {s['error_pp']['last_touch']:.1f} pp for last touch);
  it credits {under} with {ml[under]:.1f}%.
- **The next rupee earns most in {top.channel}**: marginal ROI {top.marginal_roi:.2f} against an average ROI of {top.roi:.2f}.
- **Calibration matters.** Lift tests cut the MMM's average ROI error from {ms['roi_mae_uncalibrated']:.2f} to
  {ms['roi_mae_calibrated']:.2f} revenue per rupee.

## Risks and next experiment
{', '.join(uncal) or 'No channel'} has no lift test, so its ROI rests on the weekly data alone (range
{r.set_index('channel').loc[uncal[0], 'roi_p10'] if uncal else 0:.2f}-{r.set_index('channel').loc[uncal[0], 'roi_p90'] if uncal else 0:.2f}). Run a holdout test there before cutting it further.
Revenue is not profit: margins and returns are outside this model.
"""
    open("outputs/BUDGET_MEMO.md", "w").write(text)


def main():
    a = pd.read_csv("outputs/attribution_comparison.csv", index_col=0)
    att_roi = pd.read_csv("outputs/attribution_roi.csv", index_col=0)
    s = json.load(open("outputs/attribution_summary.json"))
    r = pd.read_csv("outputs/mmm_roi.csv")
    ms = json.load(open("outputs/mmm_summary.json"))
    params = json.load(open("outputs/mmm_params.json"))["params"]
    plan = ms["budget"]
    current = {x["channel"]: x["current_lakh"] for x in plan["allocation"]}
    chart_attribution(a, s)
    chart_roi(r)
    chart_curves(params, current, plan)
    write_excel(a, att_roi, r, plan, ms, s)
    write_memo(a, r, plan, ms, s)
    print("charts, outputs/marketing_roi_pack.xlsx and outputs/BUDGET_MEMO.md written")


if __name__ == "__main__":
    main()
