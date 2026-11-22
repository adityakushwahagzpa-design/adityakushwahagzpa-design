"""Charts, Excel pack and sample relationship-manager briefs from the platform outputs."""
import json
import os

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import rm_assistant as rm

BLUE, RED, GREEN, GREY, ORANGE, PURPLE = "#2a6f97", "#c44536", "#6a994e", "#8a8a8a", "#e09f3e", "#8d6a9f"


def style(ax, title):
    ax.set_title(title, fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)


def chart_identity(m):
    fig, ax = plt.subplots(figsize=(7, 3.8))
    keys = ["precision", "recall", "f1"]
    x = np.arange(3)
    for k, (lab, col, off) in enumerate([("deterministic_baseline_test", GREY, -0.2), ("ml_matching_test", BLUE, 0.2)]):
        v = [m[lab][q] for q in keys]
        ax.bar(x + off, v, 0.4, color=col, label="Same phone or email" if k == 0 else "ML matching model")
        for xi, vi in zip(x + off, v):
            ax.text(xi, vi + 0.01, f"{vi:.3f}", ha="center", fontsize=9)
    ax.set_xticks(x, ["Precision", "Recall", "F1"])
    ax.set_ylim(0, 1.1)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    style(ax, "Identity resolution on held-out people (record pairs)")
    fig.tight_layout()
    fig.savefig("outputs/identity_resolution.png", dpi=150)
    plt.close(fig)


def chart_gains(test, rule):
    t = test.sort_values("p_churn", ascending=False)
    cum = t.churn_6m.cumsum() / t.churn_6m.sum()
    pct = np.arange(1, len(t) + 1) / len(t)
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.plot(pct * 100, cum * 100, color=BLUE, lw=2, label="Churn model")
    ax.plot([0, 100], [0, 100], color=GREY, ls="--", label="Random")
    ax.scatter(rule["flagged"] / len(t) * 100, rule["recall_pct"], color=RED, zorder=5, s=50, label="Rule-based warning list")
    ax.axvline(10, color="#ccc", lw=0.8)
    ax.text(11, 5, f"top 10% of customers\ncatch {cum.iloc[int(len(t) * 0.1)] * 100:.0f}% of leavers", fontsize=8)
    ax.set_xlabel("% of customers contacted (highest risk first)")
    ax.set_ylabel("% of leavers reached")
    ax.legend(frameon=False, fontsize=9)
    style(ax, "Churn model, Apr-Sep 2026 (out-of-time test)")
    fig.tight_layout()
    fig.savefig("outputs/churn_gains.png", dpi=150)
    plt.close(fig)
    return float(cum.iloc[int(len(t) * 0.1)])


def chart_segments(seg):
    fig, ax = plt.subplots(figsize=(7.5, 4.4))
    cols = [BLUE, RED, GREEN, ORANGE, PURPLE]
    for (_, r), c in zip(seg.iterrows(), cols):
        ax.scatter(r.churn_risk_pct, r.avg_clv / 1e3, s=r.customers / 2.5, color=c, alpha=0.75)
        ax.annotate(f"{r.segment_360}\n{r.customers:,} customers", (r.churn_risk_pct, r.avg_clv / 1e3),
                    textcoords="offset points", xytext=(12, -4), fontsize=8)
    ax.set_xlabel("Average churn risk, next 6 months (%)")
    ax.set_ylabel("Average 5-year lifetime value (Rs thousand)")
    ax.set_xlim(0, seg.churn_risk_pct.max() * 1.45)
    style(ax, "Customer segments: value vs churn risk (bubble = customers)")
    fig.tight_layout()
    fig.savefig("outputs/segments.png", dpi=150)
    plt.close(fig)


