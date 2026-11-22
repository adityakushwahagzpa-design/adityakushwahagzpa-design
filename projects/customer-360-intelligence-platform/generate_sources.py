"""Generate the source systems a Customer 360 platform has to bring together.

Starts from the customer master, accounts and loans in data/bank.db (the same fictional bank as the
text-to-SQL project) and simulates what a real bank's other systems would hold:

  sources/core_banking.csv      one clean record per customer (name, DOB, phone, email, city)
  sources/crm_contacts.csv      CRM contacts: typos, initials, swapped names, old phone numbers,
                                duplicates, missing fields, and prospects who are not customers
  sources/card_system.csv       card system: upper-case names, DD/MM/YYYY dates, card-only customers
  sources/crm_interactions.csv  complaints, service requests and NPS survey scores per CRM contact
  sources/monthly_activity.csv  Apr 2024 - Sep 2026, per customer per month: transactions, spend,
                                inflows, digital share, app logins, average balance, fees
  sources/product_events.csv    products taken up (Fixed Deposit, Credit Card, Personal Loan, Insurance)
  truth/identity_truth.csv      which person each source record really belongs to (for evaluation)
  truth/churn_truth.csv         month each customer left, if they did (for checking only)

Churn and product take-up follow known rules driven by engagement, complaints, fees, product count
and tenure, so the models have a real but noisy signal. All data is synthetic.
"""
import os
import sqlite3

import numpy as np
import pandas as pd

SEED = 360
MONTHS = pd.period_range("2024-04", "2026-09", freq="M")
PRODUCTS = ["Fixed Deposit", "Credit Card", "Personal Loan", "Insurance"]


def phone_number(rng):
    return str(rng.choice([6, 7, 8, 9])) + "".join(str(d) for d in rng.integers(0, 10, 9))


def email_for(name, rng):
    f, l = name.lower().split()
    style = rng.integers(0, 4)
    user = [f"{f}.{l}", f"{f}{l}{rng.integers(1, 99)}", f"{f[0]}{l}", f"{l}.{f}"][style]
    return f"{user}@{rng.choice(['gmail.com', 'yahoo.in', 'outlook.com', 'rediffmail.com'])}"


def typo(s, rng):
    if len(s) < 4:
        return s
    i = rng.integers(1, len(s) - 1)
    op = rng.integers(0, 3)
    if op == 0:
        return s[:i] + s[i + 1:]                       # drop a letter
    if op == 1:
        return s[:i] + s[i + 1] + s[i] + s[i + 2:]     # swap two letters
    return s[:i] + s[i] + s[i:]                        # double a letter


def messy_name(name, rng):
    f, l = name.split()
    r = rng.random()
    if r < 0.15:
        return f"{f[0]}. {l}"
    if r < 0.25:
        return f"{l} {f}"
    if r < 0.40:
        return f"{typo(f, rng)} {l}"
    if r < 0.50:
        return f"{f} {typo(l, rng)}"
    if r < 0.60:
        return f"  {f.upper()} {l.lower()} "
    return name


def messy_phone(p, rng):
    r = rng.random()
    if r < 0.25:
        return f"+91-{p}"
    if r < 0.45:
        return f"0{p}"
    if r < 0.60:
        return f"{p[:5]} {p[5:]}"
    return p


