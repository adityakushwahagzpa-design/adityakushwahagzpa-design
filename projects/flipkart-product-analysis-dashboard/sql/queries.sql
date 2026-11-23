-- Q01 | Headline KPIs | Products, order lines, units, GMV, average discount, rating and return rate
SELECT (SELECT COUNT(*) FROM products)                                       AS products,
       COUNT(*)                                                              AS order_lines,
       SUM(quantity)                                                         AS units_sold,
       ROUND(SUM(revenue) / 1e7, 2)                                          AS gmv_crore,
       (SELECT ROUND(100 * AVG(discount_pct), 1) FROM v_products)            AS avg_discount_pct,
       (SELECT ROUND(AVG(rating), 2) FROM products)                          AS avg_rating,
       ROUND(100.0 * AVG(CASE WHEN returned THEN 1 ELSE 0 END), 1)           AS return_rate_pct
FROM v_order_lines;

-- Q02 | Category performance | Products, units, GMV, share, discount, rating and return rate by category
WITH sales AS (
    SELECT category, SUM(quantity) AS units, SUM(revenue) AS gmv,
           AVG(CASE WHEN returned THEN 1.0 ELSE 0 END) AS return_rate
    FROM v_order_lines GROUP BY category
), cat AS (
    SELECT category, COUNT(*) AS products, AVG(discount_pct) AS avg_discount, AVG(rating) AS avg_rating
    FROM v_products GROUP BY category
)
SELECT c.category, c.products, s.units,
       ROUND(s.gmv / 1e7, 2)                                  AS gmv_crore,
       ROUND(100 * s.gmv / SUM(s.gmv) OVER (), 1)             AS gmv_share_pct,
       ROUND(100 * c.avg_discount, 1)                         AS avg_discount_pct,
       ROUND(c.avg_rating, 2)                                 AS avg_rating,
       ROUND(100 * s.return_rate, 1)                          AS return_rate_pct
FROM cat c
JOIN sales s USING (category)
ORDER BY s.gmv DESC;

-- Q03 | Monthly sales and growth | GMV by month with month-on-month change
SELECT month_no,
       TO_CHAR(MAKE_DATE(2025, month_no, 1), 'Mon')                              AS month,
       ROUND(SUM(revenue) / 1e7, 2)                                              AS gmv_crore,
       SUM(quantity)                                                             AS units,
       ROUND(100.0 * (SUM(revenue) / LAG(SUM(revenue)) OVER (ORDER BY month_no) - 1), 1) AS mom_change_pct
FROM v_order_lines
GROUP BY month_no
ORDER BY month_no;

-- Q04 | Big Billion Days | How much bigger is a sale day than an ordinary day?
SELECT CASE WHEN big_billion_days THEN 'Big Billion Days (1-10 Oct)' ELSE 'Rest of the year' END AS period,
       COUNT(DISTINCT order_date)                                       AS days,
       ROUND(SUM(revenue) / COUNT(DISTINCT order_date) / 1e5, 2)        AS gmv_per_day_lakh,
       ROUND(SUM(quantity)::numeric / COUNT(DISTINCT order_date), 1)    AS units_per_day,
       ROUND(AVG(1 - unit_price_paid::numeric / (SELECT selling_price FROM products p WHERE p.product_id = l.product_id)) * 100, 1)
                                                                        AS extra_discount_pct
FROM v_order_lines l
GROUP BY big_billion_days
ORDER BY period;

-- Q05 | Discount depth | Rating, units per product and return rate for each discount band
WITH units AS (
    SELECT product_id, SUM(quantity) AS units, COUNT(*) AS lines,
           COUNT(*) FILTER (WHERE returned) AS returned_lines
    FROM orders GROUP BY product_id
)
SELECT p.discount_band,
       COUNT(*)                                                           AS products,
       ROUND(AVG(p.rating), 2)                                            AS avg_rating,
       ROUND(SUM(COALESCE(u.units, 0))::numeric / COUNT(*), 1)            AS units_per_product,
       ROUND(100.0 * SUM(u.returned_lines) / SUM(u.lines), 1)             AS return_rate_pct
FROM v_products p
LEFT JOIN units u USING (product_id)
GROUP BY p.discount_band
ORDER BY p.discount_band;

-- Q06 | Flipkart Assured | Do Assured products rate better, sell more and get returned less?
WITH units AS (
    SELECT product_id, SUM(quantity) AS units, COUNT(*) AS lines,
           COUNT(*) FILTER (WHERE returned) AS returned_lines
    FROM orders GROUP BY product_id
)
SELECT CASE WHEN p.flipkart_assured THEN 'Assured' ELSE 'Not assured' END AS flipkart_assured,
       COUNT(*)                                                           AS products,
       ROUND(AVG(p.rating), 2)                                            AS avg_rating,
       ROUND(SUM(COALESCE(u.units, 0))::numeric / COUNT(*), 1)            AS units_per_product,
       ROUND(100.0 * SUM(u.returned_lines) / SUM(u.lines), 1)             AS return_rate_pct
FROM v_products p
LEFT JOIN units u USING (product_id)
GROUP BY p.flipkart_assured
ORDER BY flipkart_assured;

