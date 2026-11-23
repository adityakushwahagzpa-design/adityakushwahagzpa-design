"""
Loads data/accounts.csv and data/transfers.csv into a Neo4j 5 server, in batches.

  NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=... python neo4j/load_neo4j.py

The uniqueness constraint is created first, so each MERGE finds its account through the index;
without it every MERGE scans all accounts and loading slows to a crawl. Run prepare.py first.
"""
import os
from pathlib import Path

import pandas as pd
from neo4j import GraphDatabase

ROOT = Path(__file__).resolve().parents[1]
BATCH = 10_000


def main():
    drv = GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
                               auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))
    acc = pd.read_csv(ROOT / "data" / "accounts.csv")
    tx = pd.read_csv(ROOT / "data" / "transfers.csv")
    with drv.session() as s:
        s.run("CREATE CONSTRAINT account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE")
        for i in range(0, len(acc), BATCH):
            s.run("UNWIND $rows AS r MERGE (a:Account {id: r.id}) SET a.bank = r.bank",
                  rows=acc.iloc[i:i + BATCH].astype(str).to_dict("records"))
        for i in range(0, len(tx), BATCH):
            rows = tx.iloc[i:i + BATCH][["transfer_id", "src", "dst", "ts", "amount_usd", "cur_paid", "format"]].to_dict("records")
            s.run("""UNWIND $rows AS r
                     MATCH (a:Account {id: r.src}), (b:Account {id: r.dst})
                     CREATE (a)-[:SENT {tid: r.transfer_id, ts: datetime(r.ts), amount: r.amount_usd,
                                        currency: r.cur_paid, format: r.format}]->(b)""", rows=rows)
            print(f"{min(i + BATCH, len(tx)):,} / {len(tx):,} transfers")
    drv.close()


if __name__ == "__main__":
    main()
