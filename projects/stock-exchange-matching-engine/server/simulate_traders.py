"""
Simulated traders: sends random limit orders, market orders and cancels to the running server.

  python server/simulate_traders.py --orders 2000 --rate 50

Prices move as a random walk around ₹100.00 (10,000 paise), so the book keeps trading.
Prints a summary, including the server's own trade count, at the end.
"""
import argparse
import random
import time

import httpx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--orders", type=int, default=2000)
    ap.add_argument("--rate", type=float, default=50, help="orders per second (0 = as fast as possible)")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    mid, live, trades = 10_000, [], 0
    with httpx.Client(base_url=a.url, timeout=10) as http:
        start = time.perf_counter()
        for i in range(a.orders):
            mid = max(5_000, mid + rng.choice([-5, 0, 0, 5]))
            r = rng.random()
            if r < 0.12 and live:
                http.delete(f"/api/orders/{live.pop(rng.randrange(len(live)))}")
            else:
                side = rng.choice(["buy", "sell"])
                price = None if r < 0.22 else mid + rng.randint(-40, 40) // 5 * 5
                res = http.post("/api/orders", json={"side": side, "qty": rng.randint(1, 50) * 10, "price_paise": price}).json()
                trades += len(res["trades"])
                if res["resting_qty"]:
                    live.append(res["order_id"])
            if a.rate:
                time.sleep(max(0.0, (i + 1) / a.rate - (time.perf_counter() - start)))
        secs = time.perf_counter() - start
        server = http.get("/api/book").json()
    print(f"sent {a.orders} orders in {secs:.1f}s ({a.orders / secs:.0f}/s over HTTP), {trades} trades")
    print(f"server stats: {server['stats']}, trades written to PostgreSQL: {server['db_trades_written']}")


if __name__ == "__main__":
    main()
