# Prospect Theory Report

Parameters: α = β = 0.88, λ = 2.25, γ⁺ = 0.61, γ⁻ = 0.69 (Tversky & Kahneman, 1992).

## Classic gambles

| Gamble                                           |   Expected value (₹) |   Prospect-theory certainty equivalent (₹) | Accept vs ₹0?   |
|:-------------------------------------------------|---------------------:|-------------------------------------------:|:----------------|
| 50% win ₹1,000, else nothing                     |                  500 |                                      373.8 | Yes             |
| 50% win ₹1,000, 50% lose ₹1,000                  |                    0 |                                     -223   | No              |
| 50% win ₹2,500, 50% lose ₹1,000                  |                  750 |                                      -22.4 | No              |
| 1% win ₹1,00,000, else nothing (lottery)         |                 1000 |                                     3723.7 | Yes             |
| 1% lose ₹1,00,000, else nothing (insurance case) |                -1000 |                                    -2554.9 | No              |
| 90% lose ₹1,000, else nothing                    |                 -900 |                                     -748.4 | No              |

## Myopic loss aversion on the Nifty 50

Nifty 50 month-end closes, Sep 2007 to Nov 2026 (price index, dividends excluded). Fixed deposit assumed at 6.5% a year.

|   Horizon (months) |   Windows |   Mean Nifty return % |   Share of losing windows % |   Worst % |   FD return % |   PT value: Nifty |   PT value: FD |
|-------------------:|----------:|----------------------:|----------------------------:|----------:|--------------:|------------------:|---------------:|
|                  1 |       230 |                  0.88 |                       43.91 |    -26.41 |          0.53 |             -1.91 |           0.57 |
|                  2 |       229 |                  1.66 |                       38.43 |    -33.82 |          1.06 |             -2    |           1.05 |
|                  3 |       228 |                  2.44 |                       38.6  |    -36.81 |          1.59 |             -1.69 |           1.5  |
|                  6 |       225 |                  5.09 |                       32.89 |    -44.14 |          3.2  |             -0.77 |           2.78 |
|                  9 |       222 |                  7.93 |                       27.93 |    -47.26 |          4.84 |              0.6  |           4    |
|                 12 |       219 |                 11.1  |                       24.66 |    -52.19 |          6.5  |              2.12 |           5.19 |
|                 18 |       213 |                 18.12 |                       20.19 |    -41.13 |          9.91 |              8.51 |           7.52 |
|                 24 |       207 |                 24.67 |                       14.98 |    -20.15 |         13.42 |             13.62 |           9.83 |
|                 36 |       195 |                 37.94 |                        2.05 |     -6.28 |         20.79 |             21.41 |          14.45 |
|                 48 |       183 |                 52.92 |                        2.19 |    -24.67 |         28.65 |             28.65 |          19.15 |
|                 60 |       171 |                 71.69 |                        1.17 |     -4.76 |         37.01 |             37.66 |          23.99 |

A prospect-theory investor prefers the Nifty 50 to the fixed deposit only when checking the portfolio every **18 months** or less often.
