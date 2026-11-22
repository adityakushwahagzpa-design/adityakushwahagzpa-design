"""AI analyst for the revenue forecast, powered by Claude with tool use.

Claude does not invent numbers: it answers by calling tools that run the forecasting engine
(the LightGBM model and the ensemble) and then explains the results in plain English.

  python ai_analyst.py --commentary          # Claude writes outputs/AI_COMMENTARY.md
  python ai_analyst.py --ask "What if we cut marketing by 10% and skip the Holi promo?"
  python ai_analyst.py                       # interactive chat

Needs an Anthropic API key in the ANTHROPIC_API_KEY environment variable. Without one,
`--commentary` falls back to the rule-based outputs/COMMENTARY.md written by report.py.
"""
import argparse
import json
import os
import sys
import numpy as np
import pandas as pd

import forecast_engine as fe

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
SYSTEM = """You are an FP&A analyst at a fictional Indian D2C retailer (Apparel, Electronics, Home).
You explain the Q1 2026 revenue forecast to the CFO. Rules:
- Get every number from a tool. Never estimate or invent figures.
- For any what-if question, call run_scenario with the matching parameters.
- Amounts are in Rs crore unless stated. Revenue is not profit: say so when discounts are involved.
- Be brief and concrete: lead with the answer, then the two or three numbers that support it,
  then one risk or caveat. Mention forecast accuracy from get_backtest when asked how far to trust it."""

TOOLS = [
    {"name": "get_forecast_summary",
     "description": "Q1 2026 forecast: total, P10-P90 range, growth vs Q1 2025, and the forecast by month and product line.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_backtest",
     "description": "How accurate each model was when forecasting Q2, Q3 and Q4 2025 (daily WAPE, quarterly error, bias) and the ensemble weights.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_driver_importance",
     "description": "Share of the LightGBM model's attribution for each driver in the Q1 2026 forecast.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "run_scenario",
     "description": "Re-run the Q1 2026 forecast with changed plan drivers and return the new total and the change vs the base case, by month and product line.",
     "input_schema": {"type": "object", "properties": {
         "marketing_change_pct": {"type": "number", "description": "Change to daily marketing spend, e.g. -10 for a 10% cut. Default 0."},
         "discount_change_points": {"type": "number", "description": "Percentage points added to every day's discount, e.g. 2 adds 2 points. Default 0."},
         "skip_republic_day_sale": {"type": "boolean", "description": "Cancel the 24-26 January sale. Default false."},
         "skip_holi_promo": {"type": "boolean", "description": "Cancel the Holi promotion (late Feb-4 March). Default false."},
         "product_lines": {"type": "array", "items": {"type": "string", "enum": fe.LINES},
                           "description": "Apply the changes only to these lines. Default: all."}}}},
]


