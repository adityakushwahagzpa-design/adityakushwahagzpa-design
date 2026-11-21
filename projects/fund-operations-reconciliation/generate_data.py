"""
Generates one month (October 2026) of records for a fictional Indian equity fund,
"Aarohan Large Cap Fund", as seen from three sides:

  data/book_*         the fund accounting system (what the fund administrator booked)
  data/broker_*       broker trade confirmations
  data/custodian_*    custodian position and cash statements

The "true" activity is simulated first; the book and the custodian are then derived from it,
with known errors planted so the reconciliation has real breaks to find. The planted list
is saved to data/planted_breaks.csv and used only by test_reconciliation.py to check that
reconcile.py finds every one of them. Prices and holdings are synthetic.
"""
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

rng = np.random.default_rng(1007)
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)

HOLIDAYS = {date(2026, 10, 2), date(2026, 10, 20), date(2026, 10, 21)}  # Gandhi Jayanti, Diwali (assumed)
DAYS = [d for d in pd.bdate_range("2026-10-01", "2026-10-30").date if d not in HOLIDAYS]

SECURITIES = {  # symbol: (name, sector, start price)
    "RELIANCE": ("Reliance Industries", "Energy", 1420), "HDFCBANK": ("HDFC Bank", "Banks", 980),
    "ICICIBANK": ("ICICI Bank", "Banks", 1390), "INFY": ("Infosys", "IT", 1510), "TCS": ("TCS", "IT", 3080),
    "ITC": ("ITC", "FMCG", 405), "HINDUNILVR": ("Hindustan Unilever", "FMCG", 2480), "LT": ("Larsen & Toubro", "Capital Goods", 3650),
    "SBIN": ("State Bank of India", "Banks", 870), "BHARTIARTL": ("Bharti Airtel", "Telecom", 1980),
    "AXISBANK": ("Axis Bank", "Banks", 1160), "KOTAKBANK": ("Kotak Mahindra Bank", "Banks", 2110),
    "SUNPHARMA": ("Sun Pharma", "Pharma", 1640), "MARUTI": ("Maruti Suzuki", "Auto", 12800),
    "TATASTEEL": ("Tata Steel", "Metals", 165), "NTPC": ("NTPC", "Power", 342), "POWERGRID": ("Power Grid", "Power", 295),
    "ASIANPAINT": ("Asian Paints", "Consumer", 2390), "TITAN": ("Titan", "Consumer", 3560), "ULTRACEMCO": ("UltraTech Cement", "Cement", 12100),
}
BROKERS = ["Zerodha Institutional", "Kotak Securities", "ICICI Securities", "Motilal Oswal"]
BROKERAGE = 0.0003  # 0.03% of trade value


def next_bday(d, n=1):
    i = DAYS.index(d) if d in DAYS else None
    if i is not None and i + n < len(DAYS):
        return DAYS[i + n]
    nd = d
    while n:
        nd += timedelta(days=1)
        if nd.weekday() < 5 and nd not in HOLIDAYS:
            n -= 1
    return nd


