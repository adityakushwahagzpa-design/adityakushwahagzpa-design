"""
Limit order book with price-time priority.

  - Prices are whole numbers of paise (1 rupee = 100 paise), never floats.
  - Bids: highest price first. Asks: lowest price first. Same price: the order that arrived first fills first.
  - A limit order trades at its price or better; what is left waits in the book.
  - A market order (price None) trades at the best prices available; what is left is dropped.
  - Every trade happens at the price of the resting order (the one already in the book).
  - Cancels are lazy: the order is marked inactive and skipped when it reaches the top of the heap.
"""
from __future__ import annotations

import heapq
import itertools
from dataclasses import dataclass, field


@dataclass(slots=True)
class Order:
    id: int
    side: str                 # "buy" or "sell"
    qty: int
    price: int | None = None  # paise; None = market order
    active: bool = True


@dataclass(slots=True, frozen=True)
class Trade:
    taker_id: int             # incoming order
    maker_id: int             # resting order
    price: int                # resting order's price, in paise
    qty: int


@dataclass
class OrderBook:
    bids: list = field(default_factory=list)   # (-price, seq, order)
    asks: list = field(default_factory=list)   # (price, seq, order)
    orders: dict = field(default_factory=dict) # resting orders by id
    _seq: itertools.count = field(default_factory=itertools.count)

    def submit(self, order: Order) -> list[Trade]:
        if order.qty <= 0:
            raise ValueError("quantity must be positive")
        if order.side not in ("buy", "sell"):
            raise ValueError("side must be 'buy' or 'sell'")
        if order.id in self.orders:
            raise ValueError(f"duplicate order id {order.id}")
        buy = order.side == "buy"
        opposite = self.asks if buy else self.bids
        trades: list[Trade] = []
        while order.qty and opposite:
            best = opposite[0][2]
            if not best.active:
                heapq.heappop(opposite)
                continue
            if order.price is not None and (order.price < best.price if buy else order.price > best.price):
                break
            qty = min(order.qty, best.qty)
            trades.append(Trade(order.id, best.id, best.price, qty))
            order.qty -= qty
            best.qty -= qty
            if best.qty == 0:
                heapq.heappop(opposite)
                best.active = False
                del self.orders[best.id]
        if order.qty and order.price is not None:
            key = -order.price if buy else order.price
            heapq.heappush(self.bids if buy else self.asks, (key, next(self._seq), order))
            self.orders[order.id] = order
        return trades

    def cancel(self, order_id: int) -> bool:
        order = self.orders.pop(order_id, None)
        if order is None:
            return False
        order.active = False
        return True

    def depth(self, levels: int = 10) -> dict:
        """Top price levels on each side: [(price, total qty, number of orders)]."""
        def side(heap, sign):
            agg: dict[int, list[int]] = {}
            for key, _, o in heap:
                if o.active:
                    a = agg.setdefault(sign * key, [0, 0])
                    a[0] += o.qty
                    a[1] += 1
            prices = sorted(agg, reverse=sign < 0)[:levels]
            return [(p, agg[p][0], agg[p][1]) for p in prices]
        return {"bids": side(self.bids, -1), "asks": side(self.asks, 1)}

    def best_bid(self) -> int | None:
        while self.bids and not self.bids[0][2].active:
            heapq.heappop(self.bids)
        return -self.bids[0][0] if self.bids else None

    def best_ask(self) -> int | None:
        while self.asks and not self.asks[0][2].active:
            heapq.heappop(self.asks)
        return self.asks[0][0] if self.asks else None
