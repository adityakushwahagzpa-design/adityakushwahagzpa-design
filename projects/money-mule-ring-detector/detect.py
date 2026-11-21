"""
Step 2: find mule rings by looking at the NETWORK, not single transactions.

A single ₹20,000 transfer looks normal. What gives a mule away is its place
in the network: money arrives from many strangers and leaves within hours,
or money goes round in a circle. This script:

  1. Builds a directed graph: accounts are nodes, money flows are edges.
  2. Computes network features per account (pass-through ratio, how fast
     money leaves, number of counterparties, account age, cycles, PageRank).
  3. Scores each account with transparent AML rules.
  4. Keeps only fast pass-through money flows and groups the accounts they
     connect into candidate rings (community detection).
  5. Trains a simple ML model on the features and compares it with the rules.
  6. Measures everything against the known labels.

Run:  python detect.py   (after generate_data.py)
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

OUT = Path("outputs")
OUT.mkdir(exist_ok=True)

acc = pd.read_csv("data/accounts.csv", parse_dates=["opened"])
tx = pd.read_csv("data/transactions.csv", parse_dates=["timestamp"])
START = tx["timestamp"].min().normalize()

# ------------------------------------------------------------------
# 1. The money-flow graph
# ------------------------------------------------------------------
G = nx.DiGraph()
for r in tx.itertuples():
    if G.has_edge(r.src, r.dst):
        G[r.src][r.dst]["amount"] += r.amount
        G[r.src][r.dst]["count"] += 1
    else:
        G.add_edge(r.src, r.dst, amount=r.amount, count=1)

# ------------------------------------------------------------------
# 2. Network features per account
# ------------------------------------------------------------------
inflow = tx.groupby("dst")["amount"].sum()
outflow = tx.groupby("src")["amount"].sum()
pagerank = nx.pagerank(G, weight="amount")


def speed_of_exit(account):
    """Share of money received that leaves again within 24 hours."""
    ins = tx[tx["dst"] == account][["timestamp", "amount"]]
    outs = tx[tx["src"] == account]["timestamp"].sort_values().values
    if ins.empty or len(outs) == 0:
        return 0.0
    fast = 0.0
    for t, amt in ins.itertuples(index=False):
        later = outs[outs >= np.datetime64(t)]
        if len(later) and (later[0] - np.datetime64(t)) <= np.timedelta64(24, "h"):
            fast += amt
    return fast / ins["amount"].sum()


customers = acc[acc["kind"] == "customer"].set_index("account_id")
rows = []
for a in customers.index:
    i, o = inflow.get(a, 0.0), outflow.get(a, 0.0)
    out_tx = tx[tx["src"] == a]
    rows.append({
        "account_id": a,
        "in_degree": G.in_degree(a) if a in G else 0,
        "out_degree": G.out_degree(a) if a in G else 0,
        "pass_through": min(i, o) / max(i, o) if max(i, o) > 0 else 0.0,
        "exit_24h_share": speed_of_exit(a),
        "night_share": (out_tx["timestamp"].dt.hour.isin([23, 0, 1, 2, 3])).mean() if len(out_tx) else 0.0,
        "account_age_days": (START - customers.loc[a, "opened"]).days,
        "merchant_spend_share": out_tx[out_tx["dst"].str.startswith("M")]["amount"].sum() / o if o else 0.0,
        "pagerank": pagerank.get(a, 0.0),
        "is_mule": customers.loc[a, "is_mule"],
        "ring_id": customers.loc[a, "ring_id"],
    })
feat = pd.DataFrame(rows)

# Accounts that sit on a short cycle of large transfers (round-tripping)
big = nx.DiGraph([(u, v) for u, v, d in G.edges(data=True) if d["amount"] > 100000])
in_cycle = {n for c in nx.simple_cycles(big, length_bound=6) for n in c}
feat["in_cycle"] = feat["account_id"].isin(in_cycle).astype(int)

# ------------------------------------------------------------------
# 3. Transparent rule score (0-100)
# ------------------------------------------------------------------
feat["rule_score"] = (
    30 * (feat["pass_through"] > 0.9)
    + 25 * (feat["exit_24h_share"] > 0.6)
    + 15 * (feat["account_age_days"] < 90)
    + 10 * (feat["merchant_spend_share"] < 0.05)
    + 10 * (feat["night_share"] > 0.3)
    + 10 * feat["in_cycle"]
)
feat["rule_flag"] = (feat["rule_score"] >= 60).astype(int)

# ------------------------------------------------------------------
# 4. Ring discovery: fast pass-through flows -> communities
# ------------------------------------------------------------------
flagged = set(feat.loc[feat["rule_flag"] == 1, "account_id"])
H = nx.Graph(G.subgraph(flagged))  # flows among flagged accounts only
rings = []
if H.number_of_edges():
    comms = nx.community.louvain_communities(H, weight="amount", seed=7)
    for k, c in enumerate(sorted(comms, key=len, reverse=True)):
        if len(c) < 3:
            continue
        sub = G.subgraph(c)
        rings.append({"ring": f"D{k + 1:02d}", "accounts": len(c),
                      "money_moved": round(sum(d["amount"] for _, _, d in sub.edges(data=True))),
                      "members": " ".join(sorted(c)),
                      "true_ring_ids": " ".join(sorted(set(feat.set_index("account_id").loc[list(c), "ring_id"].astype(str)) - {"", "nan"}))})
rings_df = pd.DataFrame(rings)
rings_df.to_csv(OUT / "detected_rings.csv", index=False)

# ------------------------------------------------------------------
# 5. ML model on the same features (logistic regression)
# ------------------------------------------------------------------
X_cols = ["in_degree", "out_degree", "pass_through", "exit_24h_share", "night_share",
          "account_age_days", "merchant_spend_share", "pagerank", "in_cycle"]
X, y = feat[X_cols].values, feat["is_mule"].values
X_tr, X_te, y_tr, y_te, idx_tr, idx_te = train_test_split(X, y, feat.index, test_size=0.4, stratify=y, random_state=1)
scaler = StandardScaler().fit(X_tr)
lr = LogisticRegression(class_weight="balanced", max_iter=2000).fit(scaler.transform(X_tr), y_tr)
prob = lr.predict_proba(scaler.transform(X_te))[:, 1]
pred = (prob >= 0.5).astype(int)


def scores(y_true, y_pred, p=None):
    s = {"precision": round(precision_score(y_true, y_pred, zero_division=0), 3),
         "recall": round(recall_score(y_true, y_pred, zero_division=0), 3),
         "f1": round(f1_score(y_true, y_pred, zero_division=0), 3)}
    if p is not None:
        s["roc_auc"] = round(roc_auc_score(y_true, p), 3)
    return s


rule_te = feat.loc[idx_te, "rule_flag"].values
true_rings = feat.loc[feat["is_mule"] == 1, "ring_id"].nunique()
found = set(" ".join(rings_df["true_ring_ids"]).split()) if len(rings_df) else set()
metrics = {
    "accounts_scored": int(len(feat)), "true_mules": int(y.sum()), "true_rings": int(true_rings),
    "rules_on_test_set": scores(y_te, rule_te),
    "logistic_regression_on_test_set": scores(y_te, pred, prob),
    "rings_detected": int(len(rings_df)), "true_rings_found": len(found),
    "feature_weights": dict(sorted(zip(X_cols, np.round(lr.coef_[0], 2).tolist()), key=lambda kv: -abs(kv[1]))),
}
(OUT / "metrics.json").write_text(json.dumps(metrics, indent=2))
feat.to_csv(OUT / "account_features.csv", index=False)
print(json.dumps(metrics, indent=2))

# ------------------------------------------------------------------
# 6. Picture of the detected rings
# ------------------------------------------------------------------
show = rings_df.head(6)
fig, axes = plt.subplots(2, 3, figsize=(15, 9))
for ax, (_, r) in zip(axes.flat, show.iterrows()):
    members = r["members"].split()
    nbrs = {n for m in members for n in list(G.predecessors(m))[:12]}  # a few senders for context
    sub = G.subgraph(set(members) | nbrs)
    pos = nx.spring_layout(sub, seed=3, k=0.9)
    colours = ["#7c3aed" if n in members else "#cbd5e1" for n in sub]
    nx.draw_networkx(sub, pos, ax=ax, node_color=colours, node_size=[260 if n in members else 90 for n in sub],
                     with_labels=False, arrows=True, arrowsize=8, edge_color="#94a3b8", width=0.7)
    ax.set_title(f"{r['ring']}: {r['accounts']} accounts, ₹{r['money_moved'] / 1e5:,.1f} lakh moved", fontsize=11)
    ax.axis("off")
for ax in list(axes.flat)[len(show):]:
    ax.axis("off")
fig.suptitle("Detected mule rings (purple = flagged ring members, grey = accounts paying into them)", fontsize=13)
fig.tight_layout()
fig.savefig(OUT / "detected_rings.png", dpi=130)
print(f"Saved {len(rings_df)} rings to outputs/")
