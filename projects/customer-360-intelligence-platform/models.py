"""Intelligence layer on top of the Customer 360 table.

  Churn risk            LightGBM, P(customer leaves in the next 6 months)
  Product propensity    LightGBM per product (Fixed Deposit, Credit Card, Personal Loan, Insurance)
  Segments              K-means on behaviour, named from their profiles
  Lifetime value        5-year margin, discounted and adjusted for churn risk
  Next best action      rules combining value, risk, propensity and credit/KYC guardrails

Validation is out-of-time: train on the Sep 2025 snapshot (outcomes Oct 2025-Mar 2026), test on
the Mar 2026 snapshot (outcomes Apr-Sep 2026). The final models are refit on both snapshots and
score the current Sep 2026 view.
"""
import json
import os

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler

import features as ft

TRAIN_ASOF, TEST_ASOF, CURRENT_ASOF = "2025-09", "2026-03", "2026-09"
TARGETS = {"churn": "churn_6m", **{p: f"takes_{p.lower().replace(' ', '_')}_6m" for p in ft.PRODUCTS}}
PRODUCT_VALUE = {"Fixed Deposit": 9000, "Credit Card": 6500, "Personal Loan": 14000, "Insurance": 5000}  # Rs, yearly margin
SEG_FEATURES = ["spend_3m", "avg_balance_3m", "txn_count_3m", "digital_share", "n_products", "tenure_years", "loan_outstanding"]
DISCOUNT = 0.12


def lgbm():
    return lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=40,
                              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=3.0, verbose=-1,
                              random_state=0)


def align(X, cols):
    return X.reindex(columns=cols, fill_value=0)


def top_decile_lift(y, p):
    k = max(1, int(len(y) * 0.1))
    top = np.argsort(-p)[:k]
    return float(np.mean(np.asarray(y)[top]) / np.mean(y))


def churn_rule_baseline(f):
    """What a typical rule-based early-warning list would flag."""
    return ((f.txn_count_trend < 0.5) | (f.complaints_6m >= 2)).astype(int)


def validate(d):
    tr, te = ft.build(d, TRAIN_ASOF, True), ft.build(d, TEST_ASOF, True)
    Xtr, Xte = ft.model_matrix(tr), ft.model_matrix(te)
    Xte = align(Xte, Xtr.columns)
    res, scored = {}, te.copy()
    for name, target in TARGETS.items():
        mtr, mte = tr[target].notna(), te[target].notna()
        m = lgbm().fit(Xtr[mtr], tr.loc[mtr, target])
        p = m.predict_proba(Xte[mte])[:, 1]
        y = te.loc[mte, target]
        res[name] = {"test_customers": int(mte.sum()), "positives": int(y.sum()), "base_rate_pct": round(100 * y.mean(), 2),
                     "auc": round(roc_auc_score(y, p), 3), "avg_precision": round(average_precision_score(y, p), 3),
                     "top_decile_lift": round(top_decile_lift(y, p), 2)}
        scored.loc[mte, f"p_{name}"] = p
    # rule baseline vs model at the same list size
    flag = churn_rule_baseline(te)
    y = te.churn_6m
    k = int(flag.sum())
    top_model = scored.p_churn.rank(ascending=False, method="first") <= k
    res["churn"]["rule_baseline"] = {
        "flagged": k, "precision_pct": round(100 * y[flag == 1].mean(), 1), "recall_pct": round(100 * y[flag == 1].sum() / y.sum(), 1),
        "model_precision_same_list_size_pct": round(100 * y[top_model].mean(), 1),
        "model_recall_same_list_size_pct": round(100 * y[top_model].sum() / y.sum(), 1)}
    return res, scored


def fit_final(d):
    tr = pd.concat([ft.build(d, TRAIN_ASOF, True), ft.build(d, TEST_ASOF, True)]).reset_index(drop=True)
    X = ft.model_matrix(tr)
    models = {}
    for name, target in TARGETS.items():
        m = tr[target].notna()
        models[name] = lgbm().fit(X[m], tr.loc[m, target])
    return models, X.columns


def segment(cur, k=5, seed=0):
    Z = cur[SEG_FEATURES].copy()
    for c in ["spend_3m", "avg_balance_3m", "loan_outstanding"]:
        Z[c] = np.log1p(Z[c])
    Zs = StandardScaler().fit_transform(Z.fillna(0))
    km = KMeans(n_clusters=k, n_init=20, random_state=seed).fit(Zs)
    prof = cur.assign(cluster=km.labels_).groupby("cluster")[SEG_FEATURES].median()
    names = name_segments(prof)
    return pd.Series(km.labels_, index=cur.index).map(names), prof.rename(index=names)


def name_segments(prof):
    """Give each cluster a business name from its median profile (each name used once)."""
    names, left = {}, set(prof.index)
    rules = [
        ("Borrowers", lambda p: p.loan_outstanding),
        ("Affluent savers", lambda p: p.avg_balance_3m),
        ("Low-engagement", lambda p: -p.txn_count_3m),
        ("Newer customers", lambda p: -p.tenure_years),
    ]
    for name, score in rules:
        best = max(left, key=lambda i: score(prof.loc[i]))
        names[best] = name
        left.remove(best)
    for i in left:
        names[i] = "Everyday banking core"
    return names


