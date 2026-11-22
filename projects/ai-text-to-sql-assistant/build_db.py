"""Build data/bank.db: a synthetic SQLite database for a fictional Indian retail bank.

Tables
  branches        20 branches across 4 regions
  customers       6,000 customers (segment, city, KYC risk rating, join date)
  accounts        ~8,500 savings / current / fixed-deposit accounts
  transactions    ~180,000 transactions, Apr 2024 - Sep 2026 (UPI, NEFT, IMPS, card, ATM, cheque)
  loans           ~1,800 loans (home, personal, auto, gold, business) with status and days past due
  loan_payments   EMI payments made against loans

All names and numbers are synthetic. Amounts are in rupees.
"""
import os
import sqlite3

import numpy as np
import pandas as pd

SEED = 21
REGIONS = {"North": ["Delhi", "Lucknow", "Jaipur", "Chandigarh", "Noida"],
           "South": ["Bengaluru", "Chennai", "Hyderabad", "Kochi", "Mysuru"],
           "West": ["Mumbai", "Pune", "Ahmedabad", "Surat", "Nagpur"],
           "East": ["Kolkata", "Bhubaneswar", "Patna", "Ranchi", "Guwahati"]}
FIRST = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Rohan", "Kabir", "Arjun", "Sai", "Ananya", "Diya", "Priya", "Sneha",
         "Kavya", "Meera", "Riya", "Neha", "Rahul", "Vikram", "Pooja", "Nisha", "Karan", "Amit", "Suresh", "Lakshmi"]
LAST = ["Sharma", "Verma", "Iyer", "Reddy", "Nair", "Patel", "Shah", "Gupta", "Singh", "Das", "Mukherjee", "Rao",
        "Menon", "Joshi", "Kulkarni", "Banerjee", "Mishra", "Pillai", "Chopra", "Yadav"]
SEGMENTS = ["Retail", "Salaried", "Premium", "SME"]
CHANNELS = ["UPI", "NEFT", "IMPS", "Card", "ATM", "Cheque"]

SCHEMA = """
CREATE TABLE branches (
  branch_id INTEGER PRIMARY KEY, branch_name TEXT NOT NULL, city TEXT NOT NULL, region TEXT NOT NULL,
  opened_date TEXT NOT NULL);
CREATE TABLE customers (
  customer_id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, city TEXT NOT NULL, segment TEXT NOT NULL,
  kyc_risk TEXT NOT NULL CHECK (kyc_risk IN ('Low','Medium','High')), date_of_birth TEXT NOT NULL,
  joined_date TEXT NOT NULL, home_branch_id INTEGER NOT NULL REFERENCES branches(branch_id));
CREATE TABLE accounts (
  account_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
  branch_id INTEGER NOT NULL REFERENCES branches(branch_id),
  account_type TEXT NOT NULL CHECK (account_type IN ('Savings','Current','Fixed Deposit')),
  opened_date TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('Active','Dormant','Closed')),
  balance REAL NOT NULL, interest_rate REAL NOT NULL);
CREATE TABLE transactions (
  txn_id INTEGER PRIMARY KEY, account_id INTEGER NOT NULL REFERENCES accounts(account_id),
  txn_date TEXT NOT NULL, amount REAL NOT NULL, direction TEXT NOT NULL CHECK (direction IN ('Credit','Debit')),
  channel TEXT NOT NULL, merchant_category TEXT, is_international INTEGER NOT NULL DEFAULT 0);
CREATE TABLE loans (
  loan_id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
  branch_id INTEGER NOT NULL REFERENCES branches(branch_id), loan_type TEXT NOT NULL,
  principal REAL NOT NULL, interest_rate REAL NOT NULL, tenure_months INTEGER NOT NULL,
  disbursed_date TEXT NOT NULL, outstanding REAL NOT NULL, days_past_due INTEGER NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('Active','Closed','Written Off')));
CREATE TABLE loan_payments (
  payment_id INTEGER PRIMARY KEY, loan_id INTEGER NOT NULL REFERENCES loans(loan_id),
  payment_date TEXT NOT NULL, amount REAL NOT NULL, on_time INTEGER NOT NULL);
CREATE INDEX ix_txn_account ON transactions(account_id);
CREATE INDEX ix_txn_date ON transactions(txn_date);
CREATE INDEX ix_acc_customer ON accounts(customer_id);
CREATE INDEX ix_loan_customer ON loans(customer_id);
CREATE INDEX ix_pay_loan ON loan_payments(loan_id);
"""


