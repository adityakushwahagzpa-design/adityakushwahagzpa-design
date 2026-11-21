"""
Credit Default Prediction (machine learning)

Predicts whether a credit card borrower will default next month, using the public
"Default of Credit Card Clients" data set (30,000 borrowers, Taiwan, UCI / OpenML).

Steps
  1. Feature building: credit utilisation, repayment ratio, months in arrears, worst delay, bill trend
  2. Three models: logistic regression (scorecard style), random forest, gradient boosting
  3. Credit-risk metrics on a held-out test set: ROC AUC, Gini, KS, Brier score
  4. A 300-900 credit score with risk bands and default rate per band
  5. A cost-based approval cut-off: a missed defaulter costs 5x a wrongly declined good customer
Sex and marital status are left out of the model on fairness grounds.
"""
import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)
SEED = 42
COST_FN, COST_FP = 5.0, 1.0   # missed defaulter vs declined good customer
COLS = (["LIMIT_BAL", "SEX", "EDUCATION", "MARRIAGE", "AGE"] + [f"PAY_{i}" for i in (0, 2, 3, 4, 5, 6)]
        + [f"BILL_AMT{i}" for i in range(1, 7)] + [f"PAY_AMT{i}" for i in range(1, 7)])


# ------------------------------------------------------------------ data
def load():
    try:
        from sklearn.datasets import fetch_openml
        d = fetch_openml(data_id=42477, as_frame=True, parser="auto").frame
        y = d.iloc[:, -1].astype(int)
        X = d.iloc[:, :-1].astype(float)
        X.columns = COLS
        src = "OpenML 42477"
    except Exception as e:
        print(f"OpenML failed ({e}); trying UCI")
        import requests
        z = zipfile.ZipFile(io.BytesIO(requests.get(
            "https://archive.ics.uci.edu/static/public/350/default+of+credit+card+clients.zip", timeout=120).content))
        d = pd.read_excel(z.open([n for n in z.namelist() if n.endswith(".xls")][0]), header=1)
        y = d.iloc[:, -1].astype(int)
        X = d[COLS].astype(float)
        src = "UCI 350"
    return X, y, src


def features(X):
    f = pd.DataFrame(index=X.index)
    pay = X[[f"PAY_{i}" for i in (0, 2, 3, 4, 5, 6)]]
    bill = X[[f"BILL_AMT{i}" for i in range(1, 7)]]
    paid = X[[f"PAY_AMT{i}" for i in range(1, 7)]]
    lim = X["LIMIT_BAL"].replace(0, np.nan)
    f["credit_limit"] = X["LIMIT_BAL"]
    f["age"] = X["AGE"]
    f["education"] = X["EDUCATION"].where(X["EDUCATION"].isin([1, 2, 3]), 4)  # 4 = other/unknown
    f["latest_delay_months"] = pay["PAY_0"].clip(lower=0)
    f["worst_delay_months"] = pay.clip(lower=0).max(axis=1)
    f["months_in_arrears"] = (pay > 0).sum(axis=1)
    f["utilisation_latest"] = (bill["BILL_AMT1"] / lim).clip(-1, 3)
    f["utilisation_avg_6m"] = (bill.mean(axis=1) / lim).clip(-1, 3)
    # share of last month's bill paid this month (BILL_AMT2 is paid by PAY_AMT1)
    f["repayment_ratio_latest"] = (paid["PAY_AMT1"] / bill["BILL_AMT2"].where(bill["BILL_AMT2"] > 0)).clip(0, 2).fillna(1)
    f["repayment_ratio_avg"] = (paid.sum(axis=1) / bill.clip(lower=0).sum(axis=1).replace(0, np.nan)).clip(0, 2).fillna(1)
    f["bill_trend"] = ((bill["BILL_AMT1"] - bill["BILL_AMT6"]) / lim).clip(-3, 3)
    f["months_no_payment"] = (paid == 0).sum(axis=1)
    return f.fillna(0)


