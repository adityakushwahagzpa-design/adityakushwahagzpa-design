-- ============================================================
-- Bank transactions analysis: 20 queries, basic to advanced
-- Each query starts with a "-- Qnn | title | business question" line.
-- ============================================================

-- Q01 | Table sizes | How much data is in each table?
SELECT 'branches' AS table_name, COUNT(*) AS rows FROM branches
UNION ALL SELECT 'customers', COUNT(*) FROM customers
UNION ALL SELECT 'accounts', COUNT(*) FROM accounts
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions;

-- Q02 | Customer mix | How are customers split by segment and KYC risk rating?
SELECT segment,
       COUNT(*) AS customers,
       SUM(CASE WHEN kyc_risk = 'High' THEN 1 ELSE 0 END) AS high_risk,
       ROUND(100.0 * SUM(CASE WHEN kyc_risk = 'High' THEN 1 ELSE 0 END) / COUNT(*), 1) AS high_risk_pct
FROM customers
GROUP BY segment
ORDER BY customers DESC;

-- Q03 | Channel usage | Which payment channels carry the most transactions and value?
SELECT channel,
       COUNT(*) AS txns,
       ROUND(SUM(amount) / 1e7, 2) AS value_cr,
       ROUND(AVG(amount), 0) AS avg_ticket,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS share_of_txns_pct
FROM transactions
GROUP BY channel
ORDER BY txns DESC;

-- Q04 | Deposits by region | Which regions and branches bring in the most money? (JOIN across four tables)
SELECT b.region, b.branch_name, b.city,
       COUNT(DISTINCT c.customer_id) AS customers,
       ROUND(SUM(t.amount) FILTER (WHERE t.txn_type = 'Credit') / 1e7, 2) AS credits_cr,
       ROUND(SUM(t.amount) FILTER (WHERE t.txn_type = 'Debit') / 1e7, 2) AS debits_cr
FROM branches b
JOIN customers c ON c.branch_id = b.branch_id
JOIN accounts a ON a.customer_id = c.customer_id
JOIN transactions t ON t.account_id = a.account_id
GROUP BY b.region, b.branch_name, b.city
ORDER BY credits_cr DESC;

-- Q05 | Account book | How many accounts of each type, and what do they hold? (uses the balance view)
SELECT account_type, status,
       COUNT(*) AS accounts,
       ROUND(SUM(balance) / 1e7, 2) AS balance_cr,
       ROUND(AVG(balance), 0) AS avg_balance
FROM v_account_balance
GROUP BY account_type, status
ORDER BY account_type, status;

-- Q06 | Monthly flows | Total credits and debits by month
SELECT TO_CHAR(DATE_TRUNC('month', txn_ts), 'YYYY-MM') AS month,
       ROUND(SUM(amount) FILTER (WHERE txn_type = 'Credit') / 1e7, 2) AS credits_cr,
       ROUND(SUM(amount) FILTER (WHERE txn_type = 'Debit') / 1e7, 2) AS debits_cr,
       ROUND((SUM(amount) FILTER (WHERE txn_type = 'Credit') - SUM(amount) FILTER (WHERE txn_type = 'Debit')) / 1e7, 2) AS net_cr
FROM transactions
GROUP BY 1
ORDER BY 1;

-- Q07 | Balance bands | How many customers fall in each balance band? (CASE)
WITH cust AS (
    SELECT customer_id, SUM(balance) AS balance FROM v_account_balance WHERE status = 'Active' GROUP BY customer_id
)
SELECT CASE WHEN balance < 50000 THEN '1. Under ₹50k'
            WHEN balance < 500000 THEN '2. ₹50k–₹5 lakh'
            WHEN balance < 2500000 THEN '3. ₹5–25 lakh'
            ELSE '4. Above ₹25 lakh' END AS band,
       COUNT(*) AS customers,
       ROUND(SUM(balance) / 1e7, 2) AS balance_cr,
       ROUND(100.0 * SUM(balance) / SUM(SUM(balance)) OVER (), 1) AS share_of_balances_pct
