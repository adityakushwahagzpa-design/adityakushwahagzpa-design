"""AI text-to-SQL analytics assistant for a bank database, powered by Claude with tool use.

How a question is answered
  1. Retrieve the 4 most similar solved examples (TF-IDF) to show Claude the house style.
  2. Claude sees the data dictionary and business glossary (NPA, CASA, fiscal year ...).
  3. Claude writes SQL and tests it with the run_sql tool. Every query passes the safety guard
     (read-only, SELECT only, known tables, row limit, time limit). If the query fails or the
     result looks wrong, Claude sees the error and fixes the SQL.
  4. Claude calls final_answer with the SQL, a plain-English answer and a chart suggestion.
     The final SQL is run again by the code, so the table the user sees comes from the database,
     not from the model.

  python assistant.py --ask "What is the gross NPA ratio by region?"
  python assistant.py                 # interactive

Needs ANTHROPIC_API_KEY. `--baseline` answers without Claude by reusing the SQL of the most
similar solved example (to show why an LLM is needed).
"""
import argparse
import json
import os
import sys

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import guard
from semantic_layer import TABLES, glossary_text, schema_text

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
DB = os.environ.get("BANK_DB", "data/bank.db")

SYSTEM = f"""You are a senior data analyst at a retail bank. You answer business questions by writing
SQLite queries against the bank's database, then explaining the result in plain English.

DATABASE SCHEMA
{schema_text()}

BUSINESS GLOSSARY (follow these definitions exactly)
{glossary_text()}

RULES
- SQLite dialect. Read-only SELECT queries only. Dates are TEXT 'YYYY-MM-DD'; use strftime/date/julianday.
- Always test your query with run_sql before answering. If it errors or the result looks wrong
  (empty, NULLs, implausible numbers), fix it and run it again.
- Return only the columns the question needs, with clear aliases. Round money and ratios to 2 decimals.
  Ratios and shares are percentages (multiply by 100.0).
- Finish by calling final_answer. The answer must use the numbers returned by run_sql, in rupees with
  lakh/crore where helpful, and state any assumption you made about the question."""

TOOLS = [
    {"name": "describe_table",
     "description": "Columns of a table with a few example values, to check spellings of categories.",
     "input_schema": {"type": "object", "properties": {"table": {"type": "string", "enum": sorted(TABLES)}},
                      "required": ["table"]}},
    {"name": "run_sql",
     "description": "Run a read-only SQLite query. Returns columns, the first 20 rows and the row count, or an error.",
     "input_schema": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]}},
    {"name": "final_answer",
     "description": "Submit the final SQL, a short plain-English answer, and a chart suggestion.",
     "input_schema": {"type": "object", "properties": {
         "sql": {"type": "string"},
         "answer": {"type": "string", "description": "2-4 sentences using the numbers from run_sql."},
         "chart": {"type": "object", "properties": {
             "type": {"type": "string", "enum": ["bar", "line", "none"]},
             "x": {"type": "string", "description": "Column for the x-axis"},
             "y": {"type": "string", "description": "Column for the y-axis"}}}},
         "required": ["sql", "answer"]}},
]


class ExampleRetriever:
    def __init__(self, path="data/examples.json"):
        self.examples = json.load(open(path))
        self.vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        self.m = self.vec.fit_transform([e["question"] for e in self.examples])

    def top(self, question, k=4):
        sims = cosine_similarity(self.vec.transform([question]), self.m)[0]
        return [self.examples[i] for i in sims.argsort()[::-1][:k]]


