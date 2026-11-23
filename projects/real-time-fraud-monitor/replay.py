"""
Replays the transactions to the running API one at a time, in time order, the way a payment system would.

  python replay.py --start 2026-03-01 --limit 20000          # as fast as possible
  python replay.py --start 2026-03-01 --limit 2000 --rate 50  # 50 transactions a second, to watch the dashboard

The full file is 403,847 rows; replaying a slice is enough to watch the rules work.
"""
import argparse
import time

import httpx
import pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    ap.add_argument("--start", default="2026-01-01", help="first date to replay")
    ap.add_argument("--limit", type=int, default=20000)
    ap.add_argument("--rate", type=float, default=0, help="transactions per second (0 = as fast as possible)")
    a = ap.parse_args()
    df = pd.read_csv("data/transactions.csv.gz", dtype={"fraud_pattern": str}).sort_values("unix_time", kind="stable")
    df = df[df.unix_time >= pd.Timestamp(a.start).timestamp()].head(a.limit)
    cols = ["trans_num", "cc_num", "unix_time", "merchant", "category", "amt", "merch_lat", "merch_long", "channel", "is_fraud"]
    flagged = 0
    with httpx.Client(base_url=a.url, timeout=10) as http:
        start = time.perf_counter()
        for i, row in enumerate(df[cols].itertuples(index=False)):
            res = http.post("/api/transactions", json=dict(zip(cols, [v.item() if hasattr(v, "item") else v for v in row])))
            res.raise_for_status()
            flagged += bool(res.json()["alerts"])
            if a.rate:
                time.sleep(max(0.0, (i + 1) / a.rate - (time.perf_counter() - start)))
        secs = time.perf_counter() - start
        stats = http.get("/api/stats").json()
    print(f"replayed {len(df):,} transactions in {secs:.1f}s ({len(df) / secs:,.0f}/s over HTTP), {flagged:,} flagged")
    print(f"server: {stats}")


if __name__ == "__main__":
    main()
