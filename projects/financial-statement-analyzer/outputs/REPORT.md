# Financial Statement Analysis — 12 Indian companies

Annual statements from Yahoo Finance (₹ crore, consolidated). Every ratio in the Excel workbook is a live formula.

| symbol     | company                   | latest FY   |   Revenue ₹ cr |   Revenue CAGR 3y % |   Net margin % |   Return on equity (ROE) % |   Return on capital employed (ROCE) % |   Debt to equity (x) |   Interest coverage (x) |   Operating cash flow / net income (x) |   Piotroski F-score |   Altman Z'' (EM) | Altman zone   |
|:-----------|:--------------------------|:------------|---------------:|--------------------:|---------------:|---------------------------:|--------------------------------------:|---------------------:|------------------------:|---------------------------------------:|--------------------:|------------------:|:--------------|
| RELIANCE   | Reliance Industries       | FY2026      |   1,057,219.00 |                6.39 |           7.64 |                       8.93 |                                  8.99 |                 0.44 |                    6.12 |                                   2.38 |                   7 |              5.43 | grey          |
| TCS        | Tata Consultancy Services | FY2026      |     267,021.00 |                5.80 |          18.43 |                      45.89 |                                 54.93 |                 0.11 |                   54.37 |                                   1.06 |                   5 |             11.71 | safe          |
| INFY       | Infosys                   | FY2026      |     178,066.95 |                6.78 |          16.44 |                      33.85 |                                 41.66 |                 0.10 |                   96.87 |                                   1.22 |                   6 |             11.49 | safe          |
| HINDUNILVR | Hindustan Unilever        | FY2026      |      63,763.00 |                2.31 |          23.59 |                      30.86 |                                 22.15 |                 0.03 |                   34.69 |                                   0.73 |                   6 |              6.71 | safe          |
| ITC        | ITC                       | FY2026      |      78,213.28 |                3.65 |          26.45 |                      28.53 |                                 36.47 |                 0.03 |                  330.15 |                                   0.89 |                   3 |             13.08 | safe          |
| LT         | Larsen & Toubro           | FY2026      |     284,225.19 |               16.09 |           5.66 |                      14.72 |                                 14.55 |                 1.15 |                   10.12 |                                   1.04 |                   6 |              5.68 | grey          |
| MARUTI     | Maruti Suzuki             | FY2026      |     177,094.10 |               15.90 |           8.29 |                      13.70 |                                 17.22 |                 0.00 |                   81.09 |                                   1.30 |                   6 |              8.84 | safe          |
| SUNPHARMA  | Sun Pharmaceutical        | FY2026      |      58,220.11 |               10.39 |          19.72 |                      13.74 |                                 17.94 |                 0.06 |                   45.61 |                                   1.08 |                   5 |             12.30 | safe          |
| ASIANPAINT | Asian Paints              | FY2026      |      35,540.90 |                1.10 |          12.17 |                      20.24 |                                 24.41 |                 0.18 |                   31.72 |                                   1.64 |                   7 |              9.96 | safe          |
| TATASTEEL  | Tata Steel                | FY2026      |     230,293.47 |               -1.59 |           4.69 |                      10.56 |                                 11.32 |                 0.90 |                    3.23 |                                   3.25 |                   7 |              4.21 | grey          |
| BHARTIARTL | Bharti Airtel             | FY2026      |     210,972.80 |               14.88 |          12.65 |                      17.91 |                                 16.69 |                 1.31 |                    3.53 |                                   4.58 |                   8 |              3.80 | distress      |
| ULTRACEMCO | UltraTech Cement          | FY2026      |      87,383.52 |               11.92 |           9.34 |                      10.66 |                                 11.84 |                 0.31 |                    7.03 |                                   1.88 |                   8 |              5.17 | grey          |

- INFY: reported in USD, converted at fiscal-year average USD/INR: FY2023 80.31, FY2024 82.79, FY2025 84.54, FY2026 88.34

![Profitability](chart_profitability_growth.png)

## Piotroski F-score detail

|                              | RELIANCE   | TCS   | INFY   | HINDUNILVR   | ITC   | LT   | MARUTI   | SUNPHARMA   | ASIANPAINT   | TATASTEEL   | BHARTIARTL   | ULTRACEMCO   |
|:-----------------------------|:-----------|:------|:-------|:-------------|:------|:-----|:---------|:------------|:-------------|:------------|:-------------|:-------------|
| positive ROA                 | ✓          | ✓     | ✓      | ✓            | ✓     | ✓    | ✓        | ✓           | ✓            | ✓           | ✓            | ✓            |
| positive operating cash flow | ✓          | ✓     | ✓      | ✓            | ✓     | ✓    | ✓        | ✓           | ✓            | ✓           | ✓            | ✓            |
| ROA improving                | ✓          | ✗     | ✓      | ✓            | ✗     | ✗    | ✗        | ✗           | ✓            | ✓           | ✗            | ✓            |
| cash flow above net income   | ✓          | ✓     | ✓      | ✗            | ✗     | ✓    | ✓        | ✓           | ✓            | ✓           | ✓            | ✓            |
| leverage falling             | ✓          | ✗     | ✗      | ✓            | ✗     | ✓    | ✗        | ✗           | ✗            | ✓           | ✓            | ✓            |
| current ratio improving      | ✗          | ✗     | ✗      | ✗            | ✗     | ✓    | ✓        | ✗           | ✓            | ✗           | ✓            | ✓            |
| no share dilution            | ✓          | ✓     | ✓      | ✓            | ✗     | ✓    | ✓        | ✓           | ✓            | ✓           | ✓            | ✓            |
| gross margin improving       | ✓          | ✓     | ✗      | ✗            | ✓     | ✗    | ✗        | ✓           | ✓            | ✓           | ✓            | ✗            |
| asset turnover improving     | ✗          | ✗     | ✓      | ✓            | ✗     | ✗    | ✓        | ✗           | ✗            | ✗           | ✓            | ✓            |

_Altman Z''-score (emerging markets): above 5.85 safe, 4.15–5.85 grey zone, below 4.15 distress. For learning purposes only._