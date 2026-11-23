"""
Generates synthetic bank transfers in the same 11-column format as IBM's "Transactions for Anti Money
Laundering" dataset (HI-Small_Trans.csv), plus a patterns file like HI-Small_Patterns.txt that says which
laundering attempt and pattern each laundering transfer belongs to. Seeded, so every run is identical.

  data/HI-Small-style_Trans.csv.gz   10 days, 25,000 accounts, 518,044 transfers, 519 laundering (1 in 998)
  data/HI-Small-style_Patterns.csv   one row per laundering transfer: attempt id and pattern

Normal activity includes the things that make AML rules misfire: payroll accounts paying many staff
(looks like fan-out), merchants and utilities collecting from many customers (looks like fan-in), and
friends paying each other back (short cycles).

Laundering follows IBM's 8 patterns: fan-out, fan-in, gather-scatter, scatter-gather, cycle,
random (a chain that wanders), bipartite and stack. About 1 transfer in 1,000 is laundering.
"""
import gzip
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "data"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(981)

START = pd.Timestamp("2026-09-01")
DAYS = 10
N_ACC, N_BANKS = 25_000, 40
CUR = {"US Dollar": 1.0, "Euro": 1.08, "UK Pound": 1.27, "Indian Rupee": 0.012, "Yuan": 0.14, "Yen": 0.0067,
       "Swiss Franc": 1.13, "Australian Dollar": 0.66, "Canadian Dollar": 0.73, "Saudi Riyal": 0.27}
CUR_P = np.array([0.42, 0.18, 0.08, 0.10, 0.07, 0.05, 0.03, 0.03, 0.02, 0.02])
FORMATS = ["ACH", "Cheque", "Credit Card", "Wire", "Cash", "Reinvestment", "Bitcoin"]
FORMAT_P = np.array([0.30, 0.20, 0.25, 0.08, 0.10, 0.05, 0.02])

bank = rng.integers(1, N_BANKS + 1, N_ACC) * 10 + rng.integers(0, 10, N_ACC)    # bank ids like 70, 3402...
acct = np.array([format(x, "X") for x in rng.integers(0x80000000, 0xFFFFFFFF, N_ACC)])
home_cur = rng.choice(len(CUR), N_ACC, p=CUR_P)
cur_names = list(CUR)
rows, patterns = [], []


def ts(day_float):
    return START + pd.Timedelta(minutes=int(day_float * 1440))


def transfer(a, b, t, usd, fmt=None, laundering=0, attempt=None, pattern=None):
    c = cur_names[home_cur[a]]
    rc = cur_names[home_cur[b]] if rng.random() < 0.04 else c      # some transfers change currency
    paid, received = round(usd / CUR[c], 2), round(usd / CUR[rc], 2)
    fmt = fmt or FORMATS[rng.choice(len(FORMATS), p=FORMAT_P)]
    rows.append((ts(t), bank[a], acct[a], bank[b], acct[b], received, rc, paid, c, fmt, laundering))
    if laundering:
        patterns.append((len(rows) - 1, attempt, pattern))


def normal():
    special = rng.permutation(N_ACC)
    payroll, merchants, people = special[:60], special[60:260], special[260:]
    # everyday payments between people, each with a few regular counterparties
    friends = {a: rng.choice(people, size=rng.integers(2, 8), replace=False) for a in people}
    for a in people:
        n = rng.poisson(2.0 * DAYS)
        for _ in range(n):
            if rng.random() < 0.6:
                b = rng.choice(merchants)
                usd = float(np.exp(rng.normal(3.8, 1.0)))
            else:
                b = rng.choice(friends[a])
                usd = float(np.exp(rng.normal(4.5, 1.1)))
                if rng.random() < 0.05:     # paying a friend back: short legitimate loops
                    t = rng.uniform(0, DAYS - 1)
                    transfer(a, b, t, usd)
                    transfer(b, a, t + rng.uniform(0.01, 0.8), usd * rng.uniform(0.3, 1.0))
                    continue
            transfer(a, b, rng.uniform(0, DAYS), usd)
    # payroll: one account paying 40-300 staff on the same day (fan-out shape, legitimate)
    for p in payroll:
        staff = rng.choice(people, size=rng.integers(40, 300), replace=False)
        day = rng.integers(0, DAYS)
        for s_ in staff:
            transfer(p, s_, day + 0.4 + rng.uniform(0, 0.05), float(np.exp(rng.normal(8.0, 0.4))), fmt="ACH")
    # merchants pay suppliers and move money between their own accounts
    for m in merchants:
        for _ in range(rng.poisson(6)):
            transfer(m, rng.choice(merchants), rng.uniform(0, DAYS), float(np.exp(rng.normal(8.5, 1.0))), fmt="Wire")