FROM cust
GROUP BY 1
ORDER BY 1;

-- Q08 | Festive season | Is card and UPI spending higher in October-November? (CASE inside aggregation)
SELECT EXTRACT(YEAR FROM txn_ts)::INT AS year,
       CASE WHEN EXTRACT(MONTH FROM txn_ts) IN (10, 11) THEN 'Oct-Nov' ELSE 'Other months' END AS period,
       ROUND(SUM(amount) / COUNT(DISTINCT DATE_TRUNC('month', txn_ts)) / 1e5, 1) AS avg_monthly_spend_lakh
FROM transactions
WHERE txn_type = 'Debit' AND channel IN ('UPI', 'Card') AND txn_ts < '2026-01-01'
GROUP BY 1, 2
ORDER BY 1, 2;

-- Q09 | Running balance | Statement for one account with a running balance (window SUM)
WITH acct AS (
    SELECT account_id FROM transactions GROUP BY account_id ORDER BY COUNT(*) DESC LIMIT 1
)
SELECT t.txn_ts, t.txn_type, t.channel, t.amount,
       a.opening_balance + SUM(CASE WHEN t.txn_type = 'Credit' THEN t.amount ELSE -t.amount END)
           OVER (ORDER BY t.txn_ts, t.txn_id ROWS UNBOUNDED PRECEDING) AS running_balance
FROM transactions t
JOIN accounts a ON a.account_id = t.account_id
WHERE t.account_id = (SELECT account_id FROM acct)
ORDER BY t.txn_ts, t.txn_id
LIMIT 12;

-- Q10 | Top customers per branch | The three largest customers in every branch (DENSE_RANK)
WITH cust AS (
    SELECT c.customer_id, c.full_name, c.branch_id, c.segment, SUM(v.balance) AS balance
    FROM customers c JOIN v_account_balance v ON v.customer_id = c.customer_id
    GROUP BY c.customer_id
), ranked AS (
    SELECT *, DENSE_RANK() OVER (PARTITION BY branch_id ORDER BY balance DESC) AS rnk FROM cust
)
SELECT b.branch_name, r.rnk, r.full_name, r.segment, ROUND(r.balance / 1e5, 1) AS balance_lakh
FROM ranked r JOIN branches b ON b.branch_id = r.branch_id
WHERE r.rnk <= 3
ORDER BY b.branch_id, r.rnk;

-- Q11 | Month-on-month growth | Growth in debit value per month (LAG)
WITH m AS (
    SELECT DATE_TRUNC('month', txn_ts) AS month, SUM(amount) AS debits
    FROM transactions WHERE txn_type = 'Debit' GROUP BY 1
)
SELECT TO_CHAR(month, 'YYYY-MM') AS month,
       ROUND(debits / 1e7, 2) AS debits_cr,
       ROUND(100 * (debits / LAG(debits) OVER (ORDER BY month) - 1), 1) AS mom_growth_pct,
       ROUND(100 * (debits / LAG(debits, 12) OVER (ORDER BY month) - 1), 1) AS yoy_growth_pct
FROM m
ORDER BY month;

