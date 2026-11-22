"""Identity resolution: link core banking, CRM and card records that belong to the same person.

Steps
  1. Standardise: names (case, spaces, dots, word order), phones (last 10 digits), emails, dates.
  2. Blocking: only compare records that share a phone, an email, a date of birth, or the same name
     words, so 14,410 records need about 203,000 comparisons instead of 104 million.
  3. Matching: a logistic-regression model scores each pair from field similarities. It is trained
     on 30% of people and tested on the other 70%. A deterministic baseline (same phone or email)
     is scored the same way for comparison.
  4. Clustering: union-find joins matched pairs into one golden customer. Core banking is the system
     of record, so two core records are never merged.

Outputs: outputs/identity_crosswalk.csv (every source record -> golden customer id) and
outputs/identity_metrics.json.
"""
import json
import os
import re
from itertools import combinations

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler
from sklearn.linear_model import LogisticRegression

FEATURES = ["phone_eq", "email_eq", "dob_eq", "dob_conflict", "name_sort", "name_partial", "last_jw", "first_jw",
            "initial_ok", "city_eq"]
THRESHOLD = 0.5


# --------------------------------------------------------------------- standardise
def norm_name(s):
    s = re.sub(r"[^a-z ]", " ", str(s).lower())
    return " ".join(s.split())


def norm_phone(s):
    d = re.sub(r"\D", "", str(s)) if pd.notna(s) else ""
    return d[-10:] if len(d) >= 10 else None


def load_records(src="sources"):
    core = pd.read_csv(f"{src}/core_banking.csv")
    crm = pd.read_csv(f"{src}/crm_contacts.csv")
    card = pd.read_csv(f"{src}/card_system.csv")
    recs = pd.concat([
        pd.DataFrame({"source": "core", "record_id": core.core_id.astype(str), "name": core.full_name,
                      "phone": core.phone.astype(str), "email": core.email, "dob": core.date_of_birth, "city": core.city}),
        pd.DataFrame({"source": "crm", "record_id": crm.crm_id, "name": crm.contact_name, "phone": crm.mobile,
                      "email": crm.email, "dob": crm.dob, "city": crm.city}),
        pd.DataFrame({"source": "card", "record_id": card.card_customer_id, "name": card.cardholder_name,
                      "phone": card.phone.astype(str), "email": card.email,
                      "dob": pd.to_datetime(card.dob_ddmmyyyy, format="%d/%m/%Y").dt.strftime("%Y-%m-%d"), "city": None}),
    ], ignore_index=True)
    recs["name_n"] = recs.name.map(norm_name)
    recs["tokens"] = recs.name_n.str.split()
    recs["phone_n"] = recs.phone.map(norm_phone)
    recs["email_n"] = recs.email.str.lower().str.strip()
    recs["sorted_name"] = recs.tokens.map(lambda t: " ".join(sorted(x for x in t if len(x) > 1)))
    return recs.reset_index(drop=True)


# --------------------------------------------------------------------- blocking
def candidate_pairs(recs, max_block=60):
    pairs = set()
    keys = {"phone_n": recs.phone_n, "email_n": recs.email_n, "dob": recs.dob,
            "name": recs.sorted_name.where(recs.sorted_name.str.contains(" "))}
    for key, col in keys.items():
        for _, idx in col.dropna().groupby(col.dropna()).groups.items():
            idx = list(idx)
            if 1 < len(idx) <= max_block:
                pairs.update(combinations(sorted(idx), 2))
    # initials ("A. Sharma") block on last name + first letter
    init = recs.tokens.map(lambda t: f"{t[-1]}|{t[0][0]}" if len(t) >= 2 else None)
    init2 = recs.tokens.map(lambda t: f"{t[0]}|{t[-1][0]}" if len(t) >= 2 else None)  # swapped order
    for col in (init, init2):
        for _, idx in col.dropna().groupby(col.dropna()).groups.items():
            idx = list(idx)
            if 1 < len(idx) <= max_block:
                pairs.update(combinations(sorted(idx), 2))
    pairs = [(a, b) for a, b in pairs if not (recs.source[a] == "core" and recs.source[b] == "core")]
    return pd.DataFrame(pairs, columns=["a", "b"])


# --------------------------------------------------------------------- features
def pair_features(recs, pairs):
    A, B = recs.loc[pairs.a].reset_index(drop=True), recs.loc[pairs.b].reset_index(drop=True)
    f = pd.DataFrame(index=pairs.index)
    f["phone_eq"] = ((A.phone_n == B.phone_n) & A.phone_n.notna()).astype(int).values
    f["email_eq"] = ((A.email_n == B.email_n) & A.email_n.notna()).astype(int).values
    f["dob_eq"] = ((A.dob == B.dob) & A.dob.notna()).astype(int).values
    f["dob_conflict"] = ((A.dob != B.dob) & A.dob.notna() & B.dob.notna()).astype(int).values

    def per_pair(fn):
        return np.array([fn(x, y) for x, y in zip(A.itertuples(), B.itertuples())])

    f["name_sort"] = per_pair(lambda x, y: fuzz.token_sort_ratio(x.name_n, y.name_n) / 100)
    f["name_partial"] = per_pair(lambda x, y: fuzz.token_set_ratio(x.name_n, y.name_n) / 100)

    def parts(t):
        return (t[0], t[-1]) if len(t) >= 2 else (t[0] if t else "", "")

    def best_order(x, y):  # allow swapped first/last name
        (fx, lx), (fy, ly) = parts(x.tokens), parts(y.tokens)
        straight = JaroWinkler.similarity(lx, ly) + JaroWinkler.similarity(fx, fy)
        swapped = JaroWinkler.similarity(lx, fy) + JaroWinkler.similarity(fx, ly)
        return (lx, ly, fx, fy) if straight >= swapped else (lx, fy, fx, ly)

    orders = [best_order(x, y) for x, y in zip(A.itertuples(), B.itertuples())]
    f["last_jw"] = [JaroWinkler.similarity(a, b) for a, b, _, _ in orders]
    f["first_jw"] = [JaroWinkler.similarity(c, d) for _, _, c, d in orders]
    f["initial_ok"] = [int(bool(c) and bool(d) and c[0] == d[0]) for _, _, c, d in orders]
    f["city_eq"] = ((A.city == B.city) & A.city.notna()).astype(int).values
    return f


