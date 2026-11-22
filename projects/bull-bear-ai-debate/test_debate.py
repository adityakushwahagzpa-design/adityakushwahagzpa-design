"""Tests for the debate pipeline, using a scripted stand-in for Claude."""

import json
import shutil
from types import SimpleNamespace

import pytest

import debate


class FakeClaude:
    """Returns scripted replies in order: bull, bear, bull rebuttal, bear rebuttal, judge."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        text = self.replies.pop(0)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


BULL = ("Data center computing grew 59% on Blackwell demand [M6] and networking grew 142% [M7]. "
        "Revenue reached $215.94bn with $130.39bn operating income [F4].")
BEAR = ("The stock fell 29.7% against a 5.8% SPY gain [P1][P2] with 41.2% volatility [P3]. "
        "A $4.5bn H20 charge shows China export risk [M4][R2]. Customers may also delay [R99].")
JUDGE = json.dumps({
    "verdict": "bull", "confidence": 64, "bull_score": 7.5, "bear_score": 6,
    "strongest_bull_point": "Revenue growth [F4]", "strongest_bear_point": "Export licences [R2]",
    "unsupported_claims": ["R99 is not in the pack"],
    "what_would_change_the_verdict": "Further China restrictions",
})


@pytest.fixture
def pack():
    return debate.load_pack("NVDA")


def test_evidence_ids_cover_all_sections(pack):
    ids = debate.evidence_ids(pack)
    assert {"R1", "M12", "F4", "P11"} <= ids
    assert "R99" not in ids


def test_citation_check_flags_invented_ids(pack):
    chk = debate.check_citations(BEAR, debate.evidence_ids(pack))
    assert chk["invented_ids"] == ["R99"]
    assert set(chk["sources_used"]) == {"P", "M", "R"}


def test_uncited_paragraph_is_flagged(pack):
    text = BULL + "\n\nThis company will obviously dominate artificial intelligence forever and ever more."
    chk = debate.check_citations(text, debate.evidence_ids(pack))
    assert len(chk["uncited_paragraphs"]) == 1


def test_judge_parsing_and_validation():
    v = debate.parse_judge("Here you go:\n" + JUDGE)
    assert v["verdict"] == "bull" and v["confidence"] == 64
    with pytest.raises(ValueError):
        debate.parse_judge('{"verdict": "maybe"}')


def test_full_debate_with_fake_claude(pack):
    fake = FakeClaude([BULL, BEAR, BULL, BEAR, JUDGE])
    res = debate.run_debate(fake, pack)
    assert len(fake.calls) == 5
    assert all(c["model"] == debate.MODEL for c in fake.calls)
    # evidence pack is in every agent call; judge sees the code citation check
    assert all("EVIDENCE PACK" in c["messages"][0]["content"] for c in fake.calls)
    assert "CODE CITATION CHECK" in fake.calls[-1]["messages"][0]["content"]
    # bear invented R99 twice (case + rebuttal) -> one unique ID -> minus 1 point
    assert res["citation_check"]["bear"]["invented_ids"] == ["R99"]
    assert res["judge"]["bear_score_after_checks"] == 5
    assert res["judge"]["bull_score_after_checks"] == 7.5


def test_referee_view_matches_numbers():
    views = {t: debate.referee_view(debate.load_pack(t))["view"] for t in debate.available_tickers()}
    assert views["TSLA"] == "leans bear"
    m = debate.metrics(debate.load_pack("NVDA"))
    assert m["revenue_growth_pct"] == 65.5 and m["excess_return_pts"] == -35.5


def test_dry_run_writes_outputs(tmp_path, monkeypatch):
    out = tmp_path / "outputs"
    shutil.copytree(debate.OUT, out)
    monkeypatch.setattr(debate, "OUT", out)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    summary = debate.main(["--dry-run"])
    assert summary["mode"] == "dry run"
    assert {r["ticker"] for r in summary["results"]} == {"AAPL", "NVDA", "TSLA"}
    assert (out / "NVDA_debate_prompts.md").read_text().count("Rule-based referee view") == 1
