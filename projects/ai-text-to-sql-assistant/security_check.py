"""Red-team the SQL guard: every attack must be blocked by BOTH layers independently.

Layer 1 = static check (sqlglot). Layer 2 = read-only SQLite connection with an authorizer, tested
by sending the raw attack straight to the database with layer 1 switched off.
Writes outputs/security_report.md.
"""
import os
import shutil
import sqlite3
import tempfile

import guard

ATTACKS = [
    ("Drop a table", "DROP TABLE loans"),
    ("Delete rows", "DELETE FROM loans WHERE 1=1"),
    ("Update balances", "UPDATE accounts SET balance = balance * 10"),
    ("Insert a row", "INSERT INTO branches VALUES (99, 'Fake', 'X', 'North', '2026-01-01')"),
    ("Stacked query", "SELECT 1; DROP TABLE customers"),
    ("Comment-hidden second statement", "SELECT * FROM customers -- harmless\n; DELETE FROM customers"),
    ("Write inside a CTE", "WITH x AS (DELETE FROM loans RETURNING *) SELECT * FROM x"),
    ("Create a table", "CREATE TABLE leak AS SELECT * FROM customers"),
    ("Create a view", "CREATE VIEW v AS SELECT * FROM customers"),
    ("Create a trigger", "CREATE TRIGGER t AFTER INSERT ON loans BEGIN DELETE FROM loans; END"),
    ("Alter a table", "ALTER TABLE customers ADD COLUMN pwned TEXT"),
    ("Attach another database", "ATTACH DATABASE '/tmp/evil.db' AS evil"),
    ("Detach", "DETACH DATABASE main"),
    ("PRAGMA write", "PRAGMA writable_schema = ON"),
    ("PRAGMA read of schema", "PRAGMA table_info(customers)"),
    ("Read system catalogue", "SELECT sql FROM sqlite_master"),
    ("Read temp catalogue", "SELECT * FROM sqlite_temp_master"),
    ("Unknown table", "SELECT * FROM users"),
    ("Replace into", "REPLACE INTO branches VALUES (1, 'X', 'X', 'X', 'X')"),
    ("Vacuum into a file", "VACUUM INTO '/tmp/copy.db'"),
    ("Reindex", "REINDEX"),
    ("Begin transaction", "BEGIN TRANSACTION"),
    ("Load extension", "SELECT load_extension('/tmp/evil.so')"),
    ("Empty query", "   "),
    ("Not SQL", "please delete all loans"),
]


def layer1(sql):
    try:
        guard.check_sql(sql)
        return False
    except guard.UnsafeSQL:
        return True


def layer2(sql, db):
    """Raw execution against a copy of the database, with only the runtime protections on."""
    if not sql.strip():
        return None  # nothing reaches the database
    con = guard.connect(db)
    try:
        for stmt in [s for s in sql.split(";") if s.strip()] or [sql]:
            con.execute(stmt).fetchall()
        return False
    except (sqlite3.DatabaseError, sqlite3.Warning, ValueError):
        return True
    finally:
        con.close()


def table_counts(db):
    con = sqlite3.connect(db)
    out = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for (t,) in
           con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    return out


def run(db="data/bank.db"):
    tmp = tempfile.mkdtemp()
    copy = os.path.join(tmp, "bank.db")
    shutil.copy(db, copy)
    before = table_counts(copy)
    results = [(name, sql, layer1(sql), layer2(sql, copy)) for name, sql in ATTACKS]
    after = table_counts(copy)
    shutil.rmtree(tmp)
    lines = ["# SQL Guard Red-Team Report", "",
             f"{sum(r[2] for r in results)}/{len(results)} attacks blocked by layer 1 (static check). "
             f"{sum(bool(r[3]) for r in results)}/{sum(r[3] is not None for r in results)} blocked by layer 2 alone (read-only connection + authorizer). "
             f"Database unchanged after all attacks: {'yes' if before == after else 'NO'}.", "",
             "| Attack | Layer 1 | Layer 2 alone |", "|:--|:--:|:--:|"]
    for name, sql, l1, l2 in results:
        l2s = "nothing to run" if l2 is None else ("blocked" if l2 else "allowed")
        lines.append(f"| {name} | {'blocked' if l1 else 'ALLOWED'} | {l2s} |")
    os.makedirs("outputs", exist_ok=True)
    open("outputs/security_report.md", "w").write("\n".join(lines) + "\n")
    return results, before == after


if __name__ == "__main__":
    res, unchanged = run()
    for name, _, l1, l2 in res:
        print(f"{name:<34} layer1={'blocked' if l1 else 'ALLOWED'}  layer2={'n/a' if l2 is None else 'blocked' if l2 else 'allowed'}")
    print("database unchanged:", unchanged)
