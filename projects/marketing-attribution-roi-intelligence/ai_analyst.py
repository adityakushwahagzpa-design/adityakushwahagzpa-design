"""AI marketing analyst, powered by Claude with tool use.

Claude does not invent numbers: it answers by calling tools that read the attribution results,
run the marketing mix model's response curves and run the budget optimiser, then explains the
result for a CMO or CFO.

  python ai_analyst.py --memo                 # Claude writes outputs/AI_BUDGET_MEMO.md
  python ai_analyst.py --ask "What happens if we move 20% of Search budget to YouTube?"
  python ai_analyst.py                        # interactive chat

Needs ANTHROPIC_API_KEY. Without it, --memo prints the rule-based outputs/BUDGET_MEMO.md.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

import mmm
from generate_data import PAID

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
SYSTEM = """You are the marketing analytics lead at a fictional Indian D2C skincare brand. You advise the
CMO and CFO on where the marketing budget should go. Rules:
- Get every number from a tool. Never estimate or invent figures.
- For "what if we change spend" questions call simulate_spend_change; for "what is the best split"
  call optimise_budget. Say which channels have lift-test calibration and which do not.
- Explain the difference between average ROI (revenue per rupee spent so far) and marginal ROI
  (revenue from the next rupee): budget moves should follow marginal ROI.
