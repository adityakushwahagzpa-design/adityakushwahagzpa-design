import copy

from monitor import RuleEngine, km, load_rules

BASE = load_rules()


def eng(**changes):
    r = copy.deepcopy(BASE)
    for rule, kv in changes.items():
        r[rule].update(kv)
    return RuleEngine(r)


def tx(ts, amount=500.0, lat=19.07, lon=72.87, channel="pos", card=1):
    return {"card": card, "ts": ts, "amount": amount, "lat": lat, "lon": lon, "channel": channel}


def rules(alerts):
    return [a["rule"] for a in alerts]


def test_haversine_mumbai_delhi():
    assert 1140 < km(19.076, 72.878, 28.614, 77.209) < 1160


def test_velocity_fires_on_sixth_transaction_in_window():
    e = eng()
    out = [rules(e.check(tx(1000 + 30 * i))) for i in range(6)]
    assert out[:5] == [[]] * 5 and out[5] == ["velocity"]


def test_velocity_window_slides():
    e = eng()
    for i in range(5):
        e.check(tx(1000 + 60 * i))
    assert rules(e.check(tx(1000 + 60 * 4 + 601))) == []     # the old ones have left the 10-minute window


def test_velocity_is_per_card():
    e = eng()
    for i in range(5):
        e.check(tx(1000 + i, card=1))
    assert rules(e.check(tx(1006, card=2))) == []


def test_impossible_travel_mumbai_to_delhi_in_30_minutes():
    e = eng()
    e.check(tx(0))
    assert rules(e.check(tx(1800, lat=28.614, lon=77.209))) == ["impossible_travel"]


def test_travel_is_fine_with_enough_time():
    e = eng()
    e.check(tx(0))
    assert rules(e.check(tx(4 * 3600, lat=28.614, lon=77.209))) == []    # ~290 km/h


def test_online_purchases_are_ignored_by_the_travel_rule():
    e = eng()
    e.check(tx(0))
    assert rules(e.check(tx(600, lat=28.614, lon=77.209, channel="online"))) == []


def test_naive_travel_rule_misfires_on_online_purchases():
    e = eng(impossible_travel={"card_present_only": False, "min_distance_km": 0})
    e.check(tx(0))
    assert rules(e.check(tx(600, lat=28.614, lon=77.209, channel="online"))) == ["impossible_travel"]


def test_unusual_amount_needs_history():
    e = eng()
    for i in range(19):
        e.check(tx(i * 86400, amount=500 + i))
    assert rules(e.check(tx(20 * 86400, amount=50_000))) == []          # only 19 past transactions


def test_unusual_amount_fires_with_history():
    e = eng()
    for i in range(30):
        e.check(tx(i * 86400, amount=400 + 10 * (i % 5)))
    assert rules(e.check(tx(31 * 86400, amount=5_000))) == ["unusual_amount"]


def test_history_is_updated_after_the_check():
    e = eng()
    for i in range(20):
        e.check(tx(i * 86400, amount=100.0 + (i % 2)))
    s = e.state[1]
    n_before, mean_before = s.n, s.mean
    assert rules(e.check(tx(25 * 86400, amount=10_000))) == ["unusual_amount"]
    assert s.n == n_before + 1 and s.mean > mean_before                  # added only after it was checked


def test_rule_can_be_switched_off_in_config():
    e = eng(velocity={"enabled": False})
    assert all(rules(e.check(tx(1000 + i))) == [] for i in range(10))
