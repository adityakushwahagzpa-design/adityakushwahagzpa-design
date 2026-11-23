-- Q01 | Coverage by country | How many restaurants does Zomato list in each country, and how well rated are they?
SELECT c.country,
       COUNT(*)                                             AS restaurants,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS share_pct,
       COUNT(r.aggregate_rating)                            AS rated,
       ROUND(AVG(r.aggregate_rating), 2)                    AS avg_rating
FROM restaurants r
JOIN countries c USING (country_code)
GROUP BY c.country
ORDER BY restaurants DESC;

-- Q02 | Indian cities | Which Indian cities have the most restaurants, and what do they cost?
SELECT city,
       COUNT(*)                                                   AS restaurants,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)         AS share_of_india_pct,
       ROUND(AVG(avg_cost_for_two))                               AS avg_cost_for_two_inr,
       ROUND(AVG(aggregate_rating), 2)                            AS avg_rating
FROM restaurants
WHERE country_code = 1
GROUP BY city
ORDER BY restaurants DESC
LIMIT 10;

-- Q03 | Rating labels | How are Indian restaurants spread across Zomato's rating labels?
SELECT rating_text,
       COUNT(*)                                             AS restaurants,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)   AS share_pct,
       MIN(aggregate_rating)                                AS min_rating,
       MAX(aggregate_rating)                                AS max_rating
FROM restaurants
WHERE country_code = 1
GROUP BY rating_text
ORDER BY min_rating NULLS FIRST;

-- Q04 | Most common cuisines | Which cuisines appear on the most Indian restaurant menus?
SELECT rc.cuisine,
       COUNT(*)                                                                  AS restaurants,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM restaurants WHERE country_code = 1), 1) AS pct_of_restaurants,
       ROUND(AVG(r.aggregate_rating), 2)                                         AS avg_rating
FROM restaurant_cuisines rc
JOIN restaurants r USING (restaurant_id)
WHERE r.country_code = 1
GROUP BY rc.cuisine
ORDER BY restaurants DESC
LIMIT 10;

-- Q05 | Best-rated cuisines | Which cuisines are rated highest, counting only those with 50+ rated restaurants?
SELECT rc.cuisine,
       COUNT(*)                          AS rated_restaurants,
       ROUND(AVG(v.aggregate_rating), 2) AS avg_rating,
       ROUND(AVG(v.avg_cost_for_two))    AS avg_cost_for_two_inr
FROM restaurant_cuisines rc
JOIN v_india_rated v USING (restaurant_id)
GROUP BY rc.cuisine
HAVING COUNT(*) >= 50
ORDER BY avg_rating DESC
LIMIT 10;

-- Q06 | Price range | Do pricier restaurants get better ratings and more votes?
SELECT price_range,
       COUNT(*)                          AS rated_restaurants,
       ROUND(AVG(avg_cost_for_two))      AS avg_cost_for_two_inr,
       ROUND(AVG(aggregate_rating), 2)   AS avg_rating,
       ROUND(AVG(votes))                 AS avg_votes,
       ROUND(100.0 * AVG(CASE WHEN aggregate_rating >= 4.0 THEN 1 ELSE 0 END), 1) AS pct_rated_4_plus
FROM v_india_rated
GROUP BY price_range
ORDER BY price_range;

-- Q07 | Online delivery | Within each price range, are restaurants with online delivery rated differently?
SELECT price_range,
       ROUND(AVG(aggregate_rating) FILTER (WHERE has_online_delivery), 2)     AS rating_with_delivery,
       ROUND(AVG(aggregate_rating) FILTER (WHERE NOT has_online_delivery), 2) AS rating_without_delivery,
       ROUND(100.0 * AVG(CASE WHEN has_online_delivery THEN 1 ELSE 0 END), 1) AS pct_offering_delivery
FROM v_india_rated
GROUP BY price_range
ORDER BY price_range;

-- Q08 | Table booking | How do restaurants that take table bookings compare with those that do not?
SELECT CASE WHEN has_table_booking THEN 'Takes bookings' ELSE 'No bookings' END AS table_booking,
       COUNT(*)                          AS rated_restaurants,
       ROUND(AVG(avg_cost_for_two))      AS avg_cost_for_two_inr,
       ROUND(AVG(aggregate_rating), 2)   AS avg_rating,
       ROUND(AVG(votes))                 AS avg_votes
FROM v_india_rated
GROUP BY has_table_booking
ORDER BY table_booking;

-- Q09 | Largest chains | Which chains have the most outlets in India, and how consistent are their ratings?
SELECT restaurant_name,
       COUNT(*)                                     AS outlets,
       COUNT(aggregate_rating)                      AS rated_outlets,
       ROUND(AVG(aggregate_rating), 2)              AS avg_rating,
       ROUND(STDDEV_SAMP(aggregate_rating), 2)      AS rating_std_dev,
       MIN(aggregate_rating)                        AS worst,
       MAX(aggregate_rating)                        AS best
FROM restaurants
WHERE country_code = 1
GROUP BY restaurant_name
HAVING COUNT(*) >= 20
ORDER BY outlets DESC;

-- Q10 | Delhi NCR localities | Which localities in New Delhi have the most restaurants, and which rate best?
SELECT locality,
       COUNT(*)                          AS restaurants,
       COUNT(aggregate_rating)           AS rated,
       ROUND(AVG(aggregate_rating), 2)   AS avg_rating,
       ROUND(AVG(avg_cost_for_two))      AS avg_cost_for_two_inr
