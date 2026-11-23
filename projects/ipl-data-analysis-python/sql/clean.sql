-- Runs after the raw CSV files are loaded: standardise names, then build two helper views

-- 1. Merge renamed franchises in every team column
UPDATE matches m SET team1 = r.new_name FROM team_renames r WHERE m.team1 = r.old_name;
UPDATE matches m SET team2 = r.new_name FROM team_renames r WHERE m.team2 = r.old_name;
UPDATE matches m SET toss_winner = r.new_name FROM team_renames r WHERE m.toss_winner = r.old_name;
UPDATE matches m SET winner = r.new_name FROM team_renames r WHERE m.winner = r.old_name;
UPDATE deliveries d SET batting_team = r.new_name FROM team_renames r WHERE d.batting_team = r.old_name;

-- 2. Keep the ground name only ("Wankhede Stadium, Mumbai" -> "Wankhede Stadium") and apply venue renames
UPDATE matches SET venue = TRIM(SPLIT_PART(venue, ',', 1));
UPDATE matches m SET venue = r.new_name FROM venue_renames r WHERE m.venue = r.old_name;

-- 3. One row per delivery with the cricket rules worked out once
CREATE VIEW v_balls AS
SELECT d.*,
       m.season,
       COALESCE(d.extra_type, '') NOT LIKE '%wides%'
           AND COALESCE(d.extra_type, '') NOT LIKE '%noballs%'                     AS is_legal,      -- counts towards the over
       COALESCE(d.extra_type, '') NOT LIKE '%wides%'                              AS is_faced,      -- counts as a ball faced
       d.batter_runs + CASE WHEN d.extra_type LIKE '%wides%' OR d.extra_type LIKE '%noballs%'
                            THEN d.extra_runs ELSE 0 END                         AS bowler_runs,   -- byes and leg byes excluded
       d.is_wicket AND COALESCE(d.dismissal_kind, '') NOT IN
           ('run out', 'retired hurt', 'retired out', 'obstructing the field')    AS bowler_wicket,
       CASE WHEN d.over_no <= 5 THEN 'Powerplay (1-6)'
            WHEN d.over_no <= 14 THEN 'Middle (7-15)'
            ELSE 'Death (16-20)' END                                             AS phase
FROM deliveries d
JOIN matches m USING (match_id);

-- 4. One row per innings: total runs, and which team batted first
CREATE VIEW v_innings AS
SELECT match_id, innings, MIN(season) AS season, MIN(batting_team) AS batting_team,
       SUM(total_runs) AS runs, COUNT(*) FILTER (WHERE is_legal) AS legal_balls
FROM v_balls
GROUP BY match_id, innings;