def laundering(n_attempts=55):
    kinds = ["fan_out", "fan_in", "gather_scatter", "scatter_gather", "cycle", "random", "bipartite", "stack"]
    pool = rng.permutation(N_ACC)
    used = 0

    def take(k):
        nonlocal used
        used += k
        return pool[used - k:used]

    for attempt in range(1, n_attempts + 1):
        kind = kinds[(attempt - 1) % len(kinds)]
        t0 = rng.uniform(0, DAYS - 3)
        base = float(np.exp(rng.normal(8.5, 0.8)))
        fmt = rng.choice(["ACH", "Wire", "Cheque", "Cash", "Bitcoin"])
        tx = lambda a, b, t, k=1.0: transfer(a, b, t, base * k * rng.uniform(0.9, 1.1), fmt, 1, attempt, kind)  # noqa: E731
        if kind == "fan_out":
            src, dsts = take(1)[0], take(rng.integers(6, 13))
            for i, d in enumerate(dsts):
                tx(src, d, t0 + i * rng.uniform(0.02, 0.15))
        elif kind == "fan_in":
            dst, srcs = take(1)[0], take(rng.integers(6, 13))
            for i, s_ in enumerate(srcs):
                tx(s_, dst, t0 + i * rng.uniform(0.02, 0.15))
        elif kind == "gather_scatter":
            hub, srcs, dsts = take(1)[0], take(rng.integers(4, 9)), take(rng.integers(4, 9))
            for i, s_ in enumerate(srcs):
                tx(s_, hub, t0 + i * 0.05)
            for i, d in enumerate(dsts):
                tx(hub, d, t0 + 0.6 + i * 0.05, len(srcs) / len(dsts))
        elif kind == "scatter_gather":
            src, mids, dst = take(1)[0], take(rng.integers(4, 9)), take(1)[0]
            for i, m in enumerate(mids):
                tx(src, m, t0 + i * 0.03)
                tx(m, dst, t0 + 0.5 + i * 0.05, 0.97)
        elif kind == "cycle":
            ring, t = take(rng.integers(3, 6)), t0
            for i in range(len(ring)):
                tx(ring[i], ring[(i + 1) % len(ring)], t, 0.98 ** i)
                t += rng.uniform(0.1, 0.6)                 # each hop a few hours after the one before
        elif kind == "random":
            chain, t = take(rng.integers(4, 8)), t0
            for i in range(len(chain) - 1):
                tx(chain[i], chain[i + 1], t, 0.97 ** i)
                t += rng.uniform(0.1, 0.7)
        elif kind == "bipartite":
            left, right = take(rng.integers(3, 5)), take(rng.integers(3, 5))
            for a in left:
                for b in rng.choice(right, size=2, replace=False):
                    tx(a, b, t0 + rng.uniform(0, 1.5), 0.5)
        else:  # stack: two layers of bipartite transfers
            l1, l2, l3 = take(3), take(3), take(3)
            for a in l1:
                for b in l2:
                    tx(a, b, t0 + rng.uniform(0, 0.5), 0.33)
            for a in l2:
                for b in l3:
                    tx(a, b, t0 + 1 + rng.uniform(0, 0.5), 0.33)


def main():
    normal()
    laundering()
    cols = ["Timestamp", "From Bank", "Account", "To Bank", "Account", "Amount Received", "Receiving Currency",
            "Amount Paid", "Payment Currency", "Payment Format", "Is Laundering"]
    df = pd.DataFrame(rows)
    df[0] = df[0].dt.strftime("%Y/%m/%d %H:%M")
    df = df.sort_values(0, kind="stable")
    order = {old: new for new, old in enumerate(df.index)}
    df.columns = cols
    with gzip.open(OUT / "HI-Small-style_Trans.csv.gz", "wt", newline="") as f:
        df.to_csv(f, index=False)
    p = pd.DataFrame(patterns, columns=["row", "attempt_id", "pattern"])
    p["row"] = p["row"].map(order)
    p.sort_values("row").to_csv(OUT / "HI-Small-style_Patterns.csv", index=False)
    n, k = len(df), int(df["Is Laundering"].sum())
    print(f"{n:,} transfers, {k:,} laundering (1 in {n // k:,}), {p.attempt_id.nunique()} attempts, "
          f"{len(set(df.iloc[:, 2]) | set(df.iloc[:, 4])):,} accounts")


if __name__ == "__main__":
    main()
