"""
Loads the transfer graph and runs the AML pattern queries in Cypher.

Accounts are nodes, transfers are edges. The graph engine here is Kùzu, an embedded graph database that
speaks Cypher and installs with pip. The same graph and queries for a Neo4j server are in neo4j/.

Patterns (thresholds from config/rules.json):
  - cycle:   money that leaves an account and returns to it in 3, 4 or 5 hops, each hop later than the one
             before and within 24 hours of it, with amounts that stay close to the first hop
  - fan-in:  5+ different accounts sending $1,000+ to one account inside a 24-hour window
  - fan-out: one account sending $1,000+ to 5-30 different accounts inside a 24-hour window
             (above 30 receivers it is almost always payroll)

Cycles are written as fixed-length patterns (3, 4 and 5 hops) instead of one variable-length pattern:
the number of possible paths grows very fast with length, and fixed lengths with time and amount filters
keep every query bounded.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import kuzu
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DB = ROOT / "graph" / "aml.kuzu"
RULES = json.loads((ROOT / "config" / "rules.json").read_text())


def connect(rebuild: bool = False) -> kuzu.Connection:
    if rebuild and DB.exists():
        shutil.rmtree(DB) if DB.is_dir() else DB.unlink()
    db = kuzu.Database(str(DB))
    conn = kuzu.Connection(db)
    if rebuild:
        load(conn)
    return conn


def load(conn: kuzu.Connection) -> None:
    # PRIMARY KEY = uniqueness on account id, so every transfer finds its accounts by index, not by scanning
    conn.execute("CREATE NODE TABLE Account(id STRING, bank STRING, PRIMARY KEY (id))")
    conn.execute("CREATE REL TABLE SENT(FROM Account TO Account, tid INT64, ts TIMESTAMP, amount DOUBLE, "
                 "currency STRING, format STRING)")
    conn.execute(f"COPY Account FROM '{ROOT / 'data' / 'accounts.csv'}' (HEADER=true)")
    t = pd.read_csv(ROOT / "data" / "transfers.csv")
    edges = t.rename(columns={"src": "from", "dst": "to", "transfer_id": "tid", "amount_usd": "amount", "cur_paid": "currency"})
    path = ROOT / "graph" / "_edges.csv"
    edges[["from", "to", "tid", "ts", "amount", "currency", "format"]].to_csv(path, index=False)
    conn.execute(f"COPY SENT FROM '{path}' (HEADER=true)")
    path.unlink()


def _hops(n: int) -> str:
    """Cypher for an n-hop cycle a0 -> a1 -> ... -> a0 with time order, time gaps and amount drift filters."""
    nodes = [f"(a{i}:Account)" for i in range(n)]
    pattern = "".join(f"{nodes[i]}-[r{i}:SENT]->" for i in range(n)) + "(a0)"
    w = []
    for i in range(1, n):
        w.append(f"r{i}.ts > r{i - 1}.ts AND r{i}.ts <= r{i - 1}.ts + INTERVAL('{RULES['cycle']['max_hours_between_hops']} hours')")
        w.append(f"abs(r{i}.amount - r0.amount) <= $drift * r0.amount")
    distinct = [f"a{i}.id <> a{j}.id" for i in range(n) for j in range(i + 1, n)]
    ids = ", ".join(f"r{i}.tid" for i in range(n))
    accs = ", ".join(f"a{i}.id" for i in range(n))
    return (f"MATCH {pattern} WHERE r0.amount >= $min AND {' AND '.join(w + distinct)} "
            f"RETURN [{accs}] AS accounts, [{ids}] AS transfers, r0.ts AS first_ts")


def cycles(conn) -> list[dict]:
    c = RULES["cycle"]
    hits = []
    for n in range(c["min_hops"], c["max_hops"] + 1):
        res = conn.execute(_hops(n), {"min": float(c["min_amount_usd"]), "drift": float(c["max_amount_drift"])}).get_as_df()
        for row in res.itertuples(index=False):
            hits.append({"pattern": "cycle", "accounts": list(row.accounts), "transfers": list(row.transfers),
                         "first_ts": row.first_ts, "detail": f"{n}-hop cycle"})
    return hits


# Step 1: accounts with enough distinct counterparties in the window (fan-in: receivers; fan-out: senders)
FAN_IN = """
MATCH (src:Account)-[t:SENT]->(dst:Account)
WHERE t.ts >= $win_start AND t.ts < $win_end AND t.amount >= $min
WITH dst, count(DISTINCT src) AS senders
WHERE senders >= $min_n
RETURN dst.id AS account, senders AS n
"""

FAN_OUT = """
MATCH (src:Account)-[t:SENT]->(dst:Account)
WHERE t.ts >= $win_start AND t.ts < $win_end AND t.amount >= $min
WITH src, count(DISTINCT dst) AS receivers
WHERE receivers >= $min_n AND receivers <= $max_n
RETURN src.id AS account, receivers AS n
"""

# Step 2: the transfers behind each hit, as evidence
FAN_IN_EDGES = """
MATCH (src:Account)-[t:SENT]->(dst:Account)
WHERE t.ts >= $win_start AND t.ts < $win_end AND t.amount >= $min AND list_contains($ids, dst.id)
RETURN dst.id AS account, src.id AS other, t.tid AS tid
"""

FAN_OUT_EDGES = """
MATCH (src:Account)-[t:SENT]->(dst:Account)
WHERE t.ts >= $win_start AND t.ts < $win_end AND t.amount >= $min AND list_contains($ids, src.id)
RETURN src.id AS account, dst.id AS other, t.tid AS tid
"""


def windows(conn):
    lo, hi = conn.execute("MATCH ()-[t:SENT]->() RETURN min(t.ts), max(t.ts)").get_next()
    step = timedelta(hours=12)                       # 24-hour windows, every 12 hours, so no burst is split
    t = lo.replace(hour=0, minute=0)
    while t <= hi:
        yield t, t + timedelta(hours=24)
        t += step


def fans(conn, kind: str) -> list[dict]:
    r = RULES[kind]
    q, qe = (FAN_IN, FAN_IN_EDGES) if kind == "fan_in" else (FAN_OUT, FAN_OUT_EDGES)
    params = {"min": float(r["min_amount_usd"]), "min_n": r.get("min_senders", r.get("min_receivers"))}
    if kind == "fan_out":
        params["max_n"] = r["max_receivers"]
    hits = {}
    for start, end in windows(conn):
        w = {"win_start": start, "win_end": end, "min": params["min"]}
        found = conn.execute(q, {**params, **{k: v for k, v in w.items() if k != "min"}}).get_as_df()
        if found.empty:
            continue
        edges = conn.execute(qe, {**w, "ids": list(found.account)}).get_as_df()
        for account, g in edges.groupby("account"):
            tids, others = set(g.tid), set(g.other)
            if account in hits and hits[account]["_tids"] & tids:     # overlapping windows: same burst, merge it
                hits[account]["_tids"] |= tids
                hits[account]["_others"] |= others
                continue
            if account in hits:                                        # a second, separate burst on the same account
                account = f"{account}#{start:%m%d%H}"
            hits[account] = {"account": account.split("#")[0], "_tids": tids, "_others": others, "first_ts": start}
    out = []
    for h in hits.values():
        n = len(h["_others"])
        out.append({"pattern": kind, "accounts": [h["account"], *sorted(h["_others"])], "transfers": sorted(int(x) for x in h["_tids"]),
                    "first_ts": h["first_ts"], "detail": f"{n} {'senders' if kind == 'fan_in' else 'receivers'} in 24 h"})
    return out


def detect(conn) -> list[dict]:
    hits = []
    if RULES["cycle"]["enabled"]:
        hits += cycles(conn)
    for kind in ("fan_in", "fan_out"):
        if RULES[kind]["enabled"]:
            hits += fans(conn, kind)
    return hits


def subgraph(conn, transfer_ids: list[int]) -> list[dict]:
    """The transfers behind a case, as evidence for the case view."""
    res = conn.execute("MATCH (a:Account)-[t:SENT]->(b:Account) WHERE list_contains($ids, t.tid) "
                       "RETURN t.tid AS tid, a.id AS src, b.id AS dst, t.ts AS ts, t.amount AS amount_usd, t.format AS format "
                       "ORDER BY t.ts", {"ids": [int(x) for x in transfer_ids]}).get_as_df()
    res["ts"] = res["ts"].astype(str)
    return res.to_dict(orient="records")


if __name__ == "__main__":
    import time
    t0 = time.perf_counter()
    conn = connect(rebuild=True)
    print("loaded in", round(time.perf_counter() - t0, 1), "s:",
          conn.execute("MATCH (a:Account) RETURN count(a)").get_next()[0], "accounts,",
          conn.execute("MATCH ()-[t:SENT]->() RETURN count(t)").get_next()[0], "transfers")
    t0 = time.perf_counter()
    hits = detect(conn)
    print(len(hits), "hits in", round(time.perf_counter() - t0, 1), "s")
    print(pd.Series([h["pattern"] for h in hits]).value_counts())
    _ = datetime
