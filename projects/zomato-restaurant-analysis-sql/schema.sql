-- Zomato restaurants: three tables built by clean_data.py
DROP VIEW IF EXISTS v_india_rated;
DROP TABLE IF EXISTS restaurant_cuisines, restaurants, countries;

CREATE TABLE countries (
    country_code  INTEGER PRIMARY KEY,
    country       TEXT NOT NULL,
    currency      TEXT
);

CREATE TABLE restaurants (
    restaurant_id        INTEGER PRIMARY KEY,
    restaurant_name      TEXT NOT NULL,
    country_code         INTEGER NOT NULL REFERENCES countries(country_code),
    city                 TEXT NOT NULL,
    locality             TEXT,
    longitude            NUMERIC(11, 7),
    latitude             NUMERIC(11, 7),
    avg_cost_for_two     INTEGER CHECK (avg_cost_for_two > 0),          -- local currency; NULL = not listed
    has_table_booking    BOOLEAN NOT NULL,
    has_online_delivery  BOOLEAN NOT NULL,
    price_range          SMALLINT NOT NULL CHECK (price_range BETWEEN 1 AND 4),
    aggregate_rating     NUMERIC(2, 1) CHECK (aggregate_rating BETWEEN 1 AND 5), -- NULL = not rated
    rating_text          TEXT NOT NULL,
    votes                INTEGER NOT NULL CHECK (votes >= 0)
);

CREATE TABLE restaurant_cuisines (
    restaurant_id  INTEGER NOT NULL REFERENCES restaurants(restaurant_id),
    cuisine        TEXT NOT NULL,
    PRIMARY KEY (restaurant_id, cuisine)
);

CREATE INDEX idx_restaurants_country_city ON restaurants (country_code, city);
CREATE INDEX idx_cuisines_cuisine ON restaurant_cuisines (cuisine);

-- Indian restaurants that have a rating (most questions below are about these)
CREATE VIEW v_india_rated AS
SELECT r.*
FROM restaurants r
WHERE r.country_code = 1 AND r.aggregate_rating IS NOT NULL;
