# Zomato Restaurant Analysis | SQL (PostgreSQL)

The public Zomato restaurants dataset (9,551 restaurants in 15 countries, 8,652 of them in India) cleaned in Python, split into three related tables, and analysed with 18 SQL queries: city coverage, cuisines, price and rating, online delivery and table booking, chains, best-value restaurants and unrated listings.

| | |
|:--|:--|
| **What was analysed** | 9,551 Zomato restaurant listings with city, locality, cuisines, average cost for two, price range (1–4), online delivery and table booking flags, aggregate rating (1–5), rating label and votes. 8,652 listings (90.6%) are in India, and 6,513 of those have a rating |
| **What was done** | Cleaning in Python (ratings of 0 stored as "not rated" NULLs, cuisine text split into a separate table of 19,705 restaurant–cuisine rows); a schema with keys, checks and a view of rated Indian restaurants; 18 queries using joins, CASE, FILTER, HAVING, a self-join for cuisine pairs, window functions (share of total, ROW_NUMBER, running totals, AVG OVER), CTEs, PERCENTILE_CONT and CORR |
| **Key finding** | Price, not delivery, separates ratings: 31% of restaurants in price ranges 3–4 are rated 4.0+, against 4% in range 1. Within the same price range, online delivery moves the average rating by under 0.2 points. One in four Indian listings (24.7%) has no rating at all, and very few of those offer online delivery (1–8% of unrated listings in the four big cities, against 28% of all Indian listings). Delhi NCR dominates the data: New Delhi, Gurgaon and Noida hold 88.7% of Indian listings |

**All 18 queries with their results:** [outputs/RESULTS.md](outputs/RESULTS.md)

![Top cuisines](outputs/chart_top_cuisines.png)

![Price range vs rating](outputs/chart_price_vs_rating.png)

![Delivery vs rating](outputs/chart_delivery.png)

## Schema

```
countries (country_code PK, country, currency)
    │ 1:n
restaurants (restaurant_id PK, restaurant_name, country_code FK, city, locality, avg_cost_for_two,
             has_table_booking, has_online_delivery, price_range, aggregate_rating, rating_text, votes)
    │ 1:n
restaurant_cuisines (restaurant_id FK, cuisine)   -- PK (restaurant_id, cuisine)

view  v_india_rated  = Indian restaurants that have a rating
```

## The 18 Queries

| Level | Query | SQL used |
|:--|:--|:--|
| Basic | Q01 Coverage by country · Q02 Indian cities · Q03 Rating labels | COUNT, AVG, GROUP BY, share with SUM() OVER () |
| Joins | Q04 Most common cuisines · Q05 Best-rated cuisines (50+ rated restaurants) · Q16 Cuisine pairs | JOIN, HAVING, self-join with `a.cuisine < b.cuisine` |
| CASE and FILTER | Q06 Price range vs rating · Q07 Online delivery by price range · Q08 Table booking · Q15 Unrated restaurants | CASE, AVG(...) FILTER (WHERE ...) |
| Rankings and windows | Q09 Largest chains and rating spread · Q12 Top 3 per city · Q17 Above the city average · Q18 Rating ladder per price range | ROW_NUMBER, AVG OVER (PARTITION BY), running SUM OVER, STDDEV_SAMP |
| Distribution | Q10 Delhi localities · Q11 Best value (4.0+ for ₹500 or less) · Q13 Median and 90th-percentile cost · Q14 Votes vs rating | PERCENTILE_CONT, CORR, LN |

## What the Results Show

- **Cuisines:** North Indian is on 45.6% of Indian menus and Chinese on 31.1%; the most common pairing is Chinese with North Indian (1,775 restaurants). The best-rated cuisines with 50+ rated restaurants are Mediterranean (3.98), European (3.91) and Asian (3.85), all at ₹1,400–2,000 for two.
- **Price and rating:** the average rating climbs from 3.20 (price range 1, about ₹300 for two) to 3.73 (range 4, about ₹2,600). Votes follow price too: range 3 averages 458 votes against 60 for range 1.
- **Table booking:** restaurants that take bookings average 3.55 against 3.31, but they also cost almost three times as much (₹1,589 vs ₹546), so price explains much of the gap.
- **Chains:** Cafe Coffee Day (83 outlets), Domino's (79) and Subway (63) are the largest. Barbeque Nation has the best chain average (4.35 over 25 outlets); Pizza Hut has the widest spread (2.4 to 4.6).
- **Best value:** Saravana Bhavan, Connaught Place (4.3, ₹500 for two, 5,172 votes) and Wenger's (4.3, ₹400) lead the 4.0+ restaurants that cost ₹500 or less.
- **Votes and rating:** rating correlates 0.62 with log(votes) but only 0.31 with cost, so popular restaurants rate higher more consistently than expensive ones.

## How It Works

1. `clean_data.py` reads `data/raw/zomato.csv` and `Country-Code.xlsx` and writes `countries.csv`, `restaurants.csv` and `restaurant_cuisines.csv`.
2. `schema.sql` creates the tables, constraints, indexes and the `v_india_rated` view.
3. `queries.sql` holds the 18 queries, each headed by its business question.
4. `run_queries.py` loads the CSV files with COPY, runs every query and writes the results, three charts, `RESULTS.md` and `summary.json`.

## Limitations

- The data is a snapshot from the Zomato API (shared on Kaggle around 2018), not current listings; cities outside Delhi NCR have only about 20 restaurants each.
- Costs are in local currency, so cost comparisons are made only within India.
- Restaurant names with accented letters were garbled in the source file and are kept as they are.

## Run It Yourself

```bash
createdb zomato
pip install -r requirements.txt
python clean_data.py                      # optional: data/ already holds the cleaned CSVs
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/zomato python run_queries.py
```

Or open `schema.sql`, load `data/*.csv`, and run `queries.sql` in pgAdmin or DBeaver.

**Tools:** PostgreSQL 16, SQL, Python (pandas, psycopg2, Matplotlib)

_Data: "Zomato Restaurants Data" (Kaggle, collected from the Zomato API). Used for learning purposes._
