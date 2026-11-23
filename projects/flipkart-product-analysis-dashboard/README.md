# Flipkart Product Analysis Dashboard | Excel + SQL (PostgreSQL)

An Excel dashboard on a Flipkart-style product catalogue: 2,000 products in 8 categories and 25,000 order lines for 2025. It shows where GMV comes from, how discount depth affects ratings and returns, what the Flipkart Assured badge is worth, which brands lead and how much the Big Billion Days sale adds. Every number on the dashboard is a live Excel formula, and the same data is analysed in PostgreSQL with 14 SQL queries that reproduce the dashboard and go further.

| | |
|:--|:--|
| **What was analysed** | 2,000 products (category, brand, MRP, selling price, rating, rating count, Flipkart Assured) and 25,000 order lines for January–December 2025 (date, product, quantity, price paid, returned) |
| **What was done** | Product sheet with discount %, discount band, units sold, revenue and returns as formulas (SUMIF, COUNTIFS); order sheet with month, category lookup (INDEX/MATCH) and revenue; a one-page dashboard with 7 KPIs, 5 summary tables (COUNTIF, SUMIF, AVERAGEIF, COUNTIFS) and 4 charts. The same data loaded into PostgreSQL and analysed with 14 queries; every KPI and table matches the Excel dashboard |
| **Key finding** | Mobiles make up 9.9% of products but 41.6% of GMV, while Fashion sells the most units (24.6%) for only 5.2% of GMV and has double the average return rate (15.0% vs 7.2%). Very deep discounts backfire: products at 70%+ off average a 3.57 rating and a 17.5% return rate, against 4.06 and 2.9% at under 10% off. Flipkart Assured products sell 64% more units each (20.6 vs 12.5) with about half the returns (5.6% vs 10.3%). October, with Big Billion Days, brings 23.4% of the year's GMV, 3.4 times an average month |

**Workbook:** [Flipkart_Product_Analysis_Dashboard.xlsx](Flipkart_Product_Analysis_Dashboard.xlsx)

![Dashboard](dashboard_preview.png)

## Dashboard Contents

| Section | What it shows | Excel used |
|:--|:--|:--|
| KPI cards | Products, order lines, units sold, GMV (₹ crore), average discount, average rating, return rate | COUNTA, SUM, AVERAGE, COUNTIF |
| Category performance | Products, units, GMV, GMV share, average discount, rating and return rate for each category | COUNTIF, SUMIF, AVERAGEIF, COUNTIFS |
| Monthly sales | GMV and units for each month of 2025 | SUMIF on the month column |
| Discount depth | Rating, units per product and return rate for five discount bands | Nested IF bands, AVERAGEIF, SUMIF |
| Flipkart Assured | Assured vs not: rating, units per product, return rate | COUNTIF, AVERAGEIF, SUMIF |
| Top 10 brands | Products, GMV and rating for the 10 brands with the highest GMV | COUNTIF, SUMIF, AVERAGEIF |
| Charts | GMV by category, monthly GMV, rating by discount band, return rate by category | Excel charts linked to the tables |

## SQL Version (PostgreSQL)

**All 14 queries with their results:** [outputs/sql/RESULTS.md](outputs/sql/RESULTS.md)

| Step | File | What it does |
|:--|:--|:--|
| Schema | [sql/schema.sql](sql/schema.sql) | `products` and `orders` tables with keys and checks (price ≤ MRP, dates in 2025); views `v_products` (discount % and band) and `v_order_lines` (revenue, month, Big Billion Days flag) |
| Queries | [sql/queries.sql](sql/queries.sql) | 14 queries, each headed by its question |
| Runner | [sql/run_sql.py](sql/run_sql.py) | Loads the CSV files with COPY, runs the queries, writes `outputs/sql/` |

| Query | SQL used |
|:--|:--|
| Q01 Headline KPIs · Q02 Category performance · Q05 Discount depth · Q06 Flipkart Assured · Q07 Top 10 brands | CTEs, LEFT JOIN, CASE, share with SUM() OVER (), STRING_AGG |
| Q03 Monthly sales and growth · Q04 Big Billion Days | LAG for month-on-month change, date filters |
| Q08 Category leaders · Q11 GMV concentration | RANK OVER (PARTITION BY category), NTILE(10) with a running total |
| Q09 Returns by sub-category · Q10 Price bands · Q12 Best sellers · Q13 Low-rated products that still sell · Q14 Unsold products | HAVING, CASE bands, FILTER, anti-join with LEFT JOIN ... IS NULL |

Extra findings from SQL:
- **GMV concentration:** the top 10% of products bring 65.4% of GMV and the top 20% bring 81.6%.
- **Big Billion Days:** a sale day averages ₹20.6 lakh of GMV, 7.5 times an ordinary day (₹2.75 lakh), with an extra 10% off the selling price.
- **Price bands:** the 111 products priced ₹30,000+ bring 38.0% of GMV; products under ₹500 sell the most units (15,957) for 3.4% of GMV.

## Workbook Structure

| Sheet | Contents |
|:--|:--|
| Dashboard | KPIs, the five tables and four charts (prints on one A4 landscape page) |
| Products | 2,000 products; columns H–I and M–P are formulas |
| Orders | 25,000 order lines; month, category and revenue are formulas |
| Notes | Data dictionary, formulas and definitions (GMV, return rate, units per product) |

## How It Works

1. `generate_data.py` creates `data/products.csv` and `data/orders.csv` (seeded, so the data is the same on every run).
2. `build_dashboard.py` writes the workbook with openpyxl: raw data as values, every calculation as an Excel formula, plus the dashboard charts.
3. The workbook was recalculated in LibreOffice and checked: 87,145 formulas, 0 errors.

## Limitations

- The data is synthetic. Discount levels, the Big Billion Days spike, return rates by category and the Assured effect were built into the generator, so the dashboard finds them by design; real Flipkart data would be messier.
- GMV is counted before returns and cancellations.
- Category and brand order on the dashboard is fixed at build time; the figures update if the data changes.

## Run It Yourself

```bash
pip install -r requirements.txt
python generate_data.py      # optional: data/ already holds the CSVs
python build_dashboard.py    # then open the workbook in Excel; it recalculates on opening

createdb flipkart            # PostgreSQL version
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/flipkart python sql/run_sql.py
```

**Tools:** Microsoft Excel (SUMIF, COUNTIFS, AVERAGEIF, INDEX/MATCH, charts), PostgreSQL 16, SQL, Python (pandas, openpyxl)

_Synthetic Flipkart-style data for learning purposes; not real Flipkart data._
