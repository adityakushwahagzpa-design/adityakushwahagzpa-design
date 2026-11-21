-- Bank transactions database: four related tables
DROP VIEW IF EXISTS v_account_balance;
DROP TABLE IF EXISTS transactions, accounts, customers, branches CASCADE;

CREATE TABLE branches (
    branch_id    SMALLINT PRIMARY KEY,
    branch_name  TEXT NOT NULL,
    city         TEXT NOT NULL,
    region       TEXT NOT NULL CHECK (region IN ('North', 'South', 'East', 'West'))
);

CREATE TABLE customers (
    customer_id    INTEGER PRIMARY KEY,
    full_name      TEXT NOT NULL,
    date_of_birth  DATE NOT NULL,
    segment        TEXT NOT NULL CHECK (segment IN ('Retail', 'Premium', 'SME')),
    kyc_risk       TEXT NOT NULL CHECK (kyc_risk IN ('Low', 'Medium', 'High')),
    onboarded_on   DATE NOT NULL,
    branch_id      SMALLINT NOT NULL REFERENCES branches (branch_id)
);

CREATE TABLE accounts (
    account_id       INTEGER PRIMARY KEY,
    customer_id      INTEGER NOT NULL REFERENCES customers (customer_id),
    account_type     TEXT NOT NULL CHECK (account_type IN ('Savings', 'Current', 'Salary')),
    opened_on        DATE NOT NULL,
    status           TEXT NOT NULL CHECK (status IN ('Active', 'Closed')),
    opening_balance  NUMERIC(14, 2) NOT NULL CHECK (opening_balance >= 0)
);

CREATE TABLE transactions (
    txn_id       BIGINT PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES accounts (account_id),
    txn_ts       TIMESTAMP NOT NULL,
    txn_type     TEXT NOT NULL CHECK (txn_type IN ('Credit', 'Debit')),
    channel      TEXT NOT NULL CHECK (channel IN ('UPI', 'NEFT', 'IMPS', 'RTGS', 'ATM', 'Cash', 'Card', 'Cheque')),
    amount       NUMERIC(14, 2) NOT NULL CHECK (amount > 0),
    description  TEXT
);

-- Current balance of every account, reused by several queries
CREATE VIEW v_account_balance AS
SELECT a.account_id, a.customer_id, a.account_type, a.status,
       a.opening_balance
       + COALESCE(SUM(CASE WHEN t.txn_type = 'Credit' THEN t.amount ELSE -t.amount END), 0) AS balance
FROM accounts a
LEFT JOIN transactions t ON t.account_id = a.account_id
GROUP BY a.account_id;
