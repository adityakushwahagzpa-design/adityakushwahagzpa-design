-- Executed trades, written in batches by the server's background thread
CREATE TABLE IF NOT EXISTS trades (
    trade_id        BIGSERIAL PRIMARY KEY,
    executed_at     TIMESTAMP NOT NULL,
    taker_order_id  BIGINT NOT NULL,      -- the incoming order
    maker_order_id  BIGINT NOT NULL,      -- the order that was resting in the book
    price_paise     INTEGER NOT NULL CHECK (price_paise > 0),
    qty             INTEGER NOT NULL CHECK (qty > 0)
);
CREATE INDEX IF NOT EXISTS idx_trades_time ON trades (executed_at);