def main():
    syms = list(SECURITIES)
    # prices
    px = {}
    for s in syms:
        p0 = SECURITIES[s][2]
        r = rng.normal(0.0004, 0.014, len(DAYS))
        px[s] = np.round(p0 * np.exp(np.cumsum(r)), 2)
    prices = pd.DataFrame(px, index=pd.Index(DAYS, name="date"))

    target = rng.uniform(0.8e7, 1.6e7, len(syms))  # ₹0.8-1.6 crore per stock
    opening = pd.DataFrame({"symbol": syms, "quantity": [max(25, int(round(v / SECURITIES[s][2] / 25)) * 25) for s, v in zip(syms, target)]})
    # bonus 1:1 and split 1:2 change quantities; corporate actions (record date inside the month)
    cas = pd.DataFrame([
        ("CA01", "ITC", "Dividend", date(2026, 10, 8), date(2026, 10, 16), 6.50, None),
        ("CA02", "INFY", "Dividend", date(2026, 10, 14), date(2026, 10, 28), 23.00, None),
        ("CA03", "HINDUNILVR", "Dividend", date(2026, 10, 22), date(2026, 10, 29), 19.00, None),
        ("CA04", "TCS", "Dividend", date(2026, 10, 15), date(2026, 10, 27), 11.00, None),
        ("CA05", "POWERGRID", "Dividend", date(2026, 10, 9), date(2026, 10, 23), 4.50, None),
        ("CA06", "TATASTEEL", "Bonus", date(2026, 10, 13), date(2026, 10, 15), None, "1:1"),
        ("CA07", "MARUTI", "Split", date(2026, 10, 23), date(2026, 10, 26), None, "1:2"),
    ], columns=["ca_id", "symbol", "event", "record_date", "pay_date", "rate_per_share", "ratio"])

    # bonus and split halve the share price from the record date
    for sym, rd in [("TATASTEEL", date(2026, 10, 13)), ("MARUTI", date(2026, 10, 23))]:
        prices.loc[[d for d in DAYS if d >= rd], sym] = (prices.loc[[d for d in DAYS if d >= rd], sym] / 2).round(2)

    # true trades
    trades = []
    for k in range(1, 321):
        d = DAYS[int(rng.integers(0, len(DAYS) - 1))]  # last day kept free so T+1 settles inside data
        s = syms[int(rng.integers(0, len(syms)))]
        side = "BUY" if rng.random() < 0.5 else "SELL"
        price = round(float(prices.loc[d, s]) * (1 + rng.normal(0, 0.002)), 2)
        qty = max(5, int(round(float(rng.uniform(2e5, 2.5e6)) / price / 5)) * 5)  # ₹2-25 lakh per trade
        gross = qty * price
        comm = round(gross * BROKERAGE, 2)
        net = round(gross + comm if side == "BUY" else gross - comm, 2)
        trades.append({"trade_ref": f"T{k:04d}", "trade_date": d, "settle_date": next_bday(d), "symbol": s, "side": side,
                       "quantity": qty, "price": price, "commission": comm, "net_amount": net,
                       "broker": BROKERS[int(rng.integers(0, len(BROKERS)))]})
    trades = pd.DataFrame(trades).sort_values(["trade_date", "trade_ref"]).reset_index(drop=True)
    # keep sells within holdings (rough guard)
    planted = []

    broker = trades.copy()

    book = trades.copy()
    pick = rng.choice(trades.index, 13, replace=False)
    qty_err, amt_err, dup, missing = pick[:3], pick[3:5], pick[5:7], pick[7:9]
    fails = pick[9:13]
    for i in qty_err:
        q0 = int(book.at[i, "quantity"])
        wrong = int(str(q0)[::-1].lstrip("0") or q0) if len(set(str(q0))) > 1 and str(q0)[-1] != "0" else q0 + 10  # digits transposed (e.g. 125 keyed as 521)
        planted.append(("Trade", "Quantity keyed wrongly in book", book.at[i, "trade_ref"], book.at[i, "symbol"]))
        book.at[i, "quantity"] = wrong
        g = wrong * book.at[i, "price"]
        c = round(g * BROKERAGE, 2)
        book.at[i, "commission"] = c
        book.at[i, "net_amount"] = round(g + c if book.at[i, "side"] == "BUY" else g - c, 2)
    for i in amt_err:
        planted.append(("Trade", "Commission booked at wrong rate", book.at[i, "trade_ref"], book.at[i, "symbol"]))
        g = book.at[i, "quantity"] * book.at[i, "price"]
        c = round(g * 0.003, 2)  # 0.30% instead of 0.03%
        book.at[i, "commission"] = c
        book.at[i, "net_amount"] = round(g + c if book.at[i, "side"] == "BUY" else g - c, 2)
    dups = book.loc[dup].copy()
    for i in dup:
        planted.append(("Trade", "Duplicate booking in book", book.at[i, "trade_ref"], book.at[i, "symbol"]))
    for i in missing:
        planted.append(("Trade", "Trade missing from book", book.at[i, "trade_ref"], book.at[i, "symbol"]))
    book = pd.concat([book.drop(index=missing), dups]).sort_values(["trade_date", "trade_ref"]).reset_index(drop=True)
    book["book_id"] = [f"B{n:05d}" for n in range(1, len(book) + 1)]

    # settlement: custodian settles true trades on settle date, except planted fails
    fail_info = {}
    for n, i in enumerate(fails):
        ref = trades.at[i, "trade_ref"]
        if n < 2:  # still pending at month-end
            fail_info[ref] = None
            planted.append(("Position", "Failed settlement still pending at month-end", ref, trades.at[i, "symbol"]))
        else:      # settled late, inside the month
            late = next_bday(trades.at[i, "settle_date"], 2)
            if late > DAYS[-1]:
                late = DAYS[-1]
            fail_info[ref] = late
    cust_settle = trades.copy()
    cust_settle["actual_settle"] = [fail_info.get(r, sd) if r in fail_info else sd for r, sd in zip(trades.trade_ref, trades.settle_date)]
    late_refs = [r for r, v in fail_info.items() if v is not None]
    for r in late_refs:
        planted.append(("Trade", "Settled late (resolved inside month)", r, trades.loc[trades.trade_ref == r, "symbol"].iloc[0]))
    settled = cust_settle[cust_settle.actual_settle.notna()]

    # true holdings through time (for corporate action entitlements, use settled holdings on record date)
    def holdings_on(day, tr, settle_col):
        h = opening.set_index("symbol")["quantity"].astype(float).copy()
        t = tr[tr[settle_col].notna() & (tr[settle_col] <= day)]
        sign = np.where(t.side == "BUY", 1, -1)
        h = h.add(pd.Series(sign * t.quantity.values, index=t.symbol.values).groupby(level=0).sum(), fill_value=0)
        return h

    # custodian applies CAs to settled holdings; record events
    cust_ca, book_ca = [], []
    adj_c, adj_b = {}, {}
    for _, ca in cas.iterrows():
        hc = holdings_on(ca.record_date, cust_settle, "actual_settle").get(ca.symbol, 0) + adj_c.get((ca.symbol, ca.record_date), 0)
        hb = holdings_on(ca.record_date, book.assign(_sd=book.settle_date), "_sd").get(ca.symbol, 0)
        if ca.event == "Dividend":
            cust_ca.append({"ca_id": ca.ca_id, "symbol": ca.symbol, "event": ca.event, "pay_date": ca.pay_date,
                            "eligible_quantity": hc, "cash_credited": round(hc * ca.rate_per_share, 2), "shares_credited": 0})
            if ca.ca_id == "CA03":
                planted.append(("Corporate action", "Dividend not booked in book", ca.ca_id, ca.symbol))
            else:
                book_ca.append({"ca_id": ca.ca_id, "symbol": ca.symbol, "event": ca.event, "pay_date": ca.pay_date,
                                "eligible_quantity": hb, "cash_booked": round(hb * ca.rate_per_share, 2), "shares_booked": 0})
        else:
            a, b = map(int, ca.ratio.split(":"))
            extra_c = hc * (b - a) / a if ca.event == "Split" else hc * a / b
            extra_b = hb * (b - a) / a if ca.event == "Split" else hb * a / b
            cust_ca.append({"ca_id": ca.ca_id, "symbol": ca.symbol, "event": ca.event, "pay_date": ca.pay_date,
                            "eligible_quantity": hc, "cash_credited": 0.0, "shares_credited": extra_c})
            if ca.event == "Split":
                planted.append(("Corporate action", "Stock split not applied in book", ca.ca_id, ca.symbol))
            else:
                book_ca.append({"ca_id": ca.ca_id, "symbol": ca.symbol, "event": ca.event, "pay_date": ca.pay_date,
                                "eligible_quantity": hb, "cash_booked": 0.0, "shares_booked": extra_b})
    cust_ca, book_ca = pd.DataFrame(cust_ca), pd.DataFrame(book_ca)

    # subscriptions / redemptions (agreed on both sides)
    flows = pd.DataFrame([{"date": d, "type": t, "amount": round(float(rng.uniform(2e6, 1.2e7)), 2)}
                          for d in DAYS for t in (["Subscription"] if rng.random() < 0.5 else []) + (["Redemption"] if rng.random() < 0.3 else [])])
    opening_cash = 8.0e7
    cust_fee = round(float(rng.uniform(80000, 120000)), 2)
    planted.append(("Cash", "Custodian fee debited, not booked", "FEE-OCT", "CASH"))

    # month-end positions
    me = DAYS[-1]
    cust_pos = holdings_on(me, cust_settle, "actual_settle")
    for _, r in cust_ca.iterrows():
        cust_pos[r.symbol] = cust_pos.get(r.symbol, 0) + r.shares_credited
    book_pos = holdings_on(me, book.assign(_sd=book.settle_date), "_sd")
    for _, r in book_ca.iterrows():
        book_pos[r.symbol] = book_pos.get(r.symbol, 0) + r.shares_booked

    def cash_move(t):
        return np.where(t.side == "BUY", -t.net_amount, t.net_amount).sum()

    sub = flows.loc[flows.type == "Subscription", "amount"].sum() - flows.loc[flows.type == "Redemption", "amount"].sum()
    cust_cash = opening_cash + cash_move(settled) + cust_ca.cash_credited.sum() + sub - cust_fee
    book_cash = opening_cash + cash_move(book) + book_ca.cash_booked.sum() + sub

    # write files
    pd.DataFrame([(s, *SECURITIES[s][:2]) for s in syms], columns=["symbol", "name", "sector"]).to_csv(OUT / "securities.csv", index=False)
    prices.round(2).to_csv(OUT / "prices.csv")
    opening.to_csv(OUT / "opening_positions.csv", index=False)
    cas.to_csv(OUT / "corporate_actions.csv", index=False)
    book.drop(columns=[]).to_csv(OUT / "book_trades.csv", index=False)
    broker.drop(columns=["broker"]).assign(broker=broker.broker).to_csv(OUT / "broker_confirmations.csv", index=False)
    cust_settle.rename(columns={"actual_settle": "custodian_settle_date"})[
        ["trade_ref", "symbol", "side", "quantity", "net_amount", "settle_date", "custodian_settle_date"]].to_csv(OUT / "custodian_settlements.csv", index=False)
    book_ca.to_csv(OUT / "book_corporate_actions.csv", index=False)
    cust_ca.to_csv(OUT / "custodian_corporate_actions.csv", index=False)
    flows.to_csv(OUT / "capital_flows.csv", index=False)
    pd.DataFrame({"symbol": book_pos.index, "quantity": book_pos.values}).to_csv(OUT / "book_positions_month_end.csv", index=False)
    pd.DataFrame({"symbol": cust_pos.index, "quantity": cust_pos.values}).to_csv(OUT / "custodian_positions_month_end.csv", index=False)
    pd.DataFrame([{"source": "book", "opening_cash": opening_cash, "closing_cash": round(book_cash, 2)},
                  {"source": "custodian", "opening_cash": opening_cash, "closing_cash": round(cust_cash, 2)}]).to_csv(OUT / "cash_balances.csv", index=False)
    pd.DataFrame([{"date": me, "description": "Custody fee October 2026", "amount": -cust_fee}]).to_csv(OUT / "custodian_cash_other.csv", index=False)
    pd.DataFrame(planted, columns=["area", "break_type", "reference", "symbol"]).to_csv(OUT / "planted_breaks.csv", index=False)
    print(f"{len(trades)} trades, {len(book)} book rows, {len(planted)} planted breaks, book cash {book_cash:,.0f}, custodian cash {cust_cash:,.0f}")


if __name__ == "__main__":
    main()
