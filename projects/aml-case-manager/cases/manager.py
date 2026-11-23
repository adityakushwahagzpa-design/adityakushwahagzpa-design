"""
Turns pattern hits from the graph into cases in PostgreSQL.

  - Hits that share a transfer, or a fan-in and a fan-out on the same hub account, are merged into one case
    (a gather-scatter hub shows up as both, but it is one case for an investigator).
  - Each case stores its accounts, its transfers and the subgraph as evidence, with status 'open'.
  - set_status() moves a case to 'under review' or 'closed' and logs the change.

A case is a reason to look closer, not a finding that anyone laundered money.
"""
from __future__ import annotations

import json
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

HERE = Path(__file__).resolve().parent


def merge_hits(hits: list[dict]) -> list[dict]:
    """Union-find over hits: two hits belong to one case if they share a transfer, or if they are fan-in and fan-out
    hits centred on the same account (money gathered into one account and then spread out again)."""
    parent = list(range(len(hits)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner = {}
    for i, h in enumerate(hits):
        keys = list(h["transfers"])
        if h["pattern"] in ("fan_in", "fan_out"):
            keys.append(("hub", h["accounts"][0]))
        for k in keys:
            if k in owner:
                parent[find(i)] = find(owner[k])
            else:
                owner[k] = i
    groups: dict[int, list[dict]] = {}
    for i, h in enumerate(hits):
        groups.setdefault(find(i), []).append(h)
    cases = []
    for group in groups.values():
        transfers = sorted({t for h in group for t in h["transfers"]})
        accounts = list(dict.fromkeys(a for h in group for a in h["accounts"]))
        cases.append({"patterns": " + ".join(sorted({h["pattern"] for h in group})),
                      "detail": "; ".join(dict.fromkeys(h["detail"] for h in group)),
                      "accounts": accounts, "transfers": transfers,
                      "first_ts": min(h["first_ts"] for h in group)})
    return sorted(cases, key=lambda c: c["first_ts"])


def save(dsn: str, cases: list[dict], subgraph) -> int:
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute((HERE / "schema.sql").read_text())
        for c in cases:
            edges = subgraph(c["transfers"])
            first = min(e["ts"] for e in edges)
            cur.execute("""INSERT INTO cases (patterns, opened_for, detail, accounts, n_accounts, n_transfers, total_usd, evidence)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING case_id""",
                        (c["patterns"], first, c["detail"], c["accounts"], len(c["accounts"]), len(edges),
                         round(sum(e["amount_usd"] for e in edges), 2), json.dumps(edges)))
            case_id = cur.fetchone()[0]
            execute_values(cur, "INSERT INTO case_transfers VALUES %s", [(case_id, int(t)) for t in c["transfers"]])
            cur.execute("INSERT INTO case_events (case_id, to_status, note) VALUES (%s, 'open', 'opened by pattern rules')", (case_id,))
    conn.close()
    return len(cases)


def set_status(dsn: str, case_id: int, status: str, note: str = "") -> None:
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SELECT status FROM cases WHERE case_id = %s", (case_id,))
        old = cur.fetchone()
        if old is None:
            raise KeyError(f"case {case_id} not found")
        cur.execute("UPDATE cases SET status = %s WHERE case_id = %s", (status, case_id))
        cur.execute("INSERT INTO case_events (case_id, from_status, to_status, note) VALUES (%s, %s, %s, %s)",
                    (case_id, old[0], status, note))
    conn.close()