FROM restaurants
WHERE country_code = 1 AND city = 'New Delhi'
GROUP BY locality
HAVING COUNT(aggregate_rating) >= 20
ORDER BY restaurants DESC
LIMIT 10;

-- Q11 | Best value | Which restaurants are rated 4.0+ yet cost ₹500 or less for two? (most votes first)
SELECT restaurant_name, city, locality, avg_cost_for_two AS cost_for_two_inr, aggregate_rating, votes
FROM v_india_rated
WHERE aggregate_rating >= 4.0 AND avg_cost_for_two <= 500
ORDER BY votes DESC
LIMIT 10;

-- Q12 | Top 3 per city | What are the three most-voted restaurants in each of the four biggest cities?
WITH big_cities AS (
    SELECT city FROM restaurants WHERE country_code = 1
    GROUP BY city ORDER BY COUNT(*) DESC LIMIT 4
), ranked AS (
    SELECT v.city, v.restaurant_name, v.aggregate_rating, v.votes,
           ROW_NUMBER() OVER (PARTITION BY v.city ORDER BY v.votes DESC) AS rank_in_city
    FROM v_india_rated v
    JOIN big_cities b USING (city)
)
SELECT city, rank_in_city, restaurant_name, aggregate_rating, votes
FROM ranked
WHERE rank_in_city <= 3
ORDER BY city, rank_in_city;

-- Q13 | Cost spread | What is the median and 90th-percentile cost for two in each big city?
SELECT city,
       COUNT(avg_cost_for_two)                                                   AS priced_restaurants,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY avg_cost_for_two)             AS median_cost_inr,
       PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY avg_cost_for_two)             AS p90_cost_inr,
       MAX(avg_cost_for_two)                                                     AS max_cost_inr
FROM restaurants
WHERE country_code = 1
GROUP BY city
HAVING COUNT(*) >= 100
ORDER BY median_cost_inr DESC;

-- Q14 | Votes vs rating | How strongly do votes move with ratings, cost and price range?
SELECT ROUND(CORR(votes, aggregate_rating)::numeric, 3)           AS corr_votes_rating,
       ROUND(CORR(LN(votes + 1), aggregate_rating)::numeric, 3)   AS corr_log_votes_rating,
       ROUND(CORR(avg_cost_for_two, aggregate_rating)::numeric, 3) AS corr_cost_rating,
       ROUND(CORR(price_range, aggregate_rating)::numeric, 3)     AS corr_price_range_rating
FROM v_india_rated;

-- Q15 | Unrated restaurants | Where are restaurants still unrated, and do they offer delivery?
SELECT city,
       COUNT(*)                                                                   AS restaurants,
       COUNT(*) FILTER (WHERE aggregate_rating IS NULL)                           AS not_rated,
       ROUND(100.0 * COUNT(*) FILTER (WHERE aggregate_rating IS NULL) / COUNT(*), 1) AS not_rated_pct,
       ROUND(100.0 * AVG(CASE WHEN has_online_delivery THEN 1 ELSE 0 END)
             FILTER (WHERE aggregate_rating IS NULL), 1)                          AS delivery_pct_among_unrated
FROM restaurants
WHERE country_code = 1
GROUP BY city
HAVING COUNT(*) >= 100
ORDER BY not_rated_pct DESC;

-- Q16 | Cuisine pairs | Which two cuisines are most often served together?
SELECT a.cuisine AS cuisine_1, b.cuisine AS cuisine_2, COUNT(*) AS restaurants
FROM restaurant_cuisines a
JOIN restaurant_cuisines b ON a.restaurant_id = b.restaurant_id AND a.cuisine < b.cuisine
JOIN restaurants r ON r.restaurant_id = a.restaurant_id
WHERE r.country_code = 1
GROUP BY a.cuisine, b.cuisine
ORDER BY restaurants DESC
LIMIT 10;

-- Q17 | Above the city average | In each big city, how many rated restaurants beat their city's average rating?
WITH scored AS (
    SELECT city, aggregate_rating,
           AVG(aggregate_rating) OVER (PARTITION BY city) AS city_avg
    FROM v_india_rated
)
SELECT city,
       COUNT(*)                                             AS rated_restaurants,
       ROUND(MAX(city_avg), 2)                              AS city_avg_rating,
       COUNT(*) FILTER (WHERE aggregate_rating > city_avg)  AS above_city_avg,
       ROUND(100.0 * COUNT(*) FILTER (WHERE aggregate_rating > city_avg) / COUNT(*), 1) AS above_pct
FROM scored
GROUP BY city
HAVING COUNT(*) >= 100
ORDER BY city_avg_rating DESC;

-- Q18 | Rating ladder | Within each price range, where does each rating label fall as a share and a running total?
SELECT price_range, rating_text,
       COUNT(*) AS restaurants,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY price_range), 1) AS share_pct,
       ROUND(100.0 * SUM(COUNT(*)) OVER (PARTITION BY price_range ORDER BY MIN(aggregate_rating) DESC)
             / SUM(COUNT(*)) OVER (PARTITION BY price_range), 1)                  AS cumulative_from_top_pct
FROM v_india_rated
GROUP BY price_range, rating_text
ORDER BY price_range, MIN(aggregate_rating) DESC;
