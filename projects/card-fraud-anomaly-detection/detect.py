"""
Card Fraud Detection — anomaly detection vs supervised machine learning

Data: 284,807 real card transactions by European cardholders over two days in September 2013
(492 frauds, 0.17%). Features V1-V28 are anonymised PCA components, plus Time and Amount.
Source: OpenML data set 1597 (originally ULB Machine Learning Group, via Kaggle).

Realistic set-up: train on the first 70% of the timeline, test on the last 30%.
Models compared on the same test set
  * Rule baseline: flag the largest transactions
  * Isolation Forest (unsupervised, no fraud labels needed)
  * Local Outlier Factor (unsupervised, trained on normal transactions only)
  * Autoencoder (neural network that learns to rebuild normal transactions; high error = suspicious)
  * Gradient boosting (supervised, learns from labelled frauds)
Metrics that matter for a fraud team with limited analysts:
  * PR AUC (average precision), recall and precision when reviewing the top 0.1% / 0.5% / 1% of transactions,
    share of fraud value caught
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score
from sklearn.neighbors import LocalOutlierFactor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)
SEED = 7
BUDGETS = [0.001, 0.005, 0.01]   # share of transactions an analyst team can review


def load():
    from sklearn.datasets import fetch_openml
    d = fetch_openml(data_id=1597, as_frame=True, parser="auto").frame
    canon = {c.lower(): c for c in [f"V{i}" for i in range(1, 29)] + ["Time", "Amount", "Class"]}
    d = d.rename(columns={c: canon.get(c.lower(), c) for c in d.columns})
    print("columns:", list(d.columns)[:5], "...", list(d.columns)[-3:], d.shape)
    d["Class"] = d["Class"].astype(str).str.strip("'\"").astype(float).astype(int)
    d.attrs["real_time"] = "Time" in d
    if "Time" not in d:  # this copy has no Time column; the source file is already in time order
        d["Time"] = np.arange(len(d), dtype=float)
    out = d.sort_values("Time", kind="stable").reset_index(drop=True)
    out.attrs = d.attrs
    return out


def budget_metrics(y, score, amount):
    out = {}
    order = np.argsort(-score)
    for b in BUDGETS:
        k = max(1, int(len(y) * b))
        top = order[:k]
        out[f"top {b * 100:g}%"] = {
            "alerts": k, "frauds_caught": int(y[top].sum()),
            "recall_%": round(y[top].sum() / y.sum() * 100, 1), "precision_%": round(y[top].mean() * 100, 1),
            "fraud_value_caught_%": round(amount[top][y[top] == 1].sum() / amount[y == 1].sum() * 100, 1)}
    return out


def main():
    d = load()
    feats = [f"V{i}" for i in range(1, 29)] + ["Amount"]
    X = d[feats].copy()
    X["Amount"] = np.log1p(X["Amount"])
    if d.attrs.get("real_time", True):
        X["hour"] = (d["Time"] // 3600) % 24
    y, amount = d["Class"].values, d["Amount"].values
    cut = int(len(d) * 0.7)
    Xtr, Xte, ytr, yte, amt_te = X.iloc[:cut], X.iloc[cut:], y[:cut], y[cut:], amount[cut:]
    sc = StandardScaler().fit(Xtr[ytr == 0])
    Ztr, Zte = sc.transform(Xtr), sc.transform(Xte)
    normal = Ztr[ytr == 0]
    rng = np.random.default_rng(SEED)

    scores = {}
    scores["Rule: largest amounts"] = amt_te.astype(float)

    iso = IsolationForest(n_estimators=300, max_samples=4096, contamination="auto", random_state=SEED, n_jobs=-1).fit(Ztr)
    scores["Isolation Forest"] = -iso.score_samples(Zte)

    lof_train = normal[rng.choice(len(normal), min(40000, len(normal)), replace=False)]
    lof = LocalOutlierFactor(n_neighbors=35, novelty=True, n_jobs=-1).fit(lof_train)
    scores["Local Outlier Factor"] = -lof.score_samples(Zte)

    ae_train = normal[rng.choice(len(normal), min(60000, len(normal)), replace=False)]
    ae = MLPRegressor(hidden_layer_sizes=(20, 8, 20), activation="tanh", max_iter=60, early_stopping=True,
                      random_state=SEED).fit(ae_train, ae_train)
    scores["Autoencoder"] = ((ae.predict(Zte) - Zte) ** 2).mean(axis=1)

    gb = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0,
                                        class_weight={0: 1, 1: 20}, random_state=SEED).fit(Xtr, ytr)
    scores["Gradient boosting (supervised)"] = gb.predict_proba(Xte)[:, 1]

    results = []
    for name, s in scores.items():
        results.append({"model": name, "type": "supervised" if "supervised" in name else ("rule" if name.startswith("Rule") else "unsupervised"),
                        "roc_auc": round(roc_auc_score(yte, s), 3), "pr_auc": round(average_precision_score(yte, s), 3),
                        **{f"recall@{k}": v["recall_%"] for k, v in budget_metrics(yte, s, amt_te).items()},
                        "budget_detail": budget_metrics(yte, s, amt_te)})
        print(name, results[-1]["roc_auc"], results[-1]["pr_auc"])
    res = pd.DataFrame(results)

    # Hybrid: score = higher percentile rank of the supervised model and the Isolation Forest (catches known and new patterns)
    rank = lambda s: pd.Series(s).rank(pct=True).values
    hybrid = np.maximum(rank(scores["Gradient boosting (supervised)"]), rank(scores["Isolation Forest"]))
    hy = budget_metrics(yte, hybrid, amt_te)
    best_unsup = res[res["type"] == "unsupervised"].sort_values("pr_auc", ascending=False).iloc[0]

    summary = {
        "data": f"{len(d):,} card transactions, {int(y.sum())} frauds ({y.mean() * 100:.3f}%), OpenML 1597",
        "split": {"train_transactions": cut, "test_transactions": int(len(yte)), "test_frauds": int(yte.sum()),
                  "method": "first 70% of the timeline for training, last 30% for testing"},
        "results": res.drop(columns="budget_detail").to_dict(orient="records"),
        "budget_detail": {r["model"]: r["budget_detail"] for r in results},
        "best_unsupervised": best_unsup["model"], "hybrid_gb_or_iforest": hy,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    res.drop(columns="budget_detail").to_csv(OUT / "model_comparison.csv", index=False)
    charts(yte, scores, res, amt_te)
    md = ["# Card Fraud Detection — Results", "", summary["data"] + ".", "",
          f"Test set: last 30% of the timeline, {summary['split']['test_transactions']:,} transactions with {summary['split']['test_frauds']} frauds.", "",
          res.drop(columns="budget_detail").to_markdown(index=False), "",
          "![PR curves](chart_pr_budget.png)", "", "_recall@top 0.5% = share of frauds caught when analysts review the 0.5% highest-scored transactions._"]
    (OUT / "REPORT.md").write_text("\n".join(md))
    print(json.dumps({k: v for k, v in summary.items() if k != "budget_detail"}, indent=2, default=float))


def charts(y, scores, res, amt):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = ["#9e9e9e", "#0ea5e9", "#22c55e", "#f59e0b", "#7c3aed"]
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.8))
    for (name, s), c in zip(scores.items(), colors):
        p, r, _ = precision_recall_curve(y, s)
        ax[0].plot(r, p, color=c, lw=1.5, label=f"{name} (PR AUC {average_precision_score(y, s):.2f})")
    ax[0].set_xlabel("Recall (share of frauds caught)"); ax[0].set_ylabel("Precision (share of alerts that are fraud)")
    ax[0].set_title("Precision-recall curves, test set"); ax[0].legend(frameon=False, fontsize=8)
    budgets = [f"top {b * 100:g}%" for b in BUDGETS]
    x = np.arange(len(budgets))
    w = 0.8 / len(res)
    for k, (_, r) in enumerate(res.iterrows()):
        vals = [r[f"recall@{b}"] for b in budgets]
        ax[1].bar(x + k * w - 0.4 + w / 2, vals, w, color=colors[k], label=r["model"])
    ax[1].set_xticks(x, [f"Review {b.split()[1]}\nof transactions" for b in budgets])
    ax[1].set_ylabel("% of frauds caught"); ax[1].set_title("Frauds caught for a given review budget")
    ax[1].legend(frameon=False, fontsize=7)
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "chart_pr_budget.png", dpi=150); plt.close(fig)


if __name__ == "__main__":
    main()