class SQLTools:
    def __init__(self, db=DB):
        self.con = guard.connect(db)
        self.log = []

    def describe_table(self, table):
        if table not in TABLES:
            return {"error": f"unknown table {table}"}
        out = {}
        for col, desc in TABLES[table]["columns"].items():
            vals = [r[0] for r in self.con.execute(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL LIMIT 5")]
            out[col] = {"description": desc, "examples": vals}
        return out

    def run_sql(self, sql):
        try:
            cols, rows, safe = guard.run_query(self.con, sql)
            self.log.append({"sql": sql, "ok": True, "rows": len(rows)})
            return {"columns": cols, "rows": [list(r) for r in rows[:20]], "row_count": len(rows), "executed_sql": safe}
        except Exception as e:  # unsafe SQL and database errors both go back to the model to fix
            self.log.append({"sql": sql, "ok": False, "error": str(e)})
            return {"error": f"{type(e).__name__}: {e}"}

    def call(self, name, args):
        if name == "final_answer":
            return {"status": "received"}
        return getattr(self, name)(**(args or {}))


def build_prompt(question, retriever):
    shots = "\n\n".join(f"Q: {e['question']}\nSQL: {e['sql']}" for e in retriever.top(question))
    return f"Solved examples in the house style:\n\n{shots}\n\nQUESTION: {question}"


def ask(client, question, tools=None, retriever=None, max_turns=8):
    """Run the agent; returns dict with sql, answer, chart, result table and the attempt log."""
    tools = tools or SQLTools()
    tools.log = []
    retriever = retriever or ExampleRetriever()
    messages = [{"role": "user", "content": build_prompt(question, retriever)}]
    final = None
    for _ in range(max_turns):
        resp = client.messages.create(model=MODEL, max_tokens=2000, system=SYSTEM, tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
        if not uses:
            break
        results = []
        for b in uses:
            if b.name == "final_answer":
                final = b.input
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(tools.call(b.name, b.input), default=str)})
        if final:
            break
        messages.append({"role": "user", "content": results})
    if not final:
        return {"question": question, "sql": None, "answer": "No answer: the model did not call final_answer.",
                "attempts": tools.log}
    out = {"question": question, "sql": final["sql"], "answer": final["answer"], "chart": final.get("chart"),
           "attempts": tools.log, "sql_errors": sum(not a["ok"] for a in tools.log)}
    try:  # the table shown to the user always comes from re-running the final SQL
        cols, rows, _ = guard.run_query(tools.con, final["sql"])
        out["result"] = pd.DataFrame(rows, columns=cols)
    except Exception as e:
        out["result"], out["error"] = None, str(e)
    return out


def baseline_sql(question, retriever=None):
    """No-LLM baseline: reuse the SQL of the most similar solved example."""
    return (retriever or ExampleRetriever()).top(question, k=1)[0]["sql"]


def save_chart(res, path):
    ch, df = res.get("chart") or {}, res.get("result")
    if df is None or len(df) < 2 or ch.get("type") in (None, "none") or ch.get("x") not in df or ch.get("y") not in df:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8, 4))
    (ax.plot if ch["type"] == "line" else ax.bar)(df[ch["x"]].astype(str), df[ch["y"]], color="#2a6f97")
    ax.set_title(res["question"], fontsize=10)
    ax.set_xlabel(ch["x"])
    ax.set_ylabel(ch["y"])
    ax.spines[["top", "right"]].set_visible(False)
    plt.xticks(rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def show(res):
    print(f"\nQ: {res['question']}\n\nSQL:\n{res['sql']}\n")
    if res.get("result") is not None:
        print(res["result"].head(20).to_string(index=False))
    print(f"\n{res['answer']}")
    if res.get("sql_errors"):
        print(f"(fixed {res['sql_errors']} failed quer{'y' if res['sql_errors'] == 1 else 'ies'} along the way)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask")
    ap.add_argument("--baseline", action="store_true")
    a = ap.parse_args()
    retriever = ExampleRetriever()
    if a.baseline:
        q = a.ask or input("Question: ")
        sql = baseline_sql(q, retriever)
        cols, rows, _ = guard.run_query(guard.connect(DB), sql)
        print(f"Nearest example SQL:\n{sql}\n")
        print(pd.DataFrame(rows, columns=cols).head(20).to_string(index=False))
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY to use the AI assistant (or run with --baseline).")
    import anthropic
    client, tools = anthropic.Anthropic(), SQLTools()
    if a.ask:
        show(ask(client, a.ask, tools, retriever))
        return
    print("Ask a question about the bank's data (blank line to quit).")
    while (q := input("\n> ").strip()):
        show(ask(client, q, tools, retriever))


if __name__ == "__main__":
    main()
