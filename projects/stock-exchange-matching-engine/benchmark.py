"""
Measures how many orders per second the matching engine handles, with no network or database involved.

Three runs on a fresh book each time (orders are generated before the clock starts):
  - limit orders only, prices around a mid price so roughly half of them trade
  - a realistic mix: 70% limit, 15% market, 15% cancels
  - the same mix plus the batched trade writer's queue (trades handed off, not written)

Writes outputs/benchmark.json.
"""
import json
import queue
import random
import time
from pathlib import Path

from engine import Order, OrderBook

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)


def make_flow(n, seed, mix):
    rng = random.Random(seed)
    flow, live = [], []
    for oid in range(1, n + 1):
        r = rng.random()
        if mix and r < 0.15 and live:
            flow.append(("cancel", live.pop(rng.randrange(len(live)))))
            continue
        price = None if mix and r < 0.30 else rng.randint(9_900, 10_100)
        flow.append(("order", Order(oid, "buy" if rng.random() < 0.5 else "sell", rng.randint(1, 100), price)))
        if price is not None:
            live.append(oid)
    return flow


def run(flow, sink=None):
    book, trades = OrderBook(), 0
    start = time.perf_counter()
    for kind, x in flow:
        if kind == "cancel":
            book.cancel(x)
        else:
            out = book.submit(x)
            trades += len(out)
            if sink is not None and out:
                sink.put_nowait(out)
    secs = time.perf_counter() - start
    return {"orders": len(flow), "trades": trades, "seconds": round(secs, 3), "orders_per_second": round(len(flow) / secs)}


def main(n=1_000_000):
    results = {
        "limit_orders_only": run(make_flow(n, 1, mix=False)),
        "mixed_flow": run(make_flow(n, 2, mix=True)),
        "mixed_flow_with_trade_queue": run(make_flow(n, 2, mix=True), sink=queue.SimpleQueue()),
    }
    (OUT / "benchmark.json").write_text(json.dumps(results, indent=2))
    for name, r in results.items():
        print(f"{name:30s} {r['orders']:>9,} orders  {r['trades']:>9,} trades  {r['seconds']:>6.2f}s  {r['orders_per_second']:>9,} orders/s")


if __name__ == "__main__":
    main()
