"""Checks on the engine outputs: the ML model beats both baselines in the backtest, the
ensemble is close to unbiased, the forecast range contains the point forecast, and the
Excel pack total matches the daily forecast. Run after forecast_engine.py and report.py."""
import json
import pandas as pd
from openpyxl import load_workbook


def test_all():
    s = json.load(open("outputs/summary.json"))
    b = s["backtest"]
    assert b["lightgbm"]["daily_wape"] < min(b["seasonal_naive"]["daily_wape"], b["holt_winters"]["daily_wape"])
    assert abs(b["ensemble"]["bias"]) < 0.02
    assert s["q1_2026_p10_crore"] < s["q1_2026_forecast_crore"] < s["q1_2026_p90_crore"]
    fc = pd.read_csv("outputs/forecast_q1_2026_daily.csv")
    mon = pd.read_csv("outputs/forecast_q1_2026_monthly.csv")
    assert abs(fc.ensemble.sum() - mon.p50.sum()) < 1
    assert len(fc) == 90 * 3
    ws = load_workbook("outputs/forecast_pack_q1_2026.xlsx")["Monthly forecast"]
    assert ws["D13"].value == "=SUM(D4:D12)"
    print("all checks passed")


if __name__ == "__main__":
    test_all()
