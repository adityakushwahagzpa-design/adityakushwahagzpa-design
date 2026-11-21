# Insider Cluster-Buy Radar

Flags US companies where three or more insiders bought shares with their own money within two weeks, then tests what the stock did next.

| | |
|:--|:--|
| **What was analysed** | Every Form 4 filing in the SEC EDGAR insider transactions data sets for Q1 2025 to Q1 2026: 8,417 open-market purchases of $25,000+ by officers and directors across 2,000 companies |
| **What was done** | Cleaning and joining of SEC submission, owner and transaction tables with pandas; a cluster rule (3+ distinct insiders within 14 days); storage in PostgreSQL with SQL queries; returns after 1 week, 1 month and 3 months versus SPY from yfinance; a Streamlit dashboard |
| **Key finding** | 491 clusters found. After 1 week they beat the S&P 500 by 2.1 points on average (57% beat SPY), but the edge faded: after 3 months the median cluster trailed SPY by 5.4 points and only 40% beat it. Cluster buys mark a short-term signal, not a long-term one, in this period |

**Latest alerts:** [outputs/ALERTS.md](outputs/ALERTS.md), refreshed every Monday by GitHub Actions.

![Excess returns](outputs/excess_returns.png)

## How It Works

1. **Download:** quarterly ZIP files from sec.gov (SUBMISSION, REPORTINGOWNER, NONDERIV_TRANS tables).
2. **Filter:** transaction code "P" (open-market purchase), acquisitions only, Form 4 or 4/A, officers and directors only, value of $25,000 or more. Option exercises, grants and gifts are excluded.
3. **Cluster:** for each company, a 14-day window that contains 3+ different insiders becomes one cluster.
4. **Database:** purchases and clusters go into PostgreSQL (SQLite locally), and the report's top-companies table is a SQL query on that database.
5. **Returns:** stock return minus SPY return from the first trading day after the cluster ends.

| Horizon | Clusters measured | Average vs SPY | Median vs SPY | Share beating SPY |
|:--|--:|--:|--:|--:|
| 1 week | 461 | +2.1 pts | +0.9 pts | 57% |
| 1 month | 461 | +1.4 pts | -0.5 pts | 48% |
| 3 months | 461 | -1.4 pts | -5.4 pts | 40% |

## Limitations

- Some clusters are small biotech companies where one investment fund sits on the board and files as several insiders; a few large moves pull the averages.
- Returns start after the cluster ends; the SEC filing can arrive up to two days after each trade.
- Five quarters is a short period that includes one market regime.

## Run It Yourself

```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name your-email"      # SEC asks for a contact in the User-Agent
export DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/radar   # optional, SQLite by default
python radar.py
streamlit run app.py
```

**Tools:** Python, pandas, SQLAlchemy, PostgreSQL, SEC EDGAR, yfinance, Matplotlib, Streamlit

_For learning purposes only. Not investment advice._
