"""
Generates a synthetic bank dataset (seeded, so every run gives the same data).

  branches      8 branches across four regions
  customers     1,200 customers (Retail, Premium, SME) with a KYC risk rating
  accounts      ~1,700 savings, current and salary accounts
  transactions  ~90,000 credits and debits, Jan 2024 to Jun 2026, across 8 channels

Balances never go negative: each account is simulated in time order and a debit is
skipped if the balance cannot cover it. A few patterns are planted for the analysis
queries to find: festive-season spending, cash deposits kept just under the ₹50,000
PAN-reporting level (structuring), and dormant accounts that suddenly receive large credits.
"""
import csv
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

rng = np.random.default_rng(2026)
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)
START, END = datetime(2024, 1, 1), datetime(2026, 6, 30, 23, 59)

BRANCHES = [
    (1, "Connaught Place", "New Delhi", "North"), (2, "Hazratganj", "Lucknow", "North"),
    (3, "MG Road", "Bengaluru", "South"), (4, "T Nagar", "Chennai", "South"),
    (5, "Park Street", "Kolkata", "East"), (6, "Main Road", "Ranchi", "East"),
    (7, "Fort", "Mumbai", "West"), (8, "FC Road", "Pune", "West"),
]
FIRST = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Rohan", "Arjun", "Kabir", "Ananya", "Diya", "Isha", "Kavya", "Meera",
         "Priya", "Riya", "Sneha", "Neha", "Rahul", "Vikram", "Siddharth", "Pooja", "Nikhil", "Tanvi", "Harsh", "Sanjana"]
LAST = ["Sharma", "Verma", "Gupta", "Singh", "Kumar", "Iyer", "Nair", "Reddy", "Das", "Banerjee", "Patel", "Shah",
        "Joshi", "Mehta", "Rao", "Kushwaha", "Mishra", "Pandey", "Chatterjee", "Menon"]

DEBIT_CH = (["UPI", "Card", "ATM", "NEFT", "IMPS", "Cheque"], None)  # probabilities shift over time, see below
CREDIT_CH = (["UPI", "NEFT", "IMPS", "Cash", "Cheque", "RTGS"], [0.38, 0.28, 0.14, 0.12, 0.05, 0.03])


def rand_dt(a, b):
    return a + timedelta(seconds=int(rng.integers(0, int((b - a).total_seconds()))))


def season(ts):
    return 1.45 if ts.month in (10, 11) else (1.15 if ts.month == 3 else 1.0)  # festive and year-end


