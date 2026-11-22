"""Tests for identity resolution, the 360 table, the models' guardrails and the RM assistant."""
import json
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import features as ft
import identity_resolution as ir
import models
import rm_assistant as rm

CUR = pd.read_csv("outputs/customer_360.csv", index_col="customer_id")


# ---------------------------------------------------------------- identity resolution
def test_standardisation():
    assert ir.norm_phone("+91-98765 43210") == ir.norm_phone("09876543210") == "9876543210"
    assert ir.norm_phone("12345") is None
    assert ir.norm_name("  A. SHARMA ") == "a sharma"


def test_union_find_never_merges_two_core_records():
    uf = ir.UnionFind(4, [True, True, False, False])
    assert uf.union(0, 2) and uf.union(1, 3)
    assert not uf.union(2, 3)  # would join two core customers through their linked records
    assert uf.find(0) != uf.find(1)


def test_pairwise_scores():
    true = np.array(["a", "a", "b", "b"])
    perfect = ir.pairwise_scores(true, np.array([1, 1, 2, 2]), np.ones(4, bool))
    merged = ir.pairwise_scores(true, np.array([1, 1, 1, 1]), np.ones(4, bool))
    assert perfect["f1"] == 1.0
    assert merged["recall"] == 1.0 and merged["precision"] == pytest.approx(2 / 6, abs=1e-3)


def test_identity_results():
    m = json.load(open("outputs/identity_metrics.json"))
    assert m["ml_matching_test"]["f1"] > 0.98 > m["deterministic_baseline_test"]["f1"]
    assert m["crm_card_records_linked_correctly_pct"] > 97
    assert m["candidate_pairs"] < 0.01 * m["all_possible_pairs"]  # blocking keeps comparisons small


# ---------------------------------------------------------------- 360 table
def test_no_future_data_leaks_into_features():
    d = ft.load()
    before = ft.build(d, "2025-09")
    d2 = dict(d)
    act = d["activity"].copy()
    act.loc[act.month > "2025-09", ["spend", "txn_count"]] *= 100  # change only the future
    d2["activity"] = act
    after = ft.build(d2, "2025-09")
    pd.testing.assert_frame_equal(before, after)


def test_churn_labels_agree_with_truth():
    d = ft.load()
    f = ft.build(d, "2026-03", with_labels=True)
    truth = pd.read_csv("truth/churn_truth.csv").set_index("customer_id").churn_month.reindex(f.index)
    in_window = truth.between("2026-04", "2026-08").astype(int)  # left early enough to be absent in Aug-Sep
    assert (f.churn_6m[in_window == 1] == 1).all()


def test_product_labels_only_for_products_not_held():
    f = ft.build(ft.load(), "2026-03", with_labels=True)
    assert f.loc[f.has_fixed_deposit == 1, "takes_fixed_deposit_6m"].isna().all()


# ---------------------------------------------------------------- intelligence layer
def test_guardrail_no_credit_offers_for_risky_customers():
    risky = CUR[(CUR.max_days_past_due > 30) | (CUR.kyc_risk == "High")]
    assert len(risky) > 0
    assert not risky.next_best_action.isin(["Offer Personal Loan", "Offer Credit Card"]).any()


def test_clv_falls_as_churn_risk_rises():
    one = CUR.iloc[[0]]
    low, _ = models.lifetime_value(one, pd.Series([0.01], index=one.index))
    high, _ = models.lifetime_value(one, pd.Series([0.40], index=one.index))
    assert low.iloc[0] > high.iloc[0]


def test_model_validation_beats_chance_and_rules():
    v = json.load(open("outputs/platform_summary.json"))["validation"]
    assert v["churn"]["auc"] > 0.65 and v["churn"]["top_decile_lift"] > 2
    rb = v["churn"]["rule_baseline"]
    assert rb["model_recall_same_list_size_pct"] > rb["recall_pct"]
    assert all(v[p]["auc"] > 0.5 for p in ft.PRODUCTS)


def test_every_segment_has_a_unique_name():
    assert CUR.segment_360.nunique() == 5


# ---------------------------------------------------------------- RM assistant
def test_tools():
    t = rm.C360Tools()
    cid = int(CUR.index[0])
    p = t.get_customer_360(cid)
    assert p["customer_id"] == cid and 0 <= p["p_churn"] <= 1
    assert "error" in t.get_customer_360(-1)
    hits = t.find_customers(region="South", min_churn_risk=0.1, sort_by="clv_5y", limit=5)["customers"]
    assert len(hits) <= 5 and all(h["p_churn"] >= 0.1 for h in hits)
    assert "Do not" in rm.rule_brief(t.get_customer_360(int(CUR[CUR.kyc_risk == "High"].index[0])))


class FakeClaude:
    def __init__(self, cid):
        self.cid, self.turn, self.seen = cid, 0, None
        self.messages = self

    def create(self, **kw):
        self.turn += 1
        if self.turn == 1:
            return SimpleNamespace(stop_reason="tool_use", content=[
                SimpleNamespace(type="tool_use", id="a", name="get_customer_360", input={"customer_id": self.cid})])
        self.seen = json.loads(kw["messages"][-1]["content"][0]["content"])
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Brief ready.")])


def test_agent_loop():
    cid = int(CUR.index[5])
    fake = FakeClaude(cid)
    assert rm.run_agent(fake, rm.C360Tools(), f"Brief for {cid}") == "Brief ready."
    assert fake.seen["customer_id"] == cid
