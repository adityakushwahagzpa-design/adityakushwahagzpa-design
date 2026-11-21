# Fama-French Three-Factor Report

Monthly data, 2004-02 to 2026-09. Factors: Kenneth French data library (latest month 2026-09). ETF prices: Yahoo Finance.

## Regressions (excess returns, % per month)

| ETF   | Style                          |   CAPM beta |   CAPM alpha (%/yr) |   CAPM R² |   FF3 market |   FF3 SMB |   t(SMB) |   FF3 HML |   t(HML) |   FF3 alpha (%/yr) |   t(alpha) |   FF3 R² |
|:------|:-------------------------------|------------:|--------------------:|----------:|-------------:|----------:|---------:|----------:|---------:|-------------------:|-----------:|---------:|
| SPY   | S&P 500 (large blend)          |        0.96 |                0.11 |      0.99 |         0.99 |     -0.14 |   -19.68 |      0.01 |     2.61 |              -0.21 |      -1.07 |     1    |
| IWM   | Russell 2000 (small blend)     |        1.2  |               -3.32 |      0.84 |         1.01 |      0.87 |    47.15 |      0.21 |    15.18 |              -1.02 |      -1.94 |     0.98 |
| IWD   | Russell 1000 Value             |        0.94 |               -1.31 |      0.89 |         0.93 |     -0.05 |    -2.18 |      0.36 |    21.23 |              -1.09 |      -1.68 |     0.96 |
| IWF   | Russell 1000 Growth            |        1.02 |                0.97 |      0.92 |         1.07 |     -0.1  |    -5.15 |     -0.32 |   -21.63 |               0.43 |       0.76 |     0.97 |
| IWN   | Russell 2000 Value             |        1.16 |               -3.38 |      0.77 |         0.96 |      0.82 |    37.57 |      0.53 |    32.43 |              -0.92 |      -1.49 |     0.98 |
| IWO   | Russell 2000 Growth            |        1.24 |               -3.4  |      0.84 |         1.06 |      0.92 |    34.29 |     -0.09 |    -4.44 |              -1.25 |      -1.64 |     0.97 |
| QQQ   | Nasdaq-100 (large tech growth) |        1.1  |                3.11 |      0.83 |         1.14 |     -0.02 |    -0.44 |     -0.44 |   -12.82 |               2.65 |       2.05 |     0.89 |
| RSP   | S&P 500 Equal Weight           |        1.06 |               -1.27 |      0.92 |         1.01 |      0.13 |     4.6  |      0.25 |    12.14 |              -0.73 |      -0.92 |     0.95 |

Average R²: CAPM **0.874**, three-factor **0.963**. Funds with a three-factor alpha significant at |t| > 2: **1 of 8**.

## Factor premia (annualised)

| Factor | 1990–2006 | 2007 onwards |
|:--|--:|--:|
| SMB (small minus big) | 0.96% | -1.0% |
| HML (value minus growth) | 5.2% | -2.02% |
