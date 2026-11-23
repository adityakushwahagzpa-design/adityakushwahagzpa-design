# News Sentiment Report

Generated 23 Nov 2026. 190 headlines for 10 companies, 25 Aug 2026 to 23 Nov 2026.

## Key Results

- **Headline mix:** 123 positive, 36 neutral, 31 negative.
- **Most positive coverage:** BHARTIARTL (avg +0.33); **most negative:** SBIN (avg -0.03).
- **Same-day link:** correlation between daily sentiment and that day's return = **0.52** across 92 company-days.
- **Next-day link:** correlation with the following day's return = **-0.00**.
- **Average return on positive-news days:** +0.78%; on negative-news days: -2.21%.

## Sentiment by Company

| Symbol     |   Headlines |   Avg_Sentiment |   Positive_pct |   Negative_pct |
|:-----------|------------:|----------------:|---------------:|---------------:|
| BHARTIARTL |          17 |           0.326 |         76.471 |          5.882 |
| RELIANCE   |          19 |           0.307 |         73.684 |         21.053 |
| HDFCBANK   |          40 |           0.294 |         72.5   |         10     |
| INFY       |          16 |           0.289 |         75     |         18.75  |
| ADANIENT   |          18 |           0.241 |         61.111 |         16.667 |
| ICICIBANK  |          17 |           0.231 |         70.588 |         11.765 |
| TMPV       |          26 |           0.229 |         53.846 |         19.231 |
| TCS        |          15 |           0.215 |         60     |         20     |
| ITC        |          11 |           0.118 |         45.455 |         18.182 |
| SBIN       |          11 |          -0.03  |         36.364 |         36.364 |

![By company](chart_sentiment_by_company.png)

![Sentiment vs return](chart_sentiment_vs_return.png)

## Most Positive Headlines

| Symbol   | Date        | Headline                                                                                                                 |   Sentiment |
|:---------|:------------|:-------------------------------------------------------------------------------------------------------------------------|------------:|
| TMPV     | 19 Nov 2026 | Maruti Suzuki shares jump 5%, M&M, Tata Motors, Eicher Motors rally as Nifty Auto surges 2.6%                            |        0.92 |
| HDFCBANK | 05 Nov 2026 | HDFC Bank shares witness strong buying, rise 7% in 1 month. Can new CEO, improving fundamentals drive next leg of rally? |        0.91 |
| TMPV     | 19 Nov 2026 | Auto stocks hit the accelerator! Nifty Auto jumps 4%; Maruti, M&M, Hyundai lead the rally / What's behind the surge?     |        0.91 |
| HDFCBANK | 20 Nov 2026 | HDFC Bank shares surges 1.6% as banking stocks rally to fresh highs                                                      |        0.88 |
| RELIANCE | 02 Nov 2026 | Reliance Industries shares jump nearly 12% after record Q2 results; top Nifty gainer, biggest index...                   |        0.87 |

## Most Negative Headlines

| Symbol    | Date        | Headline                                                                                                   |   Sentiment |
|:----------|:------------|:-----------------------------------------------------------------------------------------------------------|------------:|
| TMPV      | 16 Nov 2026 | Tata Motors PV shares plunge 7%, top Nifty loser as weak JLR margins, guidance cut weigh on outlook        |       -0.73 |
| SBIN      | 23 Nov 2026 | Stock market crash today: Investors lose over Rs 6 lakh crore as Sensex ends over 1,400 points down; top   |       -0.71 |
| TMPV      | 16 Nov 2026 | Tata Motors PV shares crash 9% following Q2 results, cuts JLR guidance                                     |       -0.61 |
| HDFCBANK  | 23 Nov 2026 | Bank Nifty crashes over 2,000 points, plunges 3.1%; HDFC Bank, ICICI Bank, Axis Bank, SBI among top losers |       -0.57 |
| ICICIBANK | 23 Nov 2026 | Bank Nifty crashes over 2,000 points, plunges 3.1%; HDFC Bank, ICICI Bank, Axis Bank, SBI among top losers |       -0.57 |

## Limitations

- Google News RSS returns only recent headlines (about 100 per search), so the sample is small.
- Headlines are often written after the price has moved, so a same-day link does not mean news caused the move.
- VADER is a general-purpose model; the finance word list improves it but it can still misread context.

_For learning purposes only. Not investment advice._