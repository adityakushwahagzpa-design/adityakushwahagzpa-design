"""Reference calculations for the Market Linkages project (same maths as the Excel workbook and the website)."""
import math, json

BASE = dict(cpi=4.0, target=4.0, rstar=1.5, gap=0.0, term_premium=1.0, curvature=0.5, tau=2.0,
            coupon=6.5, maturity=10, us_rate=4.0, spot=88.0, fx_years=1.0,
            d1=20.0, g=8.0, beta=1.0, erp=6.0)

def taylor(p): return p["rstar"] + p["cpi"] + 0.5 * (p["cpi"] - p["target"]) + 0.5 * p["gap"]

def ns(m, p):
    short = taylor(p); long = short + p["term_premium"]
    b0, b1, b2, tau = long, short - long, p["curvature"], p["tau"]
    x = m / tau; f = (1 - math.exp(-x)) / x
    return b0 + b1 * f + b2 * (f - math.exp(-x))

def bond(p, y=None):
    y = ns(p["maturity"], p) if y is None else y
    n = int(p["maturity"] * 2); c = p["coupon"] / 2; r = y / 200
    cf = [(t, c + (100 if t == n else 0)) for t in range(1, n + 1)]
    price = sum(v / (1 + r) ** t for t, v in cf)
    mac = sum(t / 2 * v / (1 + r) ** t for t, v in cf) / price
    mod = mac / (1 + r)
    conv = sum(t * (t + 1) * v / (1 + r) ** (t + 2) for t, v in cf) / price / 4
    return dict(y=y, price=price, mac=mac, mod=mod, conv=conv)

def fx(p):
    i_in = ns(p["fx_years"], p) / 100; i_us = p["us_rate"] / 100; T = p["fx_years"]
    fwd = p["spot"] * ((1 + i_in) / (1 + i_us)) ** T
    return dict(i_in=i_in * 100, fwd=fwd, prem=((fwd / p["spot"]) ** (1 / T) - 1) * 100)

def equity(p):
    rf = ns(10, p); ke = rf + p["beta"] * p["erp"]
    val = p["d1"] / ((ke - p["g"]) / 100) if ke > p["g"] else float("nan")
    return dict(rf=rf, ke=ke, value=val)

def run(p):
    return dict(policy=taylor(p), y10=ns(10, p), curve={m: ns(m, p) for m in [0.25, 1, 2, 5, 10, 30]},
                bond=bond(p), fx=fx(p), equity=equity(p))

if __name__ == "__main__":
    b = run(BASE)
    print(json.dumps(b, indent=1, default=lambda v: round(v, 4)))
    hike = dict(BASE, cpi=5.0)  # inflation 1 pt above target -> policy +1.5
    h = run(hike)
    print("inflation shock: policy", round(h["policy"], 2), "bond price", round(h["bond"]["price"], 2),
          "vs", round(b["bond"]["price"], 2), "equity", round(h["equity"]["value"], 1), "vs", round(b["equity"]["value"], 1),
          "fwd", round(h["fx"]["fwd"], 3), "vs", round(b["fx"]["fwd"], 3))
    # duration approximation check
    bb = b["bond"]; dy = 1.0
    approx = bb["price"] * (-bb["mod"] * dy / 100 + 0.5 * bb["conv"] * (dy / 100) ** 2)
    exact = bond(BASE, bb["y"] + dy)["price"] - bb["price"]
    print("+100bp: approx", round(approx, 3), "exact", round(exact, 3))