# ------------------------------------------------------------------ metrics
def ks_stat(y, p):
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.max(tpr - fpr))


def evaluate(name, y, p):
    auc = roc_auc_score(y, p)
    return {"model": name, "roc_auc": round(auc, 3), "gini": round(2 * auc - 1, 3),
            "ks": round(ks_stat(y, p), 3), "brier": round(brier_score_loss(y, p), 4)}


def best_cutoff(y, p):
    grid = np.linspace(0.05, 0.8, 76)
    costs = [COST_FN * ((p < t) & (y == 1)).sum() + COST_FP * ((p >= t) & (y == 0)).sum() for t in grid]
    t = float(grid[int(np.argmin(costs))])
    decline = p >= t
    return {"cutoff_pd": round(t, 2), "approval_rate_%": round((~decline).mean() * 100, 1),
            "defaulters_caught_%": round(decline[y == 1].mean() * 100, 1),
            "good_customers_declined_%": round(decline[y == 0].mean() * 100, 1),
            "default_rate_approved_%": round(y[~decline].mean() * 100, 2),
            "default_rate_all_%": round(y.mean() * 100, 2)}


def to_score(p, base=650, base_odds=4, pdo=50):
    """Scorecard scaling: 650 points at 4:1 good:bad odds (about the portfolio average), +50 points doubles the odds."""
    odds = (1 - p) / np.clip(p, 1e-6, None)
    return np.clip(base + pdo / np.log(2) * np.log(odds / base_odds), 300, 900).round()


# ------------------------------------------------------------------ charts
def charts(y, preds, imp, bands):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"Logistic regression": "#7c3aed", "Random forest": "#0ea5e9", "Gradient boosting": "#f59e0b"}

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
    for name, p in preds.items():
        fpr, tpr, _ = roc_curve(y, p)
        ax[0].plot(fpr, tpr, label=f"{name} (AUC {roc_auc_score(y, p):.3f})", color=colors[name])
    ax[0].plot([0, 1], [0, 1], ls="--", color="grey", lw=0.8)
    ax[0].set_xlabel("False positive rate"); ax[0].set_ylabel("True positive rate")
    ax[0].set_title("ROC curves, test set"); ax[0].legend(frameon=False, fontsize=9)
    for name, p in preds.items():
        bins = pd.qcut(p, 10, duplicates="drop")
        cal = pd.DataFrame({"p": p, "y": y}).groupby(bins, observed=True).mean()
        ax[1].plot(cal["p"], cal["y"], marker="o", color=colors[name], label=name)
    ax[1].plot([0, 1], [0, 1], ls="--", color="grey", lw=0.8)
    ax[1].set_xlabel("Predicted default probability"); ax[1].set_ylabel("Actual default rate")
    ax[1].set_title("Calibration by decile"); ax[1].legend(frameon=False, fontsize=9)
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "chart_roc_calibration.png", dpi=150); plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.8))
    i = imp.sort_values()
    ax[0].barh(i.index, i, color="#7c3aed")
    ax[0].set_title("What drives default risk (permutation importance, AUC drop)")
    ax[1].bar(bands["band"], bands["default_rate_%"], color=["#2e7d32", "#7cb342", "#fbc02d", "#ef6c00", "#c62828"])
    for k, (r, n) in enumerate(zip(bands["default_rate_%"], bands["borrowers"])):
        ax[1].text(k, r + 1, f"{r:.1f}%\n(n={n:,})", ha="center", fontsize=8)
    ax[1].set_title("Actual default rate by credit score band, test set"); ax[1].set_ylabel("Default rate %")
    ax[1].tick_params(axis="x", labelsize=8)
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "chart_drivers_bands.png", dpi=150); plt.close(fig)


