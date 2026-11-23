"""
Rule engine for the fraud monitor.

Each card keeps a small state that is updated on every transaction:
  - recent:   timestamps inside the velocity window (a sliding window, oldest dropped first)
  - last:     time and location of the previous card-present purchase (for travel speed)
  - n, mean, m2: running count, mean and sum of squares of amounts (Welford's method)

check() reads the thresholds from the config, compares the transaction with the card's history,
and only then adds the transaction to the history. Updating first would compare a transaction
with itself and quietly weaken the unusual-amount rule.

Alerts are indicators for a human to review, not proof of fraud.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "rules.json"


def load_rules(path: str | Path = DEFAULT_CONFIG) -> dict:
    return json.loads(Path(path).read_text())


def km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in kilometres (haversine)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


@dataclass
class CardState:
    recent: deque = field(default_factory=deque)
    last: tuple | None = None          # (ts, lat, lon) of the last card-present purchase
    n: int = 0
    mean: float = 0.0
    m2: float = 0.0

    def update(self, tx: dict, card_present: bool) -> None:
        self.n += 1
        delta = tx["amount"] - self.mean
        self.mean += delta / self.n
        self.m2 += delta * (tx["amount"] - self.mean)
        if card_present:
            self.last = (tx["ts"], tx["lat"], tx["lon"])


class RuleEngine:
    def __init__(self, rules: dict | None = None):
        self.rules = rules or load_rules()
        self.state: dict[int, CardState] = defaultdict(CardState)

    def check(self, tx: dict) -> list[dict]:
        """tx: card, ts (unix seconds), amount, lat, lon, channel ('pos' or 'online'). Returns a list of alerts."""
        r, s, alerts = self.rules, self.state[tx["card"]], []
        card_present = tx.get("channel", "pos") == "pos"

        v = r["velocity"]
        while s.recent and tx["ts"] - s.recent[0] > v["window_seconds"]:
            s.recent.popleft()
        s.recent.append(tx["ts"])
        if v["enabled"] and len(s.recent) > v["max_tx_in_window"]:
            alerts.append({"rule": "velocity", "detail": f"{len(s.recent)} transactions in {v['window_seconds'] // 60} min"})

        t = r["impossible_travel"]
        if t["enabled"] and s.last and (card_present or not t["card_present_only"]):
            dist = km(s.last[1], s.last[2], tx["lat"], tx["lon"])
            hours = max(tx["ts"] - s.last[0], 1) / 3600
            if dist >= t["min_distance_km"] and dist / hours > t["max_speed_kmh"]:
                alerts.append({"rule": "impossible_travel", "detail": f"{dist:,.0f} km in {hours * 60:,.0f} min ({dist / hours:,.0f} km/h)"})

        u = r["unusual_amount"]
        if u["enabled"] and s.n >= u["min_history"]:
            std = (s.m2 / (s.n - 1)) ** 0.5
            if std > 0:
                z = (tx["amount"] - s.mean) / std
                if z > u["max_zscore"]:
                    alerts.append({"rule": "unusual_amount", "detail": f"₹{tx['amount']:,.0f} is {z:.1f} std devs above this card's mean of ₹{s.mean:,.0f}"})

        s.update(tx, card_present or not t["card_present_only"])   # history is updated only AFTER the checks
        return alerts
