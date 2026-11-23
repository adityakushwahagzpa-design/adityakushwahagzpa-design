# Efficient Frontier Report

Data: daily adjusted prices, 23 Nov 2021 to 23 Nov 2026 (Yahoo Finance). Risk-free rate assumed at 6.5%.

## In-sample portfolios (full period)

|              |   return_pct |   volatility_pct |   sharpe |
|:-------------|-------------:|-----------------:|---------:|
| min_variance |         8.98 |            12.29 |     0.2  |
| max_sharpe   |        19.97 |            15.71 |     0.86 |
| equal_weight |         7.59 |            13.09 |     0.08 |

Average volatility of a single stock: **22.31%**. Volatility of an equal-weight mix of the same ten: **13.09%**.

## Weights (%)

|               |   Minimum variance |   Maximum Sharpe |   Equal weight |
|:--------------|-------------------:|-----------------:|---------------:|
| Reliance      |                3.3 |              0   |             10 |
| HDFC Bank     |               12.6 |              0   |             10 |
| Infosys       |                0   |              0   |             10 |
| TCS           |               12.4 |              0   |             10 |
| ITC           |               16.7 |              0   |             10 |
| HUL           |               14.7 |              0   |             10 |
| L&T           |                0   |             10.3 |             10 |
| Sun Pharma    |               22.3 |             41.1 |             10 |
| Maruti        |                6.2 |              0   |             10 |
| Bharti Airtel |               11.7 |             48.6 |             10 |

## Out-of-sample year (weights from earlier data, held from 14 Nov 2025)

|                  |   return_pct |   volatility_pct |   max_drawdown_pct |
|:-----------------|-------------:|-----------------:|-------------------:|
| Minimum variance |        -8.94 |            13.75 |             -22.56 |
| Maximum Sharpe   |        -1.97 |            14.56 |             -16.88 |
| Equal weight     |        -8.78 |            14.18 |             -23.33 |
| Nifty 50         |        -2.05 |            14.4  |             -15.56 |
