"""Tests: safety guard, result matching, benchmark, and the agent loop with a scripted stand-in for Claude."""
import json
from types import SimpleNamespace

import pytest

import assistant
import evaluate
import guard
import security_check

BENCH = json.load(open("data/benchmark.json"))


# ---------------------------------------------------------------- guard
def test_every_attack_blocked_by_both_layers():
    results, unchanged = security_check.run()
    assert unchanged
    assert all(l1 for _, _, l1, _ in results)
    assert all(l2 in (True, None) for _, _, _, l2 in results)


def test_safe_query_runs_and_gets_a_limit():
    con = guard.connect()
    cols, rows, safe = guard.run_query(con, "SELECT region, COUNT(*) AS n FROM branches GROUP BY region")
    assert cols == ["region", "n"] and len(rows) == 4
    assert safe.endswith("LIMIT 1000")
    assert guard.check_sql("SELECT 1 FROM loans LIMIT 5").endswith("LIMIT 5")


def test_cte_names_are_not_treated_as_tables():
    assert guard.check_sql("WITH npa AS (SELECT * FROM loans WHERE days_past_due > 90) SELECT COUNT(*) FROM npa")


# ---------------------------------------------------------------- matching
def test_results_match_rules():
    gold = [("North", 1.234), ("South", 2.0)]
    assert evaluate.results_match(gold, [("South", 2.0), ("North", 1.2341)])          # row order, rounding
    assert evaluate.results_match(gold, [(1.23, "North", 9), (2, "South", 8)])          # column order, extra column
    assert not evaluate.results_match(gold, [("North", 1.3), ("South", 2.0)])           # wrong value
    assert not evaluate.results_match(gold, [("North", 1.234)])                         # missing row
    assert not evaluate.results_match([("North", 1.0), ("South", 2.0)], [("North", 2.0), ("South", 1.0)])  # misaligned


def test_gold_sql_scores_full_marks(tmp_path):
    s = evaluate.evaluate("gold", out_dir=tmp_path)
    assert s["correct"] == s["total"] == 30


def test_benchmark_is_separate_from_examples():
    ex = {e["question"].lower() for e in json.load(open("data/examples.json"))}
    assert not ex & {b["question"].lower() for b in BENCH}


def test_retriever_finds_related_example():
    top = assistant.ExampleRetriever().top("What is the gross NPA ratio for home loans?", k=1)[0]
    assert "NPA" in top["question"]


# ---------------------------------------------------------------- agent loop
def tool_use(i, name, inp):
    return SimpleNamespace(type="tool_use", id=f"t{i}", name=name, input=inp)


class ScriptedClaude:
    """Plays back a fixed list of tool calls and records what the tools returned."""

    def __init__(self, script):
        self.script, self.returns = list(script), []
        self.messages = self

    def create(self, **kw):
        last = kw["messages"][-1]
        if isinstance(last["content"], list):
            self.returns += [json.loads(r["content"]) for r in last["content"]]
        name, inp = self.script.pop(0)
        return SimpleNamespace(stop_reason="tool_use", content=[tool_use(len(self.script), name, inp)])


def test_agent_fixes_a_failed_query():
    good = "SELECT region, COUNT(*) AS branches FROM branches GROUP BY region"
    fake = ScriptedClaude([
        ("run_sql", {"sql": "SELECT region, COUNT(*) FROM branch GROUP BY region"}),   # wrong table name
        ("describe_table", {"table": "branches"}),
        ("run_sql", {"sql": good}),
        ("final_answer", {"sql": good, "answer": "Each region has 5 branches.", "chart": {"type": "bar", "x": "region", "y": "branches"}}),
    ])
    res = assistant.ask(fake, "How many branches per region?")
    assert "error" in fake.returns[0] and "branch" in fake.returns[0]["error"]
    assert "region" in fake.returns[1]
    assert fake.returns[2]["row_count"] == 4
    assert res["sql_errors"] == 1
    assert res["result"].branches.tolist() == [5, 5, 5, 5]


def test_agent_cannot_change_the_database():
    fake = ScriptedClaude([
        ("run_sql", {"sql": "DELETE FROM loans"}),
        ("final_answer", {"sql": "SELECT COUNT(*) AS loans FROM loans", "answer": "1,800 loans."}),
    ])
    res = assistant.ask(fake, "Remove all loans")
    assert "UnsafeSQL" in fake.returns[0]["error"]
    assert res["result"].loans.iloc[0] == 1800


def test_evaluation_harness_with_scripted_model(tmp_path):
    gold = {b["question"]: b["sql"] for b in BENCH}

    class GoldClaude:
        def __init__(self):
            self.messages = self

        def create(self, **kw):
            q = kw["messages"][0]["content"].split("QUESTION: ")[-1]
            return SimpleNamespace(stop_reason="tool_use",
                                   content=[tool_use(0, "final_answer", {"sql": gold[q], "answer": "ok"})])

    s = evaluate.evaluate("claude", client=GoldClaude(), out_dir=tmp_path)
    assert s["accuracy_pct"] == 100.0
