"""
Step 4 (optional): export the network for Neo4j, a graph database.

Investigators often explore suspicious networks in Neo4j, where a query like
"show every loop of 4-6 accounts that moved over ₹1 lakh" is one line.
This script writes CSV files plus a Cypher script that loads them.

Run:  python export_neo4j.py   -> neo4j/accounts.csv, neo4j/transfers.csv
Then in Neo4j Desktop: copy both CSVs into the database's import folder and
run neo4j/load_and_query.cypher.
"""

from pathlib import Path

import pandas as pd

out = Path("neo4j")
out.mkdir(exist_ok=True)
acc = pd.read_csv("data/accounts.csv")
feat = pd.read_csv("outputs/account_features.csv")[["account_id", "rule_score"]]
acc = acc.merge(feat, on="account_id", how="left").fillna({"rule_score": 0})
acc[["account_id", "kind", "opened", "rule_score"]].to_csv(out / "accounts.csv", index=False)

tx = pd.read_csv("data/transactions.csv")
flows = tx.groupby(["src", "dst"]).agg(total=("amount", "sum"), count=("amount", "size"),
                                       first=("timestamp", "min"), last=("timestamp", "max")).reset_index()
flows.round(2).to_csv(out / "transfers.csv", index=False)
print(f"Wrote {len(acc):,} accounts and {len(flows):,} aggregated transfers to neo4j/")
