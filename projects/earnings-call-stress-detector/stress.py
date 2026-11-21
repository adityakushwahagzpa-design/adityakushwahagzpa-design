"""
Earnings Call Stress Detector (text version)

Scores how "stressed" management sounds in the Q&A part of real S&P 500 earnings calls,
then checks whether stressed calls are followed by worse stock reactions.

Signals per call (executive answers in the Q&A only):
  * FinBERT tone (positive minus negative probability)
  * Tone gap: prepared remarks tone minus Q&A tone (scripted optimism that fades under questions)
  * Uncertainty words per 1,000 words (subset of the Loughran-McDonald uncertainty list)
  * Evasive phrases per 1,000 words ("too early to say", "we don't disclose", ...)
Stress index = average of the four z-scores.

Market reaction = stock return minus SPY return on the first trading session after the call.

Data: kurry/sp500_earnings_transcripts on Hugging Face (speaker-labelled transcripts) and yfinance.
"""
import json
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent / "outputs"
OUT.mkdir(exist_ok=True)

N_CALLS = int(os.environ.get("N_CALLS", 400))
START_DATE = "2023-01-01"
MAX_PREPARED = 25   # sentences sampled from prepared remarks
MAX_ANSWERS = 40    # sentences sampled from executive answers
SEED = 7

UNCERTAINTY = set("""
almost ambiguity anticipate apparent appear appeared appears approximate approximately assume assumed
assumes assumption assumptions believe believed believes cautious could depend depended depending
depends doubt doubtful estimate estimated estimates exposure fluctuate fluctuation fluctuations hopefully
imprecise indefinite likelihood may maybe might nearly occasionally pending perhaps possible possibly
predict predicting prediction preliminary presumably probable probably random risk risks roughly seems
seldom sometime sometimes somewhat speculative suggest suggests susceptible tentative turbulence uncertain
uncertainly uncertainties uncertainty unclear unknown unpredictable unproven unsettled vague variability
variable variance volatile volatility""".split())

EVASIVE = [
    r"too early to (say|tell|comment)", r"(don't|do not|won't|will not) (disclose|break out|provide|comment|guide)",
    r"not going to (comment|get into|speculate|provide)", r"(can't|cannot) (predict|speculate|comment|say)",
    r"we'll see", r"we will see", r"hard to (say|predict|know|tell)", r"difficult to (say|predict|know)",
    r"i('d| would) rather not", r"remains to be seen", r"stay tuned", r"take that offline",
]
EVASIVE_RE = re.compile("|".join(EVASIVE), re.I)
QA_START_RE = re.compile(r"(first|next|following) question|question comes from|question is from|line of .{0,40}from|"
                         r"questions? (will )?come from|go ahead with your question", re.I)


# ---------------------------------------------------------------- transcript parsing
def split_call(turns):
    """Return (prepared remarks text, executive answers text) from a list of {speaker, text}."""
    turns = [t for t in turns if isinstance(t, dict) and t.get("text")]
    qa_start = next((i for i, t in enumerate(turns) if i > 1 and t["speaker"].strip().lower() == "operator"
                     and QA_START_RE.search(t["text"])), None)
    if qa_start is None:
        return "", ""
    prepared = [t for t in turns[:qa_start] if t["speaker"].strip().lower() != "operator"]
    executives = {t["speaker"] for t in prepared}
    answers = []
    for i, t in enumerate(turns[qa_start:], start=qa_start):
        if t["speaker"].strip().lower() == "operator":
            continue
        prev = turns[i - 1]["speaker"].strip().lower()
        if prev == "operator" or t["speaker"] not in executives:
            continue  # analyst asking the question
        answers.append(t["text"])
    return " ".join(t["text"] for t in prepared), " ".join(answers)


def sentences(text, cap, rng):
    s = [x.strip() for x in re.split(r"(?<=[.!?])\s+", text) if 6 <= len(x.split()) <= 60]
    if len(s) > cap:
        s = list(rng.choice(s, cap, replace=False))
    return s


def lexicon_rates(text):
    words = re.findall(r"[a-z']+", text.lower())
    n = max(len(words), 1)
    unc = sum(w in UNCERTAINTY for w in words)
    eva = len(EVASIVE_RE.findall(text))
    return 1000 * unc / n, 1000 * eva / n, len(words)


