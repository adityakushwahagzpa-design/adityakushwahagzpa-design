# Black-Scholes Report: Nifty 50 options

As of 20 Nov 2026: Nifty 50 at **25,800.60**, strike 25,800 (30 days), 1-year historical volatility **14.29%**.
Assumed risk-free rate 6.5% and dividend yield 1.2%.

## Prices and Greeks

|               |     Call |      Put |
|:--------------|---------:|---------:|
| price         | 478.99   | 366.357  |
| delta         |   0.5501 |  -0.4489 |
| gamma         |   0.0004 |   0.0004 |
| vega_per_1pct |  29.2416 |  29.2416 |
| theta_per_day |  -8.9394 |  -5.2168 |
| rho_per_1pct  |  11.2726 |  -9.8199 |

## Checks

| Check | Result |
|:--|:--|
| Put-call parity gap | 0.00e+00 points |
| Binomial tree, 1,000 steps | 478.8922 (error -0.0982) |
| Monte Carlo, 500,000 paths | 478.3000 ± 1.8520 |
| Implied volatility recovered | 14.2885% (input 14.2885%) |

## Are returns normal? (494 daily returns)

Skewness 0.104, excess kurtosis 2.117, Jarque-Bera 93.1 (p = 5.98e-21).
Days beyond ±3 standard deviations: **5**, against **1.3** expected under a normal distribution.

## Strike ladder

|   Strike |    Call |     Put |   Call delta |   Gamma |
|---------:|--------:|--------:|-------------:|--------:|
|    24300 | 1630.19 |   25.54 |         0.94 |       0 |
|    24550 | 1400.87 |   44.9  |         0.91 |       0 |
|    24800 | 1182.2  |   74.89 |         0.86 |       0 |
|    25050 |  977.57 |  118.93 |         0.8  |       0 |
|    25300 |  790.36 |  180.39 |         0.73 |       0 |
|    25550 |  623.48 |  262.18 |         0.64 |       0 |
|    25800 |  478.99 |  366.36 |         0.55 |       0 |
|    26050 |  357.77 |  493.81 |         0.46 |       0 |
|    26300 |  259.44 |  644.14 |         0.37 |       0 |
|    26550 |  182.42 |  815.79 |         0.28 |       0 |
|    26800 |  124.26 | 1006.3  |         0.21 |       0 |
|    27050 |   81.94 | 1212.64 |         0.15 |       0 |
|    27300 |   52.27 | 1431.65 |         0.11 |       0 |