def build_identity_sources(customers, rng):
    cust = customers.copy()
    cust["phone"] = [phone_number(rng) for _ in range(len(cust))]
    cust["email"] = [email_for(n, rng) for n in cust.full_name]
    core = cust[["customer_id", "full_name", "date_of_birth", "phone", "email", "city"]].rename(
        columns={"customer_id": "core_id"})
    truth = [("core", str(r.core_id), f"P{r.core_id:05d}") for r in core.itertuples()]

    crm, cid = [], 1
    for r in cust.itertuples():
        if rng.random() > 0.82:
            continue
        for _ in range(1 + int(rng.random() < 0.10)):  # some customers have two CRM contacts
            phone = r.phone if rng.random() > 0.12 else phone_number(rng)  # old number on file
            crm.append((f"CRM{cid:06d}", messy_name(r.full_name, rng), messy_phone(phone, rng),
                        (r.email.upper() if rng.random() < 0.2 else r.email) if rng.random() > 0.25 else None,
                        r.date_of_birth if rng.random() > 0.3 else None, r.city))
            truth.append(("crm", f"CRM{cid:06d}", f"P{r.customer_id:05d}"))
            cid += 1
    first = [n.split()[0] for n in cust.full_name]
    last = [n.split()[1] for n in cust.full_name]
    for k in range(350):  # prospects who are not customers (some share a common name with customers)
        name = f"{rng.choice(first)} {rng.choice(last)}"
        crm.append((f"CRM{cid:06d}", name, messy_phone(phone_number(rng), rng), email_for(name, rng) if rng.random() > 0.3 else None,
                    (pd.Timestamp("1960-01-01") + pd.Timedelta(days=int(rng.integers(0, 16000)))).strftime("%Y-%m-%d")
                    if rng.random() > 0.4 else None, rng.choice(cust.city.unique())))
        truth.append(("crm", f"CRM{cid:06d}", f"X{k:05d}"))
        cid += 1
    crm = pd.DataFrame(crm, columns=["crm_id", "contact_name", "mobile", "email", "dob", "city"])

    cards, k = [], 1
    holders = cust.sample(frac=0.40, random_state=int(rng.integers(1e9)))
    for r in holders.itertuples():
        d = pd.Timestamp(r.date_of_birth).strftime("%d/%m/%Y")
        nm = r.full_name.upper() if rng.random() < 0.7 else messy_name(r.full_name, rng).upper()
        cards.append((f"CC{k:06d}", nm, d, r.phone[-10:] if rng.random() > 0.1 else phone_number(rng),
                      r.email if rng.random() > 0.15 else None))
        truth.append(("card", f"CC{k:06d}", f"P{r.customer_id:05d}"))
        k += 1
    for j in range(180):  # card-only customers, not in core banking
        name = f"{rng.choice(first)} {rng.choice(last)}"
        dob = (pd.Timestamp("1965-01-01") + pd.Timedelta(days=int(rng.integers(0, 13000)))).strftime("%d/%m/%Y")
        cards.append((f"CC{k:06d}", name.upper(), dob, phone_number(rng), email_for(name, rng)))
        truth.append(("card", f"CC{k:06d}", f"C{j:05d}"))
        k += 1
    cards = pd.DataFrame(cards, columns=["card_customer_id", "cardholder_name", "dob_ddmmyyyy", "phone", "email"])
    truth = pd.DataFrame(truth, columns=["source", "record_id", "person_id"])
    return core, crm, cards, truth, cust


def simulate_behaviour(cust, accounts, loans, rng):
    """Monthly activity with churn and product take-up driven by known rules."""
    n_prod = accounts[accounts.status != "Closed"].groupby("customer_id").size().reindex(cust.customer_id, fill_value=0) \
        + loans[loans.status == "Active"].groupby("customer_id").size().reindex(cust.customer_id, fill_value=0)
    seg_scale = {"Retail": 1.0, "Salaried": 1.6, "Premium": 4.0, "SME": 5.0}
    age = ((pd.Timestamp("2024-04-01") - pd.to_datetime(cust.date_of_birth)).dt.days / 365.25).values
    joined = pd.to_datetime(cust.joined_date).dt.to_period("M")

    act, events, churn_rows, inter = [], [], [], []
    for i, c in enumerate(cust.itertuples()):
        eng = rng.normal(0, 1) + (0.3 if c.segment in ("Salaried", "Premium") else 0)
        scale = seg_scale[c.segment]
        fee_prone = rng.random() < 0.25
        digital = np.clip(0.35 + 0.12 * eng - 0.006 * (age[i] - 40) + rng.normal(0, 0.1), 0.02, 0.98)
        holds = set()
        churn_at, warn = None, 0
        complaints_recent = 0.0
        start = max(0, (joined.iloc[i] - MONTHS[0]).n) if joined.iloc[i] > MONTHS[0] else 0
        bal = float(rng.lognormal(10.5, 1.0) * scale)
        for m in range(start, len(MONTHS)):
            tenure_m = (MONTHS[m] - joined.iloc[i]).n
            fees = float(rng.poisson(1.2) * 150) if fee_prone else float(rng.random() < 0.1) * 150
            # complaints: more likely when fees are charged; rise before a customer leaves
            lam_c = 0.03 + 0.04 * (fees > 0) + (0.25 if warn > 0 else 0)
            comp = int(rng.poisson(lam_c))
            complaints_recent = 0.6 * complaints_recent + comp
            if churn_at is None:
                logit = (-3.75 - 0.6 * eng + 0.55 * complaints_recent + 0.0012 * fees - 0.35 * min(n_prod.iloc[i] + len(holds), 4)
                         - 0.25 * np.log1p(max(tenure_m, 0) / 12) + 0.15 * (age[i] < 30))
                if warn == 0 and rng.random() < 1 / (1 + np.exp(-logit)):
                    warn = 1  # customer starts to drift away; leaves after 2-4 months
                    churn_at = m + int(rng.integers(2, 5))
            fade = 1.0
            if churn_at is not None:
                left = churn_at - m
                fade = 0.0 if left <= 0 else min(1.0, 0.25 + 0.25 * left)
            if churn_at is not None and m >= churn_at:
                continue
            season = 1 + 0.25 * (MONTHS[m].month in (10, 11))
            txn = int(rng.poisson(max(0.5, (9 + 4 * eng) * season * fade)))
            spend = float(np.round(txn * rng.lognormal(7.6, 0.4) * scale, 0))
            inflow = float(np.round(spend * rng.uniform(0.9, 1.4) * (1.25 if c.segment == "Salaried" else 1.0) * (fade ** 2), 0))
            bal = max(0.0, bal * rng.uniform(0.97, 1.05) + 0.3 * (inflow - spend))
            logins = int(rng.poisson(max(0.1, 14 * digital * fade * (1 + 0.2 * eng))))
            nps = int(np.clip(round(8 + 0.6 * eng - 2.5 * (complaints_recent > 0.8) - 2 * (warn > 0) + rng.normal(0, 1.2)), 0, 10)) \
                if rng.random() < 0.06 else None
            act.append((c.customer_id, str(MONTHS[m]), txn, spend, inflow, round(float(np.clip(digital + rng.normal(0, 0.05), 0, 1)), 3),
                        logins, round(bal, 0), fees))
            if comp:
                inter += [(c.customer_id, str(MONTHS[m]), "Complaint", None)] * comp
            if rng.random() < 0.05:
                inter.append((c.customer_id, str(MONTHS[m]), "Service request", None))
            if nps is not None:
                inter.append((c.customer_id, str(MONTHS[m]), "NPS survey", nps))
            if churn_at is not None:
                continue
            # product take-up (monthly hazard)
            p = {
                "Fixed Deposit": 0.0015 + 0.020 * (bal > 3e5) + 0.010 * (age[i] > 45) * (bal > 1e5),
                "Credit Card": 0.001 + 0.016 * (c.segment in ("Salaried", "Premium")) * (digital > 0.4) + 0.008 * (eng > 0.5),
                "Personal Loan": 0.001 + 0.012 * (c.segment == "Salaried") * (age[i] < 38) + 0.006 * (fees > 0),
                "Insurance": 0.001 + 0.008 * (age[i] > 35) * (bal > 1.5e5) + 0.010 * ("Fixed Deposit" in holds) + 0.008 * (c.segment == "Premium"),
            }
            for prod, pr in p.items():
                if prod not in holds and rng.random() < pr:
                    holds.add(prod)
                    events.append((c.customer_id, prod, str(MONTHS[m])))
        churn_rows.append((c.customer_id, str(MONTHS[churn_at]) if churn_at is not None and churn_at < len(MONTHS) else None))
    act = pd.DataFrame(act, columns=["customer_id", "month", "txn_count", "spend", "inflow", "digital_share", "app_logins",
                                     "avg_balance", "fees_charged"])
    events = pd.DataFrame(events, columns=["customer_id", "product", "month"])
    inter = pd.DataFrame(inter, columns=["customer_id", "month", "type", "nps_score"])
    churn = pd.DataFrame(churn_rows, columns=["customer_id", "churn_month"])
    return act, events, inter, churn


