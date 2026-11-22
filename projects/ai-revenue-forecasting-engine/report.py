"""Turns the engine outputs into charts, an Excel forecast pack and written management
commentary (generated from the numbers by rules, so every sentence traces to a figure)."""
import json
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

NAVY, RED, GREY, BAND = "#1F3864", "#C00000", "#7F7F7F", "#B4C7E7"
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

df = pd.read_csv("data/daily_revenue.csv", parse_dates=["date"])
fc = pd.read_csv("outputs/forecast_q1_2026_daily.csv", parse_dates=["date"])
mon = pd.read_csv("outputs/forecast_q1_2026_monthly.csv")
bt = pd.read_csv("outputs/backtest_daily.csv", parse_dates=["date", "origin"])
scores = pd.read_csv("outputs/backtest_scores.csv")
btq = pd.read_csv("outputs/backtest_by_quarter.csv")
scen = pd.read_csv("outputs/scenarios.csv")
imp = pd.read_csv("outputs/driver_importance.csv", index_col=0).share
S = json.load(open("outputs/summary.json"))

# ---------------- charts
hist = df.groupby("date").revenue_lakh.sum()
f = fc.groupby("date")[["ensemble", "p10", "p90"]].sum()
fig, ax = plt.subplots(figsize=(11, 3.8))
h7 = hist.rolling(7).mean().loc["2024-07-01":]
ax.plot(h7.index, h7.values, color=NAVY, lw=1, label="Actual revenue (7-day average)")
f7 = f.rolling(7, min_periods=1).mean()
ax.plot(f7.index, f7.ensemble, color=RED, lw=1.2, label="Forecast (7-day average)")
ax.fill_between(f7.index, f7.p10, f7.p90, color=RED, alpha=0.15, label="P10-P90 range")
ax.axvline(pd.Timestamp("2025-12-31"), color=GREY, ls="--", lw=0.8)
ax.set_ylabel("Rs lakh per day")
ax.set_title(f"Q1 2026 revenue forecast: Rs {S['q1_2026_forecast_crore']:.1f} crore "
             f"(range Rs {S['q1_2026_p10_crore']:.1f}-{S['q1_2026_p90_crore']:.1f} crore), "
             f"{S['yoy_growth']:+.1%} vs Q1 2025")
ax.legend(frameon=False, fontsize=8, loc="upper left")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b-%y"))
fig.tight_layout()
fig.savefig("outputs/chart_forecast.png", dpi=150)

fig, axes = plt.subplots(1, 2, figsize=(11, 3.4))
lab = {"seasonal_naive": "Seasonal naive", "holt_winters": "Holt-Winters", "lightgbm": "LightGBM", "ensemble": "Ensemble"}
axes[0].bar([lab[m] for m in scores.model], scores.daily_wape * 100,
            color=[GREY, GREY, NAVY, RED])
for i, v in enumerate(scores.daily_wape * 100):
    axes[0].text(i, v + 0.2, f"{v:.1f}%", ha="center", fontsize=8)
axes[0].set_ylabel("Daily error (WAPE, %)")
axes[0].set_title("Backtest: forecasting Q2, Q3 and Q4 2025")
q = btq.set_index("quarter")
x = range(len(q))
for i, (m, c) in enumerate([("actual", NAVY), ("holt_winters", GREY), ("ensemble", RED)]):
    axes[1].bar([k + (i - 1) * 0.27 for k in x], q[m], width=0.27, color=c, label={"actual": "Actual", "holt_winters": "Holt-Winters", "ensemble": "Ensemble"}[m])
axes[1].set_xticks(list(x), q.index)
axes[1].set_ylim(80, 110)
axes[1].set_ylabel("Rs crore")
axes[1].set_title("Quarterly totals: Holt-Winters misses Diwali in Q4")
axes[1].legend(frameon=False, fontsize=8)
fig.tight_layout()
fig.savefig("outputs/chart_backtest.png", dpi=150)

