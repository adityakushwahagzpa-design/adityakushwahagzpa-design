# Bank Transactions Analysis | SQL (PostgreSQL)

A four-table banking database queried from basic SELECTs up to window functions and CTEs: customer and channel analysis, branch performance, digital adoption, and two AML alerts (structuring and dormant-account reactivation) of the kind compliance teams run.

| | |
|:--|:--|
| **What was analysed** | A synthetic bank with 8 branches, 1,200 customers, 1,641 accounts and 143,836 transactions across 8 channels (UPI, NEFT, IMPS, RTGS, ATM, cash, card, cheque), January 2024 to June 2026 |
| **What was done** | Schema with keys and constraints, a balance view and indexes; 20 queries covering joins across all four tables, CASE, FILTER, window functions (running SUM, DENSE_RANK, LAG, moving AVG, NTILE, PERCENT_RANK, RANGE frames), CTEs and PERCENTILE_CONT; an EXPLAIN ANALYZE test of the indexes |
| **Key finding** | UPI's share of debits rose from 38% to 57% in 30 months, and card and UPI spending ran 34–38% higher in October–November. Balances were concentrated: the top 10% of customers held 54%. The AML queries flagged 6 customers making repeated cash deposits just under the ₹50,000 PAN-reporting level (up to 10 in 7 days), 5 of them rated Low or Medium KYC risk, and 7 accounts reactivated after 18+ months of dormancy by credits of ₹2.4–8.6 lakh. An index on (account_id, txn_ts) cut a statement lookup from about 6 ms to 0.1 ms |

**All 20 queries with their results:** [outputs/RESULTS.md](outputs/RESULTS.md)

![Monthly flows](outputs/chart_monthly_flows.png)

![Channels](outputs/chart_channels.png)

![Concentration](outputs/chart_concentration.png)

## Schema

```
branches (branch_id PK, branch_name, city, region)
    │ 1:n
customers (customer_id PK, full_name, date_of_birth, segment, kyc_risk, onboarded_on, branch_id FK)
    │ 1:n
accounts (account_id PK, customer_id FK, account_type, opened_on, status, opening_balance)
    │ 1:n
transactions (txn_id PK, account_id FK, txn_ts, txn_type, channel, amount, description)

view  v_account_balance  = opening balance + credits − debits, per account
```

## The 20 Queries

| Level | Query | SQL used |
|:--|:--|:--|
| Basic | Q01 Table sizes · Q02 Customer mix by segment and KYC risk · Q03 Channel usage | COUNT, GROUP BY, UNION ALL, share with SUM() OVER () |
| Joins | Q04 Credits and debits by branch (four-table join) · Q05 Account book from the balance view · Q06 Monthly flows | JOIN, FILTER, DATE_TRUNC, views |
| CASE | Q07 Customer balance bands · Q08 Festive-season spending | CASE in SELECT and inside aggregates |
| Window functions | Q09 Running balance statement · Q10 Top 3 customers per branch · Q11 Month-on-month and year-on-year growth · Q12 UPI share with 3-month moving average · Q13 Balance concentration by decile · Q14 Branch share of region · Q20 Rank and percentile within segment | SUM/AVG OVER with frames, DENSE_RANK, RANK, LAG, NTILE, PERCENT_RANK, PARTITION BY |
| CTEs and compliance | Q15 Dormant accounts · Q16 Dormant accounts reactivated by large credits · Q17 Structuring under the ₹50,000 cash level · Q18 High-risk customers with inflows above 3× their segment median · Q19 Cohort activity | WITH, LEFT JOIN, LAG on timestamps, RANGE INTERVAL windows, PERCENTILE_CONT |

## How It Works

1. `generate_data.py` creates the four CSV files (seeded, so the data is the same on every run). Balances never go negative; debits that the balance cannot cover are skipped.
2. `schema.sql` creates the tables, constraints and the balance view; `indexes.sql` adds the indexes.
3. `queries.sql` holds all 20 queries, each headed by its business question.
4. `run_queries.py` loads the data with COPY, times a lookup before and after indexing, runs every query and writes the results, charts and `RESULTS.md`.

## Limitations

- The data is synthetic. Spending patterns, UPI growth, structuring and dormant reactivations were built into the generator so the queries have something to find; real data would be messier.
- The ₹50,000 level comes from the PAN rule for cash deposits (Rule 114B, Income-tax Rules); real AML systems combine many more rules with customer profiles.

## Run It Yourself

```bash
createdb bank
pip install -r requirements.txt
python generate_data.py                      # optional: data/ already holds the CSVs
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bank python run_queries.py
```

Or open `schema.sql`, load `data/*.csv`, and run `queries.sql` in pgAdmin or DBeaver.

**Tools:** PostgreSQL 16, SQL, Python (psycopg2, pandas, Matplotlib)

_Synthetic data for learning purposes._
