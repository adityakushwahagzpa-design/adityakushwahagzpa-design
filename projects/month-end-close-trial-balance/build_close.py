"""Month-End Close & Trial Balance project: data, Excel workbook (formulas), JSON for the website."""
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

CO = "Kaveri Home Appliances Pvt. Ltd."
# code, name, type, normal side
COA = [
    (1000, "Cash at Bank", "Asset", "Dr"), (1100, "Accounts Receivable", "Asset", "Dr"),
    (1150, "Allowance for Doubtful Debts", "Asset", "Cr"), (1200, "Inventory", "Asset", "Dr"),
    (1300, "Prepaid Insurance", "Asset", "Dr"), (1500, "Office Equipment", "Asset", "Dr"),
    (1510, "Accumulated Depreciation", "Asset", "Cr"),
    (2000, "Accounts Payable", "Liability", "Cr"), (2100, "Accrued Expenses", "Liability", "Cr"),
    (2110, "Salaries Payable", "Liability", "Cr"), (2310, "Interest Payable", "Liability", "Cr"),
    (2300, "Term Loan", "Liability", "Cr"),
    (3000, "Share Capital", "Equity", "Cr"), (3100, "Retained Earnings", "Equity", "Cr"),
    (4000, "Sales Revenue", "Income", "Cr"),
    (5000, "Cost of Goods Sold", "Expense", "Dr"), (6000, "Salaries and Wages", "Expense", "Dr"),
    (6100, "Rent", "Expense", "Dr"), (6200, "Electricity", "Expense", "Dr"),
    (6300, "Insurance", "Expense", "Dr"), (6400, "Depreciation", "Expense", "Dr"),
    (6500, "Bad Debt Expense", "Expense", "Dr"), (6600, "Audit Fees", "Expense", "Dr"),
    (6700, "Interest Expense", "Expense", "Dr"), (6800, "Marketing", "Expense", "Dr"),
    (6900, "Bank Charges", "Expense", "Dr"),
]
NAME = {c: n for c, n, *_ in COA}
TYPE = {c: t for c, _, t, _ in COA}

OPENING = {1000: 1840000, 1100: 1260000, 1150: -63000, 1200: 980000, 1300: 360000, 1500: 2400000,
           1510: -600000, 2000: -840000, 2300: -1500000, 3000: -2500000, 3100: -1337000}
assert sum(OPENING.values()) == 0

# (id, date, kind, narration, [(code, dr, cr)])
J = []
def je(i, d, kind, nar, lines): J.append((i, d, kind, nar, lines))
R, A = "Regular", "Adjusting"
je("JE-001", "2026-10-02", R, "Credit sales, invoices INV-4101 to 4112", [(1100, 920000, 0), (4000, 0, 920000)])
je("JE-002", "2026-10-02", R, "Cost of goods sold for INV-4101 to 4112", [(5000, 552000, 0), (1200, 0, 552000)])
je("JE-003", "2026-10-03", R, "Stock purchase on credit, PO-2207", [(1200, 850000, 0), (2000, 0, 850000)])
je("JE-004", "2026-10-05", R, "Warehouse rent for October", [(6100, 120000, 0), (1000, 0, 120000)])
je("JE-005", "2026-10-08", R, "Receipts from customers", [(1000, 1140000, 0), (1100, 0, 1140000)])
je("JE-006", "2026-10-10", R, "Payment to suppliers", [(2000, 910000, 0), (1000, 0, 910000)])
je("JE-007", "2026-10-12", R, "Credit sales, invoices INV-4113 to 4121", [(1100, 780000, 0), (4000, 0, 780000)])
je("JE-008", "2026-10-12", R, "Cost of goods sold for INV-4113 to 4121", [(5000, 468000, 0), (1200, 0, 468000)])
je("JE-009", "2026-10-15", R, "Festive season marketing campaign", [(6800, 65000, 0), (1000, 0, 65000)])
je("JE-010", "2026-10-18", R, "Stock purchase on credit, PO-2214", [(1200, 620000, 0), (2000, 0, 620000)])
je("JE-011", "2026-10-20", R, "Receipts from customers", [(1000, 980000, 0), (1100, 0, 980000)])
je("JE-012", "2026-10-25", R, "Term loan principal repayment", [(2300, 50000, 0), (1000, 0, 50000)])
je("JE-013", "2026-10-26", R, "Credit sales, invoices INV-4122 to 4130", [(1100, 640000, 0), (4000, 0, 640000)])
je("JE-014", "2026-10-26", R, "Cost of goods sold for INV-4122 to 4130", [(5000, 384000, 0), (1200, 0, 384000)])
je("JE-015", "2026-10-28", R, "October salaries, permanent staff", [(6000, 310000, 0), (1000, 0, 310000)])
je("JE-016", "2026-10-29", R, "Payment to suppliers, cheque 004512", [(2000, 680000, 0), (1000, 0, 680000)])
je("JE-017", "2026-10-30", R, "Purchase of billing terminals (capitalised)", [(1500, 180000, 0), (1000, 0, 180000)])
je("ADJ-01", "2026-10-31", A, "Accrual: October electricity (bill due 6 Nov)", [(6200, 38500, 0), (2100, 0, 38500)])
je("ADJ-02", "2026-10-31", A, "Accrual: statutory audit fee, 1/12 of 2,40,000", [(6600, 20000, 0), (2100, 0, 20000)])
je("ADJ-03", "2026-10-31", A, "Accrual: contract staff wages unpaid at month end", [(6000, 45000, 0), (2110, 0, 45000)])
je("ADJ-04", "2026-10-31", A, "Prepayment release: insurance, 1/12 of 4,80,000", [(6300, 40000, 0), (1300, 0, 40000)])
je("ADJ-05", "2026-10-31", A, "Depreciation: equipment 24,00,000 over 5 years", [(6400, 40000, 0), (1510, 0, 40000)])
je("ADJ-06", "2026-10-31", A, "Accrual: October interest on term loan at 9%", [(6700, 11250, 0), (2310, 0, 11250)])
je("ADJ-07", "2026-10-31", A, "Allowance top-up to 5% of closing receivables", [(6500, 11000, 0), (1150, 0, 11000)])
je("ADJ-08", "2026-10-31", A, "Inventory count shortfall (book 10,46,000, count 10,38,500)", [(5000, 7500, 0), (1200, 0, 7500)])
je("ADJ-09", "2026-10-31", A, "Bank charges per October bank statement", [(6900, 1200, 0), (1000, 0, 1200)])
for _, _, _, _, l in J:
    assert sum(x[1] for x in l) == sum(x[2] for x in l)