# ------------------------------------------------------------------ main
def main():
    X, y, src = load()
    F = features(X)
    Xtr, Xte, ytr, yte = train_test_split(F, y, test_size=0.3, stratify=y, random_state=SEED)
    models = {
        "Logistic regression": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")),
        "Random forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=20, class_weight="balanced_subsample",
                                                n_jobs=-1, random_state=SEED),
        "Gradient boosting": HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05, max_leaf_nodes=31,
                                                            l2_regularization=1.0, random_state=SEED),
    }
    preds, results = {}, []
    for name, m in models.items():
        m.fit(Xtr, ytr)
        preds[name] = m.predict_proba(Xte)[:, 1]
        results.append(evaluate(name, yte.values, preds[name]))
        print(results[-1])
    res = pd.DataFrame(results)
    best = res.sort_values("roc_auc", ascending=False).iloc[0]["model"]
    p = preds[best]
    # Scores and the cut-off use gradient boosting: it is trained without class weights, so its
    # probabilities match real default rates (the class-weighted models overstate them).
    p_cal = preds["Gradient boosting"]

    imp = permutation_importance(models[best], Xte, yte, scoring="roc_auc", n_repeats=5, random_state=SEED, n_jobs=-1)
    imp = pd.Series(imp.importances_mean, index=F.columns).round(4).sort_values(ascending=False)

    score = to_score(p_cal)
    edges = [300, 550, 620, 680, 740, 901]
    labels = ["Very high risk\n300-549", "High\n550-619", "Medium\n620-679", "Low\n680-739", "Very low risk\n740-900"]
    band = pd.cut(score, edges, right=False, labels=labels)
    bands = (pd.DataFrame({"band": band, "y": yte.values}).groupby("band", observed=False)
             .agg(borrowers=("y", "size"), default_rate_=("y", "mean")).reset_index())
    bands["default_rate_%"] = (bands.pop("default_rate_") * 100).round(1)
    bands["band"] = bands["band"].astype(str)

    cut = best_cutoff(yte.values, p_cal)
    coef = models["Logistic regression"][-1].coef_[0]
    lr_coef = pd.Series(coef, index=F.columns).round(3).sort_values(key=abs, ascending=False)

    summary = {
        "data": f"Default of Credit Card Clients ({src}), {len(y):,} borrowers, default rate {y.mean() * 100:.1f}%",
        "train_test": [int(len(ytr)), int(len(yte))], "models": results, "best_model": best, "score_model": "Gradient boosting (unweighted, calibrated probabilities)",
        "top_drivers": imp.head(5).to_dict(), "logistic_coefficients_standardised": lr_coef.to_dict(),
        "cost_based_cutoff": cut, "score_bands": bands.astype(object).where(bands.notna(), None).to_dict(orient="records"),
        "cost_assumption": f"missed defaulter costs {COST_FN:.0f}x a declined good customer",
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float))
    res.to_csv(OUT / "model_comparison.csv", index=False)
    pd.DataFrame({"actual_default": yte.values, "pd_" + best.replace(" ", "_").lower(): p.round(4),
                  "pd_calibrated": p_cal.round(4), "credit_score": score}, index=Xte.index).to_csv(OUT / "test_set_scores.csv")
    charts(yte.values, preds, imp.head(10), bands)
    md = ["# Credit Default Prediction — Results", "", summary["data"] + ".", "", "## Model comparison (30% test set)", "",
          res.to_markdown(index=False), "", "![ROC](chart_roc_calibration.png)", "",
          "## Credit score bands", "", bands.assign(band=bands["band"].str.replace("\n", " ")).to_markdown(index=False), "",
          "## Cost-based approval cut-off", "", pd.Series(cut).to_frame("value").to_markdown(), "",
          "![Drivers](chart_drivers_bands.png)", "", "_For learning purposes only._"]
    (OUT / "REPORT.md").write_text("\n".join(md))
    print(json.dumps({k: v for k, v in summary.items() if k != "logistic_coefficients_standardised"}, indent=2, default=float))


if __name__ == "__main__":
    main()
