"""
Replays every transaction in time order through the rule engine and scores the alerts against is_fraud.

Outputs (outputs/):
  rule_performance.csv   alerts, true and false alerts, precision and recall for each rule and for any rule
  naive_vs_refined.csv   the impossible-travel rule as written in most tutorials vs with two refinements
  tuning_velocity.csv    precision and recall as the velocity threshold changes
  tuning_amount.csv      precision and recall as the z-score threshold changes
  chart_tuning.png       the precision/recall trade-off for both tunings
  recall_by_pattern.csv  share of each fraud pattern caught by each rule
  evaluation.json        headline numbers, including time per check
"""
import copy
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from monitor import RuleEngine, load_rules  # noqa: E402

HERE = Path(__file__).parent
OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)
RULES = ["velocity", "impossible_travel", "unusual_amount"]


def load():
    df = pd.read_csv(HERE / "data" / "transactions.csv.gz", dtype={"fraud_pattern": str}).sort_values("unix_time", kind="stable")
    txs = [{"card": c, "ts": t, "amount": a, "lat": la, "lon": lo, "channel": ch}
           for c, t, a, la, lo, ch in zip(df.cc_num, df.unix_time, df.amt, df.merch_lat, df.merch_long, df.channel)]
    return df, txs


def replay(txs, rules):
    eng = RuleEngine(rules)
    fired = {r: [] for r in RULES}
    start = time.perf_counter()
    for i, tx in enumerate(txs):
        for a in eng.check(tx):
            fired[a["rule"]].append(i)
    secs = time.perf_counter() - start
    return fired, secs


def score(fired, fraud):
    rows, total_fraud = [], int(fraud.sum())
    any_idx = set()
    for rule, idx in list(fired.items()) + [("any rule", None)]:
        s = set(idx) if idx is not None else any_idx
        if idx is not None:
            any_idx |= s
        tp = int(fraud[list(s)].sum()) if s else 0
        rows.append({"rule": rule, "alerts": len(s), "true_alerts": tp, "false_alerts": len(s) - tp,
                     "precision_pct": round(100 * tp / len(s), 1) if s else 0.0,
                     "recall_pct": round(100 * tp / total_fraud, 1)})
    return pd.DataFrame(rows)


def main():
    df, txs = load()
    fraud = df["is_fraud"].to_numpy()
    base = load_rules()

    fired, secs = replay(txs, base)
    perf = score(fired, fraud)
    perf.to_csv(OUT / "rule_performance.csv", index=False)
    print(perf.to_string(index=False))

    naive = copy.deepcopy(base)
    naive["impossible_travel"].update({"card_present_only": False, "min_distance_km": 0})
    only = lambda r, rule: {k: dict(v, enabled=(k == rule)) for k, v in r.items()}  # noqa: E731
    rows = []
    for label, cfg in [("Naive: every transaction, any distance", naive),
                       ("Refined: in-store only, 100 km minimum", base)]:
        f, _ = replay(txs, only(cfg, "impossible_travel"))
        r = score(f, fraud).iloc[1]
        rows.append({"version": label, **{k: r[k] for k in ["alerts", "true_alerts", "false_alerts", "precision_pct", "recall_pct"]}})
    nvr = pd.DataFrame(rows)

    pat = df["fraud_pattern"].fillna("")
    caught = {r: set(i) for r, i in fired.items()}
    caught["any rule"] = set().union(*caught.values())
    rbp = []
    for p in ["account_takeover", "cloned_card", "card_testing"]:
        idx = set(pat.index[pat == p])
        rbp.append({"pattern": p, "fraud_transactions": len(idx),
                    **{f"{r}_pct": round(100 * len(idx & c) / len(idx), 1) for r, c in caught.items()}})
    rbp = pd.DataFrame(rbp)
    rbp.to_csv(OUT / "recall_by_pattern.csv", index=False)
    print(rbp.to_string(index=False))
    nvr.to_csv(OUT / "naive_vs_refined.csv", index=False)
    print(nvr.to_string(index=False))

    tv = []
    for mx in [2, 3, 4, 5, 6, 8]:
        cfg = only(base, "velocity")
        cfg["velocity"]["max_tx_in_window"] = mx
        r = score(replay(txs, cfg)[0], fraud).iloc[0]
        tv.append({"max_tx_in_10_min": mx, "alerts": r.alerts, "precision_pct": r.precision_pct, "recall_pct": r.recall_pct})
    tv = pd.DataFrame(tv)
    tv.to_csv(OUT / "tuning_velocity.csv", index=False)

    ta = []
    for z in [2.0, 3.0, 4.0, 5.0, 6.0, 8.0]:
        cfg = only(base, "unusual_amount")
        cfg["unusual_amount"]["max_zscore"] = z
        r = score(replay(txs, cfg)[0], fraud).iloc[2]
        ta.append({"max_zscore": z, "alerts": r.alerts, "precision_pct": r.precision_pct, "recall_pct": r.recall_pct})
    ta = pd.DataFrame(ta)
    ta.to_csv(OUT / "tuning_amount.csv", index=False)
    print(tv.to_string(index=False))
    print(ta.to_string(index=False))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, d, x, title in [(axes[0], tv, "max_tx_in_10_min", "Velocity: max transactions in 10 min"),
                            (axes[1], ta, "max_zscore", "Unusual amount: z-score threshold")]:
        ax.plot(d[x], d["precision_pct"], marker="o", color="#1F6FEB", label="Precision")
        ax.plot(d[x], d["recall_pct"], marker="o", color="#D1242F", label="Recall")
        ax.set(title=title, xlabel="Threshold", ylabel="%", ylim=(0, 105))
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False)
    fig.suptitle("Raising a threshold trades recall for precision", fontsize=12, y=1.04)
    fig.savefig(OUT / "chart_tuning.png", dpi=130, bbox_inches="tight")
    plt.close(fig)

    summary = {
        "transactions": len(df), "cards": int(df.cc_num.nunique()), "fraud_transactions": int(fraud.sum()),
        "fraud_rate_pct": round(100 * fraud.mean(), 3),
        "microseconds_per_check": round(1e6 * secs / len(df), 1),
        "checks_per_second": round(len(df) / secs),
        "rules": perf.to_dict(orient="records"),
        "naive_vs_refined_travel": nvr.to_dict(orient="records"),
        "recall_by_pattern": rbp.to_dict(orient="records"),
    }
    (OUT / "evaluation.json").write_text(json.dumps(summary, indent=2, default=int))
    print(json.dumps({k: v for k, v in summary.items() if k not in ("rules", "naive_vs_refined_travel", "recall_by_pattern")}, indent=2))


if __name__ == "__main__":
    main()
