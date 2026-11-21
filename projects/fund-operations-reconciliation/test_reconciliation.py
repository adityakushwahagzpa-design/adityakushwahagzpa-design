"""Checks that reconcile.py finds every break planted by generate_data.py, and nothing unexplained."""
import pandas as pd

import reconcile

EXPECTED = {  # planted break type -> (exception area, issue text it must produce)
    "Quantity keyed wrongly in book": ("Trade", "Quantity mismatch"),
    "Commission booked at wrong rate": ("Trade", "Amount mismatch"),
    "Duplicate booking in book": ("Trade", "Duplicate in book"),
    "Trade missing from book": ("Trade", "Missing in book"),
    "Failed settlement still pending at month-end": ("Settlement", "Failed - pending"),
    "Settled late (resolved inside month)": ("Settlement", "Settled late"),
    "Dividend not booked in book": ("Corporate action", "Dividend: Not booked in book"),
    "Stock split not applied in book": ("Corporate action", "Split: Not booked in book"),
    "Custodian fee debited, not booked": ("Cash", "Custody fee October 2026 not booked"),
}


def test_all_planted_breaks_found():
    summary, exc = reconcile.main()
    planted = pd.read_csv(reconcile.D / "planted_breaks.csv")
    missed = []
    for _, p in planted.iterrows():
        area, issue = EXPECTED[p.break_type]
        hit = exc[(exc.area == area) & (exc.reference == p.reference) & (exc.issue == issue)]
        if hit.empty:
            missed.append((p.break_type, p.reference))
    assert not missed, f"missed: {missed}"
    # anything raised that was not planted must be a knock-on effect of a planted trade or settlement break
    keys = set(planted.reference)
    extra = exc[~exc.reference.isin(keys)]
    assert (extra.issue == "Dividend: Entitlement difference").all(), extra
    assert summary["position_breaks_unexplained"] == 0
    assert abs(summary["cash_unexplained"]) < 0.01


if __name__ == "__main__":
    test_all_planted_breaks_found()
    print("All planted breaks found; positions and cash fully explained.")