def lifetime_value(cur, p_churn):
    margin = (0.025 * cur.avg_balance_3m                       # deposit spread
              + 0.004 * cur.spend_3m * 12                       # interchange and fees on spend
              + cur.fees_6m * 2                                 # service fees
              + 0.03 * cur.loan_outstanding)                    # lending margin
    annual_retention = (1 - p_churn) ** 2
    years = np.arange(1, 6)
    factor = sum((annual_retention ** t) / (1 + DISCOUNT) ** t for t in years)
    return (margin * factor).round(0), margin.round(0)


def next_best_action(cur):
    clv_hi = cur.clv_5y >= cur.clv_5y.quantile(0.7)
    churn_hi = cur.p_churn >= cur.p_churn.quantile(0.9)
    risk_block = (cur.max_days_past_due > 30) | (cur.kyc_risk == "High")
    actions, reasons, values = [], [], []
    for i, r in cur.iterrows():
        ev = {p: r[f"p_{p}"] * PRODUCT_VALUE[p] for p in ft.PRODUCTS
              if r[f"has_{p.lower().replace(' ', '_')}"] == 0 and not (risk_block[i] and p in ("Personal Loan", "Credit Card"))}
        best = max(ev, key=ev.get) if ev else None
        if churn_hi[i] and clv_hi[i]:
            actions.append("RM retention call"); reasons.append("High value and high churn risk")
            values.append(round(r.p_churn * r.clv_5y))
        elif churn_hi[i]:
            actions.append("Retention offer (fee waiver)"); reasons.append("High churn risk")
            values.append(round(r.p_churn * r.clv_5y * 0.5))
        elif r.max_days_past_due > 30:
            actions.append("Collections follow-up"); reasons.append(f"{int(r.max_days_past_due)} days past due")
            values.append(round(r.loan_outstanding * 0.02))
        elif best and r[f"p_{best}"] >= 0.08:
            actions.append(f"Offer {best}"); reasons.append(f"{r[f'p_{best}']:.0%} propensity")
            values.append(round(ev[best]))
        else:
            actions.append("Digital engagement nudge"); reasons.append("No strong signal")
            values.append(0)
    return actions, reasons, values


def score_current(d, models, cols):
    cur = ft.build(d, CURRENT_ASOF)
    X = align(ft.model_matrix(cur), cols)
    for name, m in models.items():
        cur[f"p_{name}"] = m.predict_proba(X)[:, 1].round(4)
    cur["segment_360"], prof = segment(cur)
    cur["clv_5y"], cur["annual_margin"] = lifetime_value(cur, cur.p_churn)
    cur["next_best_action"], cur["action_reason"], cur["action_value"] = next_best_action(cur)
    names = d["customers"].set_index("customer_id").full_name
    cur.insert(0, "full_name", names.reindex(cur.index))
    return cur, prof


def importance(model, cols, k=10):
    imp = pd.Series(model.booster_.feature_importance("gain"), index=cols)
    return (imp / imp.sum() * 100).sort_values(ascending=False).head(k).round(1)


def main(out="outputs"):
    os.makedirs(out, exist_ok=True)
    d = ft.load()
    val, scored_test = validate(d)
    models, cols = fit_final(d)
    cur, prof = score_current(d, models, cols)
    cur.to_csv(f"{out}/customer_360.csv")
    prof.round(2).to_csv(f"{out}/segment_profiles.csv")
    scored_test[["churn_6m", "p_churn"]].to_csv(f"{out}/churn_test_scores.csv")
    imp = {name: importance(m, cols).to_dict() for name, m in models.items()}
    seg = cur.groupby("segment_360").agg(customers=("p_churn", "size"), avg_clv=("clv_5y", "mean"),
                                         churn_risk_pct=("p_churn", lambda s: 100 * s.mean()),
                                         digital_share=("digital_share", "mean"), products=("n_products", "mean")).round(2)
    xw = pd.read_csv(f"{out}/identity_crosswalk.csv")
    summary = {
        "current_asof": CURRENT_ASOF, "customers_scored": int(len(cur)),
        "card_only_customers_found": int(xw[(xw.source == "card") & xw.golden_id.str.startswith("N")].golden_id.nunique()),
        "validation": val, "driver_importance_pct": imp,
        "segments": seg.reset_index().to_dict(orient="records"),
        "actions": cur.next_best_action.value_counts().to_dict(),
        "action_value_lakh": round(cur.action_value.sum() / 1e5, 1),
        "total_clv_crore": round(cur.clv_5y.sum() / 1e7, 2),
        "clv_at_risk_top10_churn_crore": round(cur.loc[cur.p_churn >= cur.p_churn.quantile(0.9), "clv_5y"].sum() / 1e7, 2),
    }
    json.dump(summary, open(f"{out}/platform_summary.json", "w"), indent=2, default=str)
    print(json.dumps({k: summary[k] for k in ("validation", "actions", "segments")}, indent=1, default=str))
    print(prof.round(1).to_string())
    return cur, summary


if __name__ == "__main__":
    main()
