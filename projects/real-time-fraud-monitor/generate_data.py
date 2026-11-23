"""
Generates simulated card transactions with the same core columns as the Kaggle "Credit Card Transactions
Fraud Detection" dataset (made with the Sparkov tool): cc_num, merchant, category, amt, unix_time,
merch_lat, merch_long, is_fraud. Seeded, so every run produces the same file.

  1,000 cardholders in 20 Indian cities, 800 merchants, 1 January - 30 June 2026.
  fraud_pattern is an extra column (not in the Kaggle file) naming the pattern behind each fraud row,
  so the evaluation can show which patterns each rule catches.

  data/transactions.csv.gz  (403,847 rows, sorted by time; 488 fraud transactions on 60 cards)

Normal spending
  - Each card makes 0-6 purchases a day, mostly in its home city, at merchants of the categories its owner uses.
  - Online purchases (channel = online) carry the online merchant's registered location, which is often in
    another city. This is realistic, and it is what makes a naive impossible-travel rule misfire.
  - About 3% of cards take a trip to another city during the period and spend there for a few days.

Fraud (is_fraud = 1), on about 6% of cards
  - Account takeover: 6-15 high-value purchases over 1-3 days, mostly at night and online.
  - Cloned card: in-store purchases in a far-away city, minutes or hours after the real owner used the card at home.
  - Card testing: a burst of 6-10 small attempts within a few minutes (the "repeated attempts" pattern).
"""
import gzip
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "data"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(2026)

CITIES = {  # name: (lat, lon)
    "Mumbai": (19.076, 72.878), "Delhi": (28.614, 77.209), "Bengaluru": (12.972, 77.595), "Hyderabad": (17.385, 78.487),
    "Chennai": (13.083, 80.271), "Kolkata": (22.573, 88.364), "Pune": (18.520, 73.857), "Ahmedabad": (23.023, 72.571),
    "Jaipur": (26.912, 75.787), "Lucknow": (26.847, 80.947), "Kochi": (9.931, 76.267), "Chandigarh": (30.733, 76.779),
    "Bhopal": (23.260, 77.413), "Indore": (22.720, 75.858), "Patna": (25.594, 85.138), "Guwahati": (26.145, 91.736),
    "Bhubaneswar": (20.296, 85.825), "Nagpur": (21.146, 79.088), "Coimbatore": (11.017, 76.956), "Visakhapatnam": (17.687, 83.218),
}
# category: (channel, median amount in Rs, spread, share of normal spending)
CATS = {
    "grocery_pos": ("pos", 900, 0.6, 0.20), "gas_transport": ("pos", 1200, 0.4, 0.13), "food_dining": ("pos", 650, 0.6, 0.12),
    "shopping_pos": ("pos", 1800, 0.8, 0.10), "health_fitness": ("pos", 1100, 0.6, 0.06), "personal_care": ("pos", 500, 0.6, 0.06),
    "entertainment": ("pos", 800, 0.6, 0.06), "home": ("pos", 1500, 0.8, 0.06), "kids_pets": ("pos", 700, 0.6, 0.05),
    "shopping_net": ("online", 2200, 0.9, 0.08), "misc_net": ("online", 900, 0.9, 0.04), "grocery_net": ("online", 1100, 0.5, 0.02),
    "travel": ("online", 6000, 0.8, 0.02),
}
START, END = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-07-01")
DAYS = (END - START).days
city_names = list(CITIES)
HOUR_P = np.array([1, 1, 1, 1, 1, 2, 4, 6, 7, 7, 7, 8, 9, 8, 7, 7, 7, 8, 9, 9, 8, 6, 4, 2], dtype=float)
HOUR_P /= HOUR_P.sum()


def jitter(lat, lon, km):
    d = rng.uniform(0, km) / 111
    a = rng.uniform(0, 2 * math.pi)
    return round(lat + d * math.sin(a), 6), round(lon + d * math.cos(a) / math.cos(math.radians(lat)), 6)


def merchants(n=800):
    rows, cats = [], list(CATS)
    share = np.array([CATS[c][3] for c in cats])
    for i in range(n):
        cat = cats[rng.choice(len(cats), p=share / share.sum())]
        city = city_names[min(int(rng.exponential(5)), len(city_names) - 1)] if CATS[cat][0] == "online" else rng.choice(city_names)
        lat, lon = jitter(*CITIES[city], 15)
        rows.append({"merchant": f"M{1001 + i}", "category": cat, "channel": CATS[cat][0], "city": city, "merch_lat": lat, "merch_long": lon})
    return pd.DataFrame(rows)


