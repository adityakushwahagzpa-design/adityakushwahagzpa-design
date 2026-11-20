# News Sentiment Report

Generated 20 Nov 2026. 283 headlines for 10 companies, 24 Aug 2026 to 20 Nov 2026.

## Key Results

- **Headline mix:** 145 positive, 60 neutral, 78 negative.
- **Most positive coverage:** SBIN (avg +0.45); **most negative:** TMPV (avg -0.01).
- **Same-day link:** correlation between daily sentiment and that day's return = **0.54** across 124 company-days.
- **Next-day link:** correlation with the following day's return = **0.02**.
- **Average return on positive-news days:** +0.81%; on negative-news days: -1.90%.

## Sentiment by Company

| Symbol     |   Headlines |   Avg_Sentiment |   Positive_pct |   Negative_pct |
|:-----------|------------:|----------------:|---------------:|---------------:|
| SBIN       |           8 |           0.453 |         87.5   |          0     |
| TCS        |          17 |           0.319 |         64.706 |         11.765 |
| BHARTIARTL |          18 |           0.31  |         66.667 |          0     |
| ICICIBANK  |          21 |           0.273 |         52.381 |          4.762 |
| RELIANCE   |          28 |           0.264 |         67.857 |         25     |
| HDFCBANK   |          31 |           0.237 |         58.065 |         19.355 |
| ITC        |          11 |           0.112 |         45.455 |         36.364 |
| INFY       |          83 |           0.049 |         45.783 |         38.554 |
| ADANIENT   |          15 |           0.007 |         40     |         33.333 |
| TMPV       |          51 |          -0.007 |         35.294 |         41.176 |

![By company](chart_sentiment_by_company.png)

![Sentiment vs return](chart_sentiment_vs_return.png)

## Most Positive Headlines

| Symbol    | Date        | Headline                                                                                                                 |   Sentiment |
|:----------|:------------|:-------------------------------------------------------------------------------------------------------------------------|------------:|
| TMPV      | 19 Nov 2026 | Maruti Suzuki shares jump 5%, M&M, Tata Motors, Eicher Motors rally as Nifty Auto surges 2.6%                            |        0.92 |
| HDFCBANK  | 05 Nov 2026 | HDFC Bank shares witness strong buying, rise 7% in 1 month. Can new CEO, improving fundamentals drive next leg of rally? |        0.91 |
| TMPV      | 19 Nov 2026 | Auto stocks hit the accelerator! Nifty Auto jumps 4%; Maruti, M&M, Hyundai lead the rally | What's behind the surge?     |        0.91 |
| ICICIBANK | 18 Nov 2026 | Nifty Bank crosses 62,000, jumps 20% from 52-week low: What's driving rally? Check performance; best bank stock to buy?  |        0.9  |
| RELIANCE  | 02 Nov 2026 | Reliance Industries shares jump nearly 12% after record Q2 results; top Nifty gainer, biggest index...                   |        0.87 |

## Most Negative Headlines

| Symbol   | Date        | Headline                                                                                                                |   Sentiment |
|:---------|:------------|:------------------------------------------------------------------------------------------------------------------------|------------:|
| INFY     | 23 Oct 2026 | Infosys Plunges 10% in One Minute, Then Snaps Back: Inside the 10:38 AM Flash Crash                                     |       -0.83 |
| TMPV     | 16 Nov 2026 | Tata Motors Passenger Vehicles shares crash over 9% after Rs 5,531 crore quarterly loss, Jaguar Land Rover cuts outlook |       -0.78 |
| INFY     | 26 Oct 2026 | Infosys stock falls after Q2 earnings miss, guidance cut, but pares loss to 1%; brokerages see margin...                |       -0.78 |
| TMPV     | 16 Nov 2026 | India's Tata Motors PV falls on JLR outlook cut, weak Chinese demand                                                    |       -0.76 |
| TMPV     | 16 Nov 2026 | India’s Tata Motors PV Falls on JLR Outlook Cut, Weak Chinese Demand - The China-Global South Project                   |       -0.76 |

## Limitations

- Google News RSS returns only recent headlines (about 100 per search), so the sample is small.
- Headlines are often written after the price has moved, so a same-day link does not mean news caused the move.
- VADER is a general-purpose model; the finance word list improves it but it can still misread context.

_For learning purposes only. Not investment advice._