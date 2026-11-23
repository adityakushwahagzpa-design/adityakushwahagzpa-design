"""
Builds Flipkart_Product_Analysis_Dashboard.xlsx from data/products.csv and data/orders.csv.

Sheets
  Dashboard  KPIs, five summary tables and four charts - every number is a live formula
  Products   2,000 products; discount, discount band, units, revenue and returns are formulas
  Orders     25,000 order lines for 2025; month, category and revenue are formulas
  Notes      data dictionary and how the dashboard is calculated

Run generate_data.py first if data/ is empty, then recalculate in Excel (or LibreOffice) to see the values.
"""
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

HERE = Path(__file__).parent
OUT = HERE / "Flipkart_Product_Analysis_Dashboard.xlsx"
BLUE, YELLOW, LIGHT, GREY = "2874F0", "FFE11B", "EAF1FD", "F5F5F5"
F = "Arial"
thin = Side(style="thin", color="D0D7E2")
BOX = Border(left=thin, right=thin, top=thin, bottom=thin)

p = pd.read_csv(HERE / "data" / "products.csv")
o = pd.read_csv(HERE / "data" / "orders.csv", parse_dates=["order_date"])
NP, NO = len(p), len(o)
PR, OR = NP + 1, NO + 1  # last data row

# orders for sorting tables (values only decide row order; every figure on the dashboard is a formula)
om = o.merge(p, on="product_id")
om["rev"] = om["quantity"] * om["unit_price_paid"]
cat_order = om.groupby("category")["rev"].sum().sort_values(ascending=False).index.tolist()
brand_order = om.groupby("brand")["rev"].sum().sort_values(ascending=False).head(10).index.tolist()

wb = Workbook()
dash = wb.active
dash.title = "Dashboard"
ps, os_, ns = wb.create_sheet("Products"), wb.create_sheet("Orders"), wb.create_sheet("Notes")


def header(ws, row, cols, start=1):
    for j, name in enumerate(cols):
        c = ws.cell(row=row, column=start + j, value=name)
        c.font = Font(name=F, bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=BLUE)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BOX


# ---------------- Products ----------------
pcols = ["Product ID", "Product name", "Category", "Sub-category", "Brand", "MRP (₹)", "Selling price (₹)",
         "Discount %", "Discount band", "Rating", "Rating count", "Flipkart Assured",
         "Units sold", "Revenue (₹)", "Returned lines", "Order lines"]
header(ps, 1, pcols)
oid = f"Orders!$D$2:$D${OR}"
for i, r in enumerate(p.itertuples(index=False), start=2):
    vals = [r.product_id, r.product_name, r.category, r.sub_category, r.brand, r.mrp, r.selling_price]
    for j, v in enumerate(vals, start=1):
        ps.cell(row=i, column=j, value=v)
    ps.cell(row=i, column=8, value=f"=1-G{i}/F{i}")
    ps.cell(row=i, column=9, value=f'=IF(H{i}<0.1,"0-10%",IF(H{i}<0.3,"10-30%",IF(H{i}<0.5,"30-50%",IF(H{i}<0.7,"50-70%","70%+"))))')
    ps.cell(row=i, column=10, value=r.rating)
    ps.cell(row=i, column=11, value=r.rating_count)
    ps.cell(row=i, column=12, value=r.flipkart_assured)
    ps.cell(row=i, column=13, value=f"=SUMIF({oid},A{i},Orders!$F$2:$F${OR})")
    ps.cell(row=i, column=14, value=f"=SUMIF({oid},A{i},Orders!$H$2:$H${OR})")
    ps.cell(row=i, column=15, value=f'=COUNTIFS({oid},A{i},Orders!$I$2:$I${OR},"Yes")')
    ps.cell(row=i, column=16, value=f"=COUNTIF({oid},A{i})")
fmt = {6: "#,##0", 7: "#,##0", 8: "0.0%", 10: "0.0", 11: "#,##0", 13: "#,##0", 14: "#,##0", 15: "#,##0", 16: "#,##0"}
for col, nf in fmt.items():
    for i in range(2, PR + 1):
        ps.cell(row=i, column=col).number_format = nf
for j, w in enumerate([11, 34, 22, 18, 16, 10, 12, 10, 11, 8, 11, 10, 10, 13, 10, 10], start=1):
    ps.column_dimensions[get_column_letter(j)].width = w
ps.freeze_panes = "C2"
ps.auto_filter.ref = f"A1:P{PR}"

