# Market Efficiency Report: Nifty 50

Data: daily closes, 17 Sep 2007 to 20 Nov 2026 (4,704 returns, Yahoo Finance).

## 1. Autocorrelation

Lag-1 autocorrelation **0.0376**; 95% band for a random walk ±0.0286. Lags outside the band: [1, 6, 7, 10].
Ljung-Box Q(10) = 39.04, p = 0.0000.

## 2. Variance ratios

|        |   Variance ratio |   z (robust) |   p-value |
|:-------|-----------------:|-------------:|----------:|
| q = 2  |           1.0379 |       1.3481 |    0.1776 |
| q = 5  |           1.0246 |       0.3778 |    0.7056 |
| q = 10 |           1.0079 |       0.0785 |    0.9374 |
| q = 20 |           1.0694 |       0.4777 |    0.6328 |

## 3. Runs test

Observed runs 2,201 vs 2,342.5 expected; z = -4.14, p = 0.0000.

## 4. Sub-periods

| Period    |   Lag-1 autocorr |   Ljung-Box p |   VR(5) |   VR(5) p |   Runs test p |
|:----------|-----------------:|--------------:|--------:|----------:|--------------:|
| 2007–2014 |           0.0749 |        0.0031 |  1.0369 |    0.6762 |        0.374  |
| 2014–2020 |          -0.0299 |        0      |  1.0101 |    0.9463 |        0.0258 |
| 2020–2026 |           0.0045 |        0.4843 |  1.0116 |    0.8795 |        0      |

## 5. Trading rule (after 0.10% per trade, 24 switches)

|                     |   CAGR % |   Volatility % |   Sharpe (rf=0) |   Max drawdown % |
|:--------------------|---------:|---------------:|----------------:|-----------------:|
| Buy and hold        |    10.94 |          19.51 |            0.63 |           -45.37 |
| 50/200 MA crossover |     4.93 |          12.71 |            0.44 |           -42.21 |
