"""
End-to-end run: prepare the transfers, load the graph, find patterns, open cases in PostgreSQL, and evaluate.

  python run.py            (needs DATABASE_URL, e.g. postgresql://postgres:postgres@localhost:5432/aml)

Evaluation uses the "Is Laundering" labels and the patterns file:
  - coverage: how many labelled laundering transfers end up inside a case, overall and for each of the 8 patterns
  - case precision: how many cases contain at least one laundering transfer
  - the same numbers for a naive rule set (no amount floor, no payroll cap), to show what the refinements buy

Outputs: outputs/coverage_by_pattern.csv, outputs/rules_comparison.csv, outputs/cases.csv, outputs/evaluation.json,
outputs/case_*.png (the subgraph of three example cases).
"""
import copy
import json
import os
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import prepare  # noqa: E402
from cases.manager import merge_hits, save  # noqa: E402
from graph import kuzu_graph as g  # noqa: E402

OUT = HERE / "outputs"
OUT.mkdir(exist_ok=True)
PATTERNS = ["fan_out", "fan_in", "gather_scatter", "scatter_gather", "cycle", "random", "bipartite", "stack"]


def evaluate(cases, t, pat, label):
    in_case = set(tid for c in cases for tid in c["transfers"])
    laund = set(t.loc[t.is_laundering == 1, "transfer_id"])
    rows = []
    for p in PATTERNS:
        ids = set(pat.loc[pat.pattern == p, "row"])
        rows.append({"pattern": p, "attempts": pat.loc[pat.pattern == p, "attempt_id"].nunique(),
                     "laundering_transfers": len(ids), "in_a_case": len(ids & in_case),
                     "coverage_pct": round(100 * len(ids & in_case) / len(ids), 1)})
    attempts_hit = pat[pat.row.isin(in_case)].attempt_id.nunique()
    true_cases = sum(1 for c in cases if set(c["transfers"]) & laund)
    summary = {"rules": label, "cases": len(cases), "cases_with_laundering": true_cases,
               "case_precision_pct": round(100 * true_cases / len(cases), 1) if cases else 0,
               "transfers_in_cases": len(in_case),
               "laundering_in_cases": len(laund & in_case),
               "coverage_pct": round(100 * len(laund & in_case) / len(laund), 1),
               "attempts_touched": f"{attempts_hit} of {pat.attempt_id.nunique()}"}
    return pd.DataFrame(rows), summary


def draw(case, conn, path, title):
    edges = g.subgraph(conn, case["transfers"])
    G = nx.MultiDiGraph()
    for e in edges:
        G.add_edge(e["src"], e["dst"], amount=e["amount_usd"])
    hub = max(G, key=G.degree)
    if "cycle" in case["patterns"] or G.degree(hub) < 4:
        pos = nx.circular_layout(G)
    else:                                   # senders on the left, the hub in the middle, receivers on the right
        ins = sorted({u for u, _ in G.in_edges(hub)} - {hub})
        outs = sorted({v for _, v in G.out_edges(hub)} - {hub} - set(ins))
        pos = {hub: (0, 0)}
        pos.update({n: (-1, (len(ins) - 1) / 2 - k) for k, n in enumerate(ins)})
        pos.update({n: (1, (len(outs) - 1) / 2 - k) for k, n in enumerate(outs)})
        rest = [n for n in G if n not in pos]
        pos.update({n: (0, 1.5 + k) for k, n in enumerate(rest)})
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    nx.draw_networkx_nodes(G, pos, node_color=["#C0392B" if n == hub else "#1F3B73" for n in G], node_size=520, ax=ax)
    nx.draw_networkx_edges(G, pos, edge_color="#C0392B", arrows=True, arrowsize=14, connectionstyle="arc3,rad=0.08",
                           min_target_margin=12, ax=ax)
    nx.draw_networkx_labels(G, pos, labels={n: n.split("_")[1][:4] for n in G}, font_size=7, font_color="white", ax=ax)
    ax.set_title(title, fontsize=10)
    ax.axis("off")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    dsn = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aml")
    prepare.main()
    t0 = time.perf_counter()
    conn = g.connect(rebuild=True)
    load_s = time.perf_counter() - t0
    t = pd.read_csv(HERE / "data" / "transfers.csv")
    pat = pd.read_csv(HERE / "data" / "HI-Small-style_Patterns.csv")

    t0 = time.perf_counter()
    hits = g.detect(conn)
    detect_s = time.perf_counter() - t0
    cases = merge_hits(hits)
    n = save(dsn, cases, lambda ids: g.subgraph(conn, ids))
    cov, summary = evaluate(cases, t, pat, "Refined (config/rules.json)")

    base = copy.deepcopy(g.RULES)
    g.RULES["fan_in"]["min_amount_usd"] = 0
    g.RULES["fan_out"].update({"min_amount_usd": 0, "max_receivers": 10**9})
    g.RULES["cycle"].update({"min_amount_usd": 0, "max_amount_drift": 10.0})
    naive_cases = merge_hits(g.detect(conn))
    _, naive = evaluate(naive_cases, t, pat, "Naive (no amount floor, no payroll cap, any amounts)")
    g.RULES.update(base)

    cov.to_csv(OUT / "coverage_by_pattern.csv", index=False)
    pd.DataFrame([summary, naive]).to_csv(OUT / "rules_comparison.csv", index=False)
    laund = set(t.loc[t.is_laundering == 1, "transfer_id"])
    pd.DataFrame([{"case": i + 1, "patterns": c["patterns"], "detail": c["detail"], "accounts": len(c["accounts"]),
                   "transfers": len(c["transfers"]), "laundering_transfers": len(set(c["transfers"]) & laund)}
                  for i, c in enumerate(cases)]).to_csv(OUT / "cases.csv", index=False)

    examples = {}
    for c in cases:
        for key in ("cycle", "fan_in + fan_out", "fan_out"):
            if c["patterns"] == key and key not in examples and set(c["transfers"]) & laund:
                examples[key] = c
    for key, c in examples.items():
        draw(c, conn, OUT / f"case_{key.replace(' + ', '_and_')}.png", f"Case: {c['patterns']} · {c['detail']}")

    result = {**summary, "graph_load_seconds": round(load_s, 1), "detection_seconds": round(detect_s, 1),
              "hits": len(hits), "cases_saved": n, "naive": naive, "coverage_by_pattern": cov.to_dict(orient="records")}
    (OUT / "evaluation.json").write_text(json.dumps(result, indent=2))
    print(cov.to_string(index=False))
    print(pd.DataFrame([summary, naive]).to_string(index=False))


if __name__ == "__main__":
    main()
