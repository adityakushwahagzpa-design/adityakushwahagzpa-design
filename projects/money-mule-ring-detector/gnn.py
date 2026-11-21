"""
Step 3 (optional): a graph neural network (GraphSAGE) with PyTorch Geometric.

The logistic regression in detect.py looks at each account's own features.
A graph neural network also looks at its NEIGHBOURS' features: an account
that sends money to three suspicious accounts becomes more suspicious itself.
This is how banks catch mules that look clean on their own.

Uses the same train/test split as detect.py so the results compare fairly.

Run:  python gnn.py   (after detect.py; needs torch and torch_geometric)
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.metrics import precision_score, recall_score, f1_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch_geometric.data import Data
from torch_geometric.nn import SAGEConv

torch.manual_seed(0)
feat = pd.read_csv("outputs/account_features.csv")
tx = pd.read_csv("data/transactions.csv")

X_cols = ["in_degree", "out_degree", "pass_through", "exit_24h_share", "night_share",
          "account_age_days", "merchant_spend_share", "pagerank", "in_cycle"]
idx = {a: i for i, a in enumerate(feat["account_id"])}

# Edges between scored accounts, in both directions (money links either way)
pairs = tx[tx["src"].isin(idx) & tx["dst"].isin(idx)][["src", "dst"]].drop_duplicates()
src = pairs["src"].map(idx).values
dst = pairs["dst"].map(idx).values
edge_index = torch.tensor(np.vstack([np.r_[src, dst], np.r_[dst, src]]), dtype=torch.long)

y = feat["is_mule"].values
all_idx = np.arange(len(feat))
tr, te = train_test_split(all_idx, test_size=0.4, stratify=y, random_state=1)  # same split as detect.py
scaler = StandardScaler().fit(feat.loc[tr, X_cols].values)
x = torch.tensor(scaler.transform(feat[X_cols].values), dtype=torch.float)
data = Data(x=x, edge_index=edge_index, y=torch.tensor(y, dtype=torch.long))


class SAGE(torch.nn.Module):
    def __init__(self, d_in, d_hidden=32):
        super().__init__()
        self.c1 = SAGEConv(d_in, d_hidden)
        self.c2 = SAGEConv(d_hidden, 2)

    def forward(self, x, ei):
        return self.c2(F.relu(self.c1(x, ei)), ei)


model = SAGE(x.shape[1])
opt = torch.optim.Adam(model.parameters(), lr=0.01, weight_decay=5e-4)
weight = torch.tensor([1.0, float((y == 0).sum() / max((y == 1).sum(), 1))], dtype=torch.float)  # mules are rare: weight them up
tr_t = torch.tensor(tr)
for epoch in range(300):
    model.train(); opt.zero_grad()
    loss = F.cross_entropy(model(data.x, data.edge_index)[tr_t], data.y[tr_t], weight=weight)
    loss.backward(); opt.step()

model.eval()
with torch.no_grad():
    prob = F.softmax(model(data.x, data.edge_index), dim=1)[:, 1].numpy()
p_te, y_te = prob[te], y[te]
pred = (p_te >= 0.5).astype(int)
res = {"graphsage_on_test_set": {
    "precision": round(precision_score(y_te, pred, zero_division=0), 3),
    "recall": round(recall_score(y_te, pred, zero_division=0), 3),
    "f1": round(f1_score(y_te, pred, zero_division=0), 3),
    "roc_auc": round(roc_auc_score(y_te, p_te), 3)},
    "edges": int(edge_index.shape[1] // 2), "epochs": 300}
Path("outputs/gnn_metrics.json").write_text(json.dumps(res, indent=2))
print(json.dumps(res, indent=2))