# ---------------- Orders ----------------
ocols = ["Order ID", "Order date", "Month", "Product ID", "Category", "Quantity", "Unit price paid (₹)", "Revenue (₹)", "Returned"]
header(os_, 1, ocols)
for i, r in enumerate(o.itertuples(index=False), start=2):
    os_.cell(row=i, column=1, value=r.order_id)
    c = os_.cell(row=i, column=2, value=r.order_date.to_pydatetime())
    c.number_format = "dd-mmm-yyyy"
    os_.cell(row=i, column=3, value=f"=MONTH(B{i})")
    os_.cell(row=i, column=4, value=r.product_id)
    os_.cell(row=i, column=5, value=f"=INDEX(Products!$C$2:$C${PR},MATCH(D{i},Products!$A$2:$A${PR},0))")
    os_.cell(row=i, column=6, value=r.quantity)
    os_.cell(row=i, column=7, value=r.unit_price_paid).number_format = "#,##0"
    os_.cell(row=i, column=8, value=f"=F{i}*G{i}").number_format = "#,##0"
    os_.cell(row=i, column=9, value=r.returned)
for j, w in enumerate([14, 13, 8, 11, 22, 9, 13, 12, 9], start=1):
    os_.column_dimensions[get_column_letter(j)].width = w
os_.freeze_panes = "A2"
os_.auto_filter.ref = f"A1:I{OR}"

# ---------------- Dashboard ----------------
P = lambda col: f"Products!${col}$2:${col}${PR}"  # noqa: E731
O = lambda col: f"Orders!${col}$2:${col}${OR}"  # noqa: E731
dash.sheet_view.showGridLines = False
for j, w in enumerate([24, 12, 12, 17, 12, 12, 12, 12, 3, 16, 12, 14, 13, 12, 4], start=1):
    dash.column_dimensions[get_column_letter(j)].width = w

dash.merge_cells("A1:N1")
t = dash["A1"]
t.value = "Flipkart Product Analysis Dashboard — 2025"
t.font = Font(name=F, size=18, bold=True, color="FFFFFF")
t.fill = PatternFill("solid", fgColor=BLUE)
t.alignment = Alignment(vertical="center", indent=1)
dash.row_dimensions[1].height = 34
dash.merge_cells("A2:N2")
dash["A2"].value = (f"Synthetic Flipkart-style data: {NP:,} products in 8 categories and {NO:,} order lines (Jan–Dec 2025). "
                    "Every figure is a live formula on the Products and Orders sheets.")
dash["A2"].font = Font(name=F, size=9, italic=True, color="555555")

kpis = [
    ("Products", f"=COUNTA({P('A')})", "#,##0"),
    ("Order lines", f"=COUNTA({O('A')})", "#,##0"),
    ("Units sold", f"=SUM({O('F')})", "#,##0"),
    ("GMV (₹ crore)", f"=SUM({O('H')})/10^7", "#,##0.00"),
    ("Avg discount", f"=AVERAGE({P('H')})", "0.0%"),
    ("Avg rating", f"=AVERAGE({P('J')})", "0.00"),
    ("Return rate", f'=COUNTIF({O("I")},"Yes")/COUNTA({O("A")})', "0.0%"),
]
kpi_cols = [1, 3, 5, 7, 10, 12, 14]
for (label, formula, nf), col in zip(kpis, kpi_cols):
    lc = dash.cell(row=4, column=col, value=label)
    lc.font = Font(name=F, size=9, bold=True, color="555555")
    vc = dash.cell(row=5, column=col, value=formula)
    vc.font = Font(name=F, size=16, bold=True, color=BLUE)
    vc.number_format = nf
    for r in (4, 5):
        dash.cell(row=r, column=col).fill = PatternFill("solid", fgColor=LIGHT)
dash.row_dimensions[5].height = 26


def table_title(row, col, text):
    c = dash.cell(row=row, column=col, value=text)
    c.font = Font(name=F, size=12, bold=True, color="212121")
    dash.cell(row=row, column=col).border = Border(bottom=Side(style="medium", color=YELLOW))


def body(r0, r1, c0, c1, formats):
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            cell = dash.cell(row=r, column=c)
            cell.border = BOX
            cell.font = Font(name=F, size=10)
            if (r - r0) % 2:
                cell.fill = PatternFill("solid", fgColor=GREY)
            nf = formats.get(c - c0)
            if nf:
                cell.number_format = nf


