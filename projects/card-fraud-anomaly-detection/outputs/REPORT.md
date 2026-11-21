# Card Fraud Detection — Results

284,807 card transactions, 492 frauds (0.173%), OpenML 1597.

Test set: last 30% of the timeline, 85,443 transactions with 108 frauds.

| model                          | type         |   roc_auc |   pr_auc |   recall@top 0.1% |   recall@top 0.5% |   recall@top 1% |
|:-------------------------------|:-------------|----------:|---------:|------------------:|------------------:|----------------:|
| Rule: largest amounts          | rule         |     0.411 |    0.002 |               0   |               0.9 |             2.8 |
| Isolation Forest               | unsupervised |     0.946 |    0.055 |               0   |              35.2 |            57.4 |
| Local Outlier Factor           | unsupervised |     0.938 |    0.442 |              45.4 |              76.9 |            78.7 |
| Autoencoder                    | unsupervised |     0.917 |    0.076 |               0   |              46.3 |            72.2 |
| Gradient boosting (supervised) | supervised   |     0.973 |    0.81  |              73.1 |              87   |            88.9 |

![PR curves](chart_pr_budget.png)

_recall@top 0.5% = share of frauds caught when analysts review the 0.5% highest-scored transactions._