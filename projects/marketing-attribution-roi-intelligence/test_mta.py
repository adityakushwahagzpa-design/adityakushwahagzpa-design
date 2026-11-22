"""Tests for attribution, the marketing mix model, the optimiser and the AI analyst loop."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import ai_analyst
import attribution as at
import mmm
from generate_data import CHANNELS, MMM_TRUE, PAID, adstock, hill


def tiny_journeys():
    return pd.DataFrame({
        "path": [["YouTube", "Google Search"], ["Google Search"], ["Meta Ads"], ["YouTube"], ["Meta Ads", "Direct"]],
        "times": [[pd.Timestamp("2026-07-01"), pd.Timestamp("2026-07-08")], [pd.Timestamp("2026-07-02")],
                  [pd.Timestamp("2026-07-03")], [pd.Timestamp("2026-07-04")],
                  [pd.Timestamp("2026-07-05"), pd.Timestamp("2026-07-06")]],
        "converted": [1, 1, 0, 0, 1],
    })


# ---------------------------------------------------------------- attribution
@pytest.mark.parametrize("model", ["last_touch", "first_touch", "linear", "time_decay", "position_based"])
def test_rule_weights_sum_to_one(model):
    times = [pd.Timestamp("2026-07-01") + pd.Timedelta(days=d) for d in (0, 3, 10, 14)]
    w = at.rule_weights(["a", "b", "c", "d"], times, model)
    assert w.sum() == pytest.approx(1.0)


def test_position_based_and_time_decay_shapes():
    times = [pd.Timestamp("2026-07-01") + pd.Timedelta(days=d) for d in (0, 7, 14)]
    assert at.rule_weights(list("abc"), times, "position_based").tolist() == pytest.approx([0.4, 0.2, 0.4])
    w = at.rule_weights(list("abc"), times, "time_decay")
    assert w[1] / w[0] == pytest.approx(2.0) and w[2] / w[1] == pytest.approx(2.0)  # 7-day half-life


def test_shapley_is_efficient():
    j = tiny_journeys()
    phi = at.shapley_attribution(j)
    assert sum(phi.values()) == pytest.approx(j.converted.sum())


def test_markov_removal_effect():
    j = tiny_journeys()
    credit, removal = at.markov_attribution(j)
    assert sum(credit.values()) == pytest.approx(3)
    assert removal["Google Search"] > removal["Meta Ads"] > 0


def test_ml_counterfactual_is_most_accurate():
    s = json.load(open("outputs/attribution_summary.json"))
    assert s["best_model"] == "ml_counterfactual"
    assert s["error_pp"]["ml_counterfactual"] < 2 < s["error_pp"]["linear"] < s["error_pp"]["last_touch"]


# ---------------------------------------------------------------- MMM
def test_adstock_and_hill():
    assert adstock([1, 0, 0], 0.5).tolist() == pytest.approx([1, 0.5, 0.25])
    assert hill(3.0, 3.0) == pytest.approx(0.5)


def test_linear_solve_recovers_betas_on_clean_data():
    df = pd.read_csv("data/weekly_mmm.csv", parse_dates=["week"])
    theta = []
    for c in PAID:
        d, h, _ = MMM_TRUE[c]
        theta += [d, h / df[c].mean()]
    media = mmm.media_terms(df, np.array(theta))
    betas = np.array([MMM_TRUE[c][2] for c in PAID])
    y = mmm.base_terms(df) @ np.array([20, 3, 2, 0, 9]) + media @ betas
    coef, _ = mmm.solve_linear(df, np.array(theta), y)
    assert coef[-len(PAID):] == pytest.approx(betas, rel=1e-6)


def test_lift_row_pulls_roi_towards_test():
    df = pd.read_csv("data/weekly_mmm.csv", parse_dates=["week"])
    theta = np.array([0.3, 1.5] * len(PAID))
    y = df.revenue_lakh.values
    i = PAID.index("YouTube")
    M = mmm.media_terms(df, theta)
    roi = lambda coef: coef[5 + i] * M[:, i].sum() / df["YouTube"].sum()
    free = roi(mmm.solve_linear(df, theta, y)[0])
    target = free + 1.5
    lift = pd.DataFrame({"channel": ["YouTube"], "measured_roi": [target], "std_error": [0.01]})
    assert abs(roi(mmm.solve_linear(df, theta, y, lift)[0]) - target) < 0.05


def test_optimiser_respects_budget_and_limits():
    params = {c: {"decay": d, "half": h, "beta": b} for c, (d, h, b) in MMM_TRUE.items()}
    cur = {c: 2.0 for c in PAID}
    plan = mmm.optimise_budget(params, cur, min_change=-0.3, max_change=0.3, locked=("Affiliate",))
    alloc = {a["channel"]: a["optimised_lakh"] for a in plan["allocation"]}
    assert sum(alloc.values()) == pytest.approx(10.0, abs=1e-3)
    assert alloc["Affiliate"] == pytest.approx(2.0)
    assert all(1.4 - 1e-6 <= v <= 2.6 + 1e-6 for v in alloc.values())
    assert plan["optimised_weekly_revenue_lakh"] >= plan["current_weekly_revenue_lakh"]
    with pytest.raises(ValueError):
        mmm.optimise_budget(params, cur, total=20, min_change=-0.3, max_change=0.3)


def test_mmm_outputs_are_consistent():
    ms = json.load(open("outputs/mmm_summary.json"))
    assert ms["roi_mae_calibrated"] < ms["roi_mae_uncalibrated"]
    assert ms["fit_r2"] > 0.9
    assert ms["budget"]["true_uplift_pct"] > 0  # the recommended split also helps under the true curves


# ---------------------------------------------------------------- AI analyst
class FakeClaude:
    """Scripted stand-in: asks for two tools, then answers."""

    def __init__(self):
        self.turn, self.seen = 0, []
        self.messages = self

    def create(self, **kw):
        self.turn += 1
        if self.turn == 1:
            return SimpleNamespace(stop_reason="tool_use", content=[
                SimpleNamespace(type="tool_use", id="t1", name="simulate_spend_change",
                                input={"changes_pct": {"Google Search": -20, "YouTube": 25}}),
                SimpleNamespace(type="tool_use", id="t2", name="optimise_budget", input={"locked_channels": ["Affiliate"]})])
        self.seen = [json.loads(b["content"]) for b in kw["messages"][-1]["content"]]
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Shift to YouTube.")])


def test_agent_loop_runs_tools():
    fake, tools = FakeClaude(), ai_analyst.MarketingTools()
    assert ai_analyst.run_agent(fake, tools, "Where should budget go?") == "Shift to YouTube."
    sim, opt = fake.seen
    assert sim["new_weekly_spend_lakh"] != sim["current_weekly_spend_lakh"]
    assert {a["channel"] for a in opt["allocation"]} == set(PAID)


def test_tools_reject_bad_input():
    tools = ai_analyst.MarketingTools()
    assert "error" in tools.simulate_spend_change({"TV": 10})
    assert "error" in tools.optimise_budget(total_weekly_budget_lakh=1000)
    assert set(tools.get_attribution_comparison()["share_pct_by_model"]) == set(CHANNELS)
