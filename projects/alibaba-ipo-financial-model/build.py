"""Build an original Alibaba Group IPO financial model (Sep 2014) with formulas."""
import datetime as dt
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.series import SeriesLabel
from openpyxl.formatting.rule import ColorScaleRule

SRC = ("Source: Alibaba Group F-1/A Amendment No. 7 (15 Sep 2014), "
       "https://www.sec.gov/Archives/edgar/data/0001577552/000119312514341794/d709111df1a.htm")
HIST = ["B", "C", "D"]                       # FY2012-FY2014
FC = [chr(c) for c in range(ord("E"), ord("N") + 1)]  # FY2015E-FY2024E
ALL = HIST + FC
YEARS = ["FY2012A", "FY2013A", "FY2014A"] + [f"FY{y}E" for y in range(2015, 2025)]
NOTE = "O"

F = "Arial"
BLUE, GREEN, BLACK = "0000FF", "008000", "000000"
NAVY = PatternFill("solid", fgColor="1F3864")
SUB = PatternFill("solid", fgColor="D9E1F2")
YEL = PatternFill("solid", fgColor="FFFF00")
FCF_FILL = PatternFill("solid", fgColor="F2F2F2")
thin = Side(style="thin", color="999999")

NUM = '#,##0;(#,##0);"-"'
NUM1 = '#,##0.0;(#,##0.0);"-"'
PCT = '0.0%;(0.0%);"-"'
MULT = '0.0"x"'
USD = '$#,##0.00;($#,##0.00);"-"'

wb = Workbook()
wb.remove(wb.active)


def sheet(name, title, sub="RMB in millions unless stated; fiscal years end 31 March"):
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    ws["A1"] = title
    ws["A1"].font = Font(name=F, size=14, bold=True, color="1F3864")
    ws["A2"] = sub
    ws["A2"].font = Font(name=F, size=9, italic=True, color="595959")
    ws.column_dimensions["A"].width = 52
    for c in ALL:
        ws.column_dimensions[c].width = 11.5
    ws.column_dimensions[NOTE].width = 70
    return ws


