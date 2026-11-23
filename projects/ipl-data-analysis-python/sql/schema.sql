-- IPL 2008-2026 in PostgreSQL: matches, deliveries and two lookup tables for renamed teams and venues
DROP VIEW IF EXISTS v_balls, v_innings;
DROP TABLE IF EXISTS deliveries, matches, team_renames, venue_renames;

CREATE TABLE matches (
    match_id         INTEGER PRIMARY KEY,
    match_date       DATE NOT NULL,
    season           SMALLINT GENERATED ALWAYS AS (EXTRACT(YEAR FROM match_date)::SMALLINT) STORED,
    team1            TEXT NOT NULL,
    team2            TEXT NOT NULL,
    toss_winner      TEXT NOT NULL,
    toss_decision    TEXT NOT NULL CHECK (toss_decision IN ('bat', 'field')),
    result           TEXT NOT NULL,              -- Win, Tie or NoResult
    super_over_winner TEXT,
    winner           TEXT,
    player_of_match  TEXT,
    venue            TEXT NOT NULL,
    city             TEXT
);

CREATE TABLE deliveries (
    match_id       INTEGER NOT NULL REFERENCES matches(match_id),
    innings        SMALLINT NOT NULL,
    over_no        SMALLINT NOT NULL CHECK (over_no BETWEEN 0 AND 19),   -- 0 = first over
    ball_no        SMALLINT NOT NULL,
    batter         TEXT NOT NULL,
    bowler         TEXT NOT NULL,
    non_striker    TEXT NOT NULL,
    extra_type     TEXT,                         -- wides, noballs, byes, legbyes, penalty
    batter_runs    SMALLINT NOT NULL,
    extra_runs     SMALLINT NOT NULL,
    total_runs     SMALLINT NOT NULL,
    is_wicket      BOOLEAN NOT NULL,
    player_out     TEXT,
    dismissal_kind TEXT,
    batting_team   TEXT NOT NULL
);
CREATE INDEX idx_deliveries_match ON deliveries (match_id, innings);
CREATE INDEX idx_deliveries_batter ON deliveries (batter);
CREATE INDEX idx_deliveries_bowler ON deliveries (bowler);

-- Franchises that changed name are counted as one team
CREATE TABLE team_renames (old_name TEXT PRIMARY KEY, new_name TEXT NOT NULL);
INSERT INTO team_renames VALUES
    ('Delhi Daredevils', 'Delhi Capitals'),
    ('Kings XI Punjab', 'Punjab Kings'),
    ('Royal Challengers Bangalore', 'Royal Challengers Bengaluru'),
    ('Rising Pune Supergiants', 'Rising Pune Supergiant');

CREATE TABLE venue_renames (old_name TEXT PRIMARY KEY, new_name TEXT NOT NULL);
INSERT INTO venue_renames VALUES
    ('Feroz Shah Kotla', 'Arun Jaitley Stadium'),
    ('M.Chinnaswamy Stadium', 'M Chinnaswamy Stadium'),
    ('Punjab Cricket Association IS Bindra Stadium', 'Punjab Cricket Association Stadium'),
    ('Sardar Patel Stadium', 'Narendra Modi Stadium'),
    ('Zayed Cricket Stadium', 'Sheikh Zayed Stadium');