def rand_dates(rng, start, end, n):
    s, e = pd.Timestamp(start).value // 10**9, pd.Timestamp(end).value // 10**9
    return pd.to_datetime(rng.integers(s, e, n), unit="s").strftime("%Y-%m-%d")


def build(path="data/bank.db"):
    rng = np.random.default_rng(SEED)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)

    # branches
    br = []
    bid = 1
    for region, cities in REGIONS.items():
        for city in cities:
            br.append((bid, f"{city} Main", city, region, str(rand_dates(rng, "2005-01-01", "2018-12-31", 1)[0])))
            bid += 1
    branches = pd.DataFrame(br, columns=["branch_id", "branch_name", "city", "region", "opened_date"])
    branches.to_sql("branches", con, if_exists="append", index=False)

    # customers
    n = 6000
    home = rng.integers(1, len(branches) + 1, n)
    seg = rng.choice(SEGMENTS, n, p=[0.45, 0.35, 0.10, 0.10])
    customers = pd.DataFrame({
        "customer_id": np.arange(1, n + 1),
        "full_name": [f"{rng.choice(FIRST)} {rng.choice(LAST)}" for _ in range(n)],
        "city": branches.set_index("branch_id").city.reindex(home).values,
        "segment": seg,
        "kyc_risk": rng.choice(["Low", "Medium", "High"], n, p=[0.72, 0.22, 0.06]),
        "date_of_birth": rand_dates(rng, "1955-01-01", "2004-12-31", n),
        "joined_date": rand_dates(rng, "2012-01-01", "2026-06-30", n),
        "home_branch_id": home,
    })
    customers.to_sql("customers", con, if_exists="append", index=False)

    # accounts
    rows = []
    aid = 1
    for c in customers.itertuples():
        k = 1 + rng.poisson(0.45)
        for _ in range(k):
            if c.segment == "SME":
                t = rng.choice(["Current", "Savings", "Fixed Deposit"], p=[0.6, 0.2, 0.2])
            else:
                t = rng.choice(["Savings", "Fixed Deposit", "Current"], p=[0.75, 0.2, 0.05])
            mult = {"Retail": 1, "Salaried": 2, "Premium": 8, "SME": 6}[c.segment]
            bal = float(np.round(rng.lognormal(10.3, 1.0) * mult, 2))
            status = rng.choice(["Active", "Dormant", "Closed"], p=[0.86, 0.09, 0.05])
            rate = {"Savings": 3.0, "Current": 0.0, "Fixed Deposit": round(float(rng.choice([6.5, 7.0, 7.25, 7.5])), 2)}[t]
            opened = max(c.joined_date, str(rand_dates(rng, c.joined_date, "2026-06-30", 1)[0]))
            rows.append((aid, c.customer_id, c.home_branch_id, t, opened, status, 0.0 if status == "Closed" else bal, rate))
            aid += 1
    accounts = pd.DataFrame(rows, columns=["account_id", "customer_id", "branch_id", "account_type", "opened_date",
                                           "status", "balance", "interest_rate"])
    accounts.to_sql("accounts", con, if_exists="append", index=False)

    # transactions (savings and current accounts that are not dormant all period)
    tx_acc = accounts[accounts.account_type != "Fixed Deposit"]
    seg_by_cust = customers.set_index("customer_id").segment
    cats = ["Groceries", "Fuel", "Dining", "Travel", "Electronics", "Utilities", "Healthcare", "Education", "Shopping",
            "Rent", None]
    t_rows = []
    for a in tx_acc.itertuples():
        seg_ = seg_by_cust[a.customer_id]
        lam = {"Retail": 14, "Salaried": 24, "Premium": 36, "SME": 50}[seg_] * (0.25 if a.status != "Active" else 1)
        k = rng.poisson(lam)
        if k == 0:
            continue
        start = max(a.opened_date, "2024-04-01")
        end = "2026-09-30" if a.status == "Active" else "2025-03-31"
        if start >= end:
            continue
        dates = np.sort(rand_dates(rng, start, end, k))
        chans = rng.choice(CHANNELS, k, p=[0.48, 0.12, 0.10, 0.18, 0.08, 0.04])
        direction = rng.choice(["Credit", "Debit"], k, p=[0.38, 0.62])
        scale = {"Retail": 1, "Salaried": 1.8, "Premium": 5, "SME": 8}[seg_]
        amt = np.round(rng.lognormal(7.4, 1.2, k) * scale, 2)
        for d, ch, di, am in zip(dates, chans, direction, amt):
            cat = None if di == "Credit" or ch in ("NEFT", "Cheque") else cats[rng.integers(0, len(cats) - 1)]
            intl = int(ch == "Card" and rng.random() < 0.04)
            t_rows.append((a.account_id, d, float(am), di, ch, cat, intl))
    tx = pd.DataFrame(t_rows, columns=["account_id", "txn_date", "amount", "direction", "channel", "merchant_category",
                                       "is_international"])
    tx = tx.sort_values(["txn_date", "account_id"]).reset_index(drop=True)
    tx.insert(0, "txn_id", np.arange(1, len(tx) + 1))
    tx.to_sql("transactions", con, if_exists="append", index=False)

    # loans and payments
    loan_specs = {"Home": (2_500_000, 0.5, 8.6, [180, 240]), "Personal": (300_000, 0.6, 13.5, [24, 36, 60]),
                  "Auto": (700_000, 0.4, 9.4, [36, 60, 84]), "Gold": (150_000, 0.5, 9.9, [12]),
                  "Business": (1_200_000, 0.7, 11.8, [36, 60])}
    l_rows, p_rows = [], []
    borrowers = rng.choice(customers.customer_id.values, 1800, replace=False)
    lid, pid = 1, 1
    for cid in borrowers:
        c = customers.iloc[cid - 1]
        lt = rng.choice(list(loan_specs), p=[0.18, 0.32, 0.18, 0.17, 0.15] if c.segment != "SME" else [0.05, 0.15, 0.1, 0.1, 0.6])
        mean, sd, rate, tenures = loan_specs[lt]
        principal = float(np.round(mean * rng.lognormal(0, sd), -3))
        tenure = int(rng.choice(tenures))
        disb = str(rand_dates(rng, max(c.joined_date, "2019-04-01"), "2026-06-30", 1)[0])
        r = rate + {"Low": 0, "Medium": 0.75, "High": 2.0}[c.kyc_risk] + round(float(rng.normal(0, 0.4)), 2)
        months = (pd.Timestamp("2026-09-30") - pd.Timestamp(disb)).days // 30
        risk = {"Low": 0.04, "Medium": 0.09, "High": 0.22}[c.kyc_risk] + (0.05 if lt in ("Personal", "Business") else 0)
        if months >= tenure:
            status, dpd, out = "Closed", 0, 0.0
        else:
            u = rng.random()
            if u < risk * 0.25:
                status, dpd = "Written Off", int(rng.integers(181, 400))
            elif u < risk:
                status, dpd = "Active", int(rng.choice([15, 35, 62, 95, 120, 150]))
            else:
                status, dpd = "Active", 0
            out = float(np.round(principal * max(0.05, 1 - months / tenure) * (1 + 0.02 * (dpd > 0)), 2))
        emi = principal * (r / 1200) / (1 - (1 + r / 1200) ** -tenure)
        paid_months = min(months, tenure) - (dpd // 30)
        for m in range(max(paid_months, 0)):
            d = (pd.Timestamp(disb) + pd.DateOffset(months=m + 1)).strftime("%Y-%m-%d")
            if d > "2026-09-30":
                break
            on_time = int(rng.random() > (0.08 if dpd == 0 else 0.35))
            if d >= "2024-04-01":  # payment history kept from FY2024-25
                p_rows.append((pid, lid, d, round(emi, 2), on_time))
                pid += 1
        l_rows.append((lid, int(cid), int(c.home_branch_id), lt, principal, round(r, 2), tenure, disb, out, dpd, status))
        lid += 1
    pd.DataFrame(l_rows, columns=["loan_id", "customer_id", "branch_id", "loan_type", "principal", "interest_rate",
                                  "tenure_months", "disbursed_date", "outstanding", "days_past_due", "status"]
                 ).to_sql("loans", con, if_exists="append", index=False)
    pd.DataFrame(p_rows, columns=["payment_id", "loan_id", "payment_date", "amount", "on_time"]
                 ).to_sql("loan_payments", con, if_exists="append", index=False)
    con.commit()
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ["branches", "customers", "accounts", "transactions", "loans", "loan_payments"]}
    con.execute("VACUUM")
    con.close()
    return counts


if __name__ == "__main__":
    print(build())