- Revenue is not profit. Amounts are in Rs lakh unless stated.
- Lead with the answer, then the two or three numbers behind it, then one risk or caveat."""

TOOLS = [
    {"name": "get_attribution_comparison",
     "description": "Share of conversions credited to each channel by 8 attribution models (last touch, first touch, "
                    "linear, time decay, position based, Markov, Shapley, ML counterfactual), with each model's error "
                    "against the known true incremental share, for Jul-Sep 2026.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_channel_roi",
     "description": "Marketing mix model results per paid channel over 156 weeks: spend, revenue driven, average ROI "
                    "with P10-P90 range, marginal ROI, carry-over (decay), saturation point, and lift-test result if any.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_lift_tests",
     "description": "Experiments used to calibrate the marketing mix model: channel, design, dates, measured ROI and standard error.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "simulate_spend_change",
     "description": "Weekly revenue effect of changing each channel's weekly spend from today's level (average of the last "
                    "13 weeks), using the fitted response curves (steady state).",
     "input_schema": {"type": "object", "properties": {
         "changes_pct": {"type": "object", "description": "Map of channel to % change, e.g. {\"Google Search\": -20, "
                         "\"YouTube\": 25}. Channels: " + ", ".join(PAID),
                         "additionalProperties": {"type": "number"}}},
         "required": ["changes_pct"]}},
    {"name": "optimise_budget",
     "description": "Best split of a weekly budget across paid channels to maximise revenue, each channel kept within limits "
                    "around today's spend.",
     "input_schema": {"type": "object", "properties": {
         "total_weekly_budget_lakh": {"type": "number", "description": "Default: today's total weekly spend."},
         "min_change_pct": {"type": "number", "description": "Lowest allowed change per channel, e.g. -40. Default -40."},
         "max_change_pct": {"type": "number", "description": "Highest allowed change per channel, e.g. 40. Default 40."},
         "locked_channels": {"type": "array", "items": {"type": "string", "enum": PAID},
                             "description": "Channels whose spend must stay as it is."}}}},
]


class MarketingTools:
    def __init__(self, out="outputs", data="data"):
        self.out, self.data = out, data
        p = json.load(open(f"{out}/mmm_params.json"))
        self.params = p["params"]
        df = pd.read_csv(f"{data}/weekly_mmm.csv", parse_dates=["week"])
        self.current = mmm.current_weekly_spend(df)

    def get_attribution_comparison(self):
        a = pd.read_csv(f"{self.out}/attribution_comparison.csv", index_col=0)
        s = json.load(open(f"{self.out}/attribution_summary.json"))
        shares = a[[c for c in a.columns if c.endswith("_share_pct")]]
        return {"period": "Jul-Sep 2026", "conversions": s["conversions"], "users": s["users"],
                "share_pct_by_model": shares.round(1).to_dict(orient="index"),
                "mean_abs_error_vs_truth_pp": s["error_pp"], "most_accurate_model": s["best_model"]}

    def get_channel_roi(self):
        r = pd.read_csv(f"{self.out}/mmm_roi.csv")
        cols = ["channel", "spend_lakh", "revenue_lakh", "roi", "roi_p10", "roi_p90", "marginal_roi", "decay",
                "half_saturation", "lift_test_roi"]
        return {"period": "156 weeks, Oct 2023-Sep 2026",
                "channels": json.loads(r[cols].to_json(orient="records")),
                "current_weekly_spend_lakh": {c: round(v, 3) for c, v in self.current.items()}}

    def get_lift_tests(self):
        return json.loads(pd.read_csv(f"{self.data}/lift_tests.csv").to_json(orient="records"))

    def simulate_spend_change(self, changes_pct):
        bad = [c for c in changes_pct if c not in PAID]
        if bad:
            return {"error": f"unknown channels {bad}; use {PAID}"}
        cur = np.array([self.current[c] for c in PAID])
        new = np.array([self.current[c] * (1 + changes_pct.get(c, 0) / 100) for c in PAID]).clip(min=0)
        r0, r1 = mmm.weekly_revenue(cur, self.params), mmm.weekly_revenue(new, self.params)
        return {"current_weekly_spend_lakh": round(float(cur.sum()), 3), "new_weekly_spend_lakh": round(float(new.sum()), 3),
                "current_weekly_revenue_from_media_lakh": round(float(r0), 3),
                "new_weekly_revenue_from_media_lakh": round(float(r1), 3),
                "revenue_change_lakh_per_week": round(float(r1 - r0), 3),
                "revenue_change_per_13_weeks_lakh": round(float(r1 - r0) * 13, 2),
                "spend_change_lakh_per_week": round(float(new.sum() - cur.sum()), 3),
                "by_channel": [{"channel": c, "spend_now": round(float(a), 3), "spend_new": round(float(b), 3)}
                               for c, a, b in zip(PAID, cur, new)],
                "note": "Steady state after carry-over settles; revenue, not profit."}

    def optimise_budget(self, total_weekly_budget_lakh=None, min_change_pct=-40, max_change_pct=40, locked_channels=()):
        try:
            return mmm.optimise_budget(self.params, self.current, total_weekly_budget_lakh,
                                       min_change_pct / 100, max_change_pct / 100, tuple(locked_channels or ()))
        except ValueError as e:
            return {"error": str(e)}

    def call(self, name, args):
        return getattr(self, name)(**(args or {}))


def run_agent(client, tools, question, max_turns=8):
    """Tool-use loop: Claude requests tools, we run them, Claude writes the answer."""
    messages = [{"role": "user", "content": question}]
    for _ in range(max_turns):
        resp = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM, tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        results = []
        for b in resp.content:
            if getattr(b, "type", "") == "tool_use":
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(tools.call(b.name, b.input))})
        messages.append({"role": "user", "content": results})
    return "Stopped: too many tool calls."


MEMO_PROMPT = """Write a one-page budget memo for the CMO and CFO, about 300 words, in Markdown with these headings:
Recommendation, Why (attribution and ROI evidence), Next-quarter budget split (call optimise_budget), What-if checks
(simulate: Google Search -20%; YouTube +25%; all channels -10%), Risks and the next experiment to run."""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask")
    ap.add_argument("--memo", action="store_true")
    a = ap.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if a.memo:
            print("No ANTHROPIC_API_KEY set: showing the rule-based memo in outputs/BUDGET_MEMO.md\n")
            print(open("outputs/BUDGET_MEMO.md").read())
            return
        sys.exit("Set ANTHROPIC_API_KEY to use the AI analyst.")
    import anthropic
    client, tools = anthropic.Anthropic(), MarketingTools()
    if a.memo:
        text = run_agent(client, tools, MEMO_PROMPT)
        open("outputs/AI_BUDGET_MEMO.md", "w").write("# Marketing Budget Memo (written by Claude)\n\n" + text + "\n")
        print(text)
    elif a.ask:
        print(run_agent(client, tools, a.ask))
    else:
        print("Ask about channel ROI or the budget (blank line to quit).")
        while (q := input("\n> ").strip()):
            print(run_agent(client, tools, q))


if __name__ == "__main__":
    main()
