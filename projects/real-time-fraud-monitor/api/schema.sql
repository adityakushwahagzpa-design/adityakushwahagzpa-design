-- Fraud monitor storage: every transaction, and every alert a rule raised on it
CREATE TABLE IF NOT EXISTS transactions (
    trans_num   TEXT PRIMARY KEY,
    cc_num      BIGINT NOT NULL,
    unix_time   BIGINT NOT NULL,
    merchant    TEXT NOT NULL,
    category    TEXT NOT NULL,
    amt         NUMERIC(12, 2) NOT NULL CHECK (amt > 0),
    merch_lat   DOUBLE PRECISION NOT NULL,
    merch_long  DOUBLE PRECISION NOT NULL,
    channel     TEXT NOT NULL CHECK (channel IN ('pos', 'online')),
    is_fraud    SMALLINT                       -- label, kept only to score the rules
);
-- card + time: the dashboard's "recent history for this card" query uses it
CREATE INDEX IF NOT EXISTS idx_tx_card_time ON transactions (cc_num, unix_time DESC);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id    BIGSERIAL PRIMARY KEY,
    trans_num   TEXT NOT NULL REFERENCES transactions(trans_num),
    cc_num      BIGINT NOT NULL,
    unix_time   BIGINT NOT NULL,
    rule        TEXT NOT NULL,
    detail      TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'under review', 'closed'))
);
CREATE INDEX IF NOT EXISTS idx_alerts_card_time ON alerts (cc_num, unix_time DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_rule ON alerts (rule);