def bal(kinds):
    b = {c: OPENING.get(c, 0) for c in NAME}
    for _, _, k, _, l in J:
        if k in kinds:
            for c, dr, cr in l: b[c] += dr - cr
    return b
UNADJ, ADJ = bal({R}), bal({R, A})
assert sum(UNADJ.values()) == 0 and sum(ADJ.values()) == 0
ar_close = ADJ[1100]; assert ar_close == 1480000 and -ADJ[1150] == round(0.05 * ar_close)
assert UNADJ[1200] == 1046000
income = -sum(ADJ[c] for c in NAME if TYPE[c] == "Income")
exp = sum(ADJ[c] for c in NAME if TYPE[c] == "Expense")
NP = income - exp
unadj_np = -sum(UNADJ[c] for c in NAME if TYPE[c] == "Income") - sum(UNADJ[c] for c in NAME if TYPE[c] == "Expense")
adj_total = sum(dr for i, d, k, n, l in J if k == A for c, dr, cr in l)

# reconciliations
bank_stmt = ADJ[1000] + 680000  # cheque 004512 not yet presented
AR_SUB = [("Sharma Electronics", 520000), ("Metro Retail LLP", 410000), ("Patel Distributors", 330000), ("Om Sai Traders", 220000)]
AP_SUB = [("Voltline Components", 420000), ("Coolair Industries", 300000)]
assert sum(x for _, x in AR_SUB) == ADJ[1100] and sum(x for _, x in AP_SUB) == -ADJ[2000]

CHECKLIST = [
    ("WD-1", "Cut-off: all October sales and purchase invoices posted", "AR / AP team"),
    ("WD-1", "Bank reconciliation for October", "R2R analyst"),
    ("WD-2", "Accruals: electricity, audit fee, contract wages, interest", "R2R analyst"),
    ("WD-2", "Prepayment release: insurance", "R2R analyst"),
    ("WD-2", "Depreciation run and fixed asset register update", "R2R analyst"),
    ("WD-3", "Inventory count result posted", "Warehouse + R2R"),
    ("WD-3", "Allowance for doubtful debts review", "R2R analyst"),
    ("WD-3", "AR and AP subledger to GL reconciliation", "R2R analyst"),
    ("WD-4", "Adjusted trial balance: debits equal credits", "R2R analyst"),
    ("WD-4", "Balance sheet account review and sign-off", "Finance controller"),
    ("WD-5", "Profit and loss and balance sheet issued", "Finance controller"),
    ("WD-5", "Period locked in the ledger", "Finance controller"),
]

