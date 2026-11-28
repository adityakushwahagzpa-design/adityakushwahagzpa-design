from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from model import BASE

A = "Arial"
H = Font(name=A, bold=True, color="FFFFFF"); HF = PatternFill("solid", fgColor="0A2540")
B = Font(name=A, bold=True); N = Font(name=A); BLUE = Font(name=A, color="0000FF"); GREEN = Font(name=A, color="008000")
Y = PatternFill("solid", fgColor="FFFF00"); TOP = Border(top=Side(style="thin", color="999999"))
PCT = '0.00"%"'; NUM2 = '#,##0.00'; NUM4 = '#,##0.0000'

def hdr(ws, r, cols):
    for i, h in enumerate(cols, 1):
        c = ws.cell(row=r, column=i, value=h); c.font = H; c.fill = HF; c.alignment = Alignment(horizontal="center", wrap_text=True)
def w(ws, ws_):
    for i, v in enumerate(ws_, 1): ws.column_dimensions[get_column_letter(i)].width = v
def title(ws, t, s):
    ws["A1"] = t; ws["A1"].font = Font(name=A, bold=True, size=14); ws["A2"] = s; ws["A2"].font = Font(name=A, italic=True, color="555555")
def put(ws, r, label, val, fmt=NUM2, font=N, note=None, inp=False):
    ws.cell(row=r, column=1, value=label).font = N
    c = ws.cell(row=r, column=2, value=val); c.number_format = fmt; c.font = BLUE if inp else font
    if inp: c.fill = Y
    if note: ws.cell(row=r, column=3, value=note).font = Font(name=A, color="555555")

wb = Workbook()
ws = wb.active; ws.title = "Inputs"
title(ws, "Market Linkages Model | How one macro change moves bonds, the rupee and equities",
      "Portfolio project by Aditya Kushwaha, built on the four Bloomberg Market Concepts (BMC) topics. Illustrative inputs: edit the yellow cells.")
hdr(ws, 4, ["Input", "Value", "Note"])
rows = [("CPI inflation (%)", "cpi", "Economic indicator; the RBI's target is 4% CPI"),
        ("Inflation target (%)", "target", "RBI target under flexible inflation targeting"),
        ("Neutral real rate r* (%)", "rstar", "Illustrative assumption"),
        ("Output gap (% of potential GDP)", "gap", "Positive = economy running hot"),
        ("Term premium, 10Y over policy (%)", "term_premium", "Sets the long end of the curve"),
        ("Curve hump (Nelson-Siegel b2)", "curvature", "Shape of the belly"),
        ("Decay parameter tau (years)", "tau", "Nelson-Siegel shape"),
        ("Bond coupon (% a year, paid half-yearly)", "coupon", "10-year G-sec style bond"),
        ("Bond maturity (years)", "maturity", ""),
        ("US 1-year rate (%)", "us_rate", "Foreign rate for interest rate parity"),
        ("USD/INR spot", "spot", "Illustrative"),
        ("FX forward horizon (years)", "fx_years", ""),
        ("Next year's dividend D1 (Rs)", "d1", "Sample stock"),
        ("Dividend growth g (%)", "g", ""),
        ("Beta", "beta", ""),
        ("Equity risk premium (%)", "erp", "")]
R = {}
for i, (lab, k, note) in enumerate(rows, 5):
    put(ws, i, lab, BASE[k], NUM2, note=note, inp=True); R[k] = f"Inputs!$B${i}"
w(ws, [42, 14, 60])

ws = wb.create_sheet("Economy")
title(ws, "Economic indicators to policy rate (Taylor rule)", "i = r* + inflation + 0.5 x (inflation - target) + 0.5 x output gap")
put(ws, 4, "Inflation gap (pts)", f"={R['cpi']}-{R['target']}", PCT)
put(ws, 5, "Implied policy (repo) rate (%)", f"={R['rstar']}+{R['cpi']}+0.5*({R['cpi']}-{R['target']})+0.5*{R['gap']}", PCT, B)
put(ws, 6, "Real policy rate (%)", "=B5-" + R['cpi'], PCT)
put(ws, 7, "Stance", '=IF(B6>' + R['rstar'] + '+0.25,"Restrictive",IF(B6<' + R['rstar'] + '-0.25,"Accommodative","Neutral"))', "@")
w(ws, [38, 16, 40]); POL = "Economy!$B$5"