def main():
    with open(OUT / "branches.csv", "w", newline="") as f:
        csv.writer(f).writerows([("branch_id", "branch_name", "city", "region"), *BRANCHES])

    customers, accounts, txns = [], [], []
    seg_p = {"Retail": 0.78, "Premium": 0.12, "SME": 0.10}
    for cid in range(1, 1201):
        seg = rng.choice(list(seg_p), p=list(seg_p.values()))
        risk = rng.choice(["Low", "Medium", "High"], p=[0.7, 0.24, 0.06])
        onboard = rand_dt(datetime(2019, 1, 1), datetime(2026, 3, 31)).date()
        dob = date(int(rng.integers(1960, 2004)), int(rng.integers(1, 13)), int(rng.integers(1, 29)))
        name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        customers.append((cid, name, dob, seg, risk, onboard, int(rng.integers(1, 9))))

    aid = 100001
    for c in customers:
        cid, seg, onboard = c[0], c[3], c[5]
        types = ["Current"] if seg == "SME" else (["Salary"] if rng.random() < 0.45 else ["Savings"])
        if rng.random() < 0.35:
            types.append("Savings" if types[0] != "Savings" else "Current")
        for at in types:
            opened = max(onboard, (START - timedelta(days=int(rng.integers(0, 1500)))).date()) if rng.random() < 0.7 else onboard
            status = "Closed" if rng.random() < 0.04 else "Active"
            scale = {"Retail": 1, "Premium": 6, "SME": 10}[seg]
            ob = round(float(rng.lognormal(10.3, 0.9)) * scale, 2) if opened < START.date() else 0.0
            accounts.append([aid, cid, at, opened, status, ob, seg, c[4]])
            aid += 1

    tid = 1
    dormant = set(rng.choice([a[0] for a in accounts if a[2] == "Savings"], 14, replace=False))
    structurers = set(rng.choice([c[0] for c in customers if c[3] != "SME"], 6, replace=False))
    for a in accounts:
        acc_id, cid, at, opened, status, ob, seg, risk = a
        begin = max(START, datetime.combine(opened, datetime.min.time()))
        stop = END if status == "Active" else rand_dt(begin + timedelta(days=60), END) if begin < END - timedelta(days=90) else END
        if begin >= stop:
            continue
        if status == "Active" and rng.random() < 0.12:  # some customers drift away and stop using the account
            stop = rand_dt(begin + timedelta(days=30), END) if begin < END - timedelta(days=60) else stop
        scale = {"Retail": 1, "Premium": 5, "SME": 12}[seg]
        events = []
        # salary credits on the 1st of each month
        if at == "Salary":
            sal = round(float(rng.lognormal(10.9, 0.45)), -2)
            d = datetime(begin.year, begin.month, 1, 9, 30)
            while d < stop:
                if d >= begin:
                    events.append((d + timedelta(minutes=int(rng.integers(0, 300))), "Credit", "NEFT", sal * (1 + 0.08 * (d.year - 2024)), "Salary credit"))
                d = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        # ordinary activity
        n_cr = int(rng.poisson({"Savings": 18, "Current": 55, "Salary": 6}[at] * (stop - begin).days / 900))
        n_dr = int(rng.poisson({"Savings": 55, "Current": 85, "Salary": 160}[at] * (stop - begin).days / 900))
        for _ in range(n_cr):
            ts = rand_dt(begin, stop)
            ch = rng.choice(CREDIT_CH[0], p=CREDIT_CH[1])
            amt = float(rng.lognormal(8.6, 1.1)) * scale * (3 if ch == "RTGS" else 1)
            events.append((ts, "Credit", ch, amt, "Transfer in" if ch != "Cash" else "Cash deposit"))
        for _ in range(n_dr):
            ts = rand_dt(begin, stop)
            f = (ts - START) / (END - START)  # UPI adoption rises over time
            ch = rng.choice(DEBIT_CH[0], p=[0.38 + 0.18 * f, 0.22 - 0.05 * f, 0.16 - 0.08 * f, 0.09, 0.08, 0.07 - 0.05 * f])
            amt = float(rng.lognormal(8.15, 1.0)) * scale * season(ts) * (2.5 if ch in ("NEFT", "Cheque") else 1)
            if ch == "ATM":
                amt = float(rng.choice([2000, 5000, 10000, 20000]))
            events.append((ts, "Debit", ch, amt, {"UPI": "UPI payment", "Card": "Card purchase", "ATM": "ATM withdrawal"}.get(ch, "Payment")))
        # planted pattern: dormant then reactivated with a large credit
        if acc_id in dormant:
            gap_start = datetime(2024, 4, 1)
            react = rand_dt(datetime(2025, 9, 2), datetime(2025, 12, 31))
            events = [e for e in events if not (gap_start <= e[0] <= react)]
            events.append((react, "Credit", rng.choice(["RTGS", "Cash", "IMPS"]), float(rng.uniform(1.5e5, 9e5)), "Transfer in"))
        # planted pattern: cash deposits just under ₹50,000
        if cid in structurers and at != "Current":
            for _ in range(int(rng.integers(3, 6))):
                base = rand_dt(datetime(2025, 1, 1), datetime(2026, 5, 31))
                for k in range(int(rng.integers(3, 6))):
                    events.append((base + timedelta(days=int(rng.integers(0, 6)), hours=int(rng.integers(10, 16))), "Credit", "Cash",
                                   float(rng.uniform(45000, 49900)), "Cash deposit"))
        events.sort(key=lambda e: e[0])
        bal = ob
        for ts, typ, ch, amt, desc in events:
            amt = round(amt, 2)
            if typ == "Debit":
                if amt > bal:
                    continue
                bal -= amt
            else:
                bal += amt
            txns.append((tid, acc_id, ts.strftime("%Y-%m-%d %H:%M:%S"), typ, ch, f"{amt:.2f}", desc))
            tid += 1

    with open(OUT / "customers.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("customer_id", "full_name", "date_of_birth", "segment", "kyc_risk", "onboarded_on", "branch_id"))
        w.writerows(customers)
    with open(OUT / "accounts.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("account_id", "customer_id", "account_type", "opened_on", "status", "opening_balance"))
        w.writerows(a[:6] for a in accounts)
    txns.sort(key=lambda t: (t[2], t[1]))
    txns = [(i, *t[1:]) for i, t in enumerate(txns, start=1)]  # ids in time order
    with open(OUT / "transactions.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(("txn_id", "account_id", "txn_ts", "txn_type", "channel", "amount", "description"))
        w.writerows(txns)
    print(f"{len(customers)} customers, {len(accounts)} accounts, {len(txns)} transactions")


if __name__ == "__main__":
    main()
