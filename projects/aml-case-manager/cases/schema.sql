-- AML case management: one row per case, the transfers behind it, and a log of status changes
DROP TABLE IF EXISTS case_events, case_transfers, cases;

CREATE TABLE cases (
    case_id      SERIAL PRIMARY KEY,
    patterns     TEXT NOT NULL,                       -- e.g. 'cycle' or 'fan_in + fan_out'
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'under review', 'closed')),
    opened_for   TIMESTAMP NOT NULL,                  -- time of the first suspicious transfer
    detail       TEXT NOT NULL,
    accounts     TEXT[] NOT NULL,
    n_accounts   INTEGER NOT NULL,
    n_transfers  INTEGER NOT NULL,
    total_usd    NUMERIC(14, 2) NOT NULL,
    evidence     JSONB NOT NULL,                      -- the subgraph: every transfer with sender, receiver, time and amount
    created_at   TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE case_transfers (
    case_id      INTEGER NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    transfer_id  BIGINT NOT NULL,
    PRIMARY KEY (case_id, transfer_id)
);
CREATE INDEX idx_case_transfers_transfer ON case_transfers (transfer_id);

CREATE TABLE case_events (
    event_id     SERIAL PRIMARY KEY,
    case_id      INTEGER NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
    at           TIMESTAMP NOT NULL DEFAULT now(),
    from_status  TEXT,
    to_status    TEXT NOT NULL,
    note         TEXT
);