data = dict(company=CO, period="October 2026",
            coa=[dict(code=c, name=n, type=t, side=s) for c, n, t, s in COA],
            opening=OPENING, journal=[dict(id=i, date=d, kind=k, narration=n, lines=[dict(code=c, dr=dr, cr=cr) for c, dr, cr in l]) for i, d, k, n, l in J],
            bank=dict(gl=ADJ[1000], stmt=bank_stmt, unpresented=[("Cheque 004512, supplier payment 29 Oct", 680000)], charges=1200),
            ar_sub=AR_SUB, ap_sub=AP_SUB, checklist=CHECKLIST,
            facts=dict(revenue=income, net_profit=NP, unadj_profit=unadj_np, adj_total=adj_total, adj_count=sum(1 for j in J if j[2] == A),
                       je_count=sum(1 for j in J if j[2] == R), tb_total=sum(v for v in ADJ.values() if v > 0)))
json.dump(data, open("./close_data.json", "w"))
print(json.dumps(data["facts"]), "cash", ADJ[1000], "bank", bank_stmt)

# ---------------- Excel ----------------
wb = Workbook()
AR_ = "Arial"
H = Font(name=AR_, bold=True, color="FFFFFF"); HF = PatternFill("solid", fgColor="1F3A5F")
B = Font(name=AR_, bold=True); N = Font(name=AR_); BLUE = Font(name=AR_, color="0000FF"); GREEN = Font(name=AR_, color="008000")
TITLE = Font(name=AR_, bold=True, size=14)
NUM = '#,##0;(#,##0);"-"'
thin = Side(style="thin", color="999999"); TOP = Border(top=thin)

def header(ws, row, cols):
    for i, h in enumerate(cols, 1):
        c = ws.cell(row=row, column=i, value=h); c.font = H; c.fill = HF; c.alignment = Alignment(horizontal="center", wrap_text=True)
def widths(ws, w):
    for i, x in enumerate(w, 1): ws.column_dimensions[get_column_letter(i)].width = x
def title(ws, t, sub):
    ws["A1"] = t; ws["A1"].font = TITLE; ws["A2"] = sub; ws["A2"].font = Font(name=AR_, italic=True, color="555555")

ws = wb.active; ws.title = "README"
title(ws, f"Month-End Close & Trial Balance | {CO}", "Portfolio project by Aditya Kushwaha. Sample data for a fictional company; period October 2026.")
rows = ["Flow: Opening TB  ->  Journal (17 regular + 9 adjusting entries)  ->  Trial Balance (unadjusted and adjusted)  ->  P&L and Balance Sheet.",
        "Every balance in Trial Balance is a SUMIFS over the Journal sheet, so a new journal line flows through to the statements.",
        "Reconciliations: bank statement vs GL cash, AR and AP subledgers vs GL control accounts.",
        "Colour code: blue text = hardcoded inputs (opening balances, journal amounts, bank and subledger figures); black = formulas; green = links to another sheet.",
        "Checks: TB debits = credits, balance sheet balances, every reconciliation difference = 0 (see Checks column on each sheet)."]
for i, t in enumerate(rows, 4): ws.cell(row=i, column=1, value=t).font = N
widths(ws, [130])

ws = wb.create_sheet("Opening TB")
title(ws, "Opening Trial Balance at 30 September 2026", "Inputs (blue). Positive = debit balance, negative = credit balance.")
header(ws, 4, ["Code", "Account", "Type", "Balance (₹)"])
for r, (c, n, t, s) in enumerate(COA, 5):
    ws.cell(row=r, column=1, value=c).font = N; ws.cell(row=r, column=2, value=n).font = N; ws.cell(row=r, column=3, value=t).font = N
    x = ws.cell(row=r, column=4, value=OPENING.get(c, 0)); x.font = BLUE; x.number_format = NUM
last = 4 + len(COA)
ws.cell(row=last + 1, column=2, value="Check: total should be 0").font = B
x = ws.cell(row=last + 1, column=4, value=f"=SUM(D5:D{last})"); x.font = B; x.number_format = NUM
widths(ws, [8, 32, 11, 16])

ws = wb.create_sheet("Journal")
title(ws, "General Journal, October 2026", "One row per journal line. Amounts are inputs (blue).")
header(ws, 4, ["Entry", "Date", "Kind", "Code", "Account", "Debit (₹)", "Credit (₹)", "Narration"])
r = 5
from datetime import date
for i, d, k, n, l in J:
    for c, dr, cr in l:
        vals = [i, date.fromisoformat(d), k, c, None, dr or None, cr or None, n]
        for col, v in enumerate(vals, 1):
            cell = ws.cell(row=r, column=col, value=v); cell.font = BLUE if col in (6, 7) else N
        ws.cell(row=r, column=2).number_format = "dd-mmm-yyyy"
        e = ws.cell(row=r, column=5, value=f"=INDEX('Opening TB'!$B$5:$B${last},MATCH(D{r},'Opening TB'!$A$5:$A${last},0))"); e.font = GREEN
        for col in (6, 7): ws.cell(row=r, column=col).number_format = NUM
        r += 1
