"""
Step 1: generate a SYNTHETIC bank transaction dataset with hidden mule rings.

Real customer transaction data is confidential, so this script builds a
realistic stand-in: ordinary customers who get salaries and pay merchants,
plus planted fraud rings of three kinds seen in AML typologies:

  1. Fan-in / fan-out  - many victims pay one collector, who splits the money
                         across mules, who forward it to an exit account fast
  2. Round-tripping    - money circles through 4-6 accounts and comes back
  3. Layering chains   - money hops through several accounts, a little
                         smaller at each hop, to hide where it came from

Every account and transaction is invented. The labels (which accounts are
mules) let us measure how well the detector works.

Run:  python generate_data.py      -> data/accounts.csv, data/transactions.csv
"""

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

random.seed(42)
OUT = Path("data")
OUT.mkdir(exist_ok=True)

START = datetime(2026, 7, 1)
DAYS = 90
N_CUSTOMERS, N_EMPLOYERS, N_MERCHANTS = 2000, 25, 120

accounts, txns = [], []


def add_account(acc_id, kind, opened_days_ago, ring_id=None):
    accounts.append({"account_id": acc_id, "kind": kind,
                     "opened": (START - timedelta(days=opened_days_ago)).date(),
                     "is_mule": int(ring_id is not None), "ring_id": ring_id or ""})


def add_txn(src, dst, amount, when, channel):
    txns.append({"txn_id": f"T{len(txns) + 1:06d}", "src": src, "dst": dst,
                 "amount": round(amount, 2), "timestamp": when, "channel": channel})


def rand_time(day, night=False):
    hour = random.choice([0, 1, 2, 3, 23]) if night else random.randint(8, 21)
    return START + timedelta(days=day, hours=hour, minutes=random.randint(0, 59))


# ---------------- ordinary activity ----------------
customers = [f"C{i:04d}" for i in range(N_CUSTOMERS)]
employers = [f"E{i:03d}" for i in range(N_EMPLOYERS)]
merchants = [f"M{i:03d}" for i in range(N_MERCHANTS)]
for c in customers:
    add_account(c, "customer", random.randint(200, 3000))
for e in employers:
    add_account(e, "employer", random.randint(1000, 5000))
for m in merchants:
    add_account(m, "merchant", random.randint(500, 5000))

salary = {c: random.choice([25000, 40000, 60000, 90000, 150000]) for c in customers}
employer_of = {c: random.choice(employers) for c in customers}
friends = {c: random.sample(customers, 6) for c in customers}

for c in customers:
    for month in range(3):  # monthly salary
        add_txn(employer_of[c], c, salary[c] * random.uniform(0.98, 1.02), rand_time(month * 30 + 1), "NEFT")
    for _ in range(random.randint(3, 45)):  # card / UPI spends (some customers barely use the account)
        add_txn(c, random.choice(merchants), random.uniform(80, salary[c] * 0.05), rand_time(random.randint(0, DAYS - 1)), "UPI")
    for _ in range(random.randint(0, 6)):  # paying friends and family
        add_txn(c, random.choice(friends[c]), random.uniform(200, 8000), rand_time(random.randint(0, DAYS - 1)), "UPI")

# ---------------- legitimate look-alikes (to make detection hard) ----------------
# Landlords and small traders collect from many people and pay out quickly,
# and new students have young accounts with little card spending. A good
# detector must not flag them.
lookalikes = random.sample(customers, 60)
for c in lookalikes[:30]:  # rent collectors / small traders: many payers, fast payouts
    payers = random.sample(customers, random.randint(8, 20))
    supplier = random.choice(merchants + customers)
    for month in range(3):
        day, total = month * 30 + random.randint(1, 5), 0
        for p in payers:
            amt = random.uniform(4000, 30000)
            add_txn(p, c, amt, rand_time(day), "UPI"); total += amt
        add_txn(c, supplier, total * random.uniform(0.6, 0.95), rand_time(day) + timedelta(hours=random.randint(2, 30)), "NEFT")