fig, axes = plt.subplots(1, 2, figsize=(11, 3.4))
s2 = scen.sort_values("change_crore")
axes[0].barh(s2.scenario, s2.change_crore, color=[RED if v < 0 else NAVY for v in s2.change_crore])
for i, v in enumerate(s2.change_crore):
    axes[0].text(v + (0.1 if v >= 0 else -0.1), i, f"{v:+.2f}", va="center", ha="left" if v >= 0 else "right", fontsize=8)
axes[0].axvline(0, color=GREY, lw=0.8)
axes[0].set_xlim(min(s2.change_crore.min() * 2.2, -1), s2.change_crore.max() * 1.25)
axes[0].set_xlabel("Change in Q1 2026 revenue (Rs crore)")
axes[0].set_title("What-if scenarios")
names = {"discount_pct": "Discount %", "dow": "Day of week", "log_marketing": "Marketing spend", "doy_sin": "Time of year",
         "doy_cos": "Time of year (2)", "level_fest": "Festival in recent level", "gap": "Days ahead", "line": "Product line",
         "month": "Month", "republic_day_sale": "Republic Day sale", "holi": "Holi", "diwali_window": "Diwali",
         "independence_day_sale": "Independence Day sale"}
top = imp.head(8)[::-1]
axes[1].barh([names.get(i, i) for i in top.index], top.values * 100, color=NAVY)
axes[1].set_xlabel("Share of model attribution in Q1 forecast (%)")
axes[1].set_title("What drives the LightGBM forecast")
fig.tight_layout()
fig.savefig("outputs/chart_scenarios_drivers.png", dpi=150)

# ---------------- commentary
by_line = mon.groupby("product_line")[["p50", "last_year"]].sum()
by_line["yoy"] = by_line.p50 / by_line.last_year - 1
fast = by_line.yoy.idxmax()
slow = by_line.yoy.idxmin()
mtot = mon.groupby("month")[["p50", "last_year"]].sum()
lg = S["backtest"]["lightgbm"]
hw = S["backtest"]["holt_winters"]
best = scen.loc[scen.change_crore.idxmax()]
worst = scen.loc[scen.change_crore.idxmin()]
lines = [
    "# Q1 2026 Revenue Forecast: Management Commentary",
    "",
    "*Generated automatically from the forecast outputs. Fictional company, synthetic data.*",
    "",
    "## Headline",
    f"- Q1 2026 revenue is forecast at **Rs {S['q1_2026_forecast_crore']:.1f} crore**, up {S['yoy_growth']:.1%} on Q1 2025 "
    f"(Rs {S['q1_2025_actual_crore']:.1f} crore). The likely range is Rs {S['q1_2026_p10_crore']:.1f}-{S['q1_2026_p90_crore']:.1f} crore (P10-P90).",
    f"- By month: " + "; ".join(f"{m} Rs {r.p50 / 100:.1f} crore ({r.p50 / r.last_year - 1:+.1%})" for m, r in mtot.iterrows()) + ".",
    f"- {fast} grows fastest ({by_line.loc[fast, 'yoy']:+.1%}); {slow} is slowest ({by_line.loc[slow, 'yoy']:+.1%}).",
    "",
    "## Drivers",
    f"- The model attributes the most to discount levels ({imp.get('discount_pct', 0):.0%}), the day of the week ({imp.get('dow', 0):.0%}) "
    f"and marketing spend ({imp.get('log_marketing', 0):.0%}).",
    f"- The Republic Day sale (24-26 January) and Holi (4 March 2026) are in the plan and lift January and early March.",
    "",
    "## What-if scenarios",
    f"- Largest upside: **{best.scenario}** adds Rs {best.change_crore:.2f} crore ({best.change_pct:+.1%}). This is revenue, not profit: deeper discounts cut margin.",
    f"- Largest downside: **{worst.scenario}** reduces revenue by Rs {abs(worst.change_crore):.2f} crore ({worst.change_pct:+.1%}).",
    "",
    "## How far to trust it",
    f"- Backtested on Q2, Q3 and Q4 2025, the LightGBM model was off by {lg['daily_wape']:.1%} a day on average (WAPE) and "
    f"{lg['quarterly_total_error']:.1%} on quarterly totals, with almost no bias ({lg['bias']:+.1%}).",
    f"- Holt-Winters, which knows nothing about festivals, under-forecast by {abs(hw['bias']):.1%} overall and missed the Diwali quarter badly, "
    f"so the ensemble gives it only {S['weights']['holt_winters']:.0%} weight.",
    "- Risks: a festival date shift, a change in the marketing plan, or a pricing decision not in the plan would move the forecast.",
]
open("outputs/COMMENTARY.md", "w").write("\n".join(lines) + "\n")

