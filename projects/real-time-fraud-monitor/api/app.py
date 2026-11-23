"""
FastAPI service: checks every incoming transaction against the rules and stores transactions and alerts.

  POST /api/transactions        one transaction (Kaggle column names) -> {"alerts": [...]}
  GET  /api/stats               counts of transactions and alerts by rule
  GET  /api/alerts?limit=50     latest alerts
  GET  /api/cards/{cc_num}      the card's last 20 transactions and its alerts (from PostgreSQL)
  GET  /api/merchants/flagged   merchants where alerts were raised on 2+ different cards
  GET  /api/rules               the thresholds in use (from config/rules.json)
  GET  /                        the React dashboard (frontend/dist), if built

The rules run in memory. Inserts go to a queue that a background thread writes to PostgreSQL in batches,
so a slow database never delays a check. Set DATABASE_URL to enable storage.
"""
from __future__ import annotations

import os
import queue
import sys
import threading
import time
from collections import Counter, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from monitor import RuleEngine  # noqa: E402

DATABASE_URL = os.environ.get("DATABASE_URL")


class Tx(BaseModel):
    trans_num: str
    cc_num: int
    unix_time: int
    merchant: str
    category: str
    amt: float = Field(gt=0)
    merch_lat: float
    merch_long: float
    channel: str = Field(default="pos", pattern="^(pos|online)$")
    is_fraud: int | None = None


class Writer(threading.Thread):
    def __init__(self, dsn):
        super().__init__(daemon=True)
        import psycopg2
        from psycopg2.extras import execute_values
        self.ev, self.conn = execute_values, psycopg2.connect(dsn)
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute((Path(__file__).with_name("schema.sql")).read_text())
        self.q = queue.SimpleQueue()
        self.lock = threading.Lock()

    def run(self):
        while True:
            txs, alerts = [], []
            deadline = time.monotonic() + 0.3
            while time.monotonic() < deadline and len(txs) < 2000:
                try:
                    tx, al = self.q.get(timeout=0.1)
                    txs.append(tx)
                    alerts.extend(al)
                except queue.Empty:
                    pass
            if txs:
                with self.lock, self.conn.cursor() as cur:
                    self.ev(cur, "INSERT INTO transactions VALUES %s ON CONFLICT DO NOTHING", txs)
                    if alerts:
                        self.ev(cur, "INSERT INTO alerts (trans_num, cc_num, unix_time, rule, detail) VALUES %s", alerts)

    def query(self, sql, args=()):
        with self.lock, self.conn.cursor() as cur:
            cur.execute(sql, args)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


engine = RuleEngine()
writer = Writer(DATABASE_URL) if DATABASE_URL else None
if writer:
    writer.start()
recent_alerts: deque = deque(maxlen=500)
stats = {"transactions": 0, "flagged_transactions": 0, "by_rule": Counter(), "labelled_fraud": 0, "flagged_fraud": 0,
         "check_microseconds_total": 0.0}
app = FastAPI(title="Real-time fraud monitor")


@app.post("/api/transactions")
def submit(tx: Tx):
    t0 = time.perf_counter()
    alerts = engine.check({"card": tx.cc_num, "ts": tx.unix_time, "amount": tx.amt,
                           "lat": tx.merch_lat, "lon": tx.merch_long, "channel": tx.channel})
    stats["check_microseconds_total"] += (time.perf_counter() - t0) * 1e6
    stats["transactions"] += 1
    stats["labelled_fraud"] += tx.is_fraud or 0
    if alerts:
        stats["flagged_transactions"] += 1
        stats["flagged_fraud"] += tx.is_fraud or 0
    for a in alerts:
        stats["by_rule"][a["rule"]] += 1
        recent_alerts.appendleft({"trans_num": tx.trans_num, "cc_num": str(tx.cc_num), "unix_time": tx.unix_time,
                                  "merchant": tx.merchant, "category": tx.category, "amt": tx.amt,
                                  "channel": tx.channel, "is_fraud": tx.is_fraud, **a})
    if writer:
        writer.q.put(((tx.trans_num, tx.cc_num, tx.unix_time, tx.merchant, tx.category, tx.amt, tx.merch_lat,
                       tx.merch_long, tx.channel, tx.is_fraud),
                      [(tx.trans_num, tx.cc_num, tx.unix_time, a["rule"], a["detail"]) for a in alerts]))
    return {"trans_num": tx.trans_num, "alerts": alerts}


@app.get("/api/stats")
def get_stats():
    n = stats["transactions"]
    return {**{k: v for k, v in stats.items() if k != "check_microseconds_total"},
            "avg_check_microseconds": round(stats["check_microseconds_total"] / n, 1) if n else None,
            "storage": "PostgreSQL" if writer else "memory only"}


@app.get("/api/alerts")
def get_alerts(limit: int = 50):
    return list(recent_alerts)[: max(1, min(limit, 500))]


@app.get("/api/rules")
def get_rules():
    return engine.rules


@app.get("/api/cards/{cc_num}")
def card(cc_num: int):
    if not writer:
        raise HTTPException(503, "card history needs DATABASE_URL (PostgreSQL)")
    history = writer.query("""SELECT trans_num, unix_time, merchant, category, amt::float AS amt, channel, is_fraud
                              FROM transactions WHERE cc_num = %s ORDER BY unix_time DESC LIMIT 20""", (cc_num,))
    alerts = writer.query("""SELECT trans_num, unix_time, rule, detail, status FROM alerts
                             WHERE cc_num = %s ORDER BY unix_time DESC LIMIT 50""", (cc_num,))
    for row in history + alerts:
        row["cc_num"] = str(cc_num)
    return {"cc_num": str(cc_num), "history": history, "alerts": alerts}


@app.get("/api/merchants/flagged")
def flagged_merchants():
    if not writer:
        raise HTTPException(503, "needs DATABASE_URL (PostgreSQL)")
    return writer.query("""SELECT t.merchant, t.category, COUNT(DISTINCT a.cc_num) AS cards_flagged,
                                  COUNT(*) AS alerts, STRING_AGG(DISTINCT a.rule, ', ') AS rules
                           FROM alerts a JOIN transactions t USING (trans_num)
                           GROUP BY t.merchant, t.category
                           HAVING COUNT(DISTINCT a.cc_num) >= 2
                           ORDER BY cards_flagged DESC, alerts DESC LIMIT 15""")


DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))
