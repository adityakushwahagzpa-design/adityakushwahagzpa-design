# Anti-Money Laundering Case Manager | Python, Graph Database (Cypher), PostgreSQL

A rule-based AML platform that loads bank transfers into a graph (accounts are nodes, transfers are edges), finds suspicious patterns with Cypher queries (circular transfers, fan-in and fan-out), and turns each hit into a case in PostgreSQL for a human investigator, with a case view that draws the money flow.

| | |
|:--|:--|
| **What was built** | Data preparation in the IBM AML format; a graph of 25,000 accounts and 518,023 transfers; Cypher queries for 3-, 4- and 5-hop cycles in time order, fan-in and fan-out in 24-hour windows; case creation in PostgreSQL with status (open, under review, closed), accounts, transfers, the subgraph as evidence and a status history; a FastAPI case view; an evaluation against the laundering labels for each of the 8 laundering patterns |
| **Data** | 518,044 synthetic transfers over 10 days in the same 11-column format as IBM's HI-Small dataset, with 519 laundering transfers (1 in 998, close to HI-Small's 1 in 981) in 55 attempts across IBM's 8 patterns, plus a patterns file naming the pattern behind every laundering transfer. Normal activity includes payroll, merchants and friends paying each other back, the things that make AML rules misfire |
| **Key finding** | The rules opened **43 cases, 38 of them (88%) containing laundering**, and caught **59% of all laundering transfers**: 100% of cycles and gather-scatter, 95–98% of fan-in and fan-out, 74% of scatter-gather, and **0% of random chains, bipartite and stack** patterns, which no cycle or fan rule can see. Without the refinements (an amount floor, a cap that leaves out payroll, amounts that stay close along a cycle) the same queries opened 87 cases, only 4 with laundering, and swept 345,957 transfers (two-thirds of all transfers) into cases |

![Case view](outputs/case_view.png)

## Patterns and Rules

| Pattern | Cypher rule (thresholds in [config/rules.json](config/rules.json)) |
|:--|:--|
| Cycle | Money leaves an account and comes back in 3, 4 or 5 hops; each hop is later than the one before and within 24 hours of it; every hop is $1,000+ and within 25% of the first hop |
| Fan-in | 5+ different accounts send $1,000+ each to one account inside a 24-hour window (windows every 12 hours, so no burst is split) |
| Fan-out | One account sends $1,000+ each to 5–30 different accounts inside a 24-hour window (above 30 receivers it is payroll) |

Hits that share a transfer, or a fan-in and a fan-out on the same hub account, become one case.

## Results

| Laundering pattern (IBM's 8) | Attempts | Laundering transfers | Inside a case |
|:--|--:|--:|--:|
| Fan-out | 7 | 63 | 98.4% |
| Fan-in | 7 | 65 | 95.4% |
| Gather-scatter | 7 | 87 | 100.0% |
| Scatter-gather | 7 | 86 | 74.4% |
| Cycle | 7 | 31 | 100.0% |
| Random (a chain that wanders) | 7 | 31 | 0.0% |
| Bipartite | 7 | 48 | 0.0% |
| Stack | 6 | 108 | 0.0% |
| **All** | **55** | **519** | **59.0%** |

| Rule set | Cases | Cases with laundering | Transfers swept into cases | Laundering covered |
|:--|--:|--:|--:|--:|
| Refined (`config/rules.json`) | 43 | 38 (88.4%) | 340 | 59.0% |
| Naive (no amount floor, no payroll cap, any amounts on a cycle) | 87 | 4 (4.6%) | 345,957 | 82.1% |

The naive rules look better on coverage only because they put two-thirds of all transfers into cases, which no investigator could review. Laundering is rare (about 1 in 1,000 transfers), so the labels are what make it possible to show exactly which patterns the rules catch and which they miss: random chains, bipartite and stack layering would need path-based or machine-learning rules.

Loading the graph takes about 4 seconds and running every pattern query about 6 seconds.

| Example cases | |
|:--|:--|
| ![Gather-scatter case](outputs/case_fan_in_and_fan_out.png) | ![Cycle case](outputs/case_cycle.png) |

## Project Structure

| File | What it does |
|:--|:--|
| [prepare.py](prepare.py) | Checks the 11-column header, builds one ID per account from bank + account number, ISO timestamps, converts every amount to US dollars |
| [graph/kuzu_graph.py](graph/kuzu_graph.py) | Loads the graph (primary key on account ID) and runs the cycle, fan-in and fan-out Cypher queries |
| [cases/schema.sql](cases/schema.sql) · [cases/manager.py](cases/manager.py) | PostgreSQL `cases`, `case_transfers` and `case_events`; merges hits into cases; status changes with a log |
| [cases/app.py](cases/app.py) · [cases/static/index.html](cases/static/index.html) | Case view: case list, the money-flow graph, the transfers and buttons to start a review or close a case |
| [run.py](run.py) | The full pipeline and the evaluation; writes everything in `outputs/` |
| [neo4j/](neo4j/) | The same graph and queries for a Neo4j 5 server: a batched loader with the uniqueness constraint, and `patterns.cypher` |
| [generate_data.py](generate_data.py) | Builds the synthetic transfers and patterns file (seeded) |
| [tests/test_aml.py](tests/test_aml.py) | 7 tests: cycles in and out of time order, long gaps, changing amounts, case merging, account IDs and currency conversion |

## Run It Yourself

```bash
pip install -r requirements.txt
python -m pytest -q                                   # 7 tests
createdb aml
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aml python run.py
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aml python cases/app.py   # case view at http://127.0.0.1:8000

# With a Neo4j 5 server instead:
NEO4J_PASSWORD=... python neo4j/load_neo4j.py         # then run the queries in neo4j/patterns.cypher
```

## Mistakes This Avoids

- Unbounded path queries: cycles are fixed at 3, 4 and 5 hops with time and amount filters, so the number of paths stays small.
- Adding up amounts in different currencies: every amount is converted to US dollars first.
- Loading without a uniqueness constraint: account ID is the primary key (and a unique constraint in the Neo4j loader).
- Mixing up accounts: the same account number at two banks is two different accounts.
- Presenting flagged accounts as criminals: every case starts as "open" and goes to a person for review.

## Limitations

- The data is synthetic. IBM's HI-Small file is on Kaggle, which could not be reached from the build environment, so `generate_data.py` produces a file in the same format with the same 8 patterns. `prepare.py` reads the real `HI-Small_Trans.csv` unchanged.
- The graph queries ran here on Kùzu, an embedded graph database that speaks Cypher, because a Neo4j server could not be installed in the build environment. The Neo4j loader and queries in `neo4j/` use the same graph model but were not run here.
- Rules see only the shapes they are written for; the three patterns they miss show where a graph machine-learning model would add the most.

**Tools:** Python, Cypher (Kùzu, Neo4j), PostgreSQL, FastAPI, pandas, NetworkX, Matplotlib, pytest
