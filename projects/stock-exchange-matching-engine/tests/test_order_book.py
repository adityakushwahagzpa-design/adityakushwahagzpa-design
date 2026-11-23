import random

import pytest

from engine import Order, OrderBook
from engine.reference import ReferenceBook


def t(trades):
    return [(x.taker_id, x.maker_id, x.price, x.qty) for x in trades]


# ---- the matching rules, one test each ----

def test_limit_order_rests_when_prices_do_not_cross():
    b = OrderBook()
    assert b.submit(Order(1, "sell", 10, 10100)) == []
    assert b.submit(Order(2, "buy", 10, 10000)) == []
    assert (b.best_bid(), b.best_ask()) == (10000, 10100)


def test_trade_happens_at_resting_price():
    b = OrderBook()
    b.submit(Order(1, "sell", 10, 10000))
    assert t(b.submit(Order(2, "buy", 10, 10500))) == [(2, 1, 10000, 10)]


def test_best_price_first_then_time_priority():
    b = OrderBook()
    b.submit(Order(1, "sell", 5, 10100))
    b.submit(Order(2, "sell", 5, 10000))
    b.submit(Order(3, "sell", 5, 10000))   # same price as 2, arrived later
    assert t(b.submit(Order(4, "buy", 12, None))) == [(4, 2, 10000, 5), (4, 3, 10000, 5), (4, 1, 10100, 2)]


def test_partial_fill_leaves_rest_in_book():
    b = OrderBook()
    b.submit(Order(1, "buy", 10, 10000))
    assert t(b.submit(Order(2, "sell", 4, 9900))) == [(2, 1, 10000, 4)]
    assert b.orders[1].qty == 6


def test_unfilled_limit_remainder_rests():
    b = OrderBook()
    b.submit(Order(1, "sell", 3, 10000))
    b.submit(Order(2, "buy", 10, 10000))
    assert b.orders[2].qty == 7 and b.best_bid() == 10000


def test_market_order_remainder_is_dropped():
    b = OrderBook()
    b.submit(Order(1, "sell", 3, 10000))
    assert t(b.submit(Order(2, "buy", 10, None))) == [(2, 1, 10000, 3)]
    assert 2 not in b.orders and b.best_bid() is None


def test_cancelled_order_is_skipped():
    b = OrderBook()
    b.submit(Order(1, "sell", 5, 10000))
    b.submit(Order(2, "sell", 5, 10100))
    assert b.cancel(1) and not b.cancel(1)
    assert t(b.submit(Order(3, "buy", 5, 10200))) == [(3, 2, 10100, 5)]


def test_bad_orders_are_rejected():
    b = OrderBook()
    with pytest.raises(ValueError):
        b.submit(Order(1, "buy", 0, 100))
    with pytest.raises(ValueError):
        b.submit(Order(2, "hold", 1, 100))


def test_depth_aggregates_price_levels():
    b = OrderBook()
    b.submit(Order(1, "buy", 5, 10000))
    b.submit(Order(2, "buy", 7, 10000))
    b.submit(Order(3, "buy", 1, 9900))
    b.submit(Order(4, "sell", 2, 10200))
    b.cancel(3)
    assert b.depth() == {"bids": [(10000, 12, 2)], "asks": [(10200, 2, 1)]}


# ---- the engine against the brute-force reference on random order flow ----

def random_flow(rng, n):
    live, flow = [], []
    for oid in range(1, n + 1):
        r = rng.random()
        if r < 0.15 and live:
            flow.append(("cancel", live.pop(rng.randrange(len(live)))))
            continue
        side = rng.choice(["buy", "sell"])
        qty = rng.randint(1, 50)
        price = None if r < 0.25 else rng.randint(9_950, 10_050)   # paise, tight range so prices cross often
        flow.append(("order", oid, side, qty, price))
        if price is not None:
            live.append(oid)
    return flow


@pytest.mark.parametrize("seed", range(200))
def test_matches_reference_engine(seed):
    rng = random.Random(seed)
    fast, ref = OrderBook(), ReferenceBook()
    for step in random_flow(rng, 300):
        if step[0] == "cancel":
            assert fast.cancel(step[1]) == ref.cancel(step[1])
        else:
            _, oid, side, qty, price = step
            assert t(fast.submit(Order(oid, side, qty, price))) == ref.submit(oid, side, qty, price)
    assert {(o.id, o.side, o.qty, o.price) for o in fast.orders.values()} == ref.snapshot()