def main(db="data/bank.db"):
    rng = np.random.default_rng(SEED)
    con = sqlite3.connect(db)
    customers = pd.read_sql("SELECT * FROM customers", con)
    accounts = pd.read_sql("SELECT * FROM accounts", con)
    loans = pd.read_sql("SELECT * FROM loans", con)
    for d in ("sources", "truth"):
        os.makedirs(d, exist_ok=True)
    core, crm, cards, truth, cust = build_identity_sources(customers, rng)
    act, events, inter, churn = simulate_behaviour(customers, accounts, loans, rng)
    # CRM interactions are keyed by CRM contact, as in a real CRM (needs identity resolution to join)
    first_crm = truth[truth.source == "crm"].assign(cid=lambda d: d.person_id.str[1:]).query("person_id.str.startswith('P')",
                                                                                              engine="python")
    first_crm = first_crm.groupby("cid").record_id.first()
    inter["crm_id"] = inter.customer_id.map(lambda x: first_crm.get(f"{x:05d}"))
    inter = inter.dropna(subset=["crm_id"])[["crm_id", "month", "type", "nps_score"]]

    core.to_csv("sources/core_banking.csv", index=False)
    crm.to_csv("sources/crm_contacts.csv", index=False)
    cards.to_csv("sources/card_system.csv", index=False)
    inter.to_csv("sources/crm_interactions.csv", index=False)
    act.to_csv("sources/monthly_activity.csv", index=False)
    events.to_csv("sources/product_events.csv", index=False)
    truth.to_csv("truth/identity_truth.csv", index=False)
    churn.to_csv("truth/churn_truth.csv", index=False)
    print(f"core {len(core)}, crm {len(crm)}, cards {len(cards)}, interactions {len(inter)}, "
          f"activity rows {len(act)}, product events {len(events)}")
    print("churned by month:", churn.churn_month.dropna().str[:7].value_counts().sort_index().to_dict())
    print(events.groupby(["product"]).size().to_dict())


if __name__ == "__main__":
    main()