# ---------------------------------------------------------------- FinBERT
def load_finbert():
    from transformers import pipeline
    clf = pipeline("text-classification", model="ProsusAI/finbert", top_k=None, truncation=True, max_length=128)

    def tone(sents):
        if not sents:
            return np.nan
        out = clf(sents, batch_size=32)
        vals = []
        for res in out:
            p = {d["label"].lower(): d["score"] for d in res}
            vals.append(p.get("positive", 0) - p.get("negative", 0))
        return float(np.mean(vals))
    return tone


# ---------------------------------------------------------------- data
def load_calls():
    from huggingface_hub import hf_hub_download
    path = hf_hub_download("kurry/sp500_earnings_transcripts", "parquet_files/part-0.parquet", repo_type="dataset")
    df = pd.read_parquet(path, columns=["symbol", "company_name", "year", "quarter", "date", "structured_content"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df[df["date"] >= START_DATE].dropna(subset=["date"])
    print(f"{len(df):,} transcripts since {START_DATE}; sampling {N_CALLS}")
    return df.sample(min(N_CALLS, len(df)), random_state=SEED).reset_index(drop=True)


def score_calls(df, tone_fn):
    rng = np.random.default_rng(SEED)
    rows = []
    for i, r in df.iterrows():
        prep, ans = split_call(list(r["structured_content"]))
        if len(ans.split()) < 300 or len(prep.split()) < 300:
            continue
        unc, eva, n_words = lexicon_rates(ans)
        rows.append({
            "symbol": r["symbol"], "company": r["company_name"], "fiscal": f"{int(r['year'])} Q{int(r['quarter'])}",
            "call_time": r["date"], "answer_words": n_words,
            "prepared_tone": tone_fn(sentences(prep, MAX_PREPARED, rng)),
            "qa_tone": tone_fn(sentences(ans, MAX_ANSWERS, rng)),
            "uncertainty_per_1k": unc, "evasive_per_1k": eva,
        })
        if len(rows) % 50 == 0:
            print(f"  scored {len(rows)} calls")
    s = pd.DataFrame(rows)
    s["tone_gap"] = s["prepared_tone"] - s["qa_tone"]
    z = lambda x: (x - x.mean()) / x.std(ddof=0)
    s["stress_index"] = (z(-s["qa_tone"]) + z(s["tone_gap"]) + z(s["uncertainty_per_1k"]) + z(s["evasive_per_1k"])) / 4
    return s


def add_reactions(s):
    import yfinance as yf
    s = s.copy()
    s["yf_symbol"] = s["symbol"].str.replace(".", "-", regex=False)
    tickers = sorted(s["yf_symbol"].unique()) + ["SPY"]
    start = (s["call_time"].min() - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    end = (s["call_time"].max() + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    px = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False, threads=True)["Close"]
    px.index = pd.to_datetime(px.index).tz_localize(None)
    days = px.index

    def reaction(sym, t):
        if sym not in px:
            return np.nan, np.nan
        d = t.normalize()
        after_close = t.hour >= 16
        # event session = first session whose close reflects the call
        pos = days.searchsorted(d, side="right" if after_close else "left")
        if pos >= len(days) or pos == 0:
            return np.nan, np.nan
        e, b = days[pos], days[pos - 1]
        st, mk = px[sym], px["SPY"]
        r = st.loc[e] / st.loc[b] - 1
        m = mk.loc[e] / mk.loc[b] - 1
        return r * 100, (r - m) * 100

    res = [reaction(sym, t) for sym, t in zip(s["yf_symbol"], s["call_time"])]
    s["return_%"] = [a for a, _ in res]
    s["abnormal_%"] = [b for _, b in res]
    return s.dropna(subset=["abnormal_%", "stress_index"])


# ---------------------------------------------------------------- analysis
def analyse(s):
    from scipy.stats import spearmanr
    s = s.copy()
    s["abs_abnormal_%"] = s["abnormal_%"].abs()
    s["stress_quintile"] = pd.qcut(s["stress_index"], 5, labels=["Q1 calm", "Q2", "Q3", "Q4", "Q5 stressed"])
    q = s.groupby("stress_quintile", observed=True).agg(
        calls=("symbol", "size"), avg_abnormal=("abnormal_%", "mean"), median_abnormal=("abnormal_%", "median"),
        share_negative=("abnormal_%", lambda x: (x < 0).mean() * 100), avg_abs_move=("abs_abnormal_%", "mean")).round(2)

    corr = {}
    for col in ["stress_index", "qa_tone", "tone_gap", "uncertainty_per_1k", "evasive_per_1k"]:
        rho, p = spearmanr(s[col], s["abnormal_%"])
        rho_abs, p_abs = spearmanr(s[col], s["abs_abnormal_%"])
        corr[col] = {"rho_vs_abnormal": round(float(rho), 3), "p": round(float(p), 4),
                     "rho_vs_abs_move": round(float(rho_abs), 3), "p_abs": round(float(p_abs), 4)}
    return s, q, corr


def chart(s, q):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    colors = ["#2e7d32", "#7cb342", "#9e9e9e", "#ef6c00", "#c62828"]
    ax[0].bar(q.index.astype(str), q["avg_abnormal"], color=colors)
    ax[0].axhline(0, color="black", lw=0.8)
    ax[0].set_title("Average next-session return vs SPY by stress quintile")
    ax[0].set_ylabel("Abnormal return (%)")
    for i, v in enumerate(q["avg_abnormal"]):
        ax[0].text(i, v + (0.08 if v >= 0 else -0.25), f"{v:+.2f}", ha="center", fontsize=9)
    ax[1].bar(q.index.astype(str), q["avg_abs_move"], color=colors)
    ax[1].set_title("Average size of the move (absolute, vs SPY)")
    ax[1].set_ylabel("|Abnormal return| (%)")
    for a in ax:
        a.tick_params(axis="x", labelsize=9)
        a.spines[["top", "right"]].set_visible(False)
    fig.suptitle(f"Earnings call stress vs market reaction — {len(s)} S&P 500 calls", fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "stress_quintiles.png", dpi=150)
    plt.close(fig)


def report(s, q, corr):
    top = s.sort_values("stress_index", ascending=False).head(10)
    calm = s.sort_values("stress_index").head(5)
    cols = ["symbol", "fiscal", "stress_index", "qa_tone", "tone_gap", "uncertainty_per_1k", "evasive_per_1k", "abnormal_%"]
    summary = {
        "calls_scored": int(len(s)), "date_range": [str(s["call_time"].min().date()), str(s["call_time"].max().date())],
        "companies": int(s["symbol"].nunique()), "correlations": corr,
        "quintiles": q.reset_index().astype({"stress_quintile": str}).to_dict(orient="records"),
        "q5_minus_q1_abnormal": round(float(q["avg_abnormal"].iloc[-1] - q["avg_abnormal"].iloc[0]), 2),
        "avg_qa_tone": round(float(s["qa_tone"].mean()), 3), "avg_prepared_tone": round(float(s["prepared_tone"].mean()), 3),
        "share_calls_qa_less_positive": round(float((s["tone_gap"] > 0).mean() * 100), 1),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    s.drop(columns=["yf_symbol"], errors="ignore").to_csv(OUT / "call_scores.csv", index=False)
    md = [f"# Earnings Call Stress Report\n",
          f"{len(s)} S&P 500 earnings calls ({summary['date_range'][0]} to {summary['date_range'][1]}), "
          f"{summary['companies']} companies. Source: kurry/sp500_earnings_transcripts + yfinance.\n",
          "## Reaction by stress quintile\n", q.to_markdown(), "\n## Spearman correlations\n",
          pd.DataFrame(corr).T.to_markdown(), "\n## Most stressed calls\n", top[cols].round(3).to_markdown(index=False),
          "\n## Calmest calls\n", calm[cols].round(3).to_markdown(index=False)]
    (OUT / "REPORT.md").write_text("\n".join(md))
    print(json.dumps(summary, indent=2, default=str)[:3000])


def main():
    calls = load_calls()
    scores = score_calls(calls, load_finbert())
    scores = add_reactions(scores)
    scores, q, corr = analyse(scores)
    chart(scores, q)
    report(scores, q, corr)


if __name__ == "__main__":
    main()