jl = r - 1
ws.cell(row=r, column=5, value="Totals").font = B
for col, L in ((6, "F"), (7, "G")):
    x = ws.cell(row=r, column=col, value=f"=SUM({L}5:{L}{jl})"); x.font = B; x.number_format = NUM; x.border = TOP
ws.cell(row=r + 1, column=5, value="Check: debits - credits").font = B
x = ws.cell(row=r + 1, column=6, value=f"=F{r}-G{r}"); x.font = B; x.number_format = NUM
widths(ws, [9, 13, 11, 7, 30, 13, 13, 58]); ws.freeze_panes = "A5"
JR = lambda col: f"Journal!${col}$5:${col}${jl}"

ws = wb.create_sheet("Trial Balance")
title(ws, "Trial Balance at 31 October 2026", "All figures are formulas over the Opening TB and Journal sheets.")
header(ws, 4, ["Code", "Account", "Type", "Opening (₹)", "Regular entries (₹)", "Unadjusted (₹)", "Adjusting entries (₹)", "Adjusted (₹)", "Adj. debit (₹)", "Adj. credit (₹)"])
for r, (c, n, t, s) in enumerate(COA, 5):
    ws.cell(row=r, column=1, value=c).font = N; ws.cell(row=r, column=2, value=n).font = N; ws.cell(row=r, column=3, value=t).font = N
    f = {4: f"='Opening TB'!D{r}",
         5: f"=SUMIFS({JR('F')},{JR('D')},A{r},{JR('C')},\"Regular\")-SUMIFS({JR('G')},{JR('D')},A{r},{JR('C')},\"Regular\")",
         6: f"=D{r}+E{r}",
         7: f"=SUMIFS({JR('F')},{JR('D')},A{r},{JR('C')},\"Adjusting\")-SUMIFS({JR('G')},{JR('D')},A{r},{JR('C')},\"Adjusting\")",
         8: f"=F{r}+G{r}", 9: f"=MAX(H{r},0)", 10: f"=MAX(-H{r},0)"}
    for col, v in f.items():
        x = ws.cell(row=r, column=col, value=v); x.number_format = NUM; x.font = GREEN if col == 4 else N
tl = 4 + len(COA); t = tl + 1
ws.cell(row=t, column=2, value="Totals").font = B
for col in range(4, 11):
    L = get_column_letter(col); x = ws.cell(row=t, column=col, value=f"=SUM({L}5:{L}{tl})"); x.font = B; x.number_format = NUM; x.border = TOP
ws.cell(row=t + 1, column=2, value="Check: adjusted debits - credits").font = B
x = ws.cell(row=t + 1, column=10, value=f"=I{t}-J{t}"); x.font = B; x.number_format = NUM
widths(ws, [7, 30, 10, 14, 15, 14, 15, 14, 14, 14]); ws.freeze_panes = "C5"
row_of = {c: 5 + i for i, (c, *_) in enumerate(COA)}
TB = lambda c: f"'Trial Balance'!H{row_of[c]}"

ws = wb.create_sheet("Profit and Loss")
title(ws, "Profit and Loss, October 2026", "Linked to the adjusted trial balance.")
header(ws, 4, ["Line", "₹"])
r = 5
def line(ws, r, label, f, bold=False, green=True):
    ws.cell(row=r, column=1, value=label).font = B if bold else N
    x = ws.cell(row=r, column=2, value=f); x.number_format = NUM; x.font = B if bold else (GREEN if green else N)
line(ws, 5, "Sales revenue", f"=-{TB(4000)}"); line(ws, 6, "Cost of goods sold", f"={TB(5000)}")
line(ws, 7, "Gross profit", "=B5-B6", True)
exps = [c for c, _, t_, _ in COA if t_ == "Expense" and c != 5000]
for i, c in enumerate(exps): line(ws, 8 + i, NAME[c], f"={TB(c)}")
e1, e2 = 8, 7 + len(exps)
line(ws, e2 + 1, "Total operating expenses", f"=SUM(B{e1}:B{e2})", True)
line(ws, e2 + 2, "Net profit for October", f"=B7-B{e2+1}", True)
ws.cell(row=e2 + 3, column=1, value="Unadjusted profit (before month-end entries), for comparison").font = N
x = ws.cell(row=e2 + 3, column=2, value="=-SUMIFS('Trial Balance'!F5:F%d,'Trial Balance'!C5:C%d,\"Income\")-SUMIFS('Trial Balance'!F5:F%d,'Trial Balance'!C5:C%d,\"Expense\")" % (tl, tl, tl, tl)); x.number_format = NUM
NPCELL = f"'Profit and Loss'!B{e2+2}"
widths(ws, [58, 16])

