"""
A slow but obviously correct reference engine, used only to test order_book.py.

It keeps every resting order in a plain list and, for each incoming order, sorts the
opposite side by price then arrival number and walks it from the top. No heaps, no lazy
cancels: easy to read and check by hand.
"""
from __future__ import annotations


class ReferenceBook:
    def __init__(self):
        self.resting = []   # dicts: id, side, qty, price, arrival
        self.arrival = 0

    def submit(self, oid, side, qty, price):
        buy = side == "buy"
        trades = []
        while qty > 0:
            opposite = [o for o in self.resting if o["side"] != side]
            if not opposite:
                break
            opposite.sort(key=lambda o: ((o["price"] if buy else -o["price"]), o["arrival"]))
            best = opposite[0]
            if price is not None and (price < best["price"] if buy else price > best["price"]):
                break
            q = min(qty, best["qty"])
            trades.append((oid, best["id"], best["price"], q))
            qty -= q
            best["qty"] -= q
            if best["qty"] == 0:
                self.resting.remove(best)
        if qty > 0 and price is not None:
            self.resting.append({"id": oid, "side": side, "qty": qty, "price": price, "arrival": self.arrival})
            self.arrival += 1
        return trades

    def cancel(self, oid):
        for o in self.resting:
            if o["id"] == oid:
                self.resting.remove(o)
                return True
        return False

    def snapshot(self):
        """Resting orders as a set of (id, side, qty, price)."""
        return {(o["id"], o["side"], o["qty"], o["price"]) for o in self.resting}
