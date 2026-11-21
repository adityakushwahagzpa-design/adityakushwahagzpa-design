"""
Financial Statement Analyzer

Extracts four years of income statement, balance sheet and cash flow data for 12 large Indian
non-financial companies (Yahoo Finance) and calculates:
  * growth: revenue and profit growth, 3-year CAGR
  * profitability: gross, EBITDA, operating and net margins, ROE, ROA, ROCE, DuPont breakdown
  * liquidity and leverage: current and quick ratios, debt to equity, interest coverage
  * cash quality: operating cash flow to net income, free cash flow margin
  * scores: Piotroski F-score (0-9) and Altman Z''-score for emerging markets
Outputs an Excel workbook where every ratio is a live formula on the extracted statements,
plus a comparison CSV, charts and a Markdown report.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)
COMPANIES = {"RELIANCE": "Reliance Industries", "TCS": "Tata Consultancy Services", "INFY": "Infosys",
             "HINDUNILVR": "Hindustan Unilever", "ITC": "ITC", "LT": "Larsen & Toubro", "MARUTI": "Maruti Suzuki",
             "SUNPHARMA": "Sun Pharmaceutical", "ASIANPAINT": "Asian Paints", "TATASTEEL": "Tata Steel",
             "BHARTIARTL": "Bharti Airtel", "ULTRACEMCO": "UltraTech Cement"}

# line item -> (statement, candidate row names in Yahoo Finance)
ITEMS = {
    "Revenue": ("is", ["Total Revenue", "Operating Revenue"]),
    "Gross profit": ("is", ["Gross Profit"]),
    "EBITDA": ("is", ["EBITDA", "Normalized EBITDA"]),
    "EBIT": ("is", ["EBIT", "Operating Income"]),
    "Interest expense": ("is", ["Interest Expense", "Interest Expense Non Operating"]),
    "Net income": ("is", ["Net Income Common Stockholders", "Net Income", "Net Income From Continuing Operation Net Minority Interest"]),
    "Total assets": ("bs", ["Total Assets"]),
    "Current assets": ("bs", ["Current Assets"]),
    "Inventory": ("bs", ["Inventory"]),
    "Current liabilities": ("bs", ["Current Liabilities"]),
    "Total liabilities": ("bs", ["Total Liabilities Net Minority Interest"]),
    "Total debt": ("bs", ["Total Debt"]),
    "Shareholders' equity": ("bs", ["Stockholders Equity", "Common Stock Equity"]),
    "Retained earnings": ("bs", ["Retained Earnings"]),
    "Shares outstanding": ("bs", ["Ordinary Shares Number", "Share Issued"]),
    "Operating cash flow": ("cf", ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]),
    "Capital expenditure": ("cf", ["Capital Expenditure"]),
    "Free cash flow": ("cf", ["Free Cash Flow"]),
}
CRORE = 1e7


# ------------------------------------------------------------------ extraction
def extract(sym):
    import yfinance as yf
    t = yf.Ticker(sym + ".NS")
    sheets = {"is": t.income_stmt, "bs": t.balance_sheet, "cf": t.cashflow}
    data = {}
    for item, (st, names) in ITEMS.items():
        df = sheets[st]
        row = next((df.loc[n] for n in names if n in df.index and df.loc[n].notna().any()), None)
        data[item] = row
    f = pd.DataFrame({k: v for k, v in data.items() if v is not None}).T
    f = f.reindex(list(ITEMS))
    f.columns = [f"FY{pd.Timestamp(c).year}" if pd.Timestamp(c).month <= 6 else f"FY{pd.Timestamp(c).year + 1}" for c in f.columns]
    f = f.loc[:, ~f.columns.duplicated()].sort_index(axis=1)
    f = f.loc[:, f.loc[["Revenue", "Net income", "Total assets"]].notna().all()]  # keep complete years
    scale = pd.Series(1 / CRORE, index=f.index)
    scale["Shares outstanding"] = 1 / CRORE   # shares in crore
    return f.mul(scale, axis=0).astype(float).round(2).tail(4) if f.shape[1] else f


# ------------------------------------------------------------------ ratios (python, mirrored as Excel formulas)
RATIOS = [  # name, numerator, denominator, kind
    ("Revenue growth %", "Revenue", None, "growth"),
    ("Net income growth %", "Net income", None, "growth"),
    ("Gross margin %", "Gross profit", "Revenue", "pct"),
    ("EBITDA margin %", "EBITDA", "Revenue", "pct"),
    ("Operating (EBIT) margin %", "EBIT", "Revenue", "pct"),
    ("Net margin %", "Net income", "Revenue", "pct"),
    ("Return on equity (ROE) %", "Net income", "Shareholders' equity", "pct"),
    ("Return on assets (ROA) %", "Net income", "Total assets", "pct"),
    ("Return on capital employed (ROCE) %", "EBIT", "CAPEMP", "pct"),
    ("Asset turnover (x)", "Revenue", "Total assets", "x"),
    ("Equity multiplier (x)", "Total assets", "Shareholders' equity", "x"),
    ("Current ratio (x)", "Current assets", "Current liabilities", "x"),
    ("Quick ratio (x)", "QUICK", "Current liabilities", "x"),
    ("Debt to equity (x)", "Total debt", "Shareholders' equity", "x"),
    ("Interest coverage (x)", "EBIT", "Interest expense", "x"),
    ("Operating cash flow / net income (x)", "Operating cash flow", "Net income", "x"),
    ("Free cash flow margin %", "Free cash flow", "Revenue", "pct"),
]


def ratios(f):
    g = lambda k: f.loc[k] if k in f.index else pd.Series(np.nan, index=f.columns)
    special = {"CAPEMP": g("Total assets") - g("Current liabilities"),
               "QUICK": g("Current assets") - g("Inventory").fillna(0)}
    out = {}
    for name, num, den, kind in RATIOS:
        n = special.get(num, g(num))
        if kind == "growth":
            out[name] = (n / n.shift(1) - 1) * 100
        else:
            d = special.get(den, g(den)).replace(0, np.nan)
            out[name] = n / d * (100 if kind == "pct" else 1)
    return pd.DataFrame(out).T.round(2)


def piotroski(f):
    """9-point F-score on the latest year vs the year before."""
    if f.shape[1] < 2:
        return None, {}
    c, p = f.columns[-1], f.columns[-2]
    g = lambda k, y: f.at[k, y] if k in f.index else np.nan
    roa = lambda y: g("Net income", y) / g("Total assets", y)
    cr = lambda y: g("Current assets", y) / g("Current liabilities", y)
    lev = lambda y: g("Total debt", y) / g("Total assets", y)
    gm = lambda y: g("Gross profit", y) / g("Revenue", y)
    at = lambda y: g("Revenue", y) / g("Total assets", y)
    tests = {
        "positive ROA": roa(c) > 0, "positive operating cash flow": g("Operating cash flow", c) > 0,
        "ROA improving": roa(c) > roa(p), "cash flow above net income": g("Operating cash flow", c) > g("Net income", c),
        "leverage falling": lev(c) <= lev(p), "current ratio improving": cr(c) > cr(p),
        "no share dilution": g("Shares outstanding", c) <= g("Shares outstanding", p) * 1.001,
        "gross margin improving": gm(c) > gm(p), "asset turnover improving": at(c) > at(p),
    }
    tests = {k: bool(v) if pd.notna(v) else False for k, v in tests.items()}
    return int(sum(tests.values())), tests


def altman_em(f):
    """Altman Z''-score for emerging-market companies: 3.25 + 6.56 X1 + 3.26 X2 + 6.72 X3 + 1.05 X4."""
    c = f.columns[-1]
    g = lambda k: f.at[k, c] if k in f.index else np.nan
    ta = g("Total assets")
    x1 = (g("Current assets") - g("Current liabilities")) / ta
    x2 = g("Retained earnings") / ta
    x3 = g("EBIT") / ta
    x4 = g("Shareholders' equity") / g("Total liabilities")
    z = 3.25 + 6.56 * x1 + 3.26 * x2 + 6.72 * x3 + 1.05 * x4
    zone = "safe" if z > 5.85 else ("grey" if z >= 4.15 else "distress") if pd.notna(z) else "n/a"
    return (round(float(z), 2) if pd.notna(z) else None), zone


# ------------------------------------------------------------------ Excel with live formulas
def write_excel(all_f, comp, scores):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws0 = wb.active
    ws0.title = "Comparison"
    bold, blue, hdr = Font(name="Arial", bold=True), Font(name="Arial", color="0000FF"), PatternFill("solid", fgColor="EDE9FE")
    normal = Font(name="Arial")
    links = {}
    for sym, f in all_f.items():
        ws = wb.create_sheet(sym)
        ws["A1"] = f"{COMPANIES[sym]} ({sym}.NS) — ₹ crore, from Yahoo Finance"; ws["A1"].font = Font(name="Arial", bold=True, size=12)
        ws["A2"] = "Blue = extracted input · black = formula"; ws["A2"].font = Font(name="Arial", italic=True, size=9)
        years = list(f.columns)
        ws.cell(4, 1, "Line item").font = bold
        for j, y in enumerate(years):
            c = ws.cell(4, 2 + j, y); c.font = bold; c.fill = hdr; c.alignment = Alignment(horizontal="right")
        row_of = {}
        for i, item in enumerate(ITEMS):
            r = 5 + i
            row_of[item] = r
            ws.cell(r, 1, item).font = normal
            for j, y in enumerate(years):
                v = f.at[item, y] if item in f.index else np.nan
                c = ws.cell(r, 2 + j, None if pd.isna(v) else float(v))
                c.font = blue; c.number_format = '#,##0;(#,##0);"-"'
        start = 5 + len(ITEMS) + 2
        ws.cell(start - 1, 1, "Ratio").font = bold
        for j, y in enumerate(years):
            c = ws.cell(start - 1, 2 + j, y); c.font = bold; c.fill = hdr
        for i, (name, num, den, kind) in enumerate(RATIOS):
            r = start + i
            ws.cell(r, 1, name).font = normal
            for j in range(len(years)):
                col = get_column_letter(2 + j)
                ref = lambda k: f"{col}{row_of[k]}"
                if num == "CAPEMP":
                    n = f"({ref('Total assets')}-{ref('Current liabilities')})"
                elif num == "QUICK":
                    n = f"({ref('Current assets')}-{ref('Inventory')})"
                else:
                    n = ref(num)
                if kind == "growth":
                    if j == 0:
                        continue
                    prev = get_column_letter(1 + j)
                    formula = f"=IFERROR({col}{row_of[num]}/{prev}{row_of[num]}-1,\"\")"
                else:
                    d = f"({ref('Total assets')}-{ref('Current liabilities')})" if den == "CAPEMP" else ref(den)
                    formula = f"=IFERROR({n}/{d},\"\")"
                c = ws.cell(r, 2 + j, formula); c.font = normal
                c.number_format = "0.0%" if kind in ("pct", "growth") else '0.00"x"'
            links[(sym, name)] = (start + i, get_column_letter(1 + len(years)))
        ws.column_dimensions["A"].width = 38
        for j in range(len(years)):
            ws.column_dimensions[get_column_letter(2 + j)].width = 13
        ws.freeze_panes = "B5"

    ws0["A1"] = "Latest-year comparison (linked to each company sheet)"; ws0["A1"].font = Font(name="Arial", bold=True, size=12)
    syms = list(all_f)
    ws0.cell(3, 1, "Ratio").font = bold
    for j, sym in enumerate(syms):
        c = ws0.cell(3, 2 + j, sym); c.font = bold; c.fill = hdr
    for i, (name, _, _, kind) in enumerate(RATIOS):
        ws0.cell(4 + i, 1, name).font = normal
        for j, sym in enumerate(syms):
            r, col = links[(sym, name)]
            c = ws0.cell(4 + i, 2 + j, f"='{sym}'!{col}{r}"); c.font = Font(name="Arial", color="008000")
            c.number_format = "0.0%" if kind in ("pct", "growth") else '0.00"x"'
    base = 5 + len(RATIOS)
    ws0.cell(base, 1, "Scores (calculated in Python)").font = bold
    for k, lab in enumerate(["Piotroski F-score (0-9)", "Altman Z''-score (EM)", "Altman zone", "Revenue CAGR, 3 years %"]):
        ws0.cell(base + 1 + k, 1, lab).font = normal
        for j, sym in enumerate(syms):
            v = scores[sym][["f_score", "z_score", "z_zone", "revenue_cagr_%"][k]]
            ws0.cell(base + 1 + k, 2 + j, v).font = normal
    ws0.column_dimensions["A"].width = 38
    for j in range(len(syms)):
        ws0.column_dimensions[get_column_letter(2 + j)].width = 12
    ws0.freeze_panes = "B4"
    wb.save(OUT / "Financial_Statement_Analysis.xlsx")


# ------------------------------------------------------------------ charts
def charts(comp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    c = comp.sort_values("Return on capital employed (ROCE) %")
    fig, ax = plt.subplots(1, 2, figsize=(13, 5))
    y = np.arange(len(c))
    for k, (col, colr) in enumerate([("Net margin %", "#7c3aed"), ("Return on equity (ROE) %", "#0ea5e9"),
                                     ("Return on capital employed (ROCE) %", "#f59e0b")]):
        ax[0].barh(y + (k - 1) * 0.27, c[col], 0.27, color=colr, label=col.replace(" %", ""))
    ax[0].set_yticks(y, c.index); ax[0].legend(frameon=False, fontsize=8, loc="lower right")
    ax[0].set_title("Profitability, latest fiscal year (%)")
    ax[1].scatter(comp["Revenue CAGR 3y %"], comp["Debt to equity (x)"], s=comp["Piotroski F-score"] * 40 + 20,
                  color="#7c3aed", alpha=0.7)
    for s, r in comp.iterrows():
        ax[1].annotate(s, (r["Revenue CAGR 3y %"], r["Debt to equity (x)"]), fontsize=8, xytext=(4, 3), textcoords="offset points")
    ax[1].set_xlabel("Revenue CAGR, 3 years (%)"); ax[1].set_ylabel("Debt to equity (x)")
    ax[1].set_title("Growth vs leverage (bubble size = Piotroski F-score)")
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "chart_profitability_growth.png", dpi=150); plt.close(fig)


# ------------------------------------------------------------------ main
def main():
    all_f, rows, scores, failed = {}, [], {}, []
    for sym in COMPANIES:
        try:
            f = extract(sym)
            if f.shape[1] < 2:
                raise ValueError("fewer than 2 complete years")
        except Exception as e:
            failed.append(f"{sym}: {e}"); print(f"{sym}: failed ({e})"); continue
        all_f[sym] = f
        r = ratios(f)
        fs, tests = piotroski(f)
        z, zone = altman_em(f)
        rev = f.loc["Revenue"].dropna()
        cagr = ((rev.iloc[-1] / rev.iloc[0]) ** (1 / (len(rev) - 1)) - 1) * 100 if len(rev) > 1 else np.nan
        latest = r.iloc[:, -1]
        rows.append({"symbol": sym, "company": COMPANIES[sym], "latest FY": f.columns[-1],
                     "Revenue ₹ cr": f.at["Revenue", f.columns[-1]], "Net income ₹ cr": f.at["Net income", f.columns[-1]],
                     **latest.to_dict(), "Revenue CAGR 3y %": round(cagr, 2), "Piotroski F-score": fs,
                     "Altman Z'' (EM)": z, "Altman zone": zone})
        scores[sym] = {"f_score": fs, "z_score": z, "z_zone": zone, "revenue_cagr_%": round(cagr, 2), "f_tests": tests}
        print(f"{sym}: {list(f.columns)}, F={fs}, Z={z} ({zone})")
    comp = pd.DataFrame(rows).set_index("symbol")
    comp.to_csv(OUT / "ratio_comparison.csv")
    for sym, f in all_f.items():
        pd.concat([f, ratios(f)]).to_csv(OUT / f"{sym}_statements_ratios.csv")
    write_excel(all_f, comp, scores)
    charts(comp)

    rank = lambda col, asc=False: comp[col].sort_values(ascending=asc).dropna()
    summary = {
        "companies_analysed": int(len(comp)), "failed": failed, "fiscal_years": sorted({c for f in all_f.values() for c in f.columns}),
        "highest_roce": rank("Return on capital employed (ROCE) %").head(3).round(1).to_dict(),
        "lowest_roce": rank("Return on capital employed (ROCE) %", True).head(3).round(1).to_dict(),
        "highest_net_margin": rank("Net margin %").head(3).round(1).to_dict(),
        "fastest_revenue_cagr": rank("Revenue CAGR 3y %").head(3).round(1).to_dict(),
        "most_leveraged_de": rank("Debt to equity (x)").head(3).round(2).to_dict(),
        "f_scores": comp["Piotroski F-score"].to_dict(), "altman": comp[["Altman Z'' (EM)", "Altman zone"]].to_dict(orient="index"),
        "median_roe_%": round(float(comp["Return on equity (ROE) %"].median()), 1),
        "cash_conversion_below_1": comp.index[comp["Operating cash flow / net income (x)"] < 1].tolist(),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    show = ["company", "latest FY", "Revenue ₹ cr", "Revenue CAGR 3y %", "Net margin %", "Return on equity (ROE) %",
            "Return on capital employed (ROCE) %", "Debt to equity (x)", "Interest coverage (x)",
            "Operating cash flow / net income (x)", "Piotroski F-score", "Altman Z'' (EM)", "Altman zone"]
    md = ["# Financial Statement Analysis — 12 Indian companies", "",
          "Annual statements from Yahoo Finance (₹ crore, consolidated). Every ratio in the Excel workbook is a live formula.", "",
          comp[show].round(2).to_markdown(), "", "![Profitability](chart_profitability_growth.png)", "",
          "## Piotroski F-score detail", "",
          pd.DataFrame({s: v["f_tests"] for s, v in scores.items()}).replace({True: "✓", False: "✗"}).to_markdown(), "",
          "_Altman Z''-score (emerging markets): above 5.85 safe, 4.15–5.85 grey zone, below 4.15 distress. For learning purposes only._"]
    (OUT / "REPORT.md").write_text("\n".join(md))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