-- Q07 | Top 10 brands | Brands with the highest GMV
SELECT brand,
       COUNT(DISTINCT product_id)        AS products_sold,
       ROUND(SUM(revenue) / 1e7, 2)      AS gmv_crore,
       ROUND(AVG(rating), 2)             AS avg_rating_per_order_line,
       STRING_AGG(DISTINCT category, ', ') AS categories
FROM v_order_lines
GROUP BY brand
ORDER BY SUM(revenue) DESC
LIMIT 10;

-- Q08 | Category leaders | The top 2 brands by GMV in every category
WITH b AS (
    SELECT category, brand, SUM(revenue) AS gmv,
           RANK() OVER (PARTITION BY category ORDER BY SUM(revenue) DESC) AS rk,
           SUM(SUM(revenue)) OVER (PARTITION BY category)                 AS category_gmv
    FROM v_order_lines
    GROUP BY category, brand
)
SELECT category, rk AS rank_in_category, brand,
       ROUND(gmv / 1e5, 1)                    AS gmv_lakh,
       ROUND(100 * gmv / category_gmv, 1)     AS share_of_category_pct
FROM b
WHERE rk <= 2
ORDER BY category_gmv DESC, rk;

-- Q09 | Returns by sub-category | Which sub-categories are returned most? (300+ order lines)
SELECT category, sub_category,
       COUNT(*)                                                          AS order_lines,
       ROUND(100.0 * AVG(CASE WHEN returned THEN 1 ELSE 0 END), 1)       AS return_rate_pct,
       ROUND(SUM(revenue) FILTER (WHERE returned) / 1e5, 1)              AS returned_gmv_lakh
FROM v_order_lines
GROUP BY category, sub_category
HAVING COUNT(*) >= 300
ORDER BY return_rate_pct DESC
LIMIT 10;

-- Q10 | Price bands | How do cheap and expensive products differ in units and GMV?
SELECT CASE WHEN selling_price < 500 THEN '1. Under 500'
            WHEN selling_price < 2000 THEN '2. 500-1,999'
            WHEN selling_price < 10000 THEN '3. 2,000-9,999'
            WHEN selling_price < 30000 THEN '4. 10,000-29,999'
            ELSE '5. 30,000+' END                                   AS price_band_rs,
       COUNT(DISTINCT p.product_id)                                 AS products,
       SUM(o.quantity)                                              AS units,
       ROUND(SUM(o.quantity * o.unit_price_paid) / 1e7, 2)          AS gmv_crore,
       ROUND(100.0 * SUM(o.quantity * o.unit_price_paid) / SUM(SUM(o.quantity * o.unit_price_paid)) OVER (), 1) AS gmv_share_pct
FROM products p
JOIN orders o USING (product_id)
GROUP BY price_band_rs
ORDER BY price_band_rs;

-- Q11 | GMV concentration | What share of GMV comes from the top 10% and top 20% of products?
WITH p AS (
    SELECT product_id, SUM(revenue) AS gmv,
           NTILE(10) OVER (ORDER BY SUM(revenue) DESC) AS decile
    FROM v_order_lines
    GROUP BY product_id
)
SELECT decile,
       COUNT(*)                                                       AS products,
       ROUND(100 * SUM(gmv) / SUM(SUM(gmv)) OVER (), 1)               AS gmv_share_pct,
       ROUND(100 * SUM(SUM(gmv)) OVER (ORDER BY decile) / SUM(SUM(gmv)) OVER (), 1) AS cumulative_share_pct
FROM p
GROUP BY decile
ORDER BY decile;

-- Q12 | Best sellers | The 10 products with the most units sold
SELECT p.product_name, p.category, p.selling_price, p.rating,
       SUM(o.quantity)                                    AS units,
       ROUND(SUM(o.quantity * o.unit_price_paid) / 1e5, 2) AS gmv_lakh
FROM products p
JOIN orders o USING (product_id)
GROUP BY p.product_id, p.product_name, p.category, p.selling_price, p.rating
ORDER BY units DESC, gmv_lakh DESC
LIMIT 10;

-- Q13 | Low-rated products that still sell | Products rated under 3.5 with the most GMV
SELECT p.product_name, p.category, p.rating,
       ROUND(100 * (1 - p.selling_price::numeric / p.mrp), 1) AS discount_pct,
       SUM(o.quantity)                                         AS units,
       ROUND(100.0 * AVG(CASE WHEN o.returned THEN 1 ELSE 0 END), 1) AS return_rate_pct
FROM products p
JOIN orders o USING (product_id)
WHERE p.rating < 3.5
GROUP BY p.product_id, p.product_name, p.category, p.rating, p.selling_price, p.mrp
ORDER BY SUM(o.quantity * o.unit_price_paid) DESC
LIMIT 10;

-- Q14 | Unsold products | How many products had no orders at all in 2025, by category?
SELECT p.category,
       COUNT(*)                                                     AS products,
       COUNT(*) FILTER (WHERE o.product_id IS NULL)                 AS no_orders,
       ROUND(100.0 * COUNT(*) FILTER (WHERE o.product_id IS NULL) / COUNT(*), 1) AS no_orders_pct
FROM products p
LEFT JOIN (SELECT DISTINCT product_id FROM orders) o USING (product_id)
GROUP BY p.category
ORDER BY no_orders_pct DESC;