def year_header(ws, row, cols=ALL):
    for c in ["A"] + ALL + [NOTE]:
        ws[f"{c}{row}"].fill = NAVY
    for c, y in zip(ALL, YEARS):
        if c in cols:
            cell = ws[f"{c}{row}"]
            cell.value = y
            cell.font = Font(name=F, bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center")
    ws[f"{NOTE}{row}"] = "Notes / source"
    ws[f"{NOTE}{row}"].font = Font(name=F, bold=True, color="FFFFFF")


def section(ws, row, text):
    ws[f"A{row}"] = text
    ws[f"A{row}"].font = Font(name=F, bold=True)
    for c in ["A"] + ALL + [NOTE]:
        ws[f"{c}{row}"].fill = SUB


def put(ws, ref, val, fmt=NUM, color=None, bold=False, fill=None):
    cell = ws[ref]
    cell.value = val
    if color is None:
        if isinstance(val, str) and val.startswith("="):
            color = GREEN if "!" in val else BLACK
        else:
            color = BLUE
    cell.font = Font(name=F, color=color, bold=bold)
    if fmt:
        cell.number_format = fmt
    if fill:
        cell.fill = fill
    return cell


def label(ws, row, text, bold=False, indent=0, note=None):
    c = ws[f"A{row}"]
    c.value = text
    c.font = Font(name=F, bold=bold)
    c.alignment = Alignment(indent=indent)
    if note:
        ws[f"{NOTE}{row}"] = note
        ws[f"{NOTE}{row}"].font = Font(name=F, size=8, italic=True, color="595959")


def note(ws, row, text):
    ws[f"{NOTE}{row}"] = text
    ws[f"{NOTE}{row}"].font = Font(name=F, size=8, italic=True, color="595959")


def total_border(ws, row, cols=ALL):
    for c in cols:
        ws[f"{c}{row}"].border = Border(top=thin)


def prev(c):
    return chr(ord(c) - 1)


# ---------------------------------------------------------------- Assumptions
A = sheet("Assumptions", "Assumptions",
          "Blue = hardcoded input  |  Black = formula  |  Green = link to another sheet  |  Yellow = key lever")
A.column_dimensions["B"].width = 14
r = 4
section(A, r, "General inputs")
r += 1
gen = {}


def gin(key, text, val, fmt, nt, key_lever=False):
    global r
    label(A, r, text, note=nt)
    put(A, f"B{r}", val, fmt, fill=YEL if key_lever else None)
    gen[key] = f"Assumptions!$B${r}"
    r += 1


gin("fx", "RMB per US$ (prospectus translation rate)", 6.2036, "0.0000",
    "F-1/A No. 7: RMB6.2036 = US$1.00, Federal Reserve H.10 rate on 30 Jun 2014")
gin("ipo_price", "IPO price per ADS (US$)", 68, USD,
    "Priced 18 Sep 2014 at US$68 (top of the US$66-68 range in F-1/A No. 7); 1 ADS = 1 ordinary share", True)
gin("first_close", "First-day closing price per ADS (US$)", 93.89, USD,
    "Reference only: NYSE close on 19 Sep 2014, the first trading day")
gin("primary_ads", "ADSs sold by Alibaba (primary, millions)", 123.076931, "#,##0.0",
    "F-1/A No. 7: 123,076,931 ADSs offered by the company (base deal)")
gin("total_ads", "Total ADSs offered incl. selling shareholders (millions)", 320.1061, "#,##0.0",
    "F-1/A No. 7: 320,106,100 ADSs (368,122,000 with the over-allotment option)")
gin("fee", "Underwriting fees and offering costs (% of gross)", 0.01, PCT, "Assumption")
gin("basic", "Ordinary shares outstanding after the offering (millions)", 2465.005966, "#,##0.0",
    "F-1/A No. 7: 2,465,005,966; includes conversion of all convertible preference shares")
gin("options", "Share options outstanding (millions)", 53.692833, "#,##0.0",
    "F-1/A No. 7, as of 30 Jun 2014. Counted in full with no exercise proceeds (conservative)")
gin("rsus", "Unvested RSUs (millions)", 45.899831, "#,##0.0", "F-1/A No. 7, as of 30 Jun 2014")
gin("val_date", "Valuation date (IPO pricing date)", dt.date(2014, 9, 18), "dd-mmm-yyyy",
    "Cash flows are discounted to this date")
gin("debt_rate", "Interest rate on bank borrowings (on opening balance)", 0.045, PCT,
    "Assumption; FY2014 interest expense of RMB2,195m on ~RMB28.8bn average debt includes upfront fees")
gin("cash_yield", "Interest yield on cash and short-term investments", 0.03, PCT, "Assumption")
gin("intang_life", "Remaining life of FY2014 intangible assets (years)", 5, "0", "Assumption, straight-line")
gin("tg", "Terminal FCF growth rate", 0.03, PCT, "Assumption: long-run nominal growth", True)
gin("alipay", "Value of Alipay / Ant profit share (US$ bn)", 0, "#,##0.0",
    "Optional: Alibaba is entitled to 37.5% of Alipay's pre-tax profit (F-1/A). Set to 0 in the base case")
gin("nci", "Noncontrolling interests at 31 Mar 2014 (book)", 1079, NUM, "Balance sheet, 31 Mar 2014")

r += 1
year_header(A, r)
hdr_row = r
r += 1
asm = {}


def ain(key, text, vals, fmt=PCT, nt="Assumption", lever=False, hist=None):
    """vals: 10 forecast inputs, or 'hold' to carry the FY2014 ratio forward."""
    global r
    label(A, r, text, note=nt)
    if hist:
        for c, f in zip(HIST, hist):
            if f is not None:
                put(A, f"{c}{r}", f, fmt)
    for i, c in enumerate(FC):
        if vals == "hold":
            put(A, f"{c}{r}", f"=D{r}" if i == 0 else f"={prev(c)}{r}", fmt)
        else:
            put(A, f"{c}{r}", vals[i], fmt, fill=YEL if lever else None)
    asm[key] = r
    r += 1


section(A, r, "Revenue drivers"); r += 1
ain("gmv_g", "China retail GMV growth", [0.45, 0.35, 0.28, 0.22, 0.18, 0.15, 0.12, 0.10, 0.08, 0.06],
    nt="Assumption; GMV grew 62% in FY2013 and 56% in FY2014", lever=True,
    hist=[None, "=Revenue!C6", "=Revenue!D6"])
ain("yield", "China commerce revenue as % of GMV (effective take rate)",
    [0.027, 0.0275, 0.028, 0.0285, 0.029, 0.029, 0.029, 0.029, 0.029, 0.029], fmt='0.00%',
    nt="Assumption; includes wholesale revenue, so it is a yield on retail GMV, not a pure commission rate",
    lever=True, hist=["=Revenue!B7", "=Revenue!C7", "=Revenue!D7"])
ain("intl_g", "International commerce growth", [0.15, 0.15, 0.14, 0.13, 0.12, 0.10, 0.09, 0.08, 0.07, 0.06],
    hist=[None, "=Revenue!C12", "=Revenue!D12"])
ain("cloud_g", "Cloud computing and Internet infrastructure growth",
    [0.50, 0.50, 0.45, 0.40, 0.35, 0.30, 0.25, 0.20, 0.15, 0.10], hist=[None, "=Revenue!C14", "=Revenue!D14"])
ain("other_g", "Other revenue growth", [0.40, 0.30, 0.25, 0.20, 0.15, 0.12, 0.10, 0.08, 0.07, 0.06],
    hist=[None, "=Revenue!C16", "=Revenue!D16"])

section(A, r, "Costs (% of revenue)"); r += 1
ain("cor", "Cost of revenue", [0.27, 0.28, 0.29, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30, 0.30],
    nt="Assumption: rises with the mobile, logistics and cloud mix", lever=True,
    hist=["=-IS!B11/IS!B10", "=-IS!C11/IS!C10", "=-IS!D11/IS!D10"])
ain("pd", "Product development", [0.10] * 10, hist=["=-IS!B15/IS!B10", "=-IS!C15/IS!C10", "=-IS!D15/IS!D10"])
ain("sm", "Sales and marketing", [0.09] + [0.095] * 9, hist=["=-IS!B16/IS!B10", "=-IS!C16/IS!C10", "=-IS!D16/IS!D10"])
ain("ga", "General and administrative", [0.08, 0.075] + [0.07] * 8,
    nt="Assumption; FY2014 includes a RMB1,269m equity-settled donation",
    hist=["=-IS!B17/IS!B10", "=-IS!C17/IS!C10", "=-IS!D17/IS!D10"])
ain("oth", "Other income, net", [0.02] * 10,
    nt="Assumption; FY2014 other income (4.6% of revenue) included one-off gains",
    hist=["=IS!B26/IS!B10", "=IS!C26/IS!C10", "=IS!D26/IS!D10"])
ain("tax", "Effective tax rate (% of pre-tax income)", [0.15] * 10,
    nt="Assumption; the effective rate was 15.2%, 14.4% and 11.9% in FY2012-14",
    hist=["=-IS!B28/IS!B27", "=-IS!C28/IS!C27", "=-IS!D28/IS!D27"])
ain("sbc", "Share-based compensation (non-cash, within opex)", [0.05] * 10,
    nt="Added back in the cash flow statement only; treated as a real cost in the DCF",
    hist=["=CF!B9/IS!B10", "=CF!C9/IS!C10", "=CF!D9/IS!D10"])

section(A, r, "Capital investment"); r += 1
ain("capex", "Capital expenditure (% of revenue)", [0.09, 0.09, 0.085, 0.08, 0.08, 0.075, 0.075, 0.07, 0.07, 0.07],
    hist=["=-CF!B26/IS!B10", "=-CF!C26/IS!C10", "=-CF!D26/IS!D10"])
ain("da", "Depreciation (% of opening PP&E incl. land use rights)", [0.22] * 10,
    nt="Assumption; FY2014 depreciation was 23.5% of opening PP&E", hist=[None, None, "=CF!D7/BS!C12"])

section(A, r, "Working capital (% of revenue; tax payable as % of tax expense)"); r += 1
for key, t, br, base in (("w_rest", "Restricted cash and escrow receivables", 7, "rev"),
                         ("w_prep", "Prepayments, receivables and other assets", 10, "rev"),
                         ("w_tax", "Income tax payable (% of tax expense)", 20, "tax"),
                         ("w_esc", "Escrow money payable", 21, "rev"),
                         ("w_acc", "Accrued expenses, accounts payable and other", 22, "rev"),
                         ("w_mer", "Merchant deposits", 23, "rev"),
                         ("w_def", "Deferred revenue and customer advances", 24, "rev")):
    h = [None] + [f"=-BS!{c}{br}/IS!{c}28" if base == "tax" else f"=BS!{c}{br}/IS!{c}10" for c in ("C", "D")]
    ain(key, t, "hold", hist=h, nt="Held at the FY2014 ratio")


def AS(key, c):
    return f"Assumptions!{c}${asm[key]}"


# ---------------------------------------------------------------- Revenue
R = sheet("Revenue", "Revenue Build")
year_header(R, 4)
rows = {
    5: ("China retail GMV (RMB bn)", [663, 1077, 1678], "Sum of quarterly GMV disclosed in F-1/A No. 7"),
    6: ("  GMV growth", None, None),
    7: ("  China commerce revenue / GMV", None, None),
    9: ("China commerce", [15637, 29167, 45132], SRC),
    10: ("  Growth", None, None),
    11: ("International commerce", [3765, 4160, 4851], "F-1/A No. 7, segment revenue"),
    12: ("  Growth", None, None),
    13: ("Cloud computing and Internet infrastructure", [515, 650, 773], "F-1/A No. 7, segment revenue"),
    14: ("  Growth", None, None),
    15: ("Others", [108, 540, 1748], "F-1/A No. 7, segment revenue"),
    16: ("  Growth", None, None),
    17: ("Total revenue", None, None),
    18: ("  Growth", None, None),
    20: ("Memo: annual active buyers (millions, 31 Mar)", [123, 172, 255], "F-1/A No. 7"),
}
for row, (t, vals, nt) in rows.items():
    label(R, row, t, bold=row == 17, note=nt)
    if vals:
        for c, v in zip(HIST, vals):
            put(R, f"{c}{row}", v)
for i, c in enumerate(ALL):
    if c in FC:
        put(R, f"{c}5", f"={prev(c)}5*(1+{AS('gmv_g', c)})")
        put(R, f"{c}7", f"={AS('yield', c)}", '0.00%')
        put(R, f"{c}9", f"={c}5*1000*{c}7")
        put(R, f"{c}11", f"={prev(c)}11*(1+{AS('intl_g', c)})")
        put(R, f"{c}13", f"={prev(c)}13*(1+{AS('cloud_g', c)})")
        put(R, f"{c}15", f"={prev(c)}15*(1+{AS('other_g', c)})")
    else:
        put(R, f"{c}7", f"={c}9/({c}5*1000)", '0.00%')
    if i > 0:
        put(R, f"{c}6", f"={c}5/{prev(c)}5-1", PCT)
        for gr, base in ((10, 9), (12, 11), (14, 13), (16, 15), (18, 17)):
            put(R, f"{c}{gr}", f"={c}{base}/{prev(c)}{base}-1", PCT)
    put(R, f"{c}17", f"={c}9+{c}11+{c}13+{c}15", NUM, bold=True)
total_border(R, 17)

# ---------------------------------------------------------------- Income statement
I = sheet("IS", "Income Statement")
year_header(I, 4)
section(I, 5, "Revenue")
for row, t, rr in [(6, "China commerce", 9), (7, "International commerce", 11),
                   (8, "Cloud computing and Internet infrastructure", 13), (9, "Others", 15)]:
    label(I, row, t, indent=1)
    for c in ALL:
        put(I, f"{c}{row}", f"=Revenue!{c}{rr}")
label(I, 10, "Total revenue", bold=True)
hist_is = {
    11: ("Cost of revenue", [-6554, -9719, -13369]),
    15: ("Product development expenses", [-2897, -3753, -5093]),
    16: ("Sales and marketing expenses", [-3058, -3613, -4545]),
    17: ("General and administrative expenses", [-2211, -2889, -4218]),
    18: ("Amortization of intangible assets", [-155, -130, -315]),
    19: ("Impairment of goodwill and intangible assets", [-135, -175, -44]),
    20: ("Yahoo TIPLA amendment payment", [0, -3487, 0]),
    24: ("Interest and investment income, net", [258, 39, 1648]),
    25: ("Interest expense", [-68, -1572, -2195]),
    26: ("Other income, net", [327, 894, 2429]),
    28: ("Income tax expenses", [-842, -1457, -3196]),
    29: ("Share of results of equity investees", [-25, -6, -203]),
    31: ("Net income attributable to noncontrolling interests", [-437, -117, -88]),
}
for row, (t, vals) in hist_is.items():
    label(I, row, t, indent=1 if row in (11, 15, 16, 17, 18, 19, 20) else 0, note=SRC if row == 11 else None)
    for c, v in zip(HIST, vals):
        put(I, f"{c}{row}", v)
label(I, 12, "Gross profit", bold=True)
label(I, 13, "  Gross margin")
section(I, 14, "Operating expenses")
label(I, 21, "Total operating expenses", bold=True)
label(I, 22, "Income from operations (EBIT)", bold=True)
label(I, 23, "  EBIT margin")
label(I, 27, "Income before tax and equity investees", bold=True)
label(I, 30, "Net income", bold=True)
label(I, 32, "Net income attributable to Alibaba", bold=True)
label(I, 33, "  Net margin")
label(I, 35, "Memo: depreciation of PP&E and land use rights", note="FY2012-14 from the cash flow statement")
label(I, 36, "Memo: EBITDA (EBIT + depreciation + amortization)", bold=True)
label(I, 37, "  EBITDA margin")
label(I, 38, "Memo: diluted shares (millions)", note="FY2015E onward: post-IPO basic shares + options + RSUs (F-1/A No. 7)")
label(I, 39, "Memo: diluted EPS (RMB)")
note(I, 18, "Forecast from Schedules")
note(I, 24, "Forecast: opening cash and short-term investments x yield")
note(I, 25, "Forecast from Schedules (opening debt x rate)")
for c in ALL:
    put(I, f"{c}10", f"=SUM({c}6:{c}9)", NUM, bold=True)
    if c in FC:
        put(I, f"{c}11", f"=-{c}10*{AS('cor', c)}")
        put(I, f"{c}15", f"=-{c}10*{AS('pd', c)}")
        put(I, f"{c}16", f"=-{c}10*{AS('sm', c)}")
        put(I, f"{c}17", f"=-{c}10*{AS('ga', c)}")
        put(I, f"{c}18", f"=-Schedules!{c}12")
        put(I, f"{c}19", 0)
        put(I, f"{c}20", 0)
        put(I, f"{c}24", f"=(BS!{prev(c)}5+BS!{prev(c)}6)*{gen['cash_yield']}")
        put(I, f"{c}25", f"=-Schedules!{c}17")
        put(I, f"{c}26", f"={c}10*{AS('oth', c)}")
        put(I, f"{c}28", f"=-{c}27*{AS('tax', c)}")
        put(I, f"{c}29", 0)
        put(I, f"{c}31", 0)
        put(I, f"{c}35", f"=Schedules!{c}7")
        put(I, f"{c}38", f"={gen['basic']}+{gen['options']}+{gen['rsus']}", NUM1)
        put(I, f"{c}39", f"={c}32/{c}38", '0.00')
    else:
        put(I, f"{c}35", f"=CF!{c}7")
    put(I, f"{c}12", f"={c}10+{c}11", NUM, bold=True)
    put(I, f"{c}13", f"={c}12/{c}10", PCT)
    put(I, f"{c}21", f"=SUM({c}15:{c}20)", NUM, bold=True)
    put(I, f"{c}22", f"={c}12+{c}21", NUM, bold=True)
    put(I, f"{c}23", f"={c}22/{c}10", PCT)
    put(I, f"{c}27", f"={c}22+SUM({c}24:{c}26)", NUM, bold=True)
    put(I, f"{c}30", f"={c}27+{c}28+{c}29", NUM, bold=True)
    put(I, f"{c}32", f"={c}30+{c}31", NUM, bold=True)
    put(I, f"{c}33", f"={c}32/{c}10", PCT)
    put(I, f"{c}36", f"={c}22+{c}35-{c}18", NUM, bold=True)
    put(I, f"{c}37", f"={c}36/{c}10", PCT)
for row in (10, 12, 21, 22, 27, 30, 32):
    total_border(I, row)

# ---------------------------------------------------------------- Balance sheet
B = sheet("BS", "Balance Sheet", "RMB in millions; 31 March. FY2013-14 condensed from the audited balance sheet")
year_header(B, 4, cols=["C", "D"] + FC)
bs_hist = {
    5: ("Cash and cash equivalents", [30396, 33045]),
    6: ("Short-term investments", [2290, 10587]),
    7: ("Restricted cash and escrow receivables", [3687, 4921]),
    8: ("Loan receivables, net (micro loans)", [4426, 13159]),
    9: ("Investment securities (current + non-current)", [871, 4465]),
    10: ("Prepayments, receivables and other assets (current + non-current)", [3230, 6766]),
    11: ("Investment in equity investees", [1555, 17666]),
    12: ("Property and equipment, net, incl. land use rights", [5703, 7241]),
    13: ("Intangible assets", [334, 1906]),
    14: ("Goodwill", [11294, 11793]),
    18: ("Bank borrowings (current + non-current)", [25812, 31811]),
    19: ("Secured borrowings (micro loans)", [2098, 9264]),
    20: ("Income tax payable", [259, 1267]),
    21: ("Escrow money payable", [1315, 2659]),
    22: ("Accrued expenses, accounts payable and other liabilities", [8961, 11887]),
    23: ("Merchant deposits", [3083, 4711]),
    24: ("Deferred revenue and customer advances (current + non-current)", [5318, 6924]),
    25: ("Deferred tax and other liabilities", [703, 2208]),
    26: ("Redeemable preference shares", [5191, 0]),
    29: ("Mezzanine equity (convertible preference shares and others)", [10533, 10401]),
    30: ("Total equity incl. noncontrolling interests", [513, 30417]),
}
for row, (t, vals) in bs_hist.items():
    label(B, row, t, indent=0 if row in (29, 30) else 1, note=SRC if row == 5 else None)
    for c, v in zip(["C", "D"], vals):
        put(B, f"{c}{row}", v)
label(B, 15, "Total assets", bold=True)
section(B, 17, "Liabilities")
label(B, 27, "Total liabilities", bold=True)
label(B, 31, "Total liabilities, mezzanine equity and equity", bold=True)
label(B, 33, "Balance check (should be zero)", bold=True)
note(B, 6, "Held flat")
note(B, 8, "Held flat: the micro loan business was being moved to Ant Financial")
note(B, 12, "Forecast from Schedules")
note(B, 18, "Forecast from Schedules (held flat)")
note(B, 29, "Converts to ordinary shares at the IPO (FY2015E)")
note(B, 30, "Roll-forward: + net income + share-based compensation + IPO net proceeds + mezzanine conversion")
for c in FC:
    p = prev(c)
    put(B, f"{c}5", f"=CF!{c}50")
    put(B, f"{c}6", f"={p}6")
    put(B, f"{c}7", f"=IS!{c}10*{AS('w_rest', c)}")
    put(B, f"{c}8", f"={p}8")
    put(B, f"{c}9", f"={p}9")
    put(B, f"{c}10", f"=IS!{c}10*{AS('w_prep', c)}")
    put(B, f"{c}11", f"={p}11")
    put(B, f"{c}12", f"=Schedules!{c}8")
    put(B, f"{c}13", f"=Schedules!{c}13")
    put(B, f"{c}14", f"={p}14")
    put(B, f"{c}18", f"=Schedules!{c}16")
    put(B, f"{c}19", f"={p}19")
    put(B, f"{c}20", f"=-IS!{c}28*{AS('w_tax', c)}")
    put(B, f"{c}21", f"=IS!{c}10*{AS('w_esc', c)}")
    put(B, f"{c}22", f"=IS!{c}10*{AS('w_acc', c)}")
    put(B, f"{c}23", f"=IS!{c}10*{AS('w_mer', c)}")
    put(B, f"{c}24", f"=IS!{c}10*{AS('w_def', c)}")
    put(B, f"{c}25", f"={p}25")
    put(B, f"{c}26", f"={p}26")
    put(B, f"{c}29", 0)
    put(B, f"{c}30", f"={p}30+IS!{c}30+CF!{c}9+CF!{c}40+({p}29-{c}29)")
for c in ["C", "D"] + FC:
    put(B, f"{c}15", f"=SUM({c}5:{c}14)", NUM, bold=True)
    put(B, f"{c}27", f"=SUM({c}18:{c}26)", NUM, bold=True)
    put(B, f"{c}31", f"={c}27+{c}29+{c}30", NUM, bold=True)
    put(B, f"{c}33", f"=ROUND({c}15-{c}31,3)", NUM, bold=True)
    for rr in (15, 27, 31):
        B[f"{c}{rr}"].border = Border(top=thin)

# ---------------------------------------------------------------- Schedules
S = sheet("Schedules", "Supporting Schedules")
year_header(S, 4, cols=["D"] + FC)
section(S, 5, "Property and equipment (incl. land use rights)")
label(S, 6, "Opening balance", indent=1)
label(S, 7, "Depreciation", indent=1, note="Opening balance x depreciation rate (Assumptions)")
label(S, 8, "Closing balance", bold=True)
label(S, 9, "Capital expenditure (added in closing balance)", indent=1, note="Revenue x capex % (Assumptions)")
section(S, 10, "Intangible assets")
label(S, 11, "Opening balance", indent=1)
label(S, 12, "Amortization", indent=1, note="FY2014 balance / remaining life, straight-line")
label(S, 13, "Closing balance", bold=True)
section(S, 14, "Bank borrowings")
label(S, 15, "Opening balance", indent=1)
label(S, 16, "Closing balance", bold=True, note="Held flat at the 31 Mar 2014 level (no refinancing modelled)")
label(S, 17, "Interest expense (opening balance x rate)", indent=1)
put(S, "D8", "=BS!D12")
put(S, "D13", "=BS!D13")
put(S, "D16", "=BS!D18")
for c in FC:
    p = prev(c)
    put(S, f"{c}6", f"={p}8")
    put(S, f"{c}9", f"=IS!{c}10*{AS('capex', c)}")
    put(S, f"{c}7", f"={c}6*{AS('da', c)}")
    put(S, f"{c}8", f"={c}6+{c}9-{c}7", NUM, bold=True)
    put(S, f"{c}11", f"={p}13")
    put(S, f"{c}12", f"=MIN({c}11,$D$13/{gen['intang_life']})")
    put(S, f"{c}13", f"={c}11-{c}12", NUM, bold=True)
    put(S, f"{c}15", f"={p}16")
    put(S, f"{c}16", f"={c}15", NUM, bold=True)
    put(S, f"{c}17", f"={c}15*{gen['debt_rate']}")

# ---------------------------------------------------------------- Cash flow
C = sheet("CF", "Cash Flow Statement", "RMB in millions; FY2012-14 condensed from the audited cash flow statement")
year_header(C, 4)
cf_hist = {
    6: ("Net income", "=IS!{c}30"),
    7: ("Depreciation of PP&E and land use rights", [715, 805, 1339]),
    8: ("Amortization of intangible assets", [155, 130, 315]),
    9: ("Share-based compensation", [1254, 1259, 2844]),
    10: ("Other non-cash items and deferred taxes", [698, 497, 2971]),
    11: ("Restricted cash and escrow receivables", [-113, -974, -1329]),
    12: ("Loan receivables", [-226, -2828, -9175]),
    13: ("Prepayments, receivables and other assets", [-240, -354, -3567]),
    14: ("Income tax payable", [230, -116, 1008]),
    15: ("Escrow money payable", [94, 976, 1344]),
    16: ("Accrued expenses, accounts payable and other", [1332, 3657, 3992]),
    17: ("Merchant deposits", [583, 2338, 1628]),
    18: ("Deferred revenue and customer advances", [128, 437, 1606]),
    19: ("Deferred tax and other liabilities", [0, 0, 0]),
    26: ("Capital expenditure (PP&E, land use rights, intangibles)", [-2168, -2503, -4776]),
    27: ("(Increase) decrease in short-term investments", [3728, 2589, -8304]),
    28: ("Investments, acquisitions and other investing", [-1685, 459, -19917]),
    33: ("Net change in bank borrowings", [121, 24834, 5623]),
    34: ("Net change in secured borrowings (micro loans)", [0, 2098, 7166]),
    35: ("Share issuance / repurchase, preference shares and other", [354, -28338, -3425]),
    40: ("IPO net proceeds (primary shares)", [0, 0, 0]),
    44: ("Effect of exchange rate changes", [-54, -76, -97]),
    47: ("Cash at beginning of year", [7286, 16857, 30396]),
}
section(C, 5, "Operating activities")
for row, (t, vals) in cf_hist.items():
    label(C, row, t, indent=0 if row in (44, 47) else 1, note=SRC if row == 7 else None)
    for c in HIST:
        put(C, f"{c}{row}", vals.format(c=c) if isinstance(vals, str) else vals[HIST.index(c)])
note(C, 10, "FY2012-14: sum of the other reconciling items reported (incl. FY2014 RMB1,269m donation); forecast 0")
note(C, 26, "FY2012-14: land use rights and construction in progress + other PP&E and intangibles")
note(C, 28, "FY2012-14: reported investing total less capex and short-term investments (FY2014: RMB16.5bn equity stakes)")
note(C, 35, "FY2012-14: reported financing total less borrowing lines (FY2013: Yahoo share buy-back, Alibaba.com privatization)")
note(C, 40, "123.1m primary ADSs x US$68 x (1 - fees) x RMB6.2036")
label(C, 21, "Net cash from operating activities", bold=True)
label(C, 22, "  Memo: change in operating working capital (rows 11, 13-19)")
section(C, 25, "Investing activities")
label(C, 30, "Net cash from investing activities", bold=True)
section(C, 32, "Financing activities")
label(C, 42, "Net cash from financing activities", bold=True)
label(C, 46, "Net change in cash", bold=True)
label(C, 50, "Cash at end of year", bold=True)
label(C, 52, "Check: vs reported closing cash (FY2012-14) / balance sheet cash (forecast)",
      note="Reported closing cash: 16,857 / 30,396 / 33,045")
for c in FC:
    p = prev(c)
    put(C, f"{c}6", f"=IS!{c}30")
    put(C, f"{c}7", f"=Schedules!{c}7")
    put(C, f"{c}8", f"=Schedules!{c}12")
    put(C, f"{c}9", f"=IS!{c}10*{AS('sbc', c)}")
    put(C, f"{c}10", 0)
    for rr, br, sign in ((11, 7, -1), (12, 8, -1), (13, 10, -1), (14, 20, 1), (15, 21, 1), (16, 22, 1),
                         (17, 23, 1), (18, 24, 1), (19, 25, 1)):
        put(C, f"{c}{rr}", f"=BS!{c}{br}-BS!{p}{br}" if sign == 1 else f"=-(BS!{c}{br}-BS!{p}{br})")
    put(C, f"{c}26", f"=-Schedules!{c}9")
    put(C, f"{c}27", f"=-(BS!{c}6-BS!{p}6)")
    put(C, f"{c}28", f"=-(BS!{c}9-BS!{p}9)-(BS!{c}11-BS!{p}11)")
    put(C, f"{c}33", f"=BS!{c}18-BS!{p}18")
    put(C, f"{c}34", f"=BS!{c}19-BS!{p}19")
    put(C, f"{c}35", 0)
    put(C, f"{c}40", f"={gen['primary_ads']}*{gen['ipo_price']}*(1-{gen['fee']})*{gen['fx']}" if c == "E" else 0)
    put(C, f"{c}44", 0)
    put(C, f"{c}47", f"=BS!{p}5")
for c in ALL:
    put(C, f"{c}21", f"=SUM({c}6:{c}19)", NUM, bold=True)
    put(C, f"{c}22", f"={c}11+SUM({c}13:{c}19)", NUM)
    put(C, f"{c}30", f"=SUM({c}26:{c}28)", NUM, bold=True)
    put(C, f"{c}42", f"=SUM({c}33:{c}40)", NUM, bold=True)
    put(C, f"{c}46", f"={c}21+{c}30+{c}42+{c}44", NUM, bold=True)
    put(C, f"{c}50", f"={c}47+{c}46", NUM, bold=True)
    for rr in (21, 30, 42, 46, 50):
        C[f"{c}{rr}"].border = Border(top=thin)
for c, v in zip(HIST, [16857, 30396, 33045]):
    put(C, f"{c}52", f"=ROUND({c}50-{v},3)", NUM)
for c in FC:
    put(C, f"{c}52", f"=ROUND({c}50-BS!{c}5,3)", NUM)

# ---------------------------------------------------------------- WACC
W = sheet("WACC", "Cost of Capital", "CAPM cost of equity; market-value weights at the IPO price")
W.column_dimensions["B"].width = 16
W["A4"], W["B4"], W[f"{NOTE}4"] = "Input", "Value", "Notes / source"
for c in ("A", "B", NOTE):
    W[f"{c}4"].fill = NAVY
    W[f"{c}4"].font = Font(name=F, bold=True, color="FFFFFF")
wrows = [
    ("Risk-free rate", 0.026, PCT, "Assumption: approx. 10-year US Treasury yield, September 2014"),
    ("Equity risk premium", 0.055, PCT, "Assumption: mature-market equity risk premium"),
    ("China country risk premium", 0.01, PCT, "Assumption"),
    ("Levered beta", 1.2, "0.00", "Assumption for a large-cap Chinese internet company"),
    ("Cost of equity", "=B5+B8*B6+B7", PCT, "Risk-free rate + beta x ERP + country risk"),
    ("Pre-tax cost of debt", 0.035, PCT, "Assumption: US$ syndicated loan pricing"),
    ("Tax rate", f"=Assumptions!E{asm['tax']}", PCT, "FY2015E effective tax rate"),
    ("After-tax cost of debt", "=B10*(1-B11)", PCT, ""),
    ("Market value of equity at IPO price (RMB m)",
     f"=({gen['basic']}+{gen['options']}+{gen['rsus']})*{gen['ipo_price']}*{gen['fx']}", NUM, "Diluted shares x US$68 x FX"),
    ("Bank borrowings (RMB m)", "=BS!D18", NUM, "31 Mar 2014"),
    ("Debt / (debt + equity)", "=B14/(B13+B14)", PCT, ""),
    ("Equity / (debt + equity)", "=1-B15", PCT, ""),
    ("WACC", "=B16*B9+B15*B12", PCT, ""),
]
for i, (t, v, fmt, nt) in enumerate(wrows):
    rr = 5 + i
    label(W, rr, t, bold=t in ("Cost of equity", "WACC"), note=nt or None)
    put(W, f"B{rr}", v, fmt, bold=t == "WACC", fill=YEL if t == "WACC" else None)
WACC = "WACC!$B$17"

# ---------------------------------------------------------------- DCF
D = sheet("DCF", "Discounted Cash Flow Valuation",
          "Unlevered free cash flow, RMB in millions; valued as of the IPO pricing date")
D.column_dimensions["B"].width = 14
year_header(D, 4, cols=FC)
dl = {5: "Revenue", 6: "EBIT", 7: "Tax rate", 8: "NOPAT (EBIT x (1 - tax))", 9: "+ Depreciation",
      10: "+ Amortization of intangibles", 11: "- Capital expenditure", 12: "+ / - Change in operating working capital",
      13: "Unlevered free cash flow (FCFF)", 14: "  FCFF margin", 16: "Fiscal year end",
      17: "Years from valuation date to year end", 18: "Discount period (mid-year)",
      19: "Share of year after valuation date", 20: "FCFF counted", 21: "Discount factor", 22: "Present value of FCFF"}
for row, t in dl.items():
    label(D, row, t, bold=row in (13, 22))
note(D, 12, "Excludes loan receivables and secured borrowings (held flat)")
note(D, 13, "Share-based compensation is not added back: treated as a real cost")
note(D, 19, "FY2015E: only cash flows after 18 Sep 2014 count; cash generated Apr-Sep 2014 is ignored (conservative)")
for i, c in enumerate(FC):
    put(D, f"{c}5", f"=IS!{c}10")
    put(D, f"{c}6", f"=IS!{c}22")
    put(D, f"{c}7", f"={AS('tax', c)}", PCT)
    put(D, f"{c}8", f"={c}6*(1-{c}7)")
    put(D, f"{c}9", f"=CF!{c}7")
    put(D, f"{c}10", f"=CF!{c}8")
    put(D, f"{c}11", f"=CF!{c}26")
    put(D, f"{c}12", f"=CF!{c}22")
    put(D, f"{c}13", f"=SUM({c}8:{c}12)", NUM, bold=True, fill=FCF_FILL)
    put(D, f"{c}14", f"={c}13/{c}5", PCT)
    put(D, f"{c}16", f"=DATE({2015 + i},3,31)", "dd-mmm-yy")
    put(D, f"{c}17", f"=({c}16-{gen['val_date']})/365", "0.00")
    put(D, f"{c}19", f"=MIN(1,{c}17)", "0.00")
    put(D, f"{c}18", f"={c}17-{c}19/2", "0.00")
    put(D, f"{c}20", f"={c}13*{c}19")
    put(D, f"{c}21", f"=1/(1+{WACC})^{c}18", "0.0000")
    put(D, f"{c}22", f"={c}20*{c}21", NUM, bold=True)
section(D, 24, "Valuation summary")
vrows = [
    (25, "WACC", f"={WACC}", PCT, ""),
    (26, "Terminal growth rate", f"={gen['tg']}", PCT, ""),
    (27, "Sum of PV of FCFF (FY2015E-FY2024E)", "=SUM(E22:N22)", NUM, ""),
    (28, "Terminal value at FY2024 (Gordon growth)", "=N13*(1+B26)/(B25-B26)", NUM, ""),
    (29, "PV of terminal value", "=B28/(1+B25)^N17", NUM, "Discounted from the FY2024 year end"),
    (30, "Enterprise value", "=B27+B29", NUM, ""),
    (31, "  Terminal value as % of EV", "=B29/B30", PCT, ""),
    (32, "+ Cash and short-term investments (31 Mar 2014)", "=BS!D5+BS!D6", NUM, "Restricted cash excluded"),
    (33, "+ IPO net proceeds", "=CF!E40", NUM, ""),
    (34, "+ Investment securities and equity investees (book)", "=BS!D9+BS!D11", NUM,
     "Includes stakes in Weibo, AutoNavi and others at book value"),
    (35, "+ Alipay / Ant profit share", f"={gen['alipay']}*1000*{gen['fx']}", NUM, "Base case: 0"),
    (36, "- Bank borrowings", "=-BS!D18", NUM, ""),
    (37, "- Noncontrolling interests", f"=-{gen['nci']}", NUM, ""),
    (38, "Equity value (RMB m)", "=SUM(B30,B32:B37)", NUM, ""),
    (39, "Equity bridge adjustments (rows 32-37)", "=SUM(B32:B37)", NUM, "Used by the Sensitivity and IPO Analysis sheets"),
    (40, "Diluted shares (millions)", f"={gen['basic']}+{gen['options']}+{gen['rsus']}", NUM1,
     "Post-IPO basic shares + options + RSUs"),
    (41, "Value per share (RMB)", "=B38/B40", '0.00', ""),
    (42, "Value per ADS (US$)", f"=B41/{gen['fx']}", USD, "1 ADS = 1 ordinary share"),
    (43, "IPO price per ADS (US$)", f"={gen['ipo_price']}", USD, ""),
    (44, "Upside / (downside) vs IPO price", "=B42/B43-1", PCT, ""),
    (45, "Equity value (US$ bn)", f"=B38/{gen['fx']}/1000", '#,##0.0', ""),
]
for row, t, f, fmt, nt in vrows:
    label(D, row, t, bold=row in (30, 38, 42, 44), note=nt or None)
    put(D, f"B{row}", f, fmt, bold=row in (30, 38, 42, 44), fill=YEL if row == 42 else None)
    if row in (30, 38):
        D[f"B{row}"].border = Border(top=thin)
ch = BarChart()
ch.type = "col"
ch.title = "Revenue and FCFF, FY2015E-FY2024E (RMB m)"
ch.add_data(Reference(D, min_col=5, max_col=14, min_row=5), from_rows=True, titles_from_data=False)
ch.add_data(Reference(D, min_col=5, max_col=14, min_row=13), from_rows=True, titles_from_data=False)
ch.series[0].tx = SeriesLabel(v="Revenue")
ch.series[1].tx = SeriesLabel(v="FCFF")
ch.set_categories(Reference(D, min_col=5, max_col=14, min_row=4))
ch.roundedCorners = False
ch.legend.overlay = False
ch.title.overlay = False
ch.x_axis.delete = False
ch.y_axis.delete = False
ch.height, ch.width = 8, 18
D.add_chart(ch, "D25")

# ---------------------------------------------------------------- Sensitivity
X = sheet("Sensitivity", "Sensitivity: value per ADS (US$)",
          "Rows: WACC  |  Columns: terminal growth. Each cell re-runs the DCF with SUMPRODUCT")
X.column_dimensions["A"].width = 26
X["A4"] = "WACC \\ Terminal growth"
X["A4"].font = Font(name=F, bold=True)
cols = ["B", "C", "D", "E", "F"]
for c, d in zip(cols, ["-1%", "-0.5%", "", "+0.5%", "+1%"]):
    put(X, f"{c}5", f"=DCF!$B$26{d}", PCT, bold=True)
for i, d in enumerate(["-1%", "-0.5%", "", "+0.5%", "+1%"]):
    rr = 6 + i
    put(X, f"A{rr}", f"=DCF!$B$25{d}", PCT, bold=True)
    X[f"A{rr}"].alignment = Alignment(horizontal="right")
    for c in cols:
        f = (f"=((SUMPRODUCT(DCF!$E$20:$N$20,(1+$A{rr})^(-DCF!$E$18:$N$18))"
             f"+DCF!$N$13*(1+{c}$5)/($A{rr}-{c}$5)/(1+$A{rr})^DCF!$N$17)+DCF!$B$39)"
             f"/DCF!$B$40/{gen['fx']}")
        put(X, f"{c}{rr}", f, USD)
    for c in cols:
        X.column_dimensions[c].width = 13
X.conditional_formatting.add("B6:F10", ColorScaleRule(start_type="min", start_color="F8696B",
                                                      mid_type="num", mid_value=68, mid_color="FFFFFF",
                                                      end_type="max", end_color="63BE7B"))
X["A12"] = "Shading: red below, green above the US$68 IPO price. The centre cell equals the DCF base case."
X["A12"].font = Font(name=F, size=9, italic=True)
X["A13"] = "Check: centre cell minus DCF value per ADS"
X["A13"].font = Font(name=F)
put(X, "D13", "=ROUND(D8-DCF!B42,6)", USD)

# ---------------------------------------------------------------- IPO analysis
P = sheet("IPO Analysis", "IPO Pricing Analysis", "What the US$68 price implied, and how it compares with the DCF")
P.column_dimensions["B"].width = 18
prow = [
    (4, "Deal terms", None, None, None),
    (5, "IPO price per ADS (US$)", f"={gen['ipo_price']}", USD, ""),
    (6, "Total ADSs offered, base deal (millions)", f"={gen['total_ads']}", "#,##0.0", ""),
    (7, "Total deal size, base (US$ bn)", "=B5*B6/1000", '#,##0.00', "Primary + secondary"),
    (8, "Primary proceeds to Alibaba, gross (US$ bn)", f"=B5*{gen['primary_ads']}/1000", '#,##0.00', ""),
    (9, "Primary proceeds to Alibaba, net (RMB m)", "=CF!E40", NUM, ""),
    (11, "Valuation at the IPO price", None, None, None),
    (12, "Diluted shares (millions)", "=DCF!B40", NUM1, ""),
    (13, "Equity value at IPO price (US$ bn)", "=B5*B12/1000", '#,##0.0', ""),
    (14, "Equity value at IPO price (RMB m)", f"=B13*1000*{gen['fx']}", NUM, ""),
    (15, "Implied enterprise value (RMB m)", "=B14-DCF!B39", NUM, "Equity value less the same bridge items used in the DCF"),
    (16, "EV / Revenue FY2014A", "=B15/IS!D10", MULT, ""),
    (17, "EV / Revenue FY2015E", "=B15/IS!E10", MULT, ""),
    (18, "EV / EBITDA FY2014A", "=B15/IS!D36", MULT, ""),
    (19, "EV / EBITDA FY2015E", "=B15/IS!E36", MULT, ""),
    (20, "P / E FY2014A", "=B14/IS!D32", MULT, "Net income attributable to Alibaba"),
    (21, "P / E FY2015E", "=B14/IS!E32", MULT, ""),
    (23, "IPO price vs model", None, None, None),
    (24, "DCF value per ADS (US$)", "=DCF!B42", USD, ""),
    (25, "DCF upside / (downside) vs IPO price", "=DCF!B44", PCT, ""),
    (26, "First-day close per ADS (US$)", f"={gen['first_close']}", USD, ""),
    (27, "First-day gain vs IPO price", "=B26/B5-1", PCT, ""),
    (28, "DCF value vs first-day close", "=B24/B26-1", PCT, ""),
    (29, "Verdict", '=IF(B5<B24,"IPO priced below DCF value","IPO priced at or above DCF value")', None, ""),
]
for row, t, f, fmt, nt in prow:
    if f is None:
        section(P, row, t)
        continue
    label(P, row, t, note=nt or None, bold=row in (13, 24, 25, 29))
    put(P, f"B{row}", f, fmt, bold=row in (13, 24, 25, 29))

# ---------------------------------------------------------------- Cover
V = wb.create_sheet("Cover", 0)
V.sheet_view.showGridLines = False
V.column_dimensions["A"].width = 3
V.column_dimensions["B"].width = 36
V.column_dimensions["C"].width = 95


def vtxt(ref, val, **kw):
    V[ref] = val
    V[ref].font = Font(name=F, **kw)


vtxt("B2", "Alibaba Group Holding Limited", size=20, bold=True, color="1F3864")
vtxt("B3", "IPO Financial Model and DCF Valuation (NYSE: BABA, September 2014)", size=13, color="1F3864")
info = [("Prepared by", "Aditya Kushwaha"), ("GitHub", "https://github.com/adityakushwahagzpa-design"),
        ("LinkedIn", "https://www.linkedin.com/in/aditya-kushwaha16"),
        ("Units", "RMB in millions unless stated; fiscal years end 31 March"),
        ("Data source", SRC.replace("Source: ", ""))]
for i, (a, b) in enumerate(info):
    vtxt(f"B{5 + i}", a, bold=True)
    vtxt(f"C{5 + i}", b)
r0 = 11
vtxt(f"B{r0}", "Key outputs", bold=True, size=12)
outs = [("DCF value per ADS (US$)", "=DCF!B42", USD), ("IPO price per ADS (US$)", "=DCF!B43", USD),
        ("Upside / (downside) vs IPO price", "=DCF!B44", PCT), ("Enterprise value (RMB m)", "=DCF!B30", NUM),
        ("Equity value (US$ bn)", "=DCF!B45", '#,##0.0'), ("WACC", "=DCF!B25", PCT),
        ("Terminal growth", "=DCF!B26", PCT), ("EV / EBITDA FY2015E at the IPO price", "='IPO Analysis'!B19", MULT),
        ("Balance sheet check, all years (should be 0)", "=SUM(BS!C33:N33)", NUM)]
for i, (t, f, fmt) in enumerate(outs):
    rr = r0 + 1 + i
    vtxt(f"B{rr}", t)
    put(V, f"C{rr}", f, fmt)
    V[f"C{rr}"].alignment = Alignment(horizontal="left")
r1 = r0 + len(outs) + 2
vtxt(f"B{r1}", "Contents", bold=True, size=12)
contents = [("Assumptions", "Every input: revenue drivers, cost ratios, capex, working capital, deal terms"),
            ("Revenue", "GMV x take rate for China commerce; growth build for the other segments"),
            ("IS", "Income statement, FY2012A-FY2014A and FY2015E-FY2024E"),
            ("BS", "Balance sheet with roll-forward and balance check"),
            ("CF", "Cash flow statement; closing cash links back to the balance sheet"),
            ("Schedules", "PP&E and depreciation, intangibles, bank borrowings and interest"),
            ("WACC", "CAPM cost of equity and weighted average cost of capital"),
            ("DCF", "Unlevered free cash flow, mid-year discounting from the IPO date, equity bridge"),
            ("Sensitivity", "Value per ADS across WACC and terminal growth"),
            ("IPO Analysis", "Deal size, multiples implied by the US$68 price, comparison with the DCF")]
for i, (s, d) in enumerate(contents):
    rr = r1 + 1 + i
    V[f"B{rr}"] = s
    V[f"B{rr}"].hyperlink = f"#'{s}'!A1"
    V[f"B{rr}"].font = Font(name=F, color="0563C1", underline="single")
    vtxt(f"C{rr}", d)
r2 = r1 + len(contents) + 2
vtxt(f"B{r2}", "Colour code", bold=True, size=12)
for i, (a, b, col, fill) in enumerate([("Blue text", "Hardcoded input or reported figure", BLUE, None),
                                       ("Black text", "Formula", BLACK, None),
                                       ("Green text", "Link to another sheet", GREEN, None),
                                       ("Yellow fill", "Key assumption", BLACK, YEL)]):
    rr = r2 + 1 + i
    vtxt(f"B{rr}", a, color=col)
    if fill:
        V[f"B{rr}"].fill = fill
    vtxt(f"C{rr}", b)
vtxt(f"B{r2 + 6}", "Educational project. Historical figures are from Alibaba's public F-1 filing; forecasts are the "
                   "author's assumptions as of September 2014. Not investment advice.", size=9, italic=True)

for ws in wb.worksheets:
    if ws.title in ("Assumptions", "Revenue", "IS", "BS", "CF", "Schedules", "DCF"):
        ws.freeze_panes = "B5"

for ws in wb.worksheets:
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

wb.properties.creator = "Aditya Kushwaha"
wb.properties.title = "Alibaba Group IPO Financial Model"
wb.save("/home/claude/alibaba/Alibaba_IPO_Financial_Model.xlsx")
print("saved")
