# Black-Scholes Report: Nifty 50 options

As of 23 Nov 2026: Nifty 50 at **25,349.65**, strike 25,350 (30 days), 1-year historical volatility **14.40%**.
Assumed risk-free rate 6.5% and dividend yield 1.2%.

## Prices and Greeks

|               |     Call |      Put |
|:--------------|---------:|---------:|
| price         | 473.23   | 363.499  |
| delta         |   0.5495 |  -0.4495 |
| gamma         |   0.0004 |   0.0004 |
| vega_per_1pct |  28.7362 |  28.7362 |
| theta_per_day |  -8.8336 |  -5.1759 |
| rho_per_1pct  |  11.0607 |  -9.6639 |

## Checks

| Check | Result |
|:--|:--|
| Put-call parity gap | -1.82e-12 points |
| Binomial tree, 1,000 steps | 473.1295 (error -0.1002) |
| Monte Carlo, 500,000 paths | 472.5462 ± 1.8321 |
| Implied volatility recovered | 14.3968% (input 14.3968%) |

## Are returns normal? (493 daily returns)

Skewness 0.075, excess kurtosis 2.136, Jarque-Bera 94.2 (p = 3.53e-21).
Days beyond ±3 standard deviations: **5**, against **1.3** expected under a normal distribution.

## Strike ladder

|   Strike |    Call |     Put |   Call delta |   Gamma |
|---------:|--------:|--------:|-------------:|--------:|
|    23850 | 1626.21 |   24.47 |         0.94 |       0 |
|    24100 | 1396.46 |   43.38 |         0.91 |       0 |
|    24350 | 1177.31 |   72.91 |         0.86 |       0 |
|    24600 |  972.24 |  116.5  |         0.8  |       0 |
|    24850 |  784.69 |  177.62 |         0.73 |       0 |
|    25100 |  617.66 |  259.26 |         0.64 |       0 |
|    25350 |  473.23 |  363.5  |         0.55 |       0 |
|    25600 |  352.31 |  491.25 |         0.45 |       0 |
|    25850 |  254.49 |  642.09 |         0.36 |       0 |
|    26100 |  178.14 |  814.41 |         0.28 |       0 |
|    26350 |  120.72 | 1005.66 |         0.21 |       0 |
|    26600 |   79.14 | 1212.75 |         0.15 |       0 |
|    26850 |   50.17 | 1432.44 |         0.1  |       0 |
