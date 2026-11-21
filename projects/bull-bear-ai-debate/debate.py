"""
Bull vs Bear AI debate on a US stock, judged by a third agent.

    python evidence.py            # build evidence packs from SEC EDGAR + yfinance
    python debate.py              # run the debate (needs ANTHROPIC_API_KEY)

Flow per ticker:
  1. Bull opening        (argues to buy, citing evidence IDs)
  2. Bear opening        (argues to avoid/sell, sees the bull case)
  3. Bull rebuttal       (answers the bear's strongest points)
  4. Bear rebuttal       (answers the bull's strongest points)
  5. Judge               (scores both sides, checks citations, returns JSON verdict)

Without ANTHROPIC_API_KEY the script runs in dry-run mode: it writes the full prompts and the
evidence pack to outputs/ so the debate can be reviewed or run later. Nothing is invented.
"""
import json
import os
import re
from pathlib import Path

from evidence import OUT, TICKERS, as_prompt_text

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
MAX_TOKENS = 900

RULES = ("Use ONLY the evidence provided. Cite evidence IDs in square brackets, e.g. [R3], [M5], [F2], [P1], after every claim. "
         "No outside facts, no price targets you cannot derive from the evidence. Be specific and concise (max 250 words).")
BULL = "You are a disciplined long-only equity analyst making the BULL case (buy) for this stock. " + RULES
BEAR = "You are a sceptical short-seller making the BEAR case (avoid or sell) for this stock. " + RULES
JUDGE = ("You are an impartial investment committee chair. Judge the debate below on evidence quality, not rhetoric. "
         "Penalise any claim not supported by a cited evidence ID or that misreads the evidence. "
         "Reply with JSON only, no prose, using exactly these keys: "
         '{"verdict": "bull" | "bear" | "too close to call", "confidence": 0-100, '
         '"bull_score": 0-10, "bear_score": 0-10, "strongest_bull_point": str, "strongest_bear_point": str, '
         '"unsupported_claims": [str], "what_would_change_the_verdict": str}')


def call(client, system, user):
    msg = client.messages.create(model=MODEL, max_tokens=MAX_TOKENS, system=system,
                                 messages=[{"role": "user", "content": user}])
    return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()


def run_debate(client, ticker):
    pack = json.loads((OUT / f"{ticker}_evidence.json").read_text())
    ev = as_prompt_text(pack)
    turns = []
    turns.append(("Bull opening", call(client, BULL, f"{ev}\n\nMake your opening bull case.")))
    turns.append(("Bear opening", call(client, BEAR, f"{ev}\n\nThe bull argued:\n{turns[0][1]}\n\nMake your opening bear case.")))
    turns.append(("Bull rebuttal", call(client, BULL, f"{ev}\n\nThe bear argued:\n{turns[1][1]}\n\nRebut the bear's two strongest points.")))
    turns.append(("Bear rebuttal", call(client, BEAR, f"{ev}\n\nThe bull's rebuttal:\n{turns[2][1]}\n\nRebut the bull's two strongest points.")))
    transcript = "\n\n".join(f"### {name}\n{text}" for name, text in turns)
    raw = call(client, JUDGE, f"{ev}\n\nDEBATE TRANSCRIPT:\n{transcript}")
    m = re.search(r"\{.*\}", raw, re.S)
    verdict = json.loads(m.group(0)) if m else {"verdict": "parse error", "raw": raw}
    verdict.update({"ticker": ticker, "model": MODEL, "10k_filed": pack["10k_filed"]})
    cites = re.findall(r"\[(?:R|M|F|P)\d+\]", transcript)
    verdict["citations_used"] = len(cites)
    verdict["distinct_evidence_cited"] = len(set(cites))

    md = [f"# {pack['company']} ({ticker}) — Bull vs Bear debate", "",
          f"Evidence: 10-K filed {pack['10k_filed']} ([link]({pack['10k_url']})), SEC XBRL facts, yfinance as of {pack['market_raw']['as of']}. Model: {MODEL}.", "",
          transcript, "", "## Judge verdict", "```json", json.dumps(verdict, indent=2), "```"]
    (OUT / f"{ticker}_debate.md").write_text("\n".join(md))
    (OUT / f"{ticker}_verdict.json").write_text(json.dumps(verdict, indent=2))
    print(f"{ticker}: {verdict.get('verdict')} ({verdict.get('confidence')}% confidence)")
    return verdict


def dry_run(ticker):
    pack = json.loads((OUT / f"{ticker}_evidence.json").read_text())
    ev = as_prompt_text(pack)
    md = [f"# {pack['company']} ({ticker}) — debate prompts (dry run)", "",
          "> No ANTHROPIC_API_KEY was set, so the agents were not called. These are the exact prompts the agents receive.", "",
          "## Evidence pack", "```", ev, "```", "", "## Agent system prompts",
          f"**Bull:** {BULL}", "", f"**Bear:** {BEAR}", "", f"**Judge:** {JUDGE}"]
    (OUT / f"{ticker}_debate_prompts.md").write_text("\n".join(md))
    print(f"{ticker}: dry run written")


def main():
    key = os.environ.get("ANTHROPIC_API_KEY")
    client = None
    if key:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
    results = []
    for t in [x.strip() for x in TICKERS]:
        if not (OUT / f"{t}_evidence.json").exists():
            print(f"{t}: no evidence pack, run evidence.py first")
            continue
        results.append(run_debate(client, t) if client else dry_run(t) or {"ticker": t, "verdict": "dry run"})
    (OUT / "debate_summary.json").write_text(json.dumps({"mode": "live" if client else "dry run", "model": MODEL,
                                                         "results": results}, indent=2))


if __name__ == "__main__":
    main()