ws = wb.create_sheet("Yield Curve")
title(ws, "Government bond yield curve (Nelson-Siegel)", "Short end anchored to the policy rate; long end = policy rate + term premium.")
put(ws, 4, "Short rate b0+b1 (%)", f"={POL}", PCT)
put(ws, 5, "Long level b0 (%)", f"={POL}+{R['term_premium']}", PCT)
put(ws, 6, "Slope b1", "=B4-B5", NUM4); put(ws, 7, "Curvature b2", f"={R['curvature']}", NUM4); put(ws, 8, "tau", f"={R['tau']}", NUM2)
hdr(ws, 10, ["Maturity (years)", "Yield (%)"])
mats = [0.25, 0.5, 1, 2, 3, 5, 7, 10, 15, 20, 30]
for j, m in enumerate(mats, 11):
    ws.cell(row=j, column=1, value=m).font = BLUE; ws.cell(row=j, column=1).number_format = "0.00"
    f = f"=$B$5+$B$6*((1-EXP(-A{j}/$B$8))/(A{j}/$B$8))+$B$7*(((1-EXP(-A{j}/$B$8))/(A{j}/$B$8))-EXP(-A{j}/$B$8))"
    c = ws.cell(row=j, column=2, value=f); c.number_format = PCT
r10 = 11 + mats.index(10); r1 = 11 + mats.index(1)
put(ws, 23, "Curve shape (10Y minus 3M)", f"=B{r10}-B11", PCT)
put(ws, 24, "Shape", '=IF(B23>0.25,"Normal (upward)",IF(B23<-0.25,"Inverted","Flat"))', "@")
w(ws, [30, 16]); Y10 = f"'Yield Curve'!$B${r10}"
NSF = lambda mexpr: (f"(({POL}+{R['term_premium']})+({POL}-({POL}+{R['term_premium']}))*((1-EXP(-({mexpr})/{R['tau']}))/(({mexpr})/{R['tau']}))"
                     f"+{R['curvature']}*(((1-EXP(-({mexpr})/{R['tau']}))/(({mexpr})/{R['tau']}))-EXP(-({mexpr})/{R['tau']})))")

ws = wb.create_sheet("Bond")
title(ws, "Fixed income: bond price, duration and convexity", "Half-yearly coupons, priced at the curve yield for its maturity.")
put(ws, 4, "Yield to maturity (%)", "=" + NSF(R['maturity']), PCT, B)
put(ws, 5, "Periods (half-years)", f"={R['maturity']}*2", "0")
put(ws, 6, "Price per Rs 100 face", f"=PV(B4/200,B5,-{R['coupon']}/2,-100)", NUM4, B)
hdr(ws, 8, ["Period", "Time (yrs)", "Cash flow", "Discount factor", "PV", "t x PV", "t(t+1) x PV"])
for t in range(1, 61):
    r = 8 + t
    vals = {1: t, 2: f"=A{r}/2", 3: f"=IF(A{r}<=$B$5,{R['coupon']}/2+IF(A{r}=$B$5,100,0),0)",
            4: f"=1/(1+$B$4/200)^A{r}", 5: f"=C{r}*D{r}", 6: f"=B{r}*E{r}", 7: f"=A{r}*(A{r}+1)*C{r}/(1+$B$4/200)^(A{r}+2)"}
    for col, v in vals.items():
        c = ws.cell(row=r, column=col, value=v); c.number_format = "0" if col == 1 else NUM4
last = 68
put(ws, 7, "Check: sum of PVs = price", f"=SUM(E9:E{last})-B6", NUM4)
ws["I4"] = "Macaulay duration (yrs)"; ws["J4"] = f"=SUM(F9:F{last})/SUM(E9:E{last})"
ws["I5"] = "Modified duration"; ws["J5"] = "=J4/(1+B4/200)"
ws["I6"] = "Convexity"; ws["J6"] = f"=SUM(G9:G{last})/SUM(E9:E{last})/4"
ws["I8"] = "Yield shock (bp)"; ws["J8"] = 100; ws["J8"].font = BLUE; ws["J8"].fill = Y
ws["I9"] = "Price change: duration + convexity"; ws["J9"] = "=B6*(-J5*J8/10000+0.5*J6*(J8/10000)^2)"
ws["I10"] = "Price change: exact repricing"; ws["J10"] = f"=PV((B4+J8/100)/200,B5,-{R['coupon']}/2,-100)-B6"
for c in ["J4", "J5", "J6", "J9", "J10"]: ws[c].number_format = NUM4
for c in ["I4", "I5", "I6", "I8", "I9", "I10"]: ws[c].font = N
ws["I11"] = "Bond rows cover maturities up to 30 years (60 half-years)."; ws["I11"].font = Font(name=A, italic=True, color="555555")
w(ws, [24, 12, 12, 14, 12, 12, 14, 3, 36, 14])

ws = wb.create_sheet("FX")
title(ws, "Currencies: USD/INR forward by covered interest rate parity", "F = S x ((1 + i INR) / (1 + i USD)) ^ T")
put(ws, 4, "INR rate for the horizon (%)", "=" + NSF(R['fx_years']), PCT)
put(ws, 5, "USD rate (%)", f"={R['us_rate']}", PCT)
put(ws, 6, "Spot USD/INR", f"={R['spot']}", NUM4)
put(ws, 7, "Forward USD/INR", f"=B6*((1+B4/100)/(1+B5/100))^{R['fx_years']}", NUM4, B)
put(ws, 8, "Forward premium (% a year)", f"=((B7/B6)^(1/{R['fx_years']})-1)*100", PCT)
put(ws, 9, "Reading", '=IF(B7>B6,"USD at a forward premium: higher INR rates offset by expected INR depreciation","USD at a forward discount")', "@")
w(ws, [32, 16])