def main():
    m = merchants()
    global MID, LAT, LON
    MID, LAT, LON = m.merchant.to_numpy(), m.merch_lat.to_numpy(), m.merch_long.to_numpy()
    by_city_cat = {k: g.index.to_numpy() for k, g in m[m.channel == "pos"].groupby(["city", "category"])}
    online = {c: g.index.to_numpy() for c, g in m[m.channel == "online"].groupby("category")}
    cats = list(CATS)
    rows = []

    def buy(card, t, cat, city, fraud, amt=None, pattern=""):
        if CATS[cat][0] == "online":
            idx = rng.choice(online[cat])
        else:
            pool = by_city_cat.get((city, cat))
            if pool is None or not len(pool):
                return
            idx = rng.choice(pool)
        if amt is None:
            _, med, spread, _ = CATS[cat]
            amt = med * math.exp(rng.normal(0, spread))
        rows.append((card, int(t.timestamp()), MID[idx], cat, round(float(amt), 2), LAT[idx], LON[idx], fraud, pattern))

    cards = [int(4000_0000_0000_0000 + rng.integers(0, 10**15)) for _ in range(1000)]
    for card in cards:
        home = city_names[min(int(rng.exponential(6)), len(city_names) - 1)]
        rate = rng.uniform(0.6, 4.0)                      # purchases a day
        pref = rng.dirichlet(np.array([CATS[c][3] for c in cats]) * 40)
        trip = None
        if rng.random() < 0.03:
            d0 = int(rng.integers(5, DAYS - 10))
            trip = (d0, d0 + int(rng.integers(2, 7)), rng.choice([c for c in city_names if c != home]))
        for day in range(DAYS):
            city = trip[2] if trip and trip[0] <= day < trip[1] else home
            for _ in range(rng.poisson(rate)):
                hour = rng.choice(24, p=HOUR_P)
                t = START + pd.Timedelta(days=day, hours=int(hour), seconds=int(rng.integers(0, 3600)))
                buy(card, t, cats[rng.choice(len(cats), p=pref)], city, 0)
        if rng.random() < 0.07:                           # this card is hit by fraud once
            kind = rng.choice(["takeover", "cloned", "testing"], p=[0.5, 0.3, 0.2])
            t0 = START + pd.Timedelta(days=int(rng.integers(3, DAYS - 4)), hours=int(rng.integers(0, 24)))
            if kind == "takeover":
                for _ in range(int(rng.integers(6, 16))):
                    t = t0 + pd.Timedelta(hours=float(rng.uniform(0, 60)))
                    t = t.replace(hour=int(rng.choice([22, 23, 0, 1, 2, 3])))
                    cat = rng.choice(["shopping_net", "misc_net", "shopping_pos", "grocery_pos"], p=[0.45, 0.25, 0.15, 0.15])
                    base = {"shopping_net": 18000, "misc_net": 9000, "shopping_pos": 15000, "grocery_pos": 6000}[cat]
                    buy(card, t, cat, home, 1, base * math.exp(rng.normal(0, 0.35)), "account_takeover")
            elif kind == "cloned":
                far = max((c for c in city_names if c != home), key=lambda c: math.dist(CITIES[c], CITIES[home]) * rng.uniform(0.6, 1))
                buy(card, t0, "food_dining", home, 0)                      # the real owner, at home
                for k in range(int(rng.integers(4, 9))):
                    t = t0 + pd.Timedelta(minutes=float(20 + 90 * k + rng.uniform(0, 60)))
                    cat = rng.choice(["shopping_pos", "gas_transport", "grocery_pos", "home"])
                    buy(card, t, cat, far, 1, 8000 * math.exp(rng.normal(0, 0.5)), "cloned_card")
            else:
                for k in range(int(rng.integers(6, 11))):
                    t = t0 + pd.Timedelta(seconds=int(k * rng.uniform(15, 50)))
                    buy(card, t, "misc_net", home, 1, float(rng.uniform(1, 99)), "card_testing")

    df = pd.DataFrame(rows, columns=["cc_num", "unix_time", "merchant", "category", "amt", "merch_lat", "merch_long", "is_fraud", "fraud_pattern"])
    df = df.sort_values(["unix_time", "cc_num"], kind="stable").reset_index(drop=True)
    df.insert(0, "trans_num", [f"T{i:07d}" for i in range(1, len(df) + 1)])
    df = df.merge(m[["merchant", "channel"]], on="merchant")
    df = df.sort_values("unix_time", kind="stable").reset_index(drop=True)
    with gzip.open(OUT / "transactions.csv.gz", "wt", newline="") as f:
        df.to_csv(f, index=False)
    m.to_csv(OUT / "merchants.csv", index=False)
    print(f"{len(df):,} transactions, {df.cc_num.nunique()} cards, {df.is_fraud.sum():,} fraud "
          f"({100 * df.is_fraud.mean():.2f}%), {df[df.is_fraud == 1].cc_num.nunique()} cards hit")


if __name__ == "__main__":
    main()