# Table 1: category performance (rows 8-16)
table_title(7, 1, "Category performance")
header(dash, 8, ["Category", "Products", "Units sold", "GMV (₹ crore)", "GMV share", "Avg discount", "Avg rating", "Return rate"])
for k, cat in enumerate(cat_order):
    r = 9 + k
    dash.cell(row=r, column=1, value=cat)
    dash.cell(row=r, column=2, value=f"=COUNTIF({P('C')},A{r})")
    dash.cell(row=r, column=3, value=f"=SUMIF({O('E')},A{r},{O('F')})")
    dash.cell(row=r, column=4, value=f"=SUMIF({O('E')},A{r},{O('H')})/10^7")
    dash.cell(row=r, column=5, value=f"=D{r}/SUM($D$9:$D$16)")
    dash.cell(row=r, column=6, value=f"=AVERAGEIF({P('C')},A{r},{P('H')})")
    dash.cell(row=r, column=7, value=f"=AVERAGEIF({P('C')},A{r},{P('J')})")
    dash.cell(row=r, column=8, value=f'=COUNTIFS({O("E")},A{r},{O("I")},"Yes")/COUNTIF({O("E")},A{r})')
body(9, 16, 1, 8, {1: "#,##0", 2: "#,##0", 3: "#,##0.00", 4: "0.0%", 5: "0.0%", 6: "0.00", 7: "0.0%"})

# Table 2: monthly GMV (rows 8-20, columns J-L)
table_title(7, 10, "Monthly sales (Big Billion Days: 1–10 Oct)")
header(dash, 8, ["Month", "GMV (₹ crore)", "Units sold"], start=10)
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
for k, mname in enumerate(months):
    r = 9 + k
    dash.cell(row=r, column=10, value=mname)
    dash.cell(row=r, column=11, value=f"=SUMIF({O('C')},{k + 1},{O('H')})/10^7")
    dash.cell(row=r, column=12, value=f"=SUMIF({O('C')},{k + 1},{O('F')})")
body(9, 20, 10, 12, {1: "#,##0.00", 2: "#,##0"})

# Table 3: discount bands (rows 23-28)
table_title(22, 1, "Discount depth vs rating and returns")
header(dash, 23, ["Discount band", "Products", "Avg rating", "Units per product", "Return rate"])
for k, band in enumerate(["0-10%", "10-30%", "30-50%", "50-70%", "70%+"]):
    r = 24 + k
    dash.cell(row=r, column=1, value=band)
    dash.cell(row=r, column=2, value=f"=COUNTIF({P('I')},A{r})")
    dash.cell(row=r, column=3, value=f"=AVERAGEIF({P('I')},A{r},{P('J')})")
    dash.cell(row=r, column=4, value=f"=SUMIF({P('I')},A{r},{P('M')})/B{r}")
    dash.cell(row=r, column=5, value=f"=SUMIF({P('I')},A{r},{P('O')})/SUMIF({P('I')},A{r},{P('P')})")
body(24, 28, 1, 5, {1: "#,##0", 2: "0.00", 3: "#,##0.0", 4: "0.0%"})

# Table 4: Flipkart Assured (rows 31-33)
table_title(30, 1, "Flipkart Assured vs not")
header(dash, 31, ["Flipkart Assured", "Products", "Avg rating", "Units per product", "Return rate"])
for k, flag in enumerate(["Yes", "No"]):
    r = 32 + k
    dash.cell(row=r, column=1, value=flag)
    dash.cell(row=r, column=2, value=f"=COUNTIF({P('L')},A{r})")
    dash.cell(row=r, column=3, value=f"=AVERAGEIF({P('L')},A{r},{P('J')})")
    dash.cell(row=r, column=4, value=f"=SUMIF({P('L')},A{r},{P('M')})/B{r}")
    dash.cell(row=r, column=5, value=f"=SUMIF({P('L')},A{r},{P('O')})/SUMIF({P('L')},A{r},{P('P')})")
body(32, 33, 1, 5, {1: "#,##0", 2: "0.00", 3: "#,##0.0", 4: "0.0%"})

# Table 5: top 10 brands (rows 23-33, columns J-M)
table_title(22, 10, "Top 10 brands by GMV")
header(dash, 23, ["Brand", "Products", "GMV (₹ crore)", "Avg rating"], start=10)
for k, brand in enumerate(brand_order):
    r = 24 + k
    dash.cell(row=r, column=10, value=brand)
    dash.cell(row=r, column=11, value=f"=COUNTIF({P('E')},J{r})")
    dash.cell(row=r, column=12, value=f"=SUMIF({P('E')},J{r},{P('N')})/10^7")
    dash.cell(row=r, column=13, value=f"=AVERAGEIF({P('E')},J{r},{P('J')})")
body(24, 33, 10, 13, {1: "#,##0", 2: "#,##0.00", 3: "0.00"})


def finish(ch, title, ytitle=None):
    ch.title = title
    ch.roundedCorners = False
    ch.legend = None
    if ytitle:
        ch.y_axis.title = ytitle
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    ch.height, ch.width = 8.5, 14
    if ch.dataLabels is not None:
        for k in ("showSerName", "showCatName", "showLegendKey", "showPercent"):
            setattr(ch.dataLabels, k, False)
    return ch


