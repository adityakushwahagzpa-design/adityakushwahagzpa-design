"""Checks: every planted incident is caught, the planned festival sale raises no alert,
false alarms stay below one a day, and the drift is caught within three hours.
Run after generate_stream.py and run_realtime.py."""
import json
import pandas as pd


def test_all():
    ev = pd.read_csv("outputs/evaluation.csv")
    s = json.load(open("outputs/summary.json"))
    al = pd.read_csv("outputs/alerts.csv", parse_dates=["ts"])
    cal = pd.read_csv("data/business_calendar.csv", parse_dates=["start", "end"])
    assert (ev.detected == "Yes").all(), ev[ev.detected != "Yes"]
    assert s["false_incidents_per_day"] < 1
    e = cal.iloc[0]
    during = al[(al.ts >= e.start) & (al.ts <= e.end) & (al.metric == "volume")]
    assert during.empty, "planned festival sale should not raise volume alerts"
    assert ev.set_index("incident_id").loc["INC6", "latency_min"] <= 180
    print("all checks passed")


if __name__ == "__main__":
    test_all()