class ForecastTools:
    """Trains the final models once and answers tool calls from the engine's outputs."""

    def __init__(self):
        self.df, self.plan = fe.load()
        self.origin = pd.Timestamp("2025-12-31")
        self.fut = pd.concat([self.plan.assign(product_line=l) for l in fe.LINES]).reset_index(drop=True)
        self.summary = json.load(open("outputs/summary.json"))
        self.w = self.summary["weights"]
        self.base, self.model, _, _ = fe.forecast_all(self.df, self.fut, self.origin)
        self.base["ensemble"] = sum(self.base[m] * self.w[m] for m in fe.MODELS)

    def get_forecast_summary(self):
        mon = pd.read_csv("outputs/forecast_q1_2026_monthly.csv")
        s = self.summary
        return {"q1_2026_forecast_crore": s["q1_2026_forecast_crore"], "p10_crore": s["q1_2026_p10_crore"],
                "p90_crore": s["q1_2026_p90_crore"], "q1_2025_actual_crore": s["q1_2025_actual_crore"],
                "yoy_growth_pct": round(s["yoy_growth"] * 100, 1),
                "by_month_and_line": [{"month": r.month, "line": r.product_line, "forecast_crore": round(r.p50 / 100, 2),
                                       "same_month_2025_crore": round(r.last_year / 100, 2), "yoy_pct": round(r.yoy * 100, 1)}
                                      for r in mon.itertuples()]}

    def get_backtest(self):
        return {"tested_on": "Q2, Q3 and Q4 2025, each forecast 90 days ahead from the prior quarter end",
                "models": self.summary["backtest"], "ensemble_weights": self.w}

    def get_driver_importance(self):
        imp = pd.read_csv("outputs/driver_importance.csv", index_col=0).share
        return {k: round(float(v) * 100, 1) for k, v in imp.head(10).items()}

    def run_scenario(self, marketing_change_pct=0, discount_change_points=0, skip_republic_day_sale=False,
                     skip_holi_promo=False, product_lines=None):
        p = self.fut.copy()
        sel = p.product_line.isin(product_lines or fe.LINES)
        p.loc[sel, "marketing_lakh"] *= 1 + marketing_change_pct / 100
        p.loc[sel, "discount_pct"] += discount_change_points / 100
        if skip_republic_day_sale:
            m = sel & (p.republic_day_sale > 0)
            p.loc[m, ["discount_pct", "republic_day_sale"]] = [0.05, 0.0]
        if skip_holi_promo:
            m = sel & (p.holi > 0)
            p.loc[m, ["discount_pct", "holi"]] = [0.05, 0.0]
        Xs, lv = fe.ml_future_rows(self.df, p, self.origin)
        ml = np.exp(self.model.predict(Xs)) * lv
        new = self.base.seasonal_naive * self.w["seasonal_naive"] + self.base.holt_winters * self.w["holt_winters"] + ml * self.w["lightgbm"]
        t = self.base.assign(new=new, month=self.base.date.dt.strftime("%Y-%m"))
        g = t.groupby(["month", "product_line"])[["ensemble", "new"]].sum() / 100
        base_tot, new_tot = t.ensemble.sum() / 100, t.new.sum() / 100
        return {"base_q1_crore": round(base_tot, 2), "scenario_q1_crore": round(new_tot, 2),
                "change_crore": round(new_tot - base_tot, 2), "change_pct": round((new_tot / base_tot - 1) * 100, 2),
                "by_month_and_line": [{"month": m, "line": l, "base_crore": round(r.ensemble, 2), "scenario_crore": round(r.new, 2)}
                                      for (m, l), r in g.iterrows()],
                "note": "Revenue only; discounts lower margin. Holt-Winters and seasonal naive parts do not react to drivers."}

    def call(self, name, args):
        return getattr(self, name)(**(args or {}))


def run_agent(client, tools, question, max_turns=8):
    """Standard tool-use loop: Claude asks for tools, we run them, Claude writes the answer."""
    messages = [{"role": "user", "content": question}]
    for _ in range(max_turns):
        resp = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM, tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        results = []
        for b in resp.content:
            if getattr(b, "type", "") == "tool_use":
                out = tools.call(b.name, b.input)
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(out)})
        messages.append({"role": "user", "content": results})
    return "Stopped: too many tool calls."


COMMENTARY_PROMPT = """Write the CFO commentary for the Q1 2026 revenue forecast, about 250 words, in Markdown with
these headings: Headline, By month and product line, What drives it, What-if (run these scenarios:
marketing -20%, marketing +20%, skip the Republic Day sale, discounts +3 points), How far to trust it."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask")
    ap.add_argument("--commentary", action="store_true")
    a = ap.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if a.commentary:
            print("No ANTHROPIC_API_KEY set: using the rule-based commentary in outputs/COMMENTARY.md")
            print(open("outputs/COMMENTARY.md").read())
            return
        sys.exit("Set ANTHROPIC_API_KEY to use the AI analyst.")
    import anthropic
    client = anthropic.Anthropic()
    tools = ForecastTools()
    if a.commentary:
        text = run_agent(client, tools, COMMENTARY_PROMPT)
        open("outputs/AI_COMMENTARY.md", "w").write("# Q1 2026 Forecast: AI Commentary (Claude)\n\n" + text + "\n")
        print(text)
    elif a.ask:
        print(run_agent(client, tools, a.ask))
    else:
        print("Ask about the Q1 2026 forecast (blank line to quit).")
        while True:
            q = input("\n> ").strip()
            if not q:
                break
            print(run_agent(client, tools, q))


if __name__ == "__main__":
    main()
