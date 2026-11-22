"""Benchmark: 30 business questions with hand-written, verified gold SQL.

A prediction counts as correct when its result matches the gold result (execution accuracy):
same number of rows, every gold column found among the predicted columns with the same values
(numbers compared to 2 decimals), row order ignored. Extra columns are allowed.

  python evaluate.py --mode baseline   # no LLM: SQL of the nearest solved example
  python evaluate.py --mode claude     # the Claude agent (needs ANTHROPIC_API_KEY)
  python evaluate.py --mode gold       # sanity check: gold vs gold must be 30/30
"""
import argparse
import json
import os
import time

import pandas as pd

import assistant
import guard


def _norm(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 2)
    return str(v).strip()


def _key(v):
    return (v is None, str(type(v)), v if v is not None else 0)


def results_match(gold_rows, pred_rows):
    """True if every gold column appears in the prediction with the same values row for row."""
    if len(gold_rows) != len(pred_rows):
        return False
    if not gold_rows:
        return True
    g = [[_norm(v) for v in r] for r in gold_rows]
    p = [[_norm(v) for v in r] for r in pred_rows]
    gcols, pcols = list(zip(*g)), list(zip(*p))
    mapping, used = [], set()
    for gc in gcols:
        target = sorted(gc, key=_key)
        hit = next((j for j, pc in enumerate(pcols) if j not in used and sorted(pc, key=_key) == target), None)
        if hit is None:
            return False
        mapping.append(hit)
        used.add(hit)
    pred_proj = sorted((tuple(r[j] for j in mapping) for r in p), key=lambda t: [_key(x) for x in t])
    gold_sorted = sorted((tuple(r) for r in g), key=lambda t: [_key(x) for x in t])
    return pred_proj == gold_sorted


def evaluate(mode, bench_path="data/benchmark.json", client=None, out_dir="outputs"):
    bench = json.load(open(bench_path))
    con = guard.connect(assistant.DB)
    retriever = assistant.ExampleRetriever()
    tools = assistant.SQLTools() if mode == "claude" else None
    rows = []
    for b in bench:
        _, gold, _ = guard.run_query(con, b["sql"])
        t0 = time.time()
        rec = {"id": b["id"], "difficulty": b["difficulty"], "question": b["question"]}
        try:
            if mode == "gold":
                sql = b["sql"]
            elif mode == "baseline":
                sql = assistant.baseline_sql(b["question"], retriever)
            else:
                res = assistant.ask(client, b["question"], tools, retriever)
                sql = res["sql"]
                rec["sql_errors_fixed"] = res.get("sql_errors", 0)
                rec["answer"] = res["answer"]
            _, pred, _ = guard.run_query(con, sql)
            rec["correct"] = results_match(gold, pred)
            rec["sql"] = sql
        except Exception as e:
            rec["correct"], rec["error"] = False, f"{type(e).__name__}: {e}"
        rec["seconds"] = round(time.time() - t0, 2)
        rows.append(rec)
        print(f"{b['id']:>2} {b['difficulty']:<6} {'OK ' if rec['correct'] else 'MISS'} {b['question'][:70]}")
    df = pd.DataFrame(rows)
    by = df.groupby("difficulty").correct.agg(["sum", "count"])
    summary = {"mode": mode, "model": assistant.MODEL if mode == "claude" else None,
               "correct": int(df.correct.sum()), "total": len(df),
               "accuracy_pct": round(100 * df.correct.mean(), 1),
               "by_difficulty": {d: f"{int(r['sum'])}/{int(r['count'])}" for d, r in by.iterrows()}}
    if "sql_errors_fixed" in df:
        summary["questions_with_self_correction"] = int((df.sql_errors_fixed > 0).sum())
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(f"{out_dir}/eval_{mode}.csv", index=False)
    json.dump(summary, open(f"{out_dir}/eval_{mode}_summary.json", "w"), indent=2)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["baseline", "claude", "gold"], default="baseline")
    a = ap.parse_args()
    client = None
    if a.mode == "claude":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise SystemExit("Set ANTHROPIC_API_KEY for --mode claude")
        import anthropic
        client = anthropic.Anthropic()
    print(json.dumps(evaluate(a.mode, client=client), indent=2))


if __name__ == "__main__":
    main()