c1 = BarChart()
c1.add_data(Reference(dash, min_col=4, min_row=8, max_row=16), titles_from_data=True)
c1.set_categories(Reference(dash, min_col=1, min_row=9, max_row=16))
c1.series[0].graphicalProperties.solidFill = BLUE
c1.dataLabels = DataLabelList()
c1.dataLabels.showVal = True
c1.dataLabels.numFmt = "0.00"
dash.add_chart(finish(c1, "GMV by category (₹ crore)"), "A37")

c2 = LineChart()
c2.add_data(Reference(dash, min_col=11, min_row=8, max_row=20), titles_from_data=True)
c2.set_categories(Reference(dash, min_col=10, min_row=9, max_row=20))
c2.series[0].graphicalProperties.line.solidFill = BLUE
c2.series[0].graphicalProperties.line.width = 28000
c2.series[0].smooth = False
dash.add_chart(finish(c2, "Monthly GMV (₹ crore)"), "J37")

c3 = BarChart()
c3.add_data(Reference(dash, min_col=3, min_row=23, max_row=28), titles_from_data=True)
c3.set_categories(Reference(dash, min_col=1, min_row=24, max_row=28))
c3.series[0].graphicalProperties.solidFill = "F9A825"
c3.y_axis.scaling.min = 3.0
c3.y_axis.scaling.max = 4.3
c3.dataLabels = DataLabelList()
c3.dataLabels.showVal = True
c3.dataLabels.numFmt = "0.00"
dash.add_chart(finish(c3, "Average rating by discount band"), "A56")

c4 = BarChart()
c4.add_data(Reference(dash, min_col=8, min_row=8, max_row=16), titles_from_data=True)
c4.set_categories(Reference(dash, min_col=1, min_row=9, max_row=16))
c4.series[0].graphicalProperties.solidFill = "E53935"
c4.dataLabels = DataLabelList()
c4.dataLabels.showVal = True
c4.dataLabels.numFmt = "0.0%"
c4.y_axis.numFmt = "0%"
dash.add_chart(finish(c4, "Return rate by category"), "J56")

dash.row_dimensions[31].height = 16
dash.page_setup.orientation = "landscape"
dash.page_setup.paperSize = dash.PAPERSIZE_A4
dash.page_setup.fitToWidth = 1
dash.page_setup.fitToHeight = 1
dash.sheet_properties.pageSetUpPr.fitToPage = True
dash.print_area = "A1:O73"

# ---------------- Notes ----------------
notes = [
    ("About this workbook", ""),
    ("Data", f"Synthetic Flipkart-style data made by generate_data.py (seeded): {NP:,} products, {NO:,} order lines dated 1 Jan – 31 Dec 2025. Not real Flipkart data."),
    ("Raw data (edit these)", "Products columns A–G and J–L; Orders columns A, B, D and F–G and I. Everything else is a formula."),
    ("Products!H  Discount %", "1 − Selling price ÷ MRP  (formula =1-G2/F2)"),
    ("Products!I  Discount band", "0-10%, 10-30%, 30-50%, 50-70%, 70%+ from Discount %"),
    ("Products!M–P", "Units sold, revenue, returned lines and order lines per product, summed from Orders with SUMIF / COUNTIFS"),
    ("Orders!C  Month", "Month number of the order date  (formula =MONTH(B2))"),
    ("Orders!E  Category", "Looked up from Products with INDEX / MATCH on Product ID"),
    ("Orders!G  Unit price paid", "Selling price at the time of the order; 5–15% lower during Big Billion Days (1–10 Oct 2025)"),
    ("Orders!H  Revenue", "Quantity × Unit price paid  (formula =F2*G2)"),
    ("GMV", "Gross merchandise value: revenue of all order lines, before returns, in ₹ crore (1 crore = 10,000,000)"),
    ("Return rate", "Returned order lines ÷ all order lines"),
    ("Units per product", "Units sold in the group ÷ number of products in the group"),
    ("Dashboard order", "Categories are listed by GMV and brands are the top 10 by GMV when the workbook was built; the figures are live formulas"),
]
for i, (k, v) in enumerate(notes, start=1):
    ns.cell(row=i, column=1, value=k).font = Font(name=F, bold=True, size=12 if i == 1 else 10)
    c = ns.cell(row=i, column=2, value=v)
    c.font = Font(name=F, size=10)
    c.alignment = Alignment(wrap_text=True, vertical="top")
ns.column_dimensions["A"].width = 28
ns.column_dimensions["B"].width = 100

for ws in (ps, os_):
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.font = Font(name=F, size=10)

wb.save(OUT)
print("saved", OUT)
