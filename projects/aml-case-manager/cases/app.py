"""
Case view for investigators.

  GET  /api/cases                    all cases with status, patterns and size
  GET  /api/cases/{id}               one case: accounts, the transfers behind it (the subgraph) and its history
  POST /api/cases/{id}/status        {"status": "under review" | "closed" | "open", "note": "..."}
  GET  /                             the case view page (cases/static/index.html)

Run: DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aml python cases/app.py
"""
import os
from pathlib import Path

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/aml")
STATIC = Path(__file__).with_name("static")
app = FastAPI(title="AML case manager")


def q(sql, args=(), one=False):
    with psycopg2.connect(DSN) as conn, conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(sql, args)
        if cur.description is None:
            return None
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows


class StatusChange(BaseModel):
    status: str = Field(pattern="^(open|under review|closed)$")
    note: str = ""


@app.get("/api/cases")
def cases():
    return q("""SELECT case_id, patterns, status, opened_for, detail, n_accounts, n_transfers, total_usd::float AS total_usd
                FROM cases ORDER BY case_id""")


@app.get("/api/cases/{case_id}")
def case(case_id: int):
    c = q("SELECT *, total_usd::float AS total_usd FROM cases WHERE case_id = %s", (case_id,), one=True)
    if not c:
        raise HTTPException(404, "case not found")
    c["events"] = q("SELECT at, from_status, to_status, note FROM case_events WHERE case_id = %s ORDER BY at", (case_id,))
    return c


@app.post("/api/cases/{case_id}/status")
def change(case_id: int, body: StatusChange):
    old = q("SELECT status FROM cases WHERE case_id = %s", (case_id,), one=True)
    if not old:
        raise HTTPException(404, "case not found")
    q("UPDATE cases SET status = %s WHERE case_id = %s", (body.status, case_id))
    q("INSERT INTO case_events (case_id, from_status, to_status, note) VALUES (%s, %s, %s, %s)",
      (case_id, old["status"], body.status, body.note))
    return {"case_id": case_id, "status": body.status}


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))
