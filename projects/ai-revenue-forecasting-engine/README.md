# AI-Powered Revenue Forecasting Engine | Python, LightGBM

A forecasting engine for a retail business. It compares three models, picks a blend using a rolling backtest, gives a P10–P90 range, runs what-if scenarios on marketing and discounts, and writes its own management commentary and an Excel forecast pack, the output an FP&A team would take into a planning meeting.

| | |
|:--|:--|
| **What was analysed** | Three years (2023–2025) of daily revenue for a fictional Indian D2C retailer across Apparel, Electronics and Home (₹1,022 crore in total), with the drivers behind it: Diwali, Holi, Republic Day and Independence Day sales, planned discounts and daily marketing spend. Revenue is simulated, including an 8% Electronics price rise in April 2025 |
| **What was done** | Three models (seasonal naive, Holt-Winters and a LightGBM machine-learning model trained on calendar, festival, discount and marketing features); a rolling backtest forecasting Q2, Q3 and Q4 2025 from the end of each prior quarter; a weighted ensemble chosen on that backtest; P10–P90 ranges from backtest errors (split conformal); four what-if scenarios; SHAP-style driver attribution; automatic commentary and an Excel pack |
| **Key finding** | Q1 2026 revenue is forecast at **₹105.5 crore**, up 18.3% on Q1 2025, with a likely range of ₹100.9–110.3 crore. In the backtest, LightGBM was off by 6.6% a day and 2.7% on quarterly totals, against 11.0% and 6.4% for Holt-Winters, which missed the Diwali quarter by ₹14 crore because it cannot see festivals. Discounts drive the model most (28% of attribution); 3 extra points of discount would add ₹9.0 crore of revenue (+8.5%), but that is revenue, not profit |

![Forecast](outputs/chart_forecast.png)

![Backtest](outputs/chart_backtest.png)

![Scenarios and drivers](outputs/chart_scenarios_drivers.png)

## Backtest (Q2–Q4 2025, 90 days ahead from each quarter end)

| Model | Daily error (WAPE) | Quarterly total error | Bias | Ensemble weight |
|:--|--:|--:|--:|--:|
| Seasonal naive (last year × growth) | 14.5% | 2.1% | −0.4% | 0.00 |
| Holt-Winters (damped trend, weekly season) | 11.0% | 6.4% | −6.8% | 0.05 |
| **LightGBM** (calendar, festivals, discounts, marketing) | **6.6%** | 2.7% | −0.0% | 0.95 |
| Ensemble | 6.6% | 2.8% | −0.4% | – |

The seasonal naive model gets quarterly totals right but individual days wrong, because festivals fall on different dates each year. The ensemble weights were chosen on the same three backtest quarters, so its score is slightly optimistic.

## Q1 2026 Forecast

| Month | Forecast (₹ crore) | Same month 2025 | Growth |
|:--|--:|--:|--:|
| January 2026 | 36.0 | 30.3 | +18.9% |
| February 2026 | 31.6 | 26.7 | +18.3% |
| March 2026 | 37.8 | 32.1 | +17.7% |
| **Q1 2026** | **105.5** | **89.1** | **+18.3%** |

Electronics grows fastest (+20.4%), helped by the April 2025 price rise that was not yet in Q1 2025; Apparel is slowest (+15.1%). The full commentary is in [outputs/COMMENTARY.md](outputs/COMMENTARY.md).

## What-if Scenarios (Q1 2026 revenue, ₹105.5 crore base)

| Scenario | Change |
|:--|--:|
| All discounts +3 points | +₹8.99 crore (+8.5%) |
| Marketing spend +20% | +₹1.66 crore (+1.6%) |
| Skip the Republic Day sale | −₹1.84 crore (−1.7%) |
| Marketing spend −20% | −₹2.43 crore (−2.3%) |

Marketing has diminishing returns: cutting 20% loses more than adding 20% gains.

## How the ML Model Works

- **One model for all product lines**, with the product line as a feature, trained on log revenue relative to the recent level (trailing 28-day average), so it can forecast growth that trees cannot extrapolate on their own.
- **Direct multi-step forecasting:** in training, the recent level is measured 1–90 days before each day (chosen at random), with that gap as a feature, so the model learns to forecast up to 90 days ahead without feeding its own forecasts back in.
- **Features:** day of week, month, time of year, Diwali window, Holi, Republic Day and Independence Day sales, planned discount, log marketing spend, festival share of the recent level, days ahead.
- **Ranges:** the 10th and 90th percentiles of actual ÷ forecast in the backtest, for days (0.90–1.11) and for monthly totals (0.96–1.05).
- **Commentary:** written by rules from the numbers, so every sentence can be traced to a figure in `outputs/`.

## Files

| File | Purpose |
|:--|:--|
| `generate_data.py` | Simulates 2023–2025 daily revenue and the Q1 2026 marketing and promotion plan |
| `forecast_engine.py` | Models, backtest, ensemble, ranges, scenarios and driver attribution |
| `report.py` | Charts, `COMMENTARY.md` and `forecast_pack_q1_2026.xlsx` (monthly P10/P50/P90 with formula totals, daily forecast, backtest, scenarios) |
| `test_forecast.py` | Checks that LightGBM beats both baselines, the ensemble is close to unbiased, the range contains the forecast and the Excel totals tie |

## Run It

```
pip install pandas numpy scipy matplotlib lightgbm statsmodels openpyxl
python generate_data.py
python forecast_engine.py
python report.py
python test_forecast.py
```

## Limitations

- Simulated data: real revenue has stock-outs, competitor moves and one-off events that a model trained on three years may not have seen.
- The forecast is only as good as the marketing and promotion plan fed into it; a festival date shift or an unplanned sale changes the answer.
- Scenario results come from the ML model's learned response to discounts and marketing, not from a controlled experiment.

*Fictional company and synthetic data, built for learning.*
