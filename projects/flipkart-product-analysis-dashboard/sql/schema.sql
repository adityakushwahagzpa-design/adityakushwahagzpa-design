-- Flipkart-style product analysis in PostgreSQL: products and order lines for 2025
DROP VIEW IF EXISTS v_order_lines, v_products;
DROP TABLE IF EXISTS orders, products;

CREATE TABLE products (
    product_id        TEXT PRIMARY KEY,
    product_name      TEXT NOT NULL,
    category          TEXT NOT NULL,
    sub_category      TEXT NOT NULL,
    brand             TEXT NOT NULL,
    mrp               INTEGER NOT NULL CHECK (mrp > 0),
    selling_price     INTEGER NOT NULL CHECK (selling_price > 0),
    rating            NUMERIC(2, 1) NOT NULL CHECK (rating BETWEEN 1 AND 5),
    rating_count      INTEGER NOT NULL CHECK (rating_count >= 0),
    flipkart_assured  BOOLEAN NOT NULL,
    CHECK (selling_price <= mrp)
);

CREATE TABLE orders (
    order_id         TEXT PRIMARY KEY,
    order_date       DATE NOT NULL CHECK (order_date BETWEEN '2025-01-01' AND '2025-12-31'),
    product_id       TEXT NOT NULL REFERENCES products(product_id),
    quantity         SMALLINT NOT NULL CHECK (quantity > 0),
    unit_price_paid  INTEGER NOT NULL CHECK (unit_price_paid > 0),
    returned         BOOLEAN NOT NULL
);
CREATE INDEX idx_orders_product ON orders (product_id);
CREATE INDEX idx_orders_date ON orders (order_date);

-- Products with discount % and the same discount bands as the Excel dashboard
CREATE VIEW v_products AS
SELECT p.*,
       1 - p.selling_price::numeric / p.mrp AS discount_pct,
       CASE WHEN 1 - p.selling_price::numeric / p.mrp < 0.1 THEN '0-10%'
            WHEN 1 - p.selling_price::numeric / p.mrp < 0.3 THEN '10-30%'
            WHEN 1 - p.selling_price::numeric / p.mrp < 0.5 THEN '30-50%'
            WHEN 1 - p.selling_price::numeric / p.mrp < 0.7 THEN '50-70%'
            ELSE '70%+' END                  AS discount_band
FROM products p;

-- Order lines joined to their product, with revenue (GMV) per line
CREATE VIEW v_order_lines AS
SELECT o.*, o.quantity * o.unit_price_paid AS revenue,
       p.category, p.sub_category, p.brand, p.rating, p.flipkart_assured, p.discount_band,
       EXTRACT(MONTH FROM o.order_date)::INT AS month_no,
       o.order_date BETWEEN '2025-10-01' AND '2025-10-10' AS big_billion_days
FROM orders o
JOIN v_products p USING (product_id);
