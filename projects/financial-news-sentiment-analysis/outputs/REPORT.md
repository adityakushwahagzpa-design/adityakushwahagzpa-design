# News Sentiment Report

Generated 20 Nov 2026. 327 headlines for 10 companies, 22 Aug 2026 to 20 Nov 2026.

## Key Results

- **Headline mix:** 182 positive, 76 neutral, 69 negative.
- **Most positive coverage:** TCS (avg +0.32); **most negative:** TMPV (avg -0.01).
- **Same-day link:** correlation between daily sentiment and that day's return = **0.47** across 147 company-days.
- **Next-day link:** correlation with the following day's return = **0.05**.
- **Average return on positive-news days:** +0.74%; on negative-news days: -1.84%.

## Sentiment by Company

| Symbol     |   Headlines |   Avg_Sentiment |   Positive_pct |   Negative_pct |
|:-----------|------------:|----------------:|---------------:|---------------:|
| TCS        |          17 |           0.319 |         64.706 |         11.765 |
| BHARTIARTL |          17 |           0.311 |         64.706 |          0     |
| SBIN       |          68 |           0.29  |         63.235 |         11.765 |
| RELIANCE   |          26 |           0.28  |         69.231 |         23.077 |
| ICICIBANK  |          21 |           0.273 |         52.381 |          4.762 |
| HDFCBANK   |          30 |           0.235 |         56.667 |         20     |
| INFY       |          30 |           0.161 |         53.333 |         26.667 |
| ITC        |          10 |           0.146 |         50     |         30     |
| ADANIENT   |          58 |           0.14  |         56.897 |         24.138 |
| TMPV       |          50 |          -0.012 |         34     |         42     |

![By company](chart_sentiment_by_company.png)

![Sentiment vs return](chart_sentiment_vs_return.png)

## Most Positive Headlines

| Symbol    | Date        | Headline                                                                                                                 |   Sentiment |
|:----------|:------------|:-------------------------------------------------------------------------------------------------------------------------|------------:|
| SBIN      | 11 Nov 2026 | SBI shares gain 1%, among top Nifty gainers, as brokerages bullish on loan growth, profitability outlook                 |        0.93 |
| TMPV      | 19 Nov 2026 | Maruti Suzuki shares jump 5%, M&M, Tata Motors, Eicher Motors rally as Nifty Auto surges 2.6%                            |        0.92 |
| HDFCBANK  | 05 Nov 2026 | HDFC Bank shares witness strong buying, rise 7% in 1 month. Can new CEO, improving fundamentals drive next leg of rally? |        0.91 |
| TMPV      | 19 Nov 2026 | Auto stocks hit the accelerator! Nifty Auto jumps 4%; Maruti, M&M, Hyundai lead the rally / What's behind the surge?     |        0.91 |
| ICICIBANK | 18 Nov 2026 | Nifty Bank crosses 62,000, jumps 20% from 52-week low: What's driving rally? Check performance; best bank stock to buy?  |        0.9  |

## Most Negative Headlines

| Symbol   | Date        | Headline                                                                                                                |   Sentiment |
|:---------|:------------|:------------------------------------------------------------------------------------------------------------------------|------------:|
| TMPV     | 16 Nov 2026 | Tata Motors Passenger Vehicles shares crash over 9% after Rs 5,531 crore quarterly loss, Jaguar Land Rover cuts outlook |       -0.78 |
| TMPV     | 16 Nov 2026 | India's Tata Motors PV falls on JLR outlook cut, weak Chinese demand                                                    |       -0.76 |
| TMPV     | 16 Nov 2026 | India’s Tata Motors PV Falls on JLR Outlook Cut, Weak Chinese Demand - The China-Global South Project                   |       -0.76 |
| TMPV     | 16 Nov 2026 | Tata Motors PV shares plunge 7%, top Nifty loser as weak JLR margins, guidance cut weigh on outlook                     |       -0.73 |
| TMPV     | 16 Nov 2026 | Tata Motors PV Shares Crash 9% on Q2 Loss, JLR Outlook                                                                  |       -0.68 |

## Limitations

- Google News RSS returns only recent headlines (about 100 per search), so the sample is small.
- Headlines are often written after the price has moved, so a same-day link does not mean news caused the move.
- VADER is a general-purpose model; the finance word list improves it but it can still misread context.

_For learning purposes only. Not investment advice._