"""Tests the AI analyst without an API key: the tools return real engine numbers, and the
tool-use loop works end to end with a scripted stand-in for Claude."""
from types import SimpleNamespace as NS
import pandas as pd
import ai_analyst as ai

tools = ai.ForecastTools()


def test_tools():
    s = tools.get_forecast_summary()
    assert s["p10_crore"] < s["q1_2026_forecast_crore"] < s["p90_crore"]
    base = tools.run_scenario()
    assert abs(base["change_crore"]) < 0.01
    cut = tools.run_scenario(marketing_change_pct=-20)
    assert cut["change_crore"] < 0
    sc = pd.read_csv("outputs/scenarios.csv").set_index("scenario")
    assert abs(cut["scenario_q1_crore"] - sc.loc["Marketing spend -20%", "q1_revenue_crore"]) < 0.05
    only_home = tools.run_scenario(discount_change_points=3, product_lines=["Home"])
    all_lines = tools.run_scenario(discount_change_points=3)
    assert 0 < only_home["change_crore"] < all_lines["change_crore"]


class FakeClaude:
    """Asks for one scenario, then answers using the tool result it was given."""
    def __init__(self):
        self.messages = self
        self.turn = 0
        self.seen = None

    def create(self, **kw):
        self.turn += 1
        if self.turn == 1:
            return NS(stop_reason="tool_use", content=[NS(type="tool_use", id="t1", name="run_scenario",
                                                          input={"marketing_change_pct": -10, "skip_holi_promo": True})])
        self.seen = kw["messages"][-1]["content"][0]["content"]
        return NS(stop_reason="end_turn", content=[NS(type="text", text=f"Tool said: {self.seen[:40]}")])


def test_agent_loop():
    fake = FakeClaude()
    answer = ai.run_agent(fake, tools, "What if we cut marketing 10% and skip Holi?")
    assert fake.turn == 2 and "scenario_q1_crore" in fake.seen and answer.startswith("Tool said")


if __name__ == "__main__":
    test_tools()
    test_agent_loop()
    r = tools.run_scenario(marketing_change_pct=-10, skip_holi_promo=True)
    print("all checks passed | example tool result:", {k: r[k] for k in ["base_q1_crore", "scenario_q1_crore", "change_crore", "change_pct"]})
