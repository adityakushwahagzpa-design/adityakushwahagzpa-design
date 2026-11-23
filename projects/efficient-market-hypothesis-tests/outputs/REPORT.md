# Market Efficiency Report: Nifty 50

Data: daily closes, 17 Sep 2007 to 23 Nov 2026 (4,705 returns, Yahoo Finance).

## 1. Autocorrelation

Lag-1 autocorrelation **0.0374**; 95% band for a random walk ±0.0286. Lags outside the band: [1, 6, 7, 10].
Ljung-Box Q(10) = 38.70, p = 0.0000.

## 2. Variance ratios

|        |   Variance ratio |   z (robust) |   p-value |
|:-------|-----------------:|-------------:|----------:|
| q = 2  |           1.0375 |       1.3346 |    0.182  |
| q = 5  |           1.0242 |       0.3714 |    0.7103 |
| q = 10 |           1.0075 |       0.0744 |    0.9407 |
| q = 20 |           1.0697 |       0.4798 |    0.6314 |

## 3. Runs test

Observed runs 2,202 vs 2,343.1 expected; z = -4.13, p = 0.0000.

## 4. Sub-periods

| Period    |   Lag-1 autocorr |   Ljung-Box p |   VR(5) |   VR(5) p |   Runs test p |
|:----------|-----------------:|--------------:|--------:|----------:|--------------:|
| 2007–2014 |           0.0749 |        0.0031 |  1.0369 |    0.6762 |        0.374  |
| 2014–2020 |          -0.0292 |        0      |  1.0118 |    0.937  |        0.0244 |
| 2020–2026 |           0.0031 |        0.4674 |  1.0089 |    0.9072 |        0      |

## 5. Trading rule (after 0.10% per trade, 24 switches)

|                     |   CAGR % |   Volatility % |   Sharpe (rf=0) |   Max drawdown % |
|:--------------------|---------:|---------------:|----------------:|-----------------:|
| Buy and hold        |    10.83 |          19.51 |            0.62 |           -45.37 |
| 50/200 MA crossover |     4.93 |          12.7  |            0.44 |           -42.21 |
