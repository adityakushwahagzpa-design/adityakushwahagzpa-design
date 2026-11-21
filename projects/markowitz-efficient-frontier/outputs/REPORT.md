# Efficient Frontier Report

Data: daily adjusted prices, 22 Nov 2021 to 20 Nov 2026 (Yahoo Finance). Risk-free rate assumed at 6.5%.

## In-sample portfolios (full period)

|              |   return_pct |   volatility_pct |   sharpe |
|:-------------|-------------:|-----------------:|---------:|
| min_variance |         9.28 |            12.29 |     0.23 |
| max_sharpe   |        20.66 |            15.68 |     0.9  |
| equal_weight |         7.86 |            13.08 |     0.1  |

Average volatility of a single stock: **22.3%**. Volatility of an equal-weight mix of the same ten: **13.08%**.

## Weights (%)

|               |   Minimum variance |   Maximum Sharpe |   Equal weight |
|:--------------|-------------------:|-----------------:|---------------:|
| Reliance      |                3.4 |              0   |             10 |
| HDFC Bank     |               12.8 |              0   |             10 |
| Infosys       |                0   |              0   |             10 |
| TCS           |               12.3 |              0   |             10 |
| ITC           |               16.6 |              0   |             10 |
| HUL           |               14.8 |              0   |             10 |
| L&T           |                0   |             11.1 |             10 |
| Sun Pharma    |               22.3 |             40.8 |             10 |
| Maruti        |                6.2 |              0   |             10 |
| Bharti Airtel |               11.7 |             48.1 |             10 |

## Out-of-sample year (weights from earlier data, held from 13 Nov 2025)

|                  |   return_pct |   volatility_pct |   max_drawdown_pct |
|:-----------------|-------------:|-----------------:|-------------------:|
| Minimum variance |        -8.63 |            13.75 |             -22.58 |
| Maximum Sharpe   |        -0.61 |            14.56 |             -16.76 |
| Equal weight     |        -8.08 |            14.16 |             -23.33 |
| Nifty 50         |        -0.29 |            14.29 |             -15.56 |
