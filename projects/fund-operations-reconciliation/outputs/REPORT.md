# Month-End Reconciliation Report: Aarohan Large Cap Fund

Month-end 30 Oct 2026. 668 records checked across trades, settlements, corporate actions, positions and cash; 16 exceptions raised (14 open), 97.6% cleared automatically.

| Check | Result |
|:--|:--|
| Trade matching | 313 of 320 broker confirmations matched; breaks: Quantity mismatch 3, Amount mismatch 2, Duplicate in book 2, Missing in book 2 |
| Settlements | Settled on time 316, Settled late 2, Failed - pending 2 |
| Corporate actions | Matched 5, Not booked in book 2 |
| Positions | 8 of 20 stocks break; 0 unexplained |
| Negative holdings control | MARUTI: book shows -90 shares |
| Cash | Book ₹65,151,676.35 vs custodian ₹70,846,276.25; difference ₹-5,694,599.90; unexplained ₹0.00 |
| NAV | Book NAV ₹372,740,399 vs corrected ₹378,562,179: misstated by **-153.8 bps** until the breaks are fixed |

## Cash bridge

| Item | ₹ |
|:--|--:|
| Book closing cash | 65,151,676.35 |
| Difference (book minus custodian) | -5,694,599.90 |
| Explained by: Trade breaks (quantity, amount, duplicates, missing) | -4,018,975.40 |
| Explained by: Failed settlements booked as settled | -1,645,976.64 |
| Explained by: Corporate action cash differences | -113,620.00 |
| Explained by: Custodian charges not booked | 83,972.14 |
| Custodian closing cash | 70,846,276.25 |
| **Unexplained** | **0.00** |

## Exception log

| exception_id   | area             | reference   | symbol     | issue                               |   quantity_impact |   cash_impact |   age_days | owner                   | action                                       | status   |
|:---------------|:-----------------|:------------|:-----------|:------------------------------------|------------------:|--------------:|-----------:|:------------------------|:---------------------------------------------|:---------|
| EX001          | Trade            | T0018       | HDFCBANK   | Amount mismatch                     |                 0 |        -1,128 |         25 | Fund accounting         | Rebook commission at agreed rate             | Open     |
| EX002          | Trade            | T0022       | SBIN       | Amount mismatch                     |                 0 |        -2,805 |          7 | Fund accounting         | Rebook commission at agreed rate             | Open     |
| EX003          | Trade            | T0190       | TATASTEEL  | Duplicate in book                   |             13730 |    -1,103,536 |         16 | Fund accounting         | Reverse duplicate booking                    | Open     |
| EX004          | Trade            | T0307       | POWERGRID  | Duplicate in book                   |              3165 |       887,927 |          3 | Fund accounting         | Reverse duplicate booking                    | Open     |
| EX005          | Trade            | T0125       | INFY       | Missing in book                     |             -1500 |    -2,304,104 |          1 | Fund accounting         | Book trade from broker confirmation          | Open     |
| EX006          | Trade            | T0309       | ASIANPAINT | Missing in book                     |              -575 |    -1,361,663 |          7 | Fund accounting         | Book trade from broker confirmation          | Open     |
| EX007          | Trade            | T0071       | TITAN      | Quantity mismatch                   |                10 |        36,118 |         24 | Fund accounting         | Correct book quantity to broker confirmation | Open     |
| EX008          | Trade            | T0299       | SBIN       | Quantity mismatch                   |                10 |        -8,529 |         21 | Fund accounting         | Correct book quantity to broker confirmation | Open     |
| EX009          | Trade            | T0319       | SUNPHARMA  | Quantity mismatch                   |                99 |      -161,256 |         11 | Fund accounting         | Correct book quantity to broker confirmation | Open     |
| EX010          | Settlement       | T0170       | TCS        | Settled late                        |                 0 |             0 |          2 | Settlements / custodian | None (settled); log for broker scorecard     | Resolved |
| EX011          | Settlement       | T0276       | TITAN      | Failed - pending                    |                70 |       266,985 |         15 | Settlements / custodian | Chase counterparty; monitor for buy-in       | Open     |
| EX012          | Settlement       | T0270       | TATASTEEL  | Failed - pending                    |             23875 |     1,912,961 |         11 | Settlements / custodian | Chase counterparty; monitor for buy-in       | Open     |
| EX013          | Settlement       | T0310       | POWERGRID  | Settled late                        |                 0 |             0 |          2 | Settlements / custodian | None (settled); log for broker scorecard     | Resolved |
| EX014          | Corporate action | CA03        | HINDUNILVR | Dividend: Not booked in book        |                 0 |      -113,620 |          1 | Corporate actions       | Book entitlement per custodian               | Open     |
| EX015          | Corporate action | CA07        | MARUTI     | Split: Not booked in book           |              -965 |             0 |          4 | Corporate actions       | Book entitlement per custodian               | Open     |
| EX016          | Cash             | FEE-OCT     | CASH       | Custody fee October 2026 not booked |                 0 |        83,972 |          0 | Fund accounting         | Book fee and accrue going forward            | Open     |