def chart_actions(cur):
    a = cur.groupby("next_best_action").agg(customers=("p_churn", "size"), value=("action_value", "sum")).sort_values("customers")
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
    axes[0].barh(a.index, a.customers, color=BLUE)
    axes[1].barh(a.index, a.value / 1e5, color=GREEN)
    for ax, col, fmt in ((axes[0], "customers", "{:,.0f}"), (axes[1], "value", "{:,.1f}")):
        vals = a[col] if col == "customers" else a[col] / 1e5
        for y, v in enumerate(vals):
            ax.text(v, y, " " + fmt.format(v), va="center", fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    axes[0].set_title("Customers per next best action", fontsize=10)
    axes[1].set_title("Expected value (Rs lakh)", fontsize=10)
    fig.tight_layout()
    fig.savefig("outputs/next_best_actions.png", dpi=150)
    plt.close(fig)


def write_excel(cur, s, m):
    wb = Workbook()
    head, fill, base = Font(bold=True, color="FFFFFF", name="Arial"), PatternFill("solid", fgColor="1F3864"), Font(name="Arial")

    def table(ws, df, r0=3, fmts=None):
        for j, c in enumerate(df.columns, 1):
            cl = ws.cell(row=r0, column=j, value=c)
            cl.font, cl.fill, cl.alignment = head, fill, Alignment(wrap_text=True)
        for i, row in enumerate(df.itertuples(index=False), r0 + 1):
            for j, v in enumerate(row, 1):
                v = None if isinstance(v, float) and np.isnan(v) else v
                cl = ws.cell(row=i, column=j, value=v.item() if hasattr(v, "item") else v)
                cl.font = base
                if fmts and df.columns[j - 1] in fmts:
                    cl.number_format = fmts[df.columns[j - 1]]
        for j in range(1, len(df.columns) + 1):
            ws.column_dimensions[get_column_letter(j)].width = 18
        return r0 + len(df)

    ws = wb.active
    ws.title = "Summary"
    ws["A1"] = "Customer 360 Intelligence Platform: fictional retail bank (synthetic data), as of Sep 2026"
    ws["A1"].font = Font(bold=True, size=13, name="Arial")
    rows = [("Source records (core / CRM / card)", f"{m['records']['core']:,} / {m['records']['crm']:,} / {m['records']['card']:,}"),
            ("Identity matching F1 (ML vs same phone/email)", f"{m['ml_matching_test']['f1']:.3f} vs {m['deterministic_baseline_test']['f1']:.3f}"),
            ("CRM and card records linked to the right customer", f"{m['crm_card_records_linked_correctly_pct']}%"),
            ("Card-only customers found (not in core banking)", s["card_only_customers_found"]),
            ("Active customers scored", s["customers_scored"]),
            ("Churn model AUC / top-decile lift", f"{s['validation']['churn']['auc']} / {s['validation']['churn']['top_decile_lift']}x"),
            ("Total 5-year lifetime value (Rs crore)", s["total_clv_crore"]),
            ("Lifetime value of the 10% most likely to leave (Rs crore)", s["clv_at_risk_top10_churn_crore"])]
    for i, (k, v) in enumerate(rows, 3):
        ws.cell(row=i, column=1, value=k).font = base
        ws.cell(row=i, column=2, value=v).font = base
    ws.column_dimensions["A"].width = 56
    ws.column_dimensions["B"].width = 22

    ws = wb.create_sheet("Segments")
    ws["A1"] = "Segments"; ws["A1"].font = Font(bold=True, name="Arial")
    seg = pd.DataFrame(s["segments"])
    end = table(ws, seg, fmts={"avg_clv": "#,##0", "churn_risk_pct": "0.0", "digital_share": "0%", "products": "0.0"})
    ws.cell(row=end + 1, column=1, value="Total").font = Font(bold=True, name="Arial")
    ws.cell(row=end + 1, column=2, value=f"=SUM(B4:B{end})")

    ws = wb.create_sheet("Model accuracy")
    ws["A1"] = "Out-of-time test: trained on Sep 2025, tested on Apr-Sep 2026 outcomes"; ws["A1"].font = Font(bold=True, name="Arial")
    acc = pd.DataFrame([{"model": k, **{q: v[q] for q in ("test_customers", "positives", "base_rate_pct", "auc", "avg_precision", "top_decile_lift")}}
                        for k, v in s["validation"].items()])
    table(ws, acc)

    ws = wb.create_sheet("Action list")
    ws["A1"] = "Top 300 customers by expected value of their next best action"; ws["A1"].font = Font(bold=True, name="Arial")
    al = cur[cur.action_value > 0].sort_values("action_value", ascending=False).head(300).reset_index()[
        ["customer_id", "full_name", "segment_360", "city", "p_churn", "clv_5y", "next_best_action", "action_reason", "action_value"]]
    end = table(ws, al, fmts={"p_churn": "0.0%", "clv_5y": "#,##0", "action_value": "#,##0"})
    ws.cell(row=end + 1, column=8, value="Total").font = Font(bold=True, name="Arial")
    ws.cell(row=end + 1, column=9, value=f"=SUM(I4:I{end})").number_format = "#,##0"
    ws.freeze_panes = "A4"
    wb.save("outputs/customer_360_pack.xlsx")


def write_briefs(cur):
    os.makedirs("outputs/briefs", exist_ok=True)
    tools = rm.C360Tools()
    picks = []
    for action in ["RM retention call", "Offer Fixed Deposit", "Collections follow-up"]:
        sub = cur[cur.next_best_action == action].sort_values("action_value", ascending=False)
        if len(sub):
            picks.append(int(sub.index[0]))
    for cid in picks:
        open(f"outputs/briefs/customer_{cid}.md", "w").write(rm.rule_brief(tools.get_customer_360(cid)))
    return picks


def main():
    cur = pd.read_csv("outputs/customer_360.csv", index_col="customer_id")
    s = json.load(open("outputs/platform_summary.json"))
    m = json.load(open("outputs/identity_metrics.json"))
    test = pd.read_csv("outputs/churn_test_scores.csv")
    chart_identity(m)
    top10 = chart_gains(test, s["validation"]["churn"]["rule_baseline"])
    chart_segments(pd.DataFrame(s["segments"]))
    chart_actions(cur)
    write_excel(cur, s, m)
    picks = write_briefs(cur)
    print(f"charts, Excel pack and briefs for {picks} written; top 10% catch {top10:.0%} of leavers")


if __name__ == "__main__":
    main()
