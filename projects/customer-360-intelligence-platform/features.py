"""Build the Customer 360 table: one row per customer, as of any month-end.

Joins the bank database (profile, accounts, loans, EMI history), monthly activity, product take-up,
and CRM complaints and NPS (linked through the identity-resolution crosswalk), and optionally adds
the outcome labels for the following 6 months (churn and product take-up) for model training.
"""
import sqlite3

import numpy as np
import pandas as pd

PRODUCTS = ["Fixed Deposit", "Credit Card", "Personal Loan", "Insurance"]


def load(db="data/bank.db", src="sources", out="outputs"):
    con = sqlite3.connect(db)
    d = {
        "customers": pd.read_sql("SELECT c.*, b.region FROM customers c JOIN branches b ON b.branch_id = c.home_branch_id", con),
        "accounts": pd.read_sql("SELECT * FROM accounts", con),
        "loans": pd.read_sql("SELECT * FROM loans", con),
        "payments": pd.read_sql("SELECT * FROM loan_payments", con),
        "activity": pd.read_csv(f"{src}/monthly_activity.csv"),
        "events": pd.read_csv(f"{src}/product_events.csv"),
        "interactions": pd.read_csv(f"{src}/crm_interactions.csv"),
        "crosswalk": pd.read_csv(f"{out}/identity_crosswalk.csv"),
    }
    con.close()
    return d


def month_add(m, k):
    return str(pd.Period(m, "M") + k)


