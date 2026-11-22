"""Simulate 14 days of minute-level payment activity for a fictional Indian payments business.

Three channels (UPI, Card, NetBanking). Each minute records transaction count, failures,
refunds and value. Eight incidents are planted on known dates, plus one legitimate festival
sale that is listed in the business calendar and should NOT raise an alert.
Outputs: data/stream.csv, data/planted_incidents.csv, data/business_calendar.csv
"""
import os
import numpy as np
import pandas as pd

SEED = int(os.environ.get("SEED", 42))
DAYS = 14
START = pd.Timestamp("2026-10-01 00:00")
CHANNELS = {"UPI": dict(share=0.62, fail=0.020, ticket=520, refund=0.006),
            "Card": dict(share=0.26, fail=0.028, ticket=1850, refund=0.010),
            "NetBanking": dict(share=0.12, fail=0.022, ticket=3200, refund=0.008)}
BASE_PER_MIN = 900  # average transactions a minute across channels at the daily mean


def intraday(minute_of_day):
    h = minute_of_day / 60.0

    def bump(centre, width):  # circular, so 23:59 and 00:00 join smoothly
        d = np.minimum(np.abs(h - centre), 24 - np.abs(h - centre))
        return np.exp(-(d ** 2) / width)
    return 0.12 + 0.35 * bump(10, 8) + 0.55 * bump(13, 6) + 1.3 * bump(20.5, 5)


# incidents: (id, type, channel, start offset (day, hh:mm), minutes, description)
INCIDENTS = [
    ("INC1", "Card gateway outage", "Card", (3, "14:10"), 25, "Card failure rate jumps to ~45%"),
    ("INC2", "UPI partner degradation", "UPI", (5, "11:30"), 40, "UPI volume falls ~60%"),
    ("INC3", "Card fraud burst", "Card", (6, "03:05"), 15, "Card ticket size x4 and volume +40% at night"),
    ("INC4", "Pricing bug", "All", (8, "19:00"), 90, "Average ticket halves on all channels"),
    ("INC5", "Refund spike", "NetBanking", (9, "16:20"), 30, "NetBanking refund rate ~9%"),
    ("INC6", "Slow failure drift", "NetBanking", (11, "08:00"), 360, "NetBanking failure rate creeps from 2% to ~7%"),
    ("INC7", "Duplicate charge bug", "UPI", (12, "12:40"), 20, "UPI volume doubles at the same ticket size"),
]
FESTIVAL = ("EVT1", "Festival sale (planned)", "All", (13, "18:00"), 180, "Volume x2.3 across channels")


def ts(day, hhmm):
    h, m = map(int, hhmm.split(":"))
    return START + pd.Timedelta(days=day, hours=h, minutes=m)


def main():
    rng = np.random.default_rng(SEED)
    idx = pd.date_range(START, periods=DAYS * 1440, freq="min")
    mod = idx.hour * 60 + idx.minute
    shape = intraday(mod.values.astype(float))
    shape = shape / shape.mean()
    weekend = np.where(idx.dayofweek >= 5, 1.15, 1.0)
    trend = 1 + 0.004 * (np.arange(len(idx)) / 1440)  # slow organic growth

    rows = []
    for ch, p in CHANNELS.items():
        lam = BASE_PER_MIN * p["share"] * shape * weekend * trend
        fail_p = np.full(len(idx), p["fail"])
        refund_p = np.full(len(idx), p["refund"])
        ticket = np.full(len(idx), float(p["ticket"]))

        def window(start, minutes):
            s = idx.get_loc(start)
            return slice(s, s + minutes)

        for inc_id, kind, ich, (d, hm), mins, _ in INCIDENTS + [FESTIVAL]:
            if ich not in (ch, "All"):
                continue
            w = window(ts(d, hm), mins)
            if inc_id == "INC1":
                fail_p[w] = 0.45
            elif inc_id == "INC2":
                lam[w] *= 0.40
            elif inc_id == "INC3":
                ticket[w] *= 4.0
                lam[w] *= 1.4
            elif inc_id == "INC4":
                ticket[w] *= 0.5
            elif inc_id == "INC5":
                refund_p[w] = 0.09
            elif inc_id == "INC6":
                fail_p[w] = np.linspace(p["fail"], 0.07, mins)
            elif inc_id == "INC7":
                lam[w] *= 2.0
            elif inc_id == "EVT1":
                lam[w] *= 2.3

        n = rng.poisson(lam)
        fails = rng.binomial(n, fail_p)
        ok = n - fails
        refunds = rng.binomial(ok, refund_p)
        # value of successful payments: sum of lognormal tickets ~ n*mean with noise
        sigma = 0.9
        mu = np.log(ticket) - sigma ** 2 / 2
        mean_t = np.exp(mu + sigma ** 2 / 2)
        sd_sum = np.sqrt(np.maximum(ok, 1)) * mean_t * np.sqrt(np.exp(sigma ** 2) - 1)
        value = np.maximum(ok * mean_t + rng.normal(0, 1, len(idx)) * sd_sum, 0)
        value = np.where(ok == 0, 0, value)
        rows.append(pd.DataFrame({"ts": idx, "channel": ch, "txns": n, "failed": fails,
                                  "refunds": refunds, "value_inr": value.round(2)}))

    os.makedirs("data", exist_ok=True)
    df = pd.concat(rows).sort_values(["ts", "channel"]).reset_index(drop=True)
    df.to_csv("data/stream.csv", index=False)
    pl = pd.DataFrame([dict(incident_id=i, type=k, channel=c, start=ts(d, hm),
                            end=ts(d, hm) + pd.Timedelta(minutes=m - 1), minutes=m, description=t)
                       for i, k, c, (d, hm), m, t in INCIDENTS])
    pl.to_csv("data/planted_incidents.csv", index=False)
    i, k, c, (d, hm), m, t = FESTIVAL
    pd.DataFrame([dict(event_id=i, event=k, channel=c, start=ts(d, hm),
                       end=ts(d, hm) + pd.Timedelta(minutes=m - 1), note=t)]).to_csv(
        "data/business_calendar.csv", index=False)
    print(f"{len(df):,} rows ({DAYS} days x 1,440 minutes x {len(CHANNELS)} channels), "
          f"{int(df.txns.sum()):,} transactions, value Rs {df.value_inr.sum() / 1e7:,.1f} crore")


if __name__ == "__main__":
    main()
