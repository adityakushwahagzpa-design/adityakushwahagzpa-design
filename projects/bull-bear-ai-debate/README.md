# Bull vs Bear AI Debate

Two Claude agents argue for and against a US stock using only evidence from its latest 10-K and market data; a third agent judges the debate and returns a verdict.

| | |
|:--|:--|
| **What was analysed** | The latest 10-K filings of NVIDIA, Tesla and Apple from SEC EDGAR (Item 1A Risk Factors and Item 7 MD&A), four fiscal years of revenue, operating income, net income and operating cash flow from SEC XBRL data, and one year of prices and valuation multiples from yfinance |
| **What was done** | An evidence pack per company where every line carries an ID ([R] risk, [M] MD&A, [F] financials, [P] price); bull and bear agents with two rounds each (opening and rebuttal), forced to cite IDs; a judge agent that scores both sides, lists unsupported claims and returns a JSON verdict; a Streamlit app to run any ticker |
| **Key finding** | The evidence itself shows why a debate is useful: NVIDIA grew revenue 65.5% at a 55.6% net margin yet trailed the S&P 500 by 35.5 points over the year at 7.6x forward earnings, while Apple grew 15.1% and beat the index by 20.8 points at 32x. Strong fundamentals and weak prices pull in opposite directions, which is exactly where a structured bull vs bear argument adds value |

![Evidence scorecard](outputs/evidence_scorecard.png)

## How It Works

1. **Evidence:** `evidence.py` finds the company's CIK, downloads the latest 10-K, cuts out Item 1A and Item 7, and keeps the 12 most informative sentences from each (risk words, numbers, growth language). XBRL facts give clean annual financials, including non-December year ends.
2. **Debate:** `debate.py` runs bull opening, bear opening, bull rebuttal and bear rebuttal. Each agent may use only the evidence pack and must cite an ID after every claim.
3. **Judge:** a separate agent scores both sides from 0 to 10 on evidence quality, flags claims without support and gives a verdict (bull, bear or too close to call) with what would change it.
4. **Output:** a full transcript and verdict per ticker in `outputs/`.

The agents need an Anthropic API key. Without one, `debate.py` runs in dry-run mode and writes the exact prompts and evidence packs (see `outputs/*_debate_prompts.md`), so nothing is invented. Add `ANTHROPIC_API_KEY` as a repository secret and the weekly GitHub Actions run will produce live debates.

| | NVDA | TSLA | AAPL |
|:--|--:|--:|--:|
| Revenue growth, latest FY | 65.5% | -2.9% | 15.1% |
| Net margin, latest FY | 55.6% | 4.0% | 27.6% |
| 1-year return vs SPY | -35.5 pts | -17.4 pts | +20.8 pts |
| Forward P/E | 7.6x | 160.2x | 32.4x |
| Risk factor section | 24,478 words | 12,654 words | 12,330 words |

## Limitations

- Sentence selection is keyword-based, so some important context in the 10-K can be left out.
- Language models can still misread a figure; the judge's unsupported-claims list is there to catch this, not to guarantee accuracy.
- Market data from yfinance is as of the run date (20 Nov 2026 for the table above).

## Run It Yourself

```bash
pip install -r requirements.txt
export SEC_USER_AGENT="Your Name your-email"
export ANTHROPIC_API_KEY=...            # optional; dry run without it
TICKERS=NVDA,TSLA,AAPL python evidence.py && python debate.py
streamlit run app.py
```

**Tools:** Python, Anthropic Claude API, SEC EDGAR and XBRL APIs, BeautifulSoup, pandas, yfinance, Matplotlib, Streamlit

_For learning purposes only. Not investment advice._
