"""AI relationship-manager assistant on top of the Customer 360, powered by Claude with tool use.

  python rm_assistant.py --brief 1870          # Claude writes a meeting brief for customer 1870
  python rm_assistant.py --ask "Which high-value customers in Pune are most likely to leave?"
  python rm_assistant.py                       # chat

Claude gets every fact from tools that read the 360 table and model scores; it does not invent
figures. Without ANTHROPIC_API_KEY, --brief writes the rule-based brief instead (rule_brief below).
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

import features as ft

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
SYSTEM = """You are an assistant to relationship managers (RMs) at a fictional Indian retail bank. You
prepare customer briefs and answer portfolio questions using the bank's Customer 360 data. Rules:
- Get every fact and number from a tool. Never guess a customer's details.
- Scores are model estimates: say "churn risk 18%" not "will leave". Explain the main drivers you see.
- Respect the guardrails in the data: never suggest a loan or credit card for a customer with more
  than 30 days past due or High KYC risk.
- Be concise and practical. Amounts in rupees with lakh/crore. A brief has: Snapshot, What has changed,
  Risks, Recommended conversation (with the next best action), and Do not."""

FILTERS = {
    "segment": {"type": "string", "description": "Affluent savers, Borrowers, Everyday banking core, Low-engagement, Newer customers"},
    "city": {"type": "string"}, "region": {"type": "string", "enum": ["North", "South", "East", "West"]},
    "min_churn_risk": {"type": "number", "description": "0-1"}, "min_clv_lakh": {"type": "number"},
    "action": {"type": "string", "description": "Next best action, e.g. 'RM retention call', 'Offer Fixed Deposit'"},
    "sort_by": {"type": "string", "enum": ["p_churn", "clv_5y", "action_value", "avg_balance_3m"]},
    "limit": {"type": "integer", "description": "Default 10, max 50"},
}
TOOLS = [
    {"name": "get_customer_360", "description": "Full 360 profile of one customer: profile, products, behaviour and trends, "
     "service history, loan health, model scores, lifetime value and next best action.",
     "input_schema": {"type": "object", "properties": {"customer_id": {"type": "integer"}}, "required": ["customer_id"]}},
    {"name": "find_customers", "description": "List customers matching filters, sorted and limited.",
     "input_schema": {"type": "object", "properties": FILTERS}},
    {"name": "get_segment_profile", "description": "Size, value, churn risk and typical behaviour of each segment.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "get_portfolio_summary", "description": "Totals: customers, lifetime value, value at risk, actions planned, "
     "model accuracy.", "input_schema": {"type": "object", "properties": {}}},
]

PROFILE_COLS = ["full_name", "segment_360", "segment", "city", "region", "age", "tenure_years", "kyc_risk", "n_products",
                "has_savings", "has_current", "has_fixed_deposit", "has_loan", "has_credit_card", "has_personal_loan",
                "has_insurance", "avg_balance_3m", "balance_trend", "spend_3m", "spend_trend", "txn_count_3m",
                "txn_count_trend", "app_logins_3m", "app_logins_trend", "digital_share", "fees_6m", "complaints_6m",
                "service_requests_6m", "last_nps", "loan_outstanding", "max_days_past_due", "emi_on_time_pct",
                "p_churn", "p_Fixed Deposit", "p_Credit Card", "p_Personal Loan", "p_Insurance", "clv_5y",
                "annual_margin", "next_best_action", "action_reason", "action_value"]


def clean(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 4)
    return v


class C360Tools:
    def __init__(self, path="outputs/customer_360.csv", summary="outputs/platform_summary.json"):
        self.df = pd.read_csv(path, index_col="customer_id")
        self.summary = json.load(open(summary))

    def get_customer_360(self, customer_id):
        if customer_id not in self.df.index:
            return {"error": f"customer {customer_id} not found among active customers"}
        r = self.df.loc[customer_id]
        out = {k: clean(r[k]) for k in PROFILE_COLS if k in r}
        out["customer_id"] = int(customer_id)
        out["churn_risk_percentile"] = round(float((self.df.p_churn < r.p_churn).mean() * 100), 1)
        out["clv_percentile"] = round(float((self.df.clv_5y < r.clv_5y).mean() * 100), 1)
        out["guardrail_no_credit_products"] = bool(r.max_days_past_due > 30 or r.kyc_risk == "High")
        return out

    def find_customers(self, segment=None, city=None, region=None, min_churn_risk=None, min_clv_lakh=None, action=None,
                       sort_by="p_churn", limit=10):
        d = self.df
        if segment: d = d[d.segment_360.str.lower() == segment.lower()]
        if city: d = d[d.city.str.lower() == city.lower()]
        if region: d = d[d.region == region]
        if min_churn_risk is not None: d = d[d.p_churn >= min_churn_risk]
        if min_clv_lakh is not None: d = d[d.clv_5y >= min_clv_lakh * 1e5]
        if action: d = d[d.next_best_action.str.lower() == action.lower()]
        d = d.sort_values(sort_by or "p_churn", ascending=False).head(min(int(limit or 10), 50))
        cols = ["full_name", "segment_360", "city", "p_churn", "clv_5y", "next_best_action", "action_reason"]
        return {"matches": len(d), "customers": [{"customer_id": int(i), **{c: clean(r[c]) for c in cols}} for i, r in d.iterrows()]}

    def get_segment_profile(self):
        return self.summary["segments"]

    def get_portfolio_summary(self):
        s = self.summary
        return {k: s[k] for k in ("current_asof", "customers_scored", "card_only_customers_found", "total_clv_crore",
                                  "clv_at_risk_top10_churn_crore", "actions", "action_value_lakh")} | {
            "model_accuracy": {k: {m: v[m] for m in ("auc", "top_decile_lift")} for k, v in s["validation"].items()}}

    def call(self, name, args):
        return getattr(self, name)(**(args or {}))


def run_agent(client, tools, question, max_turns=8):
    messages = [{"role": "user", "content": question}]
    for _ in range(max_turns):
        resp = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM, tools=TOOLS, messages=messages)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        results = [{"type": "tool_result", "tool_use_id": b.id, "content": json.dumps(tools.call(b.name, b.input), default=str)}
                   for b in resp.content if getattr(b, "type", "") == "tool_use"]
        messages.append({"role": "user", "content": results})
    return "Stopped: too many tool calls."


def lakh(x):
    return f"Rs {x / 1e5:,.2f} lakh" if x >= 1e5 else f"Rs {x:,.0f}"


def trend_word(t):
    return "up" if t > 1.1 else "down" if t < 0.9 else "flat"


def rule_brief(p):
    """Template brief from the same tool output, used when no API key is set."""
    held = [n for n, k in [("Savings", "has_savings"), ("Current", "has_current"), ("Fixed Deposit", "has_fixed_deposit"),
                           ("Loan", "has_loan"), ("Credit Card", "has_credit_card"), ("Personal Loan", "has_personal_loan"),
                           ("Insurance", "has_insurance")] if p.get(k)]
    changes = [f"Spend {trend_word(p['spend_trend'])} ({p['spend_trend']:.2f}x the previous 3 months)",
               f"Transactions {trend_word(p['txn_count_trend'])} ({p['txn_count_trend']:.2f}x)",
               f"App logins {trend_word(p['app_logins_trend'])} ({p['app_logins_trend']:.2f}x)"]
    risks = []
    if p["p_churn"] >= 0.1: risks.append(f"Churn risk {p['p_churn']:.0%} (higher than {p['churn_risk_percentile']:.0f}% of customers)")
    if p["complaints_6m"]: risks.append(f"{p['complaints_6m']} complaint(s) in the last 6 months")
    if p["fees_6m"] >= 600: risks.append(f"Rs {p['fees_6m']:,.0f} in fees charged in 6 months")
    if p["max_days_past_due"]: risks.append(f"Loan {p['max_days_past_due']:.0f} days past due")
    if p.get("last_nps") is not None and p["last_nps"] <= 6: risks.append(f"Last NPS score {p['last_nps']:.0f}/10 (detractor)")
    blocked = {"Personal Loan", "Credit Card"} if p["guardrail_no_credit_products"] else set()
    props = sorted(((k[2:], v) for k, v in p.items() if k.startswith("p_") and k != "p_churn" and v is not None
                    and not p.get("has_" + k[2:].lower().replace(" ", "_")) and k[2:] not in blocked), key=lambda x: -x[1])
    lines = [f"# Customer brief: {p['full_name']} (ID {p['customer_id']})", "",
             "*Rule-based brief. `python rm_assistant.py --brief <id>` has Claude write it from the same tools.*", "",
             "## Snapshot",
             f"- {p['segment']} customer in {p['city']}, age {p['age']:.0f}, with the bank {p['tenure_years']:.1f} years; "
             f"segment: **{p['segment_360']}**; KYC risk {p['kyc_risk']}",
             f"- Products ({p['n_products']}): {', '.join(held) or 'none'}",
             f"- Average balance {lakh(p['avg_balance_3m'])}; monthly spend {lakh(p['spend_3m'])}; "
             f"digital share {p['digital_share']:.0%}",
             f"- 5-year lifetime value {lakh(p['clv_5y'])} (top {100 - p['clv_percentile']:.0f}%)", "",
             "## What has changed (last 3 months vs the 3 before)", *[f"- {c}" for c in changes], "",
             "## Risks", *([f"- {r}" for r in risks] or ["- No major risk signals"]), "",
             "## Recommended conversation",
             f"- **Next best action: {p['next_best_action']}** ({p['action_reason']})",
             "- Product propensity (products not yet held): " + (", ".join(f"{n} {v:.0%}" for n, v in props[:3]) or "none eligible"), ""]
    if p["guardrail_no_credit_products"]:
        lines += ["## Do not", "- Offer loans or credit cards (overdue loan or High KYC risk)", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--brief", type=int)
    ap.add_argument("--ask")
    a = ap.parse_args()
    tools = C360Tools()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        if a.brief:
            print(rule_brief(tools.get_customer_360(a.brief)))
            return
        sys.exit("Set ANTHROPIC_API_KEY to use the AI assistant (or use --brief for a rule-based brief).")
    import anthropic
    client = anthropic.Anthropic()
    if a.brief:
        print(run_agent(client, tools, f"Prepare a meeting brief for customer {a.brief}."))
    elif a.ask:
        print(run_agent(client, tools, a.ask))
    else:
        print("Ask about a customer or the portfolio (blank line to quit).")
        while (q := input("\n> ").strip()):
            print(run_agent(client, tools, q))


if __name__ == "__main__":
    main()
