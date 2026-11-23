from datetime import datetime, timedelta

import kuzu
import pandas as pd

import prepare
from cases.manager import merge_hits
from graph import kuzu_graph as g


def tiny_graph(tmp_path, edges):
    db = kuzu.Database(str(tmp_path / "t.kuzu"))
    conn = kuzu.Connection(db)
    conn.execute("CREATE NODE TABLE Account(id STRING, bank STRING, PRIMARY KEY (id))")
    conn.execute("CREATE REL TABLE SENT(FROM Account TO Account, tid INT64, ts TIMESTAMP, amount DOUBLE, currency STRING, format STRING)")
    for n in sorted({e[0] for e in edges} | {e[1] for e in edges}):
        conn.execute("CREATE (:Account {id: $id, bank: '1'})", {"id": n})
    t0 = datetime(2026, 9, 1, 9)
    for i, (a, b, hours, amt) in enumerate(edges):
        conn.execute("MATCH (a:Account {id: $a}), (b:Account {id: $b}) CREATE (a)-[:SENT {tid: $i, ts: $ts, amount: $amt, currency: 'US Dollar', format: 'Wire'}]->(b)",
                     {"a": a, "b": b, "i": i, "ts": t0 + timedelta(hours=hours), "amt": float(amt)})
    return conn


def test_cycle_in_time_order_is_found(tmp_path):
    conn = tiny_graph(tmp_path, [("A", "B", 0, 5000), ("B", "C", 5, 4900), ("C", "A", 9, 4800)])
    assert len(conn.execute(g._hops(3), {"min": 1000.0, "drift": 0.25}).get_as_df()) == 1


def test_cycle_out_of_time_order_is_ignored(tmp_path):
    conn = tiny_graph(tmp_path, [("A", "B", 9, 5000), ("B", "C", 5, 4900), ("C", "A", 0, 4800)])
    # money goes A->B at 09:00 but B->C at 05:00 and C->A at 00:00: whichever account you start from,
    # one hop goes back in time, so this is not money flowing around a ring
    assert conn.execute(g._hops(3), {"min": 1000.0, "drift": 0.25}).get_as_df().empty


def test_cycle_with_a_long_gap_is_ignored(tmp_path):
    conn = tiny_graph(tmp_path, [("A", "B", 0, 5000), ("B", "C", 40, 4900), ("C", "A", 45, 4800)])
    assert conn.execute(g._hops(3), {"min": 1000.0, "drift": 0.25}).get_as_df().empty


def test_cycle_where_amounts_change_a_lot_is_ignored(tmp_path):
    conn = tiny_graph(tmp_path, [("A", "B", 0, 5000), ("B", "C", 5, 900), ("C", "A", 9, 4800)])
    assert conn.execute(g._hops(3), {"min": 1000.0, "drift": 0.25}).get_as_df().empty


def test_fan_in_and_fan_out_on_one_hub_become_one_case():
    hits = [{"pattern": "fan_in", "accounts": ["H", "a", "b"], "transfers": [1, 2], "first_ts": 1, "detail": "in"},
            {"pattern": "fan_out", "accounts": ["H", "x", "y"], "transfers": [3, 4], "first_ts": 2, "detail": "out"},
            {"pattern": "cycle", "accounts": ["p", "q", "r"], "transfers": [9, 10, 11], "first_ts": 3, "detail": "c"}]
    cases = merge_hits(hits)
    assert [c["patterns"] for c in cases] == ["fan_in + fan_out", "cycle"]
    assert cases[0]["transfers"] == [1, 2, 3, 4]


def test_hits_sharing_a_transfer_are_merged():
    hits = [{"pattern": "cycle", "accounts": ["a", "b", "c"], "transfers": [1, 2, 3], "first_ts": 1, "detail": "3-hop"},
            {"pattern": "fan_in", "accounts": ["z", "a"], "transfers": [3, 7], "first_ts": 1, "detail": "fan"}]
    assert len(merge_hits(hits)) == 1


def test_prepare_builds_bank_plus_account_ids_and_usd(tmp_path, monkeypatch):
    raw = pd.DataFrame([["2026/09/01 10:00", 10, "ABC", 20, "ABC", 100.0, "Euro", 100.0, "Euro", "Wire", 0],
                        ["2026/09/01 11:00", 20, "ABC", 10, "XYZ", 50.0, "US Dollar", 50.0, "US Dollar", "ACH", 1]],
                       columns=["Timestamp", "From Bank", "Account", "To Bank", "Account", "Amount Received", "Receiving Currency",
                                "Amount Paid", "Payment Currency", "Payment Format", "Is Laundering"])
    src = tmp_path / "raw.csv"
    raw.to_csv(src, index=False)
    monkeypatch.setattr(prepare, "DATA", tmp_path)
    prepare.main(src)
    t = pd.read_csv(tmp_path / "transfers.csv")
    assert list(t.src) == ["10_ABC", "20_ABC"]          # same account number, different banks: two accounts
    assert list(t.amount_usd) == [108.0, 50.0]          # euros converted before anything is added up
    assert t.ts[0] == "2026-09-01T10:00:00"