ws = wb.create_sheet("Equity")
title(ws, "Equities: CAPM cost of equity and Gordon growth value", "ke = 10Y yield + beta x ERP ; Value = D1 / (ke - g)")
put(ws, 4, "Risk-free rate = 10Y yield (%)", f"={Y10}", PCT, GREEN)
put(ws, 5, "Cost of equity ke (%)", f"=B4+{R['beta']}*{R['erp']}", PCT, B)
put(ws, 6, "Fair value per share (Rs)", f'=IF(B5>{R["g"]},{R["d1"]}/((B5-{R["g"]})/100),"ke must exceed g")', NUM2, B)
put(ws, 7, "Implied forward P/E at 50% payout", f'=IF(B5>{R["g"]},0.5/((B5-{R["g"]})/100),"n/a")', NUM2)
ws["A9"] = "Sensitivity: fair value (Rs) for cost of equity (rows) and growth (columns)"; ws["A9"].font = B
gs = [6, 7, 8, 9, 10]; kes = [10, 11, 12, 13, 14]
for j, g in enumerate(gs, 2):
    c = ws.cell(row=10, column=j, value=g); c.font = BLUE; c.number_format = '0.0"%"'
for i, ke in enumerate(kes, 11):
    c = ws.cell(row=i, column=1, value=ke); c.font = BLUE; c.number_format = '0.0"%"'
    for j in range(2, 7):
        L = get_column_letter(j); cc = ws.cell(row=i, column=j, value=f'=IF($A{i}>{L}$10,{R["d1"]}/(($A{i}-{L}$10)/100),"-")'); cc.number_format = NUM2
w(ws, [34, 14, 12, 12, 12, 12])

ws = wb.create_sheet("Scenarios")
title(ws, "Scenarios: one change, every market", "Each row re-runs the chain with its own inputs (blue). Other inputs come from the Inputs sheet.")
cols = ["Scenario", "CPI (%)", "Output gap (%)", "Term premium (%)", "Dividend growth (%)", "Policy rate (%)", "10Y yield (%)", "Bond price (Rs)", "USD/INR forward", "Stock value (Rs)"]
hdr(ws, 4, cols)
sc = [("Base case", BASE["cpi"], BASE["gap"], BASE["term_premium"], BASE["g"]), ("Inflation spike", 5.5, 0.0, 1.2, 7.5),
      ("Growth slowdown", 3.5, -2.0, 0.6, 6.0), ("Overheating", 5.0, 1.5, 1.0, 8.5), ("Disinflation and rate cuts", 3.0, -0.5, 1.0, 8.0)]
for i, (nm, cpi, gap, tp, gg) in enumerate(sc, 5):
    ws.cell(row=i, column=1, value=nm).font = N
    for j, v in enumerate((cpi, gap, tp, gg), 2):
        c = ws.cell(row=i, column=j, value=v); c.font = BLUE; c.number_format = NUM2
    pol = f"({R['rstar']}+B{i}+0.5*(B{i}-{R['target']})+0.5*C{i})"
    ws.cell(row=i, column=6, value="=" + pol).number_format = NUM2
    def nsm(m, pol=pol, i=i):
        return (f"(({pol}+D{i})+(-D{i})*((1-EXP(-{m}/{R['tau']}))/({m}/{R['tau']}))"
                f"+{R['curvature']}*(((1-EXP(-{m}/{R['tau']}))/({m}/{R['tau']}))-EXP(-{m}/{R['tau']})))")
    ws.cell(row=i, column=7, value="=" + nsm(10)).number_format = NUM2
    ws.cell(row=i, column=8, value=f"=PV({nsm(R['maturity'])}/200,{R['maturity']}*2,-{R['coupon']}/2,-100)").number_format = NUM2
    ws.cell(row=i, column=9, value=f"={R['spot']}*((1+{nsm(R['fx_years'])}/100)/(1+{R['us_rate']}/100))^{R['fx_years']}").number_format = NUM4
    ws.cell(row=i, column=10, value=f'=IF(G{i}+{R["beta"]}*{R["erp"]}>E{i},{R["d1"]}/((G{i}+{R["beta"]}*{R["erp"]}-E{i})/100),"-")').number_format = NUM2
w(ws, [28, 10, 14, 15, 15, 14, 13, 15, 16, 16])

for s in wb.worksheets:
    for row in s.iter_rows():
        for c in row:
            if c.value is not None and c.font.name != A: c.font = Font(name=A, bold=c.font.bold, color=c.font.color)
wb.save("Market_Linkages_Model.xlsx"); print("saved")
