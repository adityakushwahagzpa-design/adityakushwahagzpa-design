"""Bull vs Bear AI Debate.

Three Claude agents debate whether to own a stock, using only an evidence pack
built from the company's latest 10-K (risk factors and MD&A), SEC XBRL
financials and one year of market data:

  1. Bull agent   - makes the buy case, citing evidence IDs such as [M6] or [F4]
  2. Bear agent   - makes the avoid/sell case, with the same rule
  3. Rebuttal     - each side answers the other's strongest points
  4. Judge agent  - scores both sides on evidence quality and returns JSON

Every citation is checked in code: an ID that is not in the evidence pack is
flagged as invented, and a paragraph with no citation is flagged as unsupported.

Without ANTHROPIC_API_KEY the script runs in dry-run mode: it writes the exact
prompts each agent would receive and a rule-based referee view computed from the
same numbers, so the project still runs end to end.

Usage:
    python debate.py                 # all evidence packs in outputs/
    python debate.py --tickers NVDA  # one stock
    python debate.py --dry-run       # never call the API
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "outputs"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")

CITE_RE = re.compile(r"\[([RMFP]\d+)\]")

RULES = (
    "Use ONLY the evidence provided. Cite evidence IDs in square brackets, e.g. "
    "[R3], [M5], [F2], [P1], after every claim. No outside facts, no price targets "
    "you cannot derive from the evidence. Be specific and concise (max 250 words)."
)
BULL_SYSTEM = (
    "You are a disciplined long-only equity analyst making the BULL case (buy) "
    "for this stock. " + RULES
)
BEAR_SYSTEM = (
    "You are a sceptical short-seller making the BEAR case (avoid or sell) for "
    "this stock. " + RULES
)
REBUTTAL_TASK = (
    "Here is your opponent's case. Rebut their two strongest points using only the "
    "evidence pack, citing IDs after every claim (max 150 words).\n\nOPPONENT:\n{other}"
)
JUDGE_SYSTEM = (
    "You are an impartial investment committee chair. Judge the debate below on "
    "evidence quality, not rhetoric. Penalise any claim not supported by a cited "
    "evidence ID or that misreads the evidence. Reply with JSON only, no prose, "
    'using exactly these keys: {"verdict": "bull" | "bear" | "too close to call", '
    '"confidence": 0-100, "bull_score": 0-10, "bear_score": 0-10, '
    '"strongest_bull_point": str, "strongest_bear_point": str, '
    '"unsupported_claims": [str], "what_would_change_the_verdict": str}'
)
JUDGE_KEYS = {
    "verdict", "confidence", "bull_score", "bear_score", "strongest_bull_point",
    "strongest_bear_point", "unsupported_claims", "what_would_change_the_verdict",
}


# ---------------------------------------------------------------- evidence
def load_pack(ticker: str, folder: Path | None = None) -> dict:
    folder = folder or OUT
    return json.loads((folder / f"{ticker}_evidence.json").read_text())


def available_tickers(folder: Path | None = None) -> list[str]:
    folder = folder or OUT
    return sorted(p.name.split("_")[0] for p in folder.glob("*_evidence.json"))


def evidence_ids(pack: dict) -> set[str]:
    ids = set()
    for key in ("risk_evidence", "mda_evidence", "financials", "market"):
        for line in pack[key]:
            m = re.match(r"\[([RMFP]\d+)\]", line)
            if m:
                ids.add(m.group(1))
    return ids


def evidence_text(pack: dict) -> str:
    return "\n".join([
        f"COMPANY: {pack['company']} ({pack['ticker']}), 10-K for period "
        f"{pack['period']} filed {pack['10k_filed']}",
        "", "RISK FACTORS (Item 1A excerpts):", *pack["risk_evidence"],
        "", "MANAGEMENT DISCUSSION (Item 7 excerpts):", *pack["mda_evidence"],
        "", "FINANCIALS (SEC XBRL, USD billions):", *pack["financials"],
        "", "MARKET DATA:", *pack["market"],
    ])


# ---------------------------------------------------------------- checks
def check_citations(text: str, valid_ids: set[str]) -> dict:
    """Count citations, invented IDs and paragraphs with no citation."""
    cited = CITE_RE.findall(text)
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if len(p.split()) >= 8]
    uncited = [p[:90] for p in paras if not CITE_RE.search(p)]
    invented = sorted(set(c for c in cited if c not in valid_ids))
    return {
        "citations": len(cited),
        "unique_ids": len(set(cited)),
        "invented_ids": invented,
        "uncited_paragraphs": uncited,
        "sources_used": sorted({c[0] for c in cited if c in valid_ids}),
    }


def parse_judge(raw: str) -> dict:
    """Pull the JSON object out of the judge reply and validate it."""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("judge did not return JSON")
    verdict = json.loads(m.group(0))
    missing = JUDGE_KEYS - verdict.keys()
    if missing:
        raise ValueError(f"judge JSON missing keys: {sorted(missing)}")
    if verdict["verdict"] not in ("bull", "bear", "too close to call"):
        raise ValueError(f"bad verdict: {verdict['verdict']}")
    for k, hi in (("confidence", 100), ("bull_score", 10), ("bear_score", 10)):
        verdict[k] = max(0, min(hi, float(verdict[k])))
    return verdict


def apply_citation_penalty(verdict: dict, bull_chk: dict, bear_chk: dict) -> dict:
    """Code-level referee: each invented ID costs a side 1 point."""
    verdict = dict(verdict)
    verdict["bull_score_after_checks"] = max(0.0, verdict["bull_score"] - len(bull_chk["invented_ids"]))
    verdict["bear_score_after_checks"] = max(0.0, verdict["bear_score"] - len(bear_chk["invented_ids"]))
    return verdict


# ---------------------------------------------------------------- metrics
def metrics(pack: dict) -> dict:
    fin = pack["financials_raw"]
    mkt = pack["market_raw"]
    last, prev = fin[-1], fin[-2]
    return {
        "revenue_growth_pct": round((last["Revenue"] / prev["Revenue"] - 1) * 100, 1),
        "net_margin_pct": round(last["Net income"] / last["Revenue"] * 100, 1),
        "cash_conversion": round(last["Cash from operations"] / last["Net income"], 2),
        "excess_return_pts": round(mkt["1y return %"] - mkt["SPY 1y return %"], 1),
        "volatility_pct": mkt["annualised volatility %"],
        "forward_pe": mkt["forward P/E"],
        "risk_kwords": round(pack["risk_section_words"] / 1000, 1),
    }


def referee_view(pack: dict) -> dict:
    """Transparent rule-based baseline used in dry runs (not the AI verdict)."""
    m = metrics(pack)
    bull, bear = [], []
    (bull if m["revenue_growth_pct"] > 10 else bear if m["revenue_growth_pct"] < 0 else []).append(
        f"Revenue growth {m['revenue_growth_pct']}% [F]")
    (bull if m["net_margin_pct"] > 20 else bear if m["net_margin_pct"] < 8 else []).append(
        f"Net margin {m['net_margin_pct']}% [F]")
    (bull if m["cash_conversion"] >= 0.9 else bear).append(
        f"Cash from operations / net income {m['cash_conversion']}x [F]")
    (bull if m["forward_pe"] < 25 else bear if m["forward_pe"] > 50 else []).append(
        f"Forward P/E {m['forward_pe']} [P]")
    (bull if m["excess_return_pts"] > 0 else bear).append(
        f"1-year return vs SPY {m['excess_return_pts']:+} pts [P]")
    (bear if m["volatility_pct"] > 40 else bull if m["volatility_pct"] < 30 else []).append(
        f"Volatility {m['volatility_pct']}% [P]")
    lean = len(bull) - len(bear)
    view = "leans bull" if lean >= 2 else "leans bear" if lean <= -2 else "mixed"
    return {"view": view, "bull_signals": bull, "bear_signals": bear, "metrics": m}


# ---------------------------------------------------------------- agents
def ask(client, system: str, user: str, max_tokens: int = 700) -> str:
    resp = client.messages.create(
        model=MODEL, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


def run_debate(client, pack: dict) -> dict:
    ev = evidence_text(pack)
    ids = evidence_ids(pack)
    pack_msg = f"EVIDENCE PACK:\n{ev}"

    bull = ask(client, BULL_SYSTEM, pack_msg)
    bear = ask(client, BEAR_SYSTEM, pack_msg)
    bull_reb = ask(client, BULL_SYSTEM, pack_msg + "\n\n" + REBUTTAL_TASK.format(other=bear), 450)
    bear_reb = ask(client, BEAR_SYSTEM, pack_msg + "\n\n" + REBUTTAL_TASK.format(other=bull), 450)

    bull_all, bear_all = bull + "\n\n" + bull_reb, bear + "\n\n" + bear_reb
    bull_chk, bear_chk = check_citations(bull_all, ids), check_citations(bear_all, ids)

    transcript = (
        f"{pack_msg}\n\nBULL CASE:\n{bull}\n\nBEAR CASE:\n{bear}\n\n"
        f"BULL REBUTTAL:\n{bull_reb}\n\nBEAR REBUTTAL:\n{bear_reb}\n\n"
        f"CODE CITATION CHECK: bull invented IDs {bull_chk['invented_ids']}, "
        f"bear invented IDs {bear_chk['invented_ids']}"
    )
    verdict = parse_judge(ask(client, JUDGE_SYSTEM, transcript, 900))
    verdict = apply_citation_penalty(verdict, bull_chk, bear_chk)
    return {
        "ticker": pack["ticker"], "company": pack["company"],
        "bull": bull, "bear": bear, "bull_rebuttal": bull_reb, "bear_rebuttal": bear_reb,
        "citation_check": {"bull": bull_chk, "bear": bear_chk},
        "judge": verdict, "referee": referee_view(pack),
    }


# ---------------------------------------------------------------- outputs
def write_debate_md(res: dict, folder: Path | None = None) -> Path:
    folder = folder or OUT
    j, c, r = res["judge"], res["citation_check"], res["referee"]
    md = [
        f"# {res['company']} ({res['ticker']}): Bull vs Bear debate", "",
        f"**Verdict: {j['verdict'].upper()}** (confidence {j['confidence']:.0f}/100) · "
        f"Bull {j['bull_score_after_checks']:.1f}/10 · Bear {j['bear_score_after_checks']:.1f}/10 · "
        f"model `{MODEL}`", "",
        f"- Strongest bull point: {j['strongest_bull_point']}",
        f"- Strongest bear point: {j['strongest_bear_point']}",
        f"- What would change the verdict: {j['what_would_change_the_verdict']}",
        f"- Rule-based referee view: {r['view']}", "",
        "## Bull case", res["bull"], "", "## Bear case", res["bear"], "",
        "## Bull rebuttal", res["bull_rebuttal"], "", "## Bear rebuttal", res["bear_rebuttal"], "",
        "## Citation check (done in code)", "",
        "| Side | Citations | Unique IDs | Invented IDs | Uncited paragraphs |",
        "|:--|--:|--:|:--|--:|",
    ]
    for side in ("bull", "bear"):
        k = c[side]
        md.append(f"| {side.title()} | {k['citations']} | {k['unique_ids']} | "
                  f"{', '.join(k['invented_ids']) or 'none'} | {len(k['uncited_paragraphs'])} |")
    if j["unsupported_claims"]:
        md += ["", "**Claims the judge marked unsupported:**", *[f"- {u}" for u in j["unsupported_claims"]]]
    path = folder / f"{res['ticker']}_debate.md"
    path.write_text("\n".join(md) + "\n")
    return path


def write_prompts_md(pack: dict, folder: Path | None = None) -> Path:
    folder = folder or OUT
    ref = referee_view(pack)
    md = [
        f"# {pack['company']} ({pack['ticker']}) — debate prompts (dry run)", "",
        "> No ANTHROPIC_API_KEY was set, so the agents were not called. These are the "
        "exact prompts the agents receive.", "",
        "## Evidence pack", "```", evidence_text(pack), "```", "",
        "## Agent system prompts",
        f"**Bull:** {BULL_SYSTEM}", "", f"**Bear:** {BEAR_SYSTEM}", "",
        f"**Rebuttal task:** {REBUTTAL_TASK.split(chr(10))[0]}", "",
        f"**Judge:** {JUDGE_SYSTEM}", "",
        f"## Rule-based referee view: {ref['view']}", "",
        "Bull signals: " + ("; ".join(ref["bull_signals"]) or "none"), "",
        "Bear signals: " + ("; ".join(ref["bear_signals"]) or "none"),
    ]
    path = folder / f"{pack['ticker']}_debate_prompts.md"
    path.write_text("\n".join(md) + "\n")
    return path


def write_scorecard(packs: list[dict], folder: Path | None = None) -> None:
    folder = folder or OUT
    rows = []
    for p in packs:
        m = metrics(p)
        rows.append([p["ticker"], m["revenue_growth_pct"], m["net_margin_pct"],
                     m["excess_return_pts"], m["volatility_pct"], m["risk_kwords"]])
    header = ["ticker", "Revenue growth, latest FY %", "Net margin, latest FY %",
              "1y return vs SPY, pts", "Volatility %", "Risk factors (k words)"]
    with open(folder / "evidence_scorecard.csv", "w", newline="") as f:
        csv.writer(f).writerows([header, *rows])

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 5, figsize=(15, 3.6))
    colors = ["#2a6f97", "#c44536", "#6a994e", "#8d6a9f", "#e09f3e"]
    for i, ax in enumerate(axes):
        vals = [r[i + 1] for r in rows]
        ax.bar([r[0] for r in rows], vals, color=colors[i])
        ax.axhline(0, color="#444", lw=0.8)
        ax.set_title(header[i + 1], fontsize=10)
        for x, v in enumerate(vals):
            ax.text(x, v, f"{v:g}", ha="center", va="bottom" if v >= 0 else "top", fontsize=9)
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle("Evidence scorecard: what each side has to work with", fontsize=12)
    fig.tight_layout()
    fig.savefig(folder / "evidence_scorecard.png", dpi=150)
    plt.close(fig)


def main(argv=None, client=None) -> dict:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tickers", nargs="*")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    tickers = args.tickers or available_tickers()
    packs = [load_pack(t) for t in tickers]
    write_scorecard(packs)

    live = client is not None or (not args.dry_run and os.environ.get("ANTHROPIC_API_KEY"))
    if live and client is None:
        import anthropic
        client = anthropic.Anthropic()

    results = []
    for pack in packs:
        write_prompts_md(pack)
        ref = referee_view(pack)
        if live:
            try:
                res = run_debate(client, pack)
                write_debate_md(res)
                j = res["judge"]
                results.append({
                    "ticker": pack["ticker"], "verdict": j["verdict"], "confidence": j["confidence"],
                    "bull_score": j["bull_score_after_checks"], "bear_score": j["bear_score_after_checks"],
                    "invented_ids": res["citation_check"]["bull"]["invented_ids"]
                    + res["citation_check"]["bear"]["invented_ids"],
                    "referee_view": ref["view"],
                })
                print(f"{pack['ticker']}: {j['verdict']} ({j['confidence']:.0f}%) | referee {ref['view']}")
                continue
            except Exception as e:  # keep going for the other tickers
                reason = f"live run failed: {type(e).__name__}"
        else:
            reason = "no ANTHROPIC_API_KEY"
        results.append({"ticker": pack["ticker"], "verdict": "dry run", "reason": reason,
                        "referee_view": ref["view"]})
        print(f"{pack['ticker']}: dry run ({reason}) | referee {ref['view']}")

    summary = {"mode": "live" if live else "dry run", "model": MODEL, "results": results}
    (OUT / "debate_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    main()