-- Q12 | Digital adoption | Share of debits made by UPI, with a 3-month moving average (AVG over a window)
WITH m AS (
    SELECT DATE_TRUNC('month', txn_ts) AS month,
           100.0 * COUNT(*) FILTER (WHERE channel = 'UPI') / COUNT(*) AS upi_share
    FROM transactions WHERE txn_type = 'Debit' GROUP BY 1
)
SELECT TO_CHAR(month, 'YYYY-MM') AS month, ROUND(upi_share, 1) AS upi_share_pct,
       ROUND(AVG(upi_share) OVER (ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS moving_avg_3m
FROM m
ORDER BY month;

-- Q13 | Concentration | What share of all balances do the top 10% of customers hold? (NTILE)
WITH cust AS (
    SELECT customer_id, SUM(balance) AS balance FROM v_account_balance GROUP BY customer_id
), d AS (
    SELECT balance, NTILE(10) OVER (ORDER BY balance DESC) AS decile FROM cust
)
SELECT decile, COUNT(*) AS customers, ROUND(SUM(balance) / 1e7, 2) AS balance_cr,
       ROUND(100 * SUM(balance) / SUM(SUM(balance)) OVER (), 1) AS share_pct,
       ROUND(100 * SUM(SUM(balance)) OVER (ORDER BY decile) / SUM(SUM(balance)) OVER (), 1) AS cumulative_pct
FROM d
GROUP BY decile
ORDER BY decile;

-- Q14 | Branch share | Each branch's share of its region's credits (window SUM with PARTITION BY)
WITH b AS (
    SELECT br.region, br.branch_name, SUM(t.amount) AS credits
    FROM transactions t
    JOIN accounts a ON a.account_id = t.account_id
    JOIN customers c ON c.customer_id = a.customer_id
    JOIN branches br ON br.branch_id = c.branch_id
    WHERE t.txn_type = 'Credit'
    GROUP BY br.region, br.branch_name
)
SELECT region, branch_name, ROUND(credits / 1e7, 2) AS credits_cr,
       ROUND(100 * credits / SUM(credits) OVER (PARTITION BY region), 1) AS share_of_region_pct,
       RANK() OVER (ORDER BY credits DESC) AS national_rank
FROM b
ORDER BY region, credits DESC;

-- Q15 | Dormant accounts | Active accounts with no transaction in the last 12 months of data (CTE + LEFT JOIN)
WITH last_txn AS (
    SELECT account_id, MAX(txn_ts) AS last_ts FROM transactions GROUP BY account_id
), data_end AS (SELECT MAX(txn_ts) AS ts FROM transactions)
SELECT a.account_type,
       COUNT(*) AS dormant_accounts,
       ROUND(SUM(v.balance) / 1e5, 1) AS balance_lakh
FROM accounts a
JOIN v_account_balance v ON v.account_id = a.account_id
LEFT JOIN last_txn l ON l.account_id = a.account_id
CROSS JOIN data_end e
WHERE a.status = 'Active' AND (l.last_ts IS NULL OR l.last_ts < e.ts - INTERVAL '365 days')
GROUP BY a.account_type
ORDER BY dormant_accounts DESC;

-- Q16 | AML alert: reactivated dormant accounts | A gap of 365+ days followed by a credit of ₹1 lakh or more (LAG on timestamps)
WITH gaps AS (
    SELECT t.*, LAG(txn_ts) OVER (PARTITION BY account_id ORDER BY txn_ts) AS prev_ts
    FROM transactions t
)
SELECT g.account_id, c.full_name, c.kyc_risk, g.prev_ts::DATE AS last_activity, g.txn_ts::DATE AS reactivated_on,
       (g.txn_ts::DATE - g.prev_ts::DATE) AS days_dormant, g.channel, g.amount
FROM gaps g
JOIN accounts a ON a.account_id = g.account_id
JOIN customers c ON c.customer_id = a.customer_id
WHERE g.prev_ts IS NOT NULL AND g.txn_ts - g.prev_ts >= INTERVAL '365 days'
  AND g.txn_type = 'Credit' AND g.amount >= 100000
ORDER BY g.amount DESC;

-- Q17 | AML alert: structuring | 3+ cash deposits of ₹45,000–49,999 within 7 days, just under the ₹50,000 PAN-reporting level (RANGE window)
WITH cash AS (
    SELECT a.customer_id, t.txn_ts, t.amount
    FROM transactions t JOIN accounts a ON a.account_id = t.account_id
    WHERE t.channel = 'Cash' AND t.txn_type = 'Credit' AND t.amount BETWEEN 45000 AND 49999.99
), w AS (
    SELECT customer_id, txn_ts,
           COUNT(*) OVER (PARTITION BY customer_id ORDER BY txn_ts RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW) AS n_7d,
           SUM(amount) OVER (PARTITION BY customer_id ORDER BY txn_ts RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW) AS sum_7d
    FROM cash
)
SELECT w.customer_id, c.full_name, c.segment, c.kyc_risk,
       COUNT(*) FILTER (WHERE n_7d >= 3) AS flagged_windows,
       MAX(n_7d) AS max_deposits_in_7_days,
       ROUND(MAX(sum_7d), 0) AS max_cash_in_7_days
FROM w JOIN customers c ON c.customer_id = w.customer_id
GROUP BY w.customer_id, c.full_name, c.segment, c.kyc_risk
HAVING MAX(n_7d) >= 3
ORDER BY max_cash_in_7_days DESC;

-- Q18 | High-risk customers with outsized inflows | High KYC-risk customers whose monthly credits exceed 3x their segment's median (PERCENTILE_CONT)
WITH monthly AS (
    SELECT c.customer_id, c.segment, c.kyc_risk, DATE_TRUNC('month', t.txn_ts) AS month, SUM(t.amount) AS credits
    FROM transactions t
    JOIN accounts a ON a.account_id = t.account_id
    JOIN customers c ON c.customer_id = a.customer_id
    WHERE t.txn_type = 'Credit'
    GROUP BY 1, 2, 3, 4
), seg_median AS (
    SELECT segment, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY credits)::NUMERIC AS median_credits FROM monthly GROUP BY segment
)
SELECT m.customer_id, m.segment, COUNT(*) AS months_flagged,
       ROUND(MAX(m.credits / s.median_credits), 1) AS max_multiple_of_median,
       ROUND(MAX(m.credits), 0) AS max_monthly_credits
FROM monthly m JOIN seg_median s ON s.segment = m.segment
WHERE m.kyc_risk = 'High' AND m.credits > 3 * s.median_credits
GROUP BY m.customer_id, m.segment
ORDER BY months_flagged DESC, max_multiple_of_median DESC;

-- Q19 | Cohort activity | Of customers onboarded each year, how many transacted in the last 3 months of data?
WITH data_end AS (SELECT MAX(txn_ts) AS ts FROM transactions),
recent AS (
    SELECT DISTINCT a.customer_id
    FROM transactions t JOIN accounts a ON a.account_id = t.account_id CROSS JOIN data_end e
    WHERE t.txn_ts >= e.ts - INTERVAL '3 months'
)
SELECT EXTRACT(YEAR FROM c.onboarded_on)::INT AS cohort,
       COUNT(*) AS customers,
       COUNT(r.customer_id) AS active_last_3m,
       ROUND(100.0 * COUNT(r.customer_id) / COUNT(*), 1) AS active_pct
FROM customers c LEFT JOIN recent r ON r.customer_id = c.customer_id
GROUP BY 1
ORDER BY 1;

-- Q20 | Customer value ranking | Each customer's total credits, rank and percentile within segment (RANK, PERCENT_RANK)
WITH cust AS (
    SELECT c.customer_id, c.full_name, c.segment, SUM(t.amount) AS credits
    FROM customers c
    JOIN accounts a ON a.customer_id = c.customer_id
    JOIN transactions t ON t.account_id = a.account_id
    WHERE t.txn_type = 'Credit'
    GROUP BY c.customer_id
)
SELECT segment, full_name, ROUND(credits / 1e5, 1) AS credits_lakh,
       RANK() OVER (PARTITION BY segment ORDER BY credits DESC) AS rank_in_segment,
       ROUND((100 * PERCENT_RANK() OVER (PARTITION BY segment ORDER BY credits))::NUMERIC, 1) AS percentile
FROM cust
ORDER BY segment, rank_in_segment
LIMIT 15;