def build(d, asof, with_labels=False):
    """360 view of every customer active in month `asof` (YYYY-MM), using only data up to `asof`."""
    act = d["activity"][d["activity"].month <= asof]
    pop = act[act.month == asof].customer_id.unique()
    c = d["customers"].set_index("customer_id").loc[pop].copy()
    end = pd.Period(asof, "M").end_time.normalize()

    f = pd.DataFrame(index=c.index)
    f["segment"], f["region"], f["city"], f["kyc_risk"] = c.segment, c.region, c.city, c.kyc_risk
    f["age"] = ((end - pd.to_datetime(c.date_of_birth)).dt.days / 365.25).round(1)
    f["tenure_years"] = ((end - pd.to_datetime(c.joined_date)).dt.days / 365.25).clip(lower=0).round(1)

    # products held
    acc = d["accounts"][(d["accounts"].opened_date <= end.strftime("%Y-%m-%d")) & (d["accounts"].status != "Closed")]
    for t in ["Savings", "Current", "Fixed Deposit"]:
        f[f"has_{t.lower().replace(' ', '_')}"] = f.index.isin(acc[acc.account_type == t].customer_id).astype(int)
    ln = d["loans"][(d["loans"].disbursed_date <= end.strftime("%Y-%m-%d")) & (d["loans"].status == "Active")]
    f["has_loan"] = f.index.isin(ln.customer_id).astype(int)
    f["loan_outstanding"] = ln.groupby("customer_id").outstanding.sum().reindex(f.index, fill_value=0)
    f["max_days_past_due"] = ln.groupby("customer_id").days_past_due.max().reindex(f.index, fill_value=0)
    pay = d["payments"][d["payments"].payment_date <= end.strftime("%Y-%m-%d")].merge(
        d["loans"][["loan_id", "customer_id"]], on="loan_id")
    f["emi_on_time_pct"] = (pay.groupby("customer_id").on_time.mean() * 100).reindex(f.index).round(1)
    ev = d["events"][d["events"].month <= asof]
    for p in PRODUCTS:
        col = f"has_{p.lower().replace(' ', '_')}"
        f[col] = (f.get(col, 0) | f.index.isin(ev[ev["product"] == p].customer_id)).astype(int) if col in f else \
            f.index.isin(ev[ev["product"] == p].customer_id).astype(int)
    held = [c_ for c_ in f.columns if c_.startswith("has_")]
    f["n_products"] = f[held].sum(axis=1)

    # behaviour: last 3 months vs the 3 before
    def window(k0, k1):
        return act[(act.month > month_add(asof, -k1)) & (act.month <= month_add(asof, -k0))].groupby("customer_id")
    last3, prev3, last6 = window(0, 3), window(3, 6), window(0, 6)
    for col in ["txn_count", "spend", "inflow", "app_logins"]:
        f[f"{col}_3m"] = last3[col].mean().reindex(f.index).fillna(0).round(1)
        prev = prev3[col].mean().reindex(f.index)
        f[f"{col}_trend"] = (f[f"{col}_3m"] / prev.replace(0, np.nan)).clip(0, 5).fillna(1).round(3)
    f["avg_balance_3m"] = last3.avg_balance.mean().reindex(f.index).fillna(0).round(0)
    f["balance_trend"] = (f.avg_balance_3m / prev3.avg_balance.mean().reindex(f.index).replace(0, np.nan)).clip(0, 5).fillna(1).round(3)
    f["digital_share"] = last3.digital_share.mean().reindex(f.index).round(3)
    f["fees_6m"] = last6.fees_charged.sum().reindex(f.index).fillna(0)
    f["active_months_6m"] = last6.size().reindex(f.index).fillna(0)

    # CRM (through the identity crosswalk: CRM contact -> golden customer)
    xw = d["crosswalk"][d["crosswalk"].source == "crm"].set_index("record_id").golden_id
    it = d["interactions"][d["interactions"].month <= asof].copy()
    it["customer_id"] = it.crm_id.map(xw)
    it = it[it.customer_id.str.startswith("C", na=False)]
    it["customer_id"] = it.customer_id.str[1:].astype(int)
    recent = it[it.month > month_add(asof, -6)]
    f["complaints_6m"] = recent[recent.type == "Complaint"].groupby("customer_id").size().reindex(f.index, fill_value=0)
    f["service_requests_6m"] = recent[recent.type == "Service request"].groupby("customer_id").size().reindex(f.index, fill_value=0)
    nps = it[it.type == "NPS survey"].sort_values("month").groupby("customer_id").nps_score.last()
    f["last_nps"] = nps.reindex(f.index)
    f["in_crm"] = f.index.isin(xw[xw.str.startswith("C")].str[1:].astype(int)).astype(int)
    xc = d["crosswalk"]
    f["in_card_system"] = f.index.isin(xc[(xc.source == "card") & xc.golden_id.str.startswith("C")].golden_id.str[1:].astype(int)).astype(int)

    f["has_credit_card"] = (f.has_credit_card | f.in_card_system).astype(int)
    f["n_products"] = f[held].sum(axis=1)

    if with_labels:
        fut = d["activity"][(d["activity"].month > asof) & (d["activity"].month <= month_add(asof, 6))]
        # churned = no activity in the last 2 months of the window (left the bank)
        tail = fut[fut.month > month_add(asof, 4)].customer_id.unique()
        f["churn_6m"] = (~f.index.isin(tail)).astype(int)
        fe = d["events"][(d["events"].month > asof) & (d["events"].month <= month_add(asof, 6))]
        for p in PRODUCTS:
            key = p.lower().replace(" ", "_")
            took = f.index.isin(fe[fe["product"] == p].customer_id)
            f[f"takes_{key}_6m"] = np.where(f[f"has_{key}"] == 1, np.nan, took.astype(int))
    f.index.name = "customer_id"
    return f


NUMERIC = ["age", "tenure_years", "n_products", "has_savings", "has_current", "has_fixed_deposit", "has_loan",
           "has_credit_card", "has_personal_loan", "has_insurance", "loan_outstanding", "max_days_past_due",
           "emi_on_time_pct", "txn_count_3m", "txn_count_trend", "spend_3m", "spend_trend", "inflow_3m", "inflow_trend",
           "app_logins_3m", "app_logins_trend", "avg_balance_3m", "balance_trend", "digital_share", "fees_6m",
           "active_months_6m", "complaints_6m", "service_requests_6m", "last_nps", "in_crm", "in_card_system"]
CATEGORICAL = ["segment", "kyc_risk", "region"]


def model_matrix(f):
    X = f[NUMERIC].copy()
    for c in CATEGORICAL:
        X = X.join(pd.get_dummies(f[c], prefix=c, dtype=int))
    return X


if __name__ == "__main__":
    d = load()
    f = build(d, "2026-03", with_labels=True)
    print(f.shape)
    print(f[["churn_6m"] + [c for c in f if c.startswith("takes_")]].mean().round(4))
    print(f.describe().T[["mean", "min", "max"]].round(2).to_string())