# ---------------- Excel forecast pack
wb = Workbook()
hdr = PatternFill("solid", fgColor="1F3864")


def sheet(ws, frame, title, fmts):
    ws["A1"] = title
    ws["A1"].font = Font(name="Arial", bold=True, size=13, color="1F3864")
    for j, c in enumerate(frame.columns, 1):
        cell = ws.cell(row=3, column=j, value=c)
        cell.font = Font(name="Arial", bold=True, color="FFFFFF")
        cell.fill = hdr
        ws.column_dimensions[get_column_letter(j)].width = max(14, len(str(c)) + 4)
    for i, row in enumerate(frame.itertuples(index=False), 4):
        for j, v in enumerate(row, 1):
            cell = ws.cell(row=i, column=j, value=v)
            cell.font = Font(name="Arial")
            col = frame.columns[j - 1]
            if col in fmts:
                cell.number_format = fmts[col]


ws = wb.active
ws.title = "Monthly forecast"
m = mon.copy()
m.columns = ["Month", "Product line", "P10 (Rs lakh)", "P50 forecast (Rs lakh)", "P90 (Rs lakh)", "Same month 2025 (Rs lakh)", "YoY growth"]
sheet(ws, m, "Q1 2026 revenue forecast by month and product line", {c: "#,##0.0" for c in m.columns[2:6]} | {"YoY growth": "0.0%"})
n = len(m) + 4
ws.cell(row=n, column=1, value="Total Q1 2026").font = Font(name="Arial", bold=True)
for col in "CDEF":
    ws[f"{col}{n}"] = f"=SUM({col}4:{col}{n - 1})"
    ws[f"{col}{n}"].number_format = "#,##0.0"
    ws[f"{col}{n}"].font = Font(name="Arial", bold=True)
ws[f"G{n}"] = f"=D{n}/F{n}-1"
ws[f"G{n}"].number_format = "0.0%"
ws.cell(row=n + 2, column=1, value="P10/P90: 10th and 90th percentile of backtest errors on monthly totals (split conformal).").font = Font(name="Arial", italic=True, size=9)

d = fc[["date", "product_line", "seasonal_naive", "holt_winters", "lightgbm", "ensemble", "p10", "p90", "discount_pct", "marketing_lakh"]].copy()
d["date"] = d.date.dt.date
sheet(wb.create_sheet("Daily forecast"), d.round(2), "Daily forecast by model (Rs lakh)", {c: "#,##0.00" for c in d.columns[2:8]})
sheet(wb.create_sheet("Backtest"), scores, "Backtest accuracy: Q2-Q4 2025", {"daily_wape": "0.0%", "quarterly_total_error": "0.0%", "bias": "0.0%", "weight": "0.00"})
sheet(wb.create_sheet("Scenarios"), scen, "What-if scenarios for Q1 2026 (Rs crore)", {"change_pct": "0.0%"})
wb.save("outputs/forecast_pack_q1_2026.xlsx")
print("report done")
