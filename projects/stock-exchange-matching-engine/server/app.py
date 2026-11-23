"""
FastAPI server around the matching engine.

  POST   /api/orders          {"side": "buy", "qty": 10, "price_paise": 10025}   (price_paise null = market order)
  DELETE /api/orders/{id}     cancel a resting order
  GET    /api/book            top 10 price levels, last trades, totals
  WS     /ws                  pushes the book and new trades after every order
  GET    /                    the React order book (frontend/dist), if it has been built

Executed trades go onto a queue; a background thread writes them to PostgreSQL in batches,
so the database never sits inside the matching loop. Set DATABASE_URL to enable it.
"""
from __future__ import annotations

import itertools
import os
import queue
import threading
import time
from collections import deque
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import Order, OrderBook  # noqa: E402

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
DATABASE_URL = os.environ.get("DATABASE_URL")


class TradeWriter(threading.Thread):
    """Drains the trade queue and inserts trades into PostgreSQL every 0.5 s or every 500 trades."""

    def __init__(self, dsn: str):
        super().__init__(daemon=True)
        import psycopg2
        from psycopg2.extras import execute_values
        self.execute_values = execute_values
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = True
        with self.conn.cursor() as cur:
            cur.execute(Path(__file__).with_name("schema.sql").read_text())
        self.q: queue.SimpleQueue = queue.SimpleQueue()
        self.written = 0

    def run(self):
        batch, last = [], time.monotonic()
        while True:
            try:
                batch.append(self.q.get(timeout=0.5))
            except queue.Empty:
                pass
            if batch and (len(batch) >= 500 or time.monotonic() - last >= 0.5):
                with self.conn.cursor() as cur:
                    self.execute_values(cur, "INSERT INTO trades (executed_at, taker_order_id, maker_order_id, price_paise, qty) VALUES %s", batch)
                self.written += len(batch)
                batch, last = [], time.monotonic()


class NewOrder(BaseModel):
    side: str = Field(pattern="^(buy|sell)$")
    qty: int = Field(gt=0, le=1_000_000)
    price_paise: int | None = Field(default=None, gt=0)


book = OrderBook()
ids = itertools.count(1)
recent = deque(maxlen=50)
stats = {"orders": 0, "trades": 0, "volume": 0}
clients: set[WebSocket] = set()
writer = TradeWriter(DATABASE_URL) if DATABASE_URL else None
if writer:
    writer.start()

app = FastAPI(title="Mini stock exchange")


def snapshot():
    return {"book": book.depth(10), "trades": list(recent)[:20], "stats": stats,
            "best_bid": book.best_bid(), "best_ask": book.best_ask(),
            "db_trades_written": writer.written if writer else None}


async def broadcast():
    msg = snapshot()
    dead = []
    for ws in clients:
        try:
            await ws.send_json(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


@app.post("/api/orders")
async def place(o: NewOrder):
    order = Order(next(ids), o.side, o.qty, o.price_paise)
    trades = book.submit(order)
    now = time.time()
    stats["orders"] += 1
    for tr in trades:
        stats["trades"] += 1
        stats["volume"] += tr.qty
        recent.appendleft({"time": now, "taker": tr.taker_id, "maker": tr.maker_id, "price_paise": tr.price,
                           "qty": tr.qty, "side": o.side})
        if writer:
            writer.q.put((time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)), tr.taker_id, tr.maker_id, tr.price, tr.qty))
    await broadcast()
    resting = order.id in book.orders
    return {"order_id": order.id,
            "trades": [{"maker_order_id": t.maker_id, "price_paise": t.price, "qty": t.qty} for t in trades],
            "resting_qty": book.orders[order.id].qty if resting else 0}


@app.delete("/api/orders/{order_id}")
async def cancel(order_id: int):
    if not book.cancel(order_id):
        raise HTTPException(404, "order not found or already filled")
    await broadcast()
    return {"cancelled": order_id}


@app.get("/api/book")
async def get_book():
    return snapshot()


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    await websocket.send_json(snapshot())
    try:
        while True:
            await websocket.receive_text()   # keep the connection open; the client sends nothing
    except WebSocketDisconnect:
        clients.discard(websocket)


if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="ui")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))
