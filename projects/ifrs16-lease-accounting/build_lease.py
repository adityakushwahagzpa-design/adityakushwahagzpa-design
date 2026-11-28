"""IFRS 16 / Ind AS 116 lease accounting project: Excel workbook with formulas + check values."""
import json
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

INP = dict(rent=150000, esc=0.05, rate=0.10, years=5, idc=75000, start=date(2026, 4, 1))
n = INP["years"] * 12; r = INP["rate"] / 12
pay = [INP["rent"] * (1 + INP["esc"]) ** ((m - 1) // 12) for m in range(1, n + 1)]
pv = sum(p / (1 + r) ** m for m, p in enumerate(pay, 1))
L = [pv]; intr = []
for m in range(n):
    i = L[-1] * r; intr.append(i); L.append(L[-1] + i - pay[m])
rou = pv + INP["idc"]; dep = rou / n
fy = []
for y in range(INP["years"]):
    s = slice(12 * y, 12 * y + 12)
    fy.append(dict(fy=f"FY{27+y}", interest=sum(intr[s]), dep=dep * 12, rent=sum(pay[s]), close=L[12 * y + 12]))
cur = L[12] - L[24]
facts = dict(pv=pv, rou=rou, total_pay=sum(pay), total_int=sum(intr), y1_charge=fy[0]["interest"] + fy[0]["dep"], y1_rent=fy[0]["rent"],
             cur=cur, noncur=L[24], close_fy27=L[12], end=L[-1])
print(json.dumps({k: round(v) for k, v in facts.items()}, indent=0))
for x in fy: print({k: (round(v) if isinstance(v, float) else v) for k, v in x.items()})
json.dump(dict(inputs={k: (str(v) if k == "start" else v) for k, v in INP.items()}, facts=facts), open("./lease_check.json", "w"))

AR_ = "Arial"
H = Font(name=AR_, bold=True, color="FFFFFF"); HF = PatternFill("solid", fgColor="1F3A5F")
B = Font(name=AR_, bold=True); N = Font(name=AR_); BLUE = Font(name=AR_, color="0000FF"); GREEN = Font(name=AR_, color="008000")
Y = PatternFill("solid", fgColor="FFFF00")
NUM = '#,##0;(#,##0);"-"'; PCT = "0.0%"
TOP = Border(top=Side(style="thin", color="999999"))
def header(ws, row, cols):
    for i, h in enumerate(cols, 1):
        c = ws.cell(row=row, column=i, value=h); c.font = H; c.fill = HF; c.alignment = Alignment(horizontal="center", wrap_text=True)
def widths(ws, w):
    for i, x in enumerate(w, 1): ws.column_dimensions[get_column_letter(i)].width = x
def title(ws, t, sub):
    ws["A1"] = t; ws["A1"].font = Font(name=AR_, bold=True, size=14); ws["A2"] = sub; ws["A2"].font = Font(name=AR_, italic=True, color="555555")

wb = Workbook(); ws = wb.active; ws.title = "Inputs"
title(ws, "IFRS 16 / Ind AS 116 Lease Accounting | Warehouse lease, Kaveri Home Appliances Pvt. Ltd.",
      "Portfolio project by Aditya Kushwaha. Sample lease for a fictional company. Edit the yellow cells; every other sheet recalculates.")
rows = [("Commencement date", INP["start"], "dd-mmm-yyyy", "Lease starts 1 April 2026 (start of FY27)"),
        ("Monthly rent, year 1 (₹)", INP["rent"], NUM, "Payable at the end of each month (in arrears)"),
        ("Annual escalation", INP["esc"], PCT, "Rent steps up at the start of each lease year"),
        ("Lease term (years)", INP["years"], "0", "Non-cancellable period; no extension option reasonably certain"),
        ("Incremental borrowing rate (annual)", INP["rate"], PCT, "Rate implicit in the lease not readily determinable"),
        ("Initial direct costs (₹)", INP["idc"], NUM, "Broker fee; added to the right-of-use asset"),
        ("Monthly discount rate", "=B8/12", "0.0000%", "Annual rate / 12"),
        ("Term in months", "=B7*12", "0", "")]
header(ws, 3, ["Input", "Value", "Note"])
for i, (l, v, fmt, note) in enumerate(rows, 4):
    ws.cell(row=i, column=1, value=l).font = N
    c = ws.cell(row=i, column=2, value=v); c.number_format = fmt
    if not str(v).startswith("="): c.font = BLUE; c.fill = Y
    else: c.font = N
    ws.cell(row=i, column=3, value=note).font = N
widths(ws, [38, 16, 64])

ws = wb.create_sheet("Schedule")
title(ws, "Monthly lease liability and right-of-use asset schedule", "Liability: opening + interest - payment. ROU asset: straight line over the lease term.")
cols = ["Month", "Period end", "Lease year", "Fiscal year", "Payment (₹)", "Discount factor", "PV of payment (₹)",
        "Opening liability (₹)", "Interest (₹)", "Closing liability (₹)", "Opening ROU (₹)", "Depreciation (₹)", "Closing ROU (₹)"]
header(ws, 4, cols)
f0, f1 = 5, 4 + n
for m in range(1, n + 1):
    rr = 4 + m
    f = {1: m, 2: f"=EOMONTH(Inputs!$B$4,A{rr}-1)", 3: f"=INT((A{rr}-1)/12)+1",
         4: f'="FY"&TEXT(MOD(YEAR(B{rr})+IF(MONTH(B{rr})>=4,1,0),100),"00")',
         5: f"=Inputs!$B$5*(1+Inputs!$B$6)^(C{rr}-1)", 6: f"=1/(1+Inputs!$B$10)^A{rr}", 7: f"=E{rr}*F{rr}",
         8: ("=Summary!$B$5" if m == 1 else f"=J{rr-1}"), 9: f"=H{rr}*Inputs!$B$10", 10: f"=H{rr}+I{rr}-E{rr}",
         11: ("=Summary!$B$7" if m == 1 else f"=M{rr-1}"), 12: "=Summary!$B$7/Inputs!$B$11", 13: f"=K{rr}-L{rr}"}
    for col, v in f.items():
        c = ws.cell(row=rr, column=col, value=v); c.font = N
        c.number_format = {1: "0", 2: "dd-mmm-yyyy", 3: "0", 4: "@", 6: "0.0000"}.get(col, NUM)
    ws.cell(row=rr, column=4).number_format = "General"
t = f1 + 1
ws.cell(row=t, column=4, value="Totals").font = B
for col in (5, 7, 9, 12):
    L_ = get_column_letter(col); c = ws.cell(row=t, column=col, value=f"=SUM({L_}{f0}:{L_}{f1})"); c.font = B; c.number_format = NUM; c.border = TOP
widths(ws, [7, 13, 9, 9, 13, 10, 14, 15, 12, 15, 15, 13, 15]); ws.freeze_panes = "B5"
S = lambda col: f"Schedule!${col}${f0}:${col}${f1}"

ws = wb.create_sheet("Summary")
title(ws, "Initial measurement, annual impact and balance sheet split", "All figures are formulas.")
items = [("Initial measurement", None),
         ("Lease liability at commencement (PV of payments) (₹)", f"=SUM({S('G')})"),
         ("Add: initial direct costs (₹)", "=Inputs!B9"),
         ("Right-of-use asset at commencement (₹)", "=B5+B6"),
         ("Total undiscounted payments (₹)", f"=SUM({S('E')})"),
         ("Total interest over the lease (₹)", f"=SUM({S('I')})"),
         ("Check: closing liability at end of term (should be 0)", f"=ROUND(Schedule!J{f1},0)")]
for i, (l, v) in enumerate(items, 4):
    ws.cell(row=i, column=1, value=l).font = B if v is None else N
    if v: c = ws.cell(row=i, column=2, value=v); c.number_format = NUM; c.font = N
ws["A12"] = "Profit and loss impact by fiscal year"; ws["A12"].font = B
hdr = ["Fiscal year", "Interest (₹)", "Depreciation (₹)", "Total IFRS 16 charge (₹)", "Rent paid (₹)", "Charge - rent (₹)", "Closing liability (₹)"]
for i, h in enumerate(hdr, 1):
    c = ws.cell(row=13, column=i, value=h); c.font = H; c.fill = HF; c.alignment = Alignment(horizontal="center", wrap_text=True)
for y in range(INP["years"]):
    rr = 14 + y; ws.cell(row=rr, column=1, value=f"FY{27+y}").font = N
    fs = {2: f"=SUMIFS({S('I')},{S('D')},A{rr})", 3: f"=SUMIFS({S('L')},{S('D')},A{rr})", 4: f"=B{rr}+C{rr}",
          5: f"=SUMIFS({S('E')},{S('D')},A{rr})", 6: f"=D{rr}-E{rr}",
          7: f"=INDEX({S('J')},MATCH(A{rr},{S('D')},0)+11)"}
    for col, v in fs.items(): c = ws.cell(row=rr, column=col, value=v); c.number_format = NUM; c.font = N
tr = 14 + INP["years"]; ws.cell(row=tr, column=1, value="Total").font = B
for col in range(2, 7):
    L_ = get_column_letter(col); c = ws.cell(row=tr, column=col, value=f"=SUM({L_}14:{L_}{tr-1})"); c.font = B; c.number_format = NUM; c.border = TOP
ws.cell(row=tr + 1, column=1, value="Charge is higher than rent in early years (front-loaded interest) and lower later; over the full term the totals differ only by the initial direct costs.").font = Font(name=AR_, italic=True)
b = tr + 3
ws.cell(row=b, column=1, value="Balance sheet split at 31 March 2027").font = B
ws.cell(row=b + 1, column=1, value="Lease liability at 31 March 2027 (₹)").font = N
c = ws.cell(row=b + 1, column=2, value=f"=Schedule!J{4+12}"); c.number_format = NUM
ws.cell(row=b + 2, column=1, value="Current portion: principal due within 12 months (₹)").font = N
c = ws.cell(row=b + 2, column=2, value=f"=Schedule!J{4+12}-Schedule!J{4+24}"); c.number_format = NUM
ws.cell(row=b + 3, column=1, value="Non-current portion (₹)").font = N
c = ws.cell(row=b + 3, column=2, value=f"=B{b+1}-B{b+2}"); c.number_format = NUM
ws.cell(row=b + 4, column=1, value="Right-of-use asset at 31 March 2027 (₹)").font = N
c = ws.cell(row=b + 4, column=2, value=f"=Schedule!M{4+12}"); c.number_format = NUM
m0 = b + 6
ws.cell(row=m0, column=1, value="Maturity analysis of undiscounted payments (disclosure, at commencement)").font = B
for y in range(INP["years"]):
    ws.cell(row=m0 + 1 + y, column=1, value=f"Year {y+1}").font = N
    c = ws.cell(row=m0 + 1 + y, column=2, value=f"=SUMIFS({S('E')},{S('C')},{y+1})"); c.number_format = NUM
widths(ws, [58, 16, 16, 18, 15, 15, 17])

ws = wb.create_sheet("Journal Entries")
title(ws, "Journal entries", "Day one and the first month; the same pattern repeats each month.")
header(ws, 4, ["Date", "Account", "Debit (₹)", "Credit (₹)", "Narration"])
je = [("=Inputs!B4", "Right-of-use asset", "=Summary!B5", None, "Recognise lease at PV of payments"),
      (None, "Lease liability", None, "=Summary!B5", ""),
      ("=Inputs!B4", "Right-of-use asset", "=Inputs!B9", None, "Capitalise initial direct costs"),
      (None, "Cash at bank", None, "=Inputs!B9", ""),
      ("=Schedule!B5", "Interest expense", "=Schedule!I5", None, "Unwind interest for month 1"),
      (None, "Lease liability", None, "=Schedule!I5", ""),
      ("=Schedule!B5", "Lease liability", "=Schedule!E5", None, "Month 1 rent paid"),
      (None, "Cash at bank", None, "=Schedule!E5", ""),
      ("=Schedule!B5", "Depreciation expense", "=Schedule!L5", None, "Month 1 ROU depreciation"),
      (None, "Accumulated depreciation, ROU asset", None, "=Schedule!L5", "")]
for i, row in enumerate(je, 5):
    for col, v in enumerate(row, 1):
        c = ws.cell(row=i, column=col, value=v); c.font = GREEN if (isinstance(v, str) and v.startswith("=")) else N
        if col == 1: c.number_format = "dd-mmm-yyyy"
        if col in (3, 4): c.number_format = NUM
ws.cell(row=15, column=2, value="Totals").font = B
for col, L_ in ((3, "C"), (4, "D")):
    c = ws.cell(row=15, column=col, value=f"=SUM({L_}5:{L_}14)"); c.font = B; c.number_format = NUM; c.border = TOP
widths(ws, [13, 36, 14, 14, 40])
wb.save("./IFRS16_Lease_Accounting.xlsx"); print("saved")