ws = wb.create_sheet("Balance Sheet")
title(ws, "Balance Sheet at 31 October 2026", "Linked to the adjusted trial balance; October profit added to retained earnings.")
header(ws, 4, ["Line", "₹"])
items = [("Cash at bank", f"={TB(1000)}"), ("Accounts receivable", f"={TB(1100)}"), ("Less: allowance for doubtful debts", f"={TB(1150)}"),
         ("Inventory", f"={TB(1200)}"), ("Prepaid insurance", f"={TB(1300)}"), ("Office equipment", f"={TB(1500)}"),
         ("Less: accumulated depreciation", f"={TB(1510)}")]
for i, (l, f) in enumerate(items): line(ws, 5 + i, l, f)
line(ws, 12, "Total assets", "=SUM(B5:B11)", True)
liab = [("Accounts payable", f"=-{TB(2000)}"), ("Accrued expenses", f"=-{TB(2100)}"), ("Salaries payable", f"=-{TB(2110)}"),
        ("Interest payable", f"=-{TB(2310)}"), ("Term loan", f"=-{TB(2300)}"), ("Share capital", f"=-{TB(3000)}"),
        ("Retained earnings (opening)", f"=-{TB(3100)}"), ("Profit for October", f"={NPCELL}")]
for i, (l, f) in enumerate(liab): line(ws, 14 + i, l, f)
line(ws, 22, "Total liabilities and equity", "=SUM(B14:B21)", True)
line(ws, 24, "Check: assets - (liabilities + equity)", "=B12-B22", True)
widths(ws, [44, 16])

ws = wb.create_sheet("Reconciliations")
title(ws, "Reconciliations at 31 October 2026", "Inputs from the bank statement and subledgers are blue.")
ws["A4"] = "Bank reconciliation"; ws["A4"].font = B
line(ws, 5, "Balance per bank statement", bank_stmt, green=False); ws["B5"].font = BLUE
line(ws, 6, "Less: unpresented cheque 004512 (supplier payment, 29 Oct)", 680000, green=False); ws["B6"].font = BLUE
line(ws, 7, "Adjusted bank balance", "=B5-B6", True)
line(ws, 8, "Balance per GL (after ADJ-09 bank charges)", f"={TB(1000)}")
line(ws, 9, "Difference (should be 0)", "=B7-B8", True)
ws["A11"] = "Accounts receivable subledger"; ws["A11"].font = B
for i, (n, v) in enumerate(AR_SUB):
    line(ws, 12 + i, n, v, green=False); ws.cell(row=12 + i, column=2).font = BLUE
line(ws, 16, "Subledger total", "=SUM(B12:B15)", True); line(ws, 17, "GL control account 1100", f"={TB(1100)}")
line(ws, 18, "Difference (should be 0)", "=B16-B17", True)
ws["A20"] = "Accounts payable subledger"; ws["A20"].font = B
for i, (n, v) in enumerate(AP_SUB):
    line(ws, 21 + i, n, v, green=False); ws.cell(row=21 + i, column=2).font = BLUE
line(ws, 23, "Subledger total", "=SUM(B21:B22)", True); line(ws, 24, "GL control account 2000", f"=-{TB(2000)}")
line(ws, 25, "Difference (should be 0)", "=B23-B24", True)
widths(ws, [58, 16])

ws = wb.create_sheet("Close Checklist")
title(ws, "Month-End Close Checklist, October 2026", "Five working days (WD) after month end.")
header(ws, 4, ["Day", "Task", "Owner", "Status"])
for r, (d, tsk, o) in enumerate(CHECKLIST, 5):
    for col, v in enumerate((d, tsk, o, "Done"), 1): ws.cell(row=r, column=col, value=v).font = N
widths(ws, [8, 60, 20, 10])

for s in wb.worksheets:
    for row in s.iter_rows():
        for c in row:
            if c.font and c.font.name != AR_: c.font = Font(name=AR_, bold=c.font.bold, color=c.font.color)
wb.save("./Month_End_Close_Trial_Balance.xlsx")
print("saved")
