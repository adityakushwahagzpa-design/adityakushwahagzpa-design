"""SQL safety guard: two independent layers so a model can never change or leak the database.

Layer 1 (static, sqlglot): the text must parse as exactly one read-only query (SELECT / WITH /
UNION) over the known tables only. Anything else (INSERT, UPDATE, DELETE, DROP, ATTACH, PRAGMA,
CREATE, multiple statements, sqlite_master) is rejected before it reaches the database. A row
limit is added if missing.

Layer 2 (runtime, SQLite): the database is opened read-only, an authorizer callback denies every
action except reading, and a progress handler stops queries that run longer than the time limit.
"""
import sqlite3
import time

import logging

import sqlglot
from sqlglot import exp

from semantic_layer import ALLOWED_TABLES

logging.getLogger("sqlglot").setLevel(logging.ERROR)

MAX_ROWS = 1000
TIME_LIMIT_S = 10

FORBIDDEN = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command, exp.Pragma,
             exp.Attach if hasattr(exp, "Attach") else exp.Command, exp.Merge, exp.TruncateTable)


BANNED_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer", "sqlite_offset",
                    "sqlite_compileoption_get", "sqlite_compileoption_used", "sqlite_source_id"}
SYSTEM_TABLES = {"sqlite_master", "sqlite_temp_master", "sqlite_schema", "sqlite_temp_schema", "sqlite_sequence"}


class UnsafeSQL(ValueError):
    pass


def check_sql(sql: str) -> str:
    """Return a safe, limited version of `sql` or raise UnsafeSQL with the reason."""
    if not sql or not sql.strip():
        raise UnsafeSQL("empty query")
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except sqlglot.errors.ParseError as e:
        raise UnsafeSQL(f"could not parse SQL: {str(e).splitlines()[0]}") from None
    if len(statements) != 1:
        raise UnsafeSQL("exactly one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise UnsafeSQL(f"only SELECT queries are allowed, got {tree.key.upper()}")
    for node in tree.walk():
        if isinstance(node, FORBIDDEN):
            raise UnsafeSQL(f"{node.key.upper()} is not allowed")
    for f in tree.find_all(exp.Func):
        name = (f.name if isinstance(f, exp.Anonymous) else f.sql_name()).lower()
        if name in BANNED_FUNCTIONS:
            raise UnsafeSQL(f"function {name} is not allowed")
    ctes = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        name = t.name.lower()
        if name in ctes:
            continue
        if name not in ALLOWED_TABLES:
            raise UnsafeSQL(f"unknown or restricted table: {t.name}")
    if not tree.args.get("limit"):
        tree = tree.limit(MAX_ROWS)
    return tree.sql(dialect="sqlite")


def _authorizer(action, arg1, arg2, dbname, source):
    if action == sqlite3.SQLITE_READ and (arg1 or "").lower() in SYSTEM_TABLES:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in BANNED_FUNCTIONS:
        return sqlite3.SQLITE_DENY
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
    if hasattr(sqlite3, "SQLITE_RECURSIVE"):
        allowed.add(sqlite3.SQLITE_RECURSIVE)
    return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY


def connect(path="data/bank.db"):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    con.set_authorizer(_authorizer)
    return con


def run_query(con, sql: str, check=True):
    """Run a query safely; returns (columns, rows, safe_sql)."""
    safe = check_sql(sql) if check else sql
    start = time.monotonic()
    con.set_progress_handler(lambda: 1 if time.monotonic() - start > TIME_LIMIT_S else 0, 10_000)
    try:
        cur = con.execute(safe)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchmany(MAX_ROWS)
    finally:
        con.set_progress_handler(None, 0)
    return cols, rows, safe
