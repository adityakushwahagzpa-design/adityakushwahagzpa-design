# Marketing Budget Memo (rule-based)

*Written by report.py from the model outputs. `python ai_analyst.py --memo` has Claude write this memo using the
same numbers through tool calls.*

## Recommendation
Move budget towards YouTube (+40%), Google Search (+18%), Meta Ads (+4%) and away from Influencers (-32%), Affiliate (-40%), keeping the
total weekly spend the same. The response curves put the gain at **4.9% more media-driven
revenue** for the same money; checked against the true curves (possible because the data is simulated) the gain is
3.5%.

## Why
- **Last-touch reporting misleads.** It gives Direct 17.5% of the credit against a true incremental share
  of 2.7%, and gives YouTube only 6.4% against a true 28.5%.
  The ML counterfactual model is closest to the truth (error 1.1 pp vs 12.1 pp for last touch);
  it credits YouTube with 28.2%.
- **The next rupee earns most in YouTube**: marginal ROI 1.40 against an average ROI of 2.97.
- **Calibration matters.** Lift tests cut the MMM's average ROI error from 0.67 to
  0.40 revenue per rupee.

## Risks and next experiment
Affiliate has no lift test, so its ROI rests on the weekly data alone (range
0.55-1.31). Run a holdout test there before cutting it further.
Revenue is not profit: margins and returns are outside this model.
