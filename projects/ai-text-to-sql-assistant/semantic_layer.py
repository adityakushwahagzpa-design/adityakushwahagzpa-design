"""Data dictionary and business glossary given to the model with every question.

The glossary turns bank terms (NPA, CASA, fiscal year, active customer) into exact SQL rules, so the
model does not have to guess what the business means by them.
"""

TABLES = {
    "branches": {
        "about": "One row per branch.",
        "columns": {
            "branch_id": "Primary key.",
            "branch_name": "e.g. 'Pune Main'.",
            "city": "Branch city.",
            "region": "'North', 'South', 'East' or 'West'.",
            "opened_date": "YYYY-MM-DD.",
        },
    },
    "customers": {
        "about": "One row per customer.",
        "columns": {
            "customer_id": "Primary key.",
            "full_name": "Customer name (synthetic).",
            "city": "Customer city (same as home branch city).",
            "segment": "'Retail', 'Salaried', 'Premium' or 'SME'.",
            "kyc_risk": "KYC/AML risk rating: 'Low', 'Medium' or 'High'.",
            "date_of_birth": "YYYY-MM-DD.",
            "joined_date": "Date the customer joined the bank, YYYY-MM-DD.",
            "home_branch_id": "FK to branches.branch_id.",
        },
    },
    "accounts": {
        "about": "Deposit accounts. A customer can have several.",
        "columns": {
            "account_id": "Primary key.",
            "customer_id": "FK to customers.",
            "branch_id": "FK to branches.",
            "account_type": "'Savings', 'Current' or 'Fixed Deposit'.",
            "opened_date": "YYYY-MM-DD.",
            "status": "'Active', 'Dormant' or 'Closed' (closed accounts have balance 0).",
            "balance": "Current balance in rupees.",
            "interest_rate": "Annual %, e.g. 7.25.",
        },
    },
    "transactions": {
        "about": "Savings and current account transactions from 2024-04-01 to 2026-09-30.",
        "columns": {
            "txn_id": "Primary key.",
            "account_id": "FK to accounts.",
            "txn_date": "YYYY-MM-DD.",
            "amount": "Always positive, in rupees.",
            "direction": "'Credit' (money in) or 'Debit' (money out).",
            "channel": "'UPI', 'NEFT', 'IMPS', 'Card', 'ATM' or 'Cheque'.",
            "merchant_category": "For debits only: 'Groceries', 'Fuel', 'Dining', 'Travel', 'Electronics', "
                                 "'Utilities', 'Healthcare', 'Education', 'Shopping', 'Rent'; NULL otherwise.",
            "is_international": "1 if an international card transaction, else 0.",
        },
    },
    "loans": {
        "about": "One row per loan.",
        "columns": {
            "loan_id": "Primary key.",
            "customer_id": "FK to customers.",
            "branch_id": "FK to branches.",
            "loan_type": "'Home', 'Personal', 'Auto', 'Gold' or 'Business'.",
            "principal": "Amount disbursed, rupees.",
            "interest_rate": "Annual %.",
            "tenure_months": "Loan term in months.",
            "disbursed_date": "YYYY-MM-DD.",
            "outstanding": "Amount still owed today, rupees (0 if closed).",
            "days_past_due": "Days the oldest unpaid EMI is overdue (0 = up to date).",
            "status": "'Active', 'Closed' or 'Written Off'.",
        },
    },
    "loan_payments": {
        "about": "EMI payments received, from 2024-04-01.",
        "columns": {
            "payment_id": "Primary key.",
            "loan_id": "FK to loans.",
            "payment_date": "YYYY-MM-DD.",
            "amount": "EMI amount, rupees.",
            "on_time": "1 if paid by the due date, else 0.",
        },
    },
}

GLOSSARY = [
    "Today is 2026-09-30 (the last day of data). 'Last 90 days' means txn_date > date('2026-09-30', '-90 days').",
    "Fiscal year runs April to March. FY2025-26 (also 'FY26') = 2025-04-01 to 2026-03-31.",
    "Quarter Q1 = Apr-Jun, Q2 = Jul-Sep, Q3 = Oct-Dec, Q4 = Jan-Mar of the fiscal year.",
    "Active customer: has at least one transaction in the last 90 days.",
    "NPA (non-performing asset): loan with status 'Active' and days_past_due > 90.",
    "Gross NPA ratio = outstanding of NPA loans / outstanding of all Active loans.",
    "SMA buckets for Active loans: SMA-0 = 1-30 days past due, SMA-1 = 31-60, SMA-2 = 61-90.",
    "Deposits = balance of accounts with status 'Active' or 'Dormant'.",
    "CASA ratio = Savings + Current deposits / total deposits (including Fixed Deposits).",
    "Large transaction (for AML review): amount >= 200000.",
    "Customer age = whole years between date_of_birth and 2026-09-30.",
    "Amounts are in rupees. 1 lakh = 100,000 and 1 crore = 10,000,000.",
    "Spend = Debit transactions. Inflow = Credit transactions.",
]


def schema_text():
    lines = []
    for t, spec in TABLES.items():
        lines.append(f"TABLE {t} -- {spec['about']}")
        for c, d in spec["columns"].items():
            lines.append(f"  {c}: {d}")
    return "\n".join(lines)


def glossary_text():
    return "\n".join(f"- {g}" for g in GLOSSARY)


ALLOWED_TABLES = set(TABLES)