# --------------------------------------------------------------------- clustering
class UnionFind:
    def __init__(self, n, is_core):
        self.p = list(range(n))
        self.core = [bool(c) for c in is_core]  # does the cluster contain a core record?

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb or (self.core[ra] and self.core[rb]):
            return False
        self.p[rb] = ra
        self.core[ra] = self.core[ra] or self.core[rb]
        return True


def cluster(recs, pairs, prob, threshold=THRESHOLD):
    uf = UnionFind(len(recs), recs.source == "core")
    order = np.argsort(-prob)  # strongest matches first, so a weak link cannot block a strong one
    for i in order:
        if prob[i] < threshold:
            break
        uf.union(pairs.a.iat[i], pairs.b.iat[i])
    return np.array([uf.find(i) for i in range(len(recs))])


def golden_ids(recs, roots):
    gid = {}
    for root in np.unique(roots):
        members = np.where(roots == root)[0]
        core = recs.loc[members][recs.source.loc[members] == "core"]
        gid[root] = f"C{int(core.record_id.iloc[0]):05d}" if len(core) else f"N{root:06d}"
    return np.array([gid[r] for r in roots])


# --------------------------------------------------------------------- evaluation
def pairwise_scores(true_ids, pred_ids, mask):
    """Precision/recall/F1 over all record pairs among records in `mask`."""
    t = pd.Series(true_ids[mask])
    p = pd.Series(pred_ids[mask])
    def n_pairs(s): return int((s.value_counts() * (s.value_counts() - 1) // 2).sum())
    tp = n_pairs(t.astype(str) + "|" + p.astype(str))
    pp, tt = n_pairs(p), n_pairs(t)
    prec = tp / pp if pp else 1.0
    rec = tp / tt if tt else 1.0
    return {"precision": round(prec, 4), "recall": round(rec, 4), "f1": round(2 * prec * rec / (prec + rec), 4)}


def main(out="outputs"):
    os.makedirs(out, exist_ok=True)
    recs = load_records()
    truth = pd.read_csv("truth/identity_truth.csv", dtype=str)
    recs = recs.merge(truth, on=["source", "record_id"], how="left")
    pairs = candidate_pairs(recs)
    X = pair_features(recs, pairs)
    y = (recs.person_id.values[pairs.a] == recs.person_id.values[pairs.b]).astype(int)

    rng = np.random.default_rng(0)
    persons = recs.person_id.unique()
    train_people = set(rng.choice(persons, int(0.3 * len(persons)), replace=False))
    in_train = recs.person_id.isin(train_people).values
    tr = in_train[pairs.a] & in_train[pairs.b]
    model = LogisticRegression(max_iter=2000, C=1.0).fit(X[FEATURES][tr], y[tr])
    prob = model.predict_proba(X[FEATURES])[:, 1]

    roots = cluster(recs, pairs, prob)
    recs["golden_id"] = golden_ids(recs, roots)
    # deterministic baseline: same phone or same email
    base_prob = ((X.phone_eq == 1) | (X.email_eq == 1)).astype(float).values
    base_roots = cluster(recs, pairs, base_prob)

    test = ~in_train
    true_ids = recs.person_id.values
    ml = pairwise_scores(true_ids, roots, test)
    base = pairwise_scores(true_ids, base_roots, test)

    # record-level: is each CRM/card record attached to the right core customer (or correctly left alone)?
    non_core = test & (recs.source != "core").values
    expected = np.where(recs.person_id.str.startswith("P"), recs.person_id.str[1:].radd("C"), "NEW")
    got = np.where(recs.golden_id.str.startswith("C"), recs.golden_id, "NEW")
    link_acc = float((expected[non_core] == got[non_core]).mean())
    unmatched_ok = float((got[non_core & (expected == "NEW")] == "NEW").mean())

    metrics = {
        "records": {"core": int((recs.source == "core").sum()), "crm": int((recs.source == "crm").sum()),
                    "card": int((recs.source == "card").sum())},
        "candidate_pairs": int(len(pairs)), "all_possible_pairs": int(len(recs) * (len(recs) - 1) // 2),
        "golden_customers": int(recs.golden_id.nunique()),
        "true_people": int(recs.person_id.nunique()),
        "ml_matching_test": ml, "deterministic_baseline_test": base,
        "crm_card_records_linked_correctly_pct": round(100 * link_acc, 2),
        "non_customers_correctly_left_unlinked_pct": round(100 * unmatched_ok, 2),
        "model_weights": dict(zip(FEATURES, np.round(model.coef_[0], 2).tolist())),
    }
    json.dump(metrics, open(f"{out}/identity_metrics.json", "w"), indent=2)
    recs[["source", "record_id", "name", "golden_id"]].to_csv(f"{out}/identity_crosswalk.csv", index=False)
    print(json.dumps(metrics, indent=1))
    return recs, metrics


if __name__ == "__main__":
    main()
