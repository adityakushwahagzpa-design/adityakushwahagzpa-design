-- Indexes for the joins and time filters used above
CREATE INDEX IF NOT EXISTS idx_txn_account_ts ON transactions (account_id, txn_ts);
CREATE INDEX IF NOT EXISTS idx_txn_ts ON transactions (txn_ts);
CREATE INDEX IF NOT EXISTS idx_accounts_customer ON accounts (customer_id);
CREATE INDEX IF NOT EXISTS idx_customers_branch ON customers (branch_id);
ANALYZE;