for c in lookalikes[30:]:  # new students / first jobbers: young accounts, family transfers
    for a in accounts:
        if a["account_id"] == c:
            a["opened"] = (START - timedelta(days=random.randint(5, 80))).date()
    parent = random.choice(customers)
    for month in range(3):
        amt = random.uniform(5000, 20000)
        t = rand_time(month * 30 + 2)
        add_txn(parent, c, amt, t, "UPI")
        add_txn(c, random.choice(customers), amt * random.uniform(0.5, 0.9), t + timedelta(hours=random.randint(3, 40)), "UPI")

# ---------------- planted mule rings ----------------
ring_no = 0


def new_mules(n, ring):
    ids = []
    for _ in range(n):
        acc = f"X{len([a for a in accounts if a['account_id'].startswith('X')]):04d}"
        age = random.randint(5, 60) if random.random() < 0.7 else random.randint(400, 2000)  # 30% are older, bought accounts
        add_account(acc, "customer", age, ring)
        ids.append(acc)
        for _ in range(random.randint(3, 35)):  # camouflage: ordinary-looking spending
            add_txn(acc, random.choice(merchants), random.uniform(100, 3000), rand_time(random.randint(0, DAYS - 1)), "UPI")
    return ids


for _ in range(4):  # fan-in / fan-out rings
    ring_no += 1; ring = f"R{ring_no:02d}"
    collector, *mules = new_mules(random.randint(5, 7), ring)
    exit_acc = new_mules(1, ring)[0]
    victims = random.sample(customers, random.randint(15, 25))
    for wave in range(random.randint(3, 5)):
        day = random.randint(0, DAYS - 3)
        total = 0
        for v in random.sample(victims, random.randint(6, len(victims))):
            amt = random.uniform(5000, 49000)
            add_txn(v, collector, amt, rand_time(day), "UPI"); total += amt
        share = total * 0.97 / len(mules)
        for m in mules:
            t = rand_time(day, night=random.random() < 0.5) + timedelta(hours=random.randint(1, 6))
            add_txn(collector, m, share, t, "IMPS")
            add_txn(m, exit_acc, share * 0.98, t + timedelta(hours=random.choice([2, 6, 20, 40, 70])), "IMPS")

for _ in range(2):  # round-tripping cycles
    ring_no += 1; ring = f"R{ring_no:02d}"
    loop = new_mules(random.randint(4, 6), ring)
    for _ in range(random.randint(4, 7)):
        day, amt = random.randint(0, DAYS - 3), random.uniform(200000, 900000)
        t = rand_time(day)
        for a, b in zip(loop, loop[1:] + loop[:1]):
            add_txn(a, b, amt, t, "RTGS"); amt *= 0.995; t += timedelta(hours=random.randint(2, 12))

for _ in range(2):  # layering chains
    ring_no += 1; ring = f"R{ring_no:02d}"
    chain = new_mules(random.randint(5, 7), ring)
    source = random.choice(employers)  # dirty money disguised as business payments
    for _ in range(random.randint(3, 6)):
        day, amt = random.randint(0, DAYS - 3), random.uniform(300000, 1500000)
        t = rand_time(day)
        add_txn(source, chain[0], amt, t, "NEFT")
        for a, b in zip(chain, chain[1:]):
            amt *= random.uniform(0.96, 0.99); t += timedelta(hours=random.randint(1, 8))
            add_txn(a, b, amt, t, "IMPS")

pd.DataFrame(accounts).to_csv(OUT / "accounts.csv", index=False)
tx = pd.DataFrame(txns).sort_values("timestamp")
tx.to_csv(OUT / "transactions.csv", index=False)
mules = sum(a["is_mule"] for a in accounts)
print(f"{len(accounts):,} accounts ({mules} mules in {ring_no} rings), {len(tx):,} transactions")
