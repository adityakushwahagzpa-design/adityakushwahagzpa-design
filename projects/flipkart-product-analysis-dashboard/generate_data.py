"""
Creates a synthetic Flipkart-style product catalogue and a year of order lines (seeded, same data every run).

  data/products.csv  2,000 products in 8 categories: brand, MRP, selling price, rating, rating count, Flipkart Assured
  data/orders.csv    order lines for 2025: date, product, quantity, price paid, returned (Yes/No)

Patterns built into the generator (so the dashboard has something to find):
  - Fashion carries the deepest discounts and the highest return rate; Mobiles and Electronics the shallowest discounts.
  - Very deep discounts (60%+) go with lower ratings.
  - Flipkart Assured products have slightly higher ratings and fewer returns.
  - The Big Billion Days sale (October) lifts orders and adds an extra discount on the price paid.
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OUT = HERE / "data"
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(2025)

# category: (sub-categories, brands, MRP range in Rs, typical discount, demand weight, base return rate)
CATS = {
    "Mobiles": (["Smartphone", "Feature Phone"], ["Samsung", "Redmi", "Realme", "Vivo", "OPPO", "Motorola", "POCO", "Apple"],
                (6000, 80000), 0.12, 1.0, 0.05),
    "Electronics": (["Headphones", "Smartwatch", "Power Bank", "Speaker", "Laptop"], ["boAt", "Noise", "JBL", "Sony", "HP", "Lenovo", "Mi", "Ambrane"],
                    (800, 70000), 0.30, 1.2, 0.07),
    "Fashion": (["Men's T-Shirt", "Women's Kurta", "Jeans", "Sneakers", "Saree"], ["Roadster", "HRX", "Libas", "Puma", "Levi's", "Allen Solly", "Campus", "W"],
                (400, 6000), 0.55, 2.2, 0.16),
    "Home & Kitchen": (["Cookware", "Bedsheet", "Mixer Grinder", "Storage", "Water Bottle"], ["Prestige", "Pigeon", "Milton", "Bajaj", "Cello", "Flipkart SmartBuy", "Philips", "Solimo"],
                       (300, 9000), 0.42, 1.4, 0.08),
    "Beauty & Personal Care": (["Face Wash", "Trimmer", "Perfume", "Shampoo", "Lipstick"], ["Himalaya", "Mamaearth", "Philips", "Lakme", "Nivea", "Beardo", "Dove", "Maybelline"],
                               (150, 4000), 0.32, 1.3, 0.04),
    "Appliances": (["Washing Machine", "Refrigerator", "Air Conditioner", "Television", "Microwave"], ["LG", "Samsung", "Whirlpool", "Voltas", "Haier", "IFB", "Godrej", "TCL"],
                   (7000, 65000), 0.28, 0.5, 0.06),
    "Sports & Fitness": (["Yoga Mat", "Dumbbells", "Cricket Bat", "Cycle", "Football"], ["Nivia", "Boldfit", "SG", "Hero", "Kookaburra", "Strauss", "Cosco", "Decathlon"],
                         (250, 15000), 0.45, 0.8, 0.07),
    "Books & Stationery": (["Fiction", "Exam Prep", "Notebooks", "Pens", "Children's Books"], ["Penguin", "Arihant", "Classmate", "Reynolds", "Disha", "Harper", "Navneet", "Cello"],
                           (80, 1500), 0.22, 1.0, 0.03),
}


def products(n=2000):
    rows, cats = [], list(CATS)
    weights = np.array([CATS[c][4] for c in cats])
    pick = rng.choice(len(cats), size=n, p=weights / weights.sum())
    for i, ci in enumerate(pick):
        cat = cats[ci]
        subs, brands, (lo, hi), disc, _, _ = CATS[cat]
        sub, brand = rng.choice(subs), rng.choice(brands)
        mrp = float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
        mrp = round(mrp / 10) * 10 - 1 if mrp > 100 else round(mrp)
        d = float(np.clip(rng.normal(disc, 0.12), 0.0, 0.85))
        sp = max(49, round(mrp * (1 - d)))
        assured = rng.random() < 0.55
        rating = rng.normal(4.05, 0.32) + (0.08 if assured else -0.05) - (0.35 if d > 0.6 else 0) - (0.15 if d > 0.7 else 0)
        rating = float(np.clip(round(rating, 1), 1.5, 4.9))
        count = int(rng.lognormal(6.3 + (0.6 if assured else 0), 1.2))
        rows.append({"product_id": f"FK{100001 + i}", "product_name": f"{brand} {sub} {rng.choice(['Pro', 'Plus', 'Lite', 'Max', 'Classic', 'Neo', 'Prime', 'Edge'])} {rng.integers(1, 99)}",
                     "category": cat, "sub_category": sub, "brand": brand, "mrp": int(mrp), "selling_price": int(sp),
                     "rating": rating, "rating_count": count, "flipkart_assured": "Yes" if assured else "No"})
    return pd.DataFrame(rows)


def orders(p, n=25000):
    days = pd.date_range("2025-01-01", "2025-12-31")
    w = np.ones(len(days))
    w[(days.month == 10) & (days.day <= 10)] *= 6.0        # Big Billion Days
    w[days.month.isin([10, 11])] *= 1.4                    # festive season
    w[days.month == 1] *= 1.15                             # Republic Day sale
    date = rng.choice(days, size=n, p=w / w.sum())
    demand = (p["rating_count"] ** 0.5) * np.where(p["flipkart_assured"] == "Yes", 1.2, 1.0) \
        * np.where(p["rating"] < 3.5, 0.6, 1.0) * (1 + p["mrp"].lt(1000) * 0.5)
    idx = rng.choice(len(p), size=n, p=(demand / demand.sum()).to_numpy())
    pp = p.iloc[idx].reset_index(drop=True)
    qty = np.where(pp["selling_price"] < 1000, rng.choice([1, 1, 1, 2, 2, 3], size=n), 1)
    bbd = (pd.DatetimeIndex(date).month == 10) & (pd.DatetimeIndex(date).day <= 10)
    price = np.round(pp["selling_price"] * np.where(bbd, rng.uniform(0.85, 0.95, size=n), 1.0)).astype(int)
    base_ret = pp["category"].map({c: v[5] for c, v in CATS.items()}).to_numpy()
    ret_p = base_ret * np.where(pp["flipkart_assured"] == "Yes", 0.7, 1.25) * np.where(pp["rating"] < 3.5, 1.5, 1.0)
    returned = np.where(rng.random(n) < ret_p, "Yes", "No")
    o = pd.DataFrame({"order_date": pd.DatetimeIndex(date).date, "product_id": pp["product_id"], "quantity": qty,
                      "unit_price_paid": price, "returned": returned}).sort_values("order_date").reset_index(drop=True)
    o.insert(0, "order_id", [f"OD{250000001 + i}" for i in range(len(o))])
    return o


def main():
    p = products()
    o = orders(p)
    p.to_csv(OUT / "products.csv", index=False)
    o.to_csv(OUT / "orders.csv", index=False)
    print(f"products {len(p)}, orders {len(o)}, units {o['quantity'].sum()}, "
          f"GMV Rs {(o['quantity'] * o['unit_price_paid']).sum() / 1e7:.2f} crore")


if __name__ == "__main__":
    main()
