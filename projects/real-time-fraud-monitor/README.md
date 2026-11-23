# Real-Time Transaction Fraud Monitor | Python, FastAPI, PostgreSQL, React

A service that checks every card transaction the moment it arrives against three configurable rules (velocity, impossible travel and unusual amount), stores transactions and alerts in PostgreSQL, and shows a live alert queue for a human reviewer. Alerts are indicators that a case needs a look, not proof of fraud.

| | |
|:--|:--|
| **What was built** | A rule engine that keeps per-card state (a sliding time window, the last in-store location, a running mean and standard deviation of amounts); thresholds in `config/rules.json`; a FastAPI service; a replay script that streams transactions in time order; PostgreSQL tables with an index on card and time; a React dashboard; an evaluation script with precision and recall per rule |
| **Data** | 403,847 simulated card transactions (1,000 cards, 800 merchants, 20 Indian cities, January–June 2026) with the same core columns as the Kaggle Sparkov fraud dataset: `cc_num`, `amt`, `unix_time`, `merch_lat`, `merch_long`, `is_fraud`. 488 are fraud (0.12%), across 60 cards, in three patterns: account takeover, cloned card and card testing |
| **Key finding** | Simple rules catch some fraud and flag a lot of normal spending, and each rule catches a different pattern. Velocity is precise (100%) but only sees card testing; impossible travel catches 27.5% of cloned-card fraud at 71.7% precision; unusual amount catches the most fraud (28.3% recall) but only 2.4% of its alerts are real. Together the rules catch 37.9% of fraud transactions. The textbook impossible-travel rule raised 16,343 alerts at 1.2% precision; limiting it to in-store purchases over 100 km cut that to 53 alerts at 71.7% |

![Dashboard](outputs/dashboard.png)

## The Rules

| Rule | Fires when | Config (`config/rules.json`) |
|:--|:--|:--|
| Velocity | A card makes more than 5 transactions in 10 minutes | `window_seconds`, `max_tx_in_window` |
| Impossible travel | Two in-store purchases are 100 km+ apart and the speed needed exceeds 900 km/h | `max_speed_kmh`, `min_distance_km`, `card_present_only` |
| Unusual amount | The amount is more than 4 standard deviations above the card's mean, after at least 20 purchases | `max_zscore`, `min_history` |

Each rule can be switched off or retuned in the config file without touching the code.

## Results (all 403,847 transactions replayed in time order)

| Rule | Alerts | Real fraud | False alerts | Precision | Recall |
|:--|--:|--:|--:|--:|--:|
| Velocity | 21 | 21 | 0 | 100.0% | 4.3% |
| Impossible travel | 53 | 38 | 15 | 71.7% | 7.8% |
| Unusual amount | 5,640 | 138 | 5,502 | 2.4% | 28.3% |
| **Any rule** | **5,702** | **185** | **5,517** | **3.2%** | **37.9%** |

| Fraud pattern | Transactions | Velocity | Impossible travel | Unusual amount | Any rule |
|:--|--:|--:|--:|--:|--:|
| Account takeover (large night-time purchases) | 279 | 0% | 0% | 35.1% | 35.1% |
| Cloned card (in-store purchases in a far city) | 138 | 0% | 27.5% | 29.0% | 47.8% |
| Card testing (6–10 small attempts in minutes) | 71 | 29.6% | 0% | 0% | 29.6% |

**Why the travel rule needed refining:** online purchases carry the merchant's registered address, often in another city, so the textbook version flagged ordinary online shopping as "travel". Counting only in-store purchases, and only jumps of 100 km or more, removed 16,290 false alerts.

**Tuning:** lowering the velocity threshold from 5 to 3 transactions in 10 minutes doubles its recall (4.3% → 8.4%) with still no false alerts; going down to 2 drops precision to 30%. For unusual amount, a z-score of 2 catches 57.6% of fraud but raises 15,145 alerts. Full tables are in [outputs/](outputs/).

![Tuning](outputs/chart_tuning.png)

**Speed:** about 3 microseconds per check in a straight replay (over 300,000 checks a second). Over HTTP the replay runs at about 550 transactions a second, so the network, not the rules, sets the pace.

## Project Structure

| File | What it does |
|:--|:--|
| [monitor/engine.py](monitor/engine.py) | Per-card state and the three rules; the history is updated only after the checks |
| [config/rules.json](config/rules.json) | Every threshold |
| [api/app.py](api/app.py) | FastAPI: `POST /api/transactions`, alerts, stats, card history, merchants flagged on 2+ cards; serves the dashboard |
| [api/schema.sql](api/schema.sql) | `transactions` and `alerts` tables, indexed on card and time |
| [replay.py](replay.py) | Streams transactions to the API one at a time, in time order |
| [evaluate.py](evaluate.py) | Precision and recall per rule and per pattern, the naive vs refined travel rule, and threshold tuning |
| [generate_data.py](generate_data.py) | Builds the simulated dataset (seeded) |
| [tests/test_rules.py](tests/test_rules.py) | 12 tests, one per rule behaviour |
| [frontend/src/main.jsx](frontend/src/main.jsx) | React dashboard: live alerts, alerts by rule, card history, merchants flagged on several cards |

## Run It Yourself

```bash
pip install -r requirements.txt
python -m pytest -q                        # 12 tests
python evaluate.py                         # precision and recall on all 403,847 transactions

createdb fraud
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/fraud python api/app.py
# open http://127.0.0.1:8000, then in another terminal:
python replay.py --limit 80000             # or --rate 50 to watch alerts arrive
```

## Mistakes This Avoids

- Updating the card's history before checking the transaction (a test checks the order).
- Replaying transactions out of time order: the replay sorts by time, and a second replay must start on a fresh server, or the sliding window breaks.
- Flagging unusual amounts on cards with almost no history: the rule waits for 20 past purchases.
- Querying a card's history without an index: `transactions` is indexed on card and time.

## Limitations

- The data is simulated, not real card data. The Kaggle Sparkov file could not be downloaded in this environment, so `generate_data.py` creates a dataset with the same core columns and similar patterns. Swap in the Kaggle CSV (renaming columns if needed) to rerun everything on it.
- The `fraud_pattern` column exists only to explain the results; the rules never read it, and they never read `is_fraud`.
- Rules give a list of cases to review. A production system would add more signals (device, merchant risk, a trained model) and a feedback loop from reviewers.

**Tools:** Python, FastAPI, PostgreSQL, React (Vite), pandas, Matplotlib, pytest
