-- Q01 | Scoring by season | How have first-innings scores, 200+ totals and sixes changed season by season?
WITH first_inn AS (
    SELECT season, runs FROM v_innings WHERE innings = 1
), sixes AS (
    SELECT season, COUNT(*) FILTER (WHERE batter_runs = 6) AS sixes FROM v_balls GROUP BY season
)
SELECT f.season,
       COUNT(*)                                   AS matches,
       ROUND(AVG(f.runs), 1)                      AS avg_first_innings,
       MAX(f.runs)                                AS highest_first_innings,
       (SELECT COUNT(*) FROM v_innings i WHERE i.season = f.season AND i.runs >= 200) AS totals_200_plus,
       ROUND(MAX(s.sixes)::numeric / COUNT(*), 1) AS sixes_per_match
FROM first_inn f
JOIN sixes s USING (season)
GROUP BY f.season
ORDER BY f.season;

-- Q02 | Before and after the Impact Player rule | How do 2008-2022 and 2023-2026 compare?
SELECT CASE WHEN season >= 2023 THEN '2023-2026' ELSE '2008-2022' END AS era,
       COUNT(DISTINCT match_id)                                    AS matches,
       ROUND(AVG(runs) FILTER (WHERE innings = 1), 1)              AS avg_first_innings,
       COUNT(*) FILTER (WHERE runs >= 200)                         AS totals_200_plus,
       ROUND(6.0 * SUM(runs) / SUM(legal_balls), 2)                AS run_rate
FROM v_innings
GROUP BY era
ORDER BY era;

-- Q03 | Run rate by phase | How fast do teams score in the powerplay, middle and death overs each season?
SELECT season,
       ROUND(6.0 * SUM(total_runs) FILTER (WHERE phase = 'Powerplay (1-6)')
             / COUNT(*) FILTER (WHERE phase = 'Powerplay (1-6)' AND is_legal), 2) AS powerplay_rr,
       ROUND(6.0 * SUM(total_runs) FILTER (WHERE phase = 'Middle (7-15)')
             / COUNT(*) FILTER (WHERE phase = 'Middle (7-15)' AND is_legal), 2)   AS middle_rr,
       ROUND(6.0 * SUM(total_runs) FILTER (WHERE phase = 'Death (16-20)')
             / COUNT(*) FILTER (WHERE phase = 'Death (16-20)' AND is_legal), 2)   AS death_rr
FROM v_balls
GROUP BY season
ORDER BY season;

-- Q04 | Toss and chasing | Does winning the toss, or batting second, win matches?
WITH bat_first AS (
    SELECT match_id, batting_team AS team_batting_first FROM v_innings WHERE innings = 1
)
SELECT COUNT(*)                                                                         AS matches_with_result,
       ROUND(100.0 * AVG(CASE WHEN m.toss_decision = 'field' THEN 1 ELSE 0 END), 1)    AS chose_to_field_pct,
       ROUND(100.0 * AVG(CASE WHEN m.toss_winner = m.winner THEN 1 ELSE 0 END), 1)     AS toss_winner_won_pct,
       ROUND(100.0 * AVG(CASE WHEN m.winner <> b.team_batting_first THEN 1 ELSE 0 END), 1) AS chasing_team_won_pct
FROM matches m
JOIN bat_first b USING (match_id)
WHERE m.result = 'Win';

-- Q05 | Champions | Who won each final? (the last match of each season)
WITH ranked AS (
    SELECT season, match_date, team1, team2, winner, venue,
           ROW_NUMBER() OVER (PARTITION BY season ORDER BY match_date DESC, match_id DESC) AS rn
    FROM matches
)
SELECT season, winner AS champion,
       CASE WHEN winner = team1 THEN team2 ELSE team1 END AS runner_up,
       venue
FROM ranked
WHERE rn = 1
ORDER BY season;

-- Q06 | Team records | Matches, wins, win % and titles for every franchise
WITH sides AS (
    SELECT season, team1 AS team, winner FROM matches
    UNION ALL
    SELECT season, team2, winner FROM matches
), finals AS (
    SELECT DISTINCT ON (season) season, winner FROM matches ORDER BY season, match_date DESC, match_id DESC
)
SELECT s.team,
       COUNT(DISTINCT s.season)                                       AS seasons,
       COUNT(*)                                                       AS matches,
       COUNT(*) FILTER (WHERE s.team = s.winner)                      AS wins,
       ROUND(100.0 * COUNT(*) FILTER (WHERE s.team = s.winner) / COUNT(*), 1) AS win_pct,
       (SELECT COUNT(*) FROM finals f WHERE f.winner = s.team)        AS titles
FROM sides s
GROUP BY s.team
ORDER BY titles DESC, win_pct DESC;

-- Q07 | Top run scorers | Who has scored the most runs, and how fast?
SELECT b.batter,
       SUM(b.batter_runs)                                            AS runs,
       COUNT(*) FILTER (WHERE b.is_faced)                            AS balls_faced,
       ROUND(100.0 * SUM(b.batter_runs) / COUNT(*) FILTER (WHERE b.is_faced), 2) AS strike_rate,
       COUNT(*) FILTER (WHERE b.batter_runs = 6)                     AS sixes,
       COUNT(DISTINCT b.season)                                      AS seasons
FROM v_balls b
GROUP BY b.batter
ORDER BY runs DESC
LIMIT 10;

-- Q08 | Fastest scorers | Highest strike rate among batters with 1,500+ balls faced
SELECT batter,
       SUM(batter_runs)                                              AS runs,
       COUNT(*) FILTER (WHERE is_faced)                              AS balls_faced,
       ROUND(100.0 * SUM(batter_runs) / COUNT(*) FILTER (WHERE is_faced), 2) AS strike_rate
FROM v_balls
GROUP BY batter
HAVING COUNT(*) FILTER (WHERE is_faced) >= 1500
ORDER BY strike_rate DESC
LIMIT 10;

-- Q09 | Top wicket takers | Most wickets, with economy and average
SELECT bowler,
       COUNT(*) FILTER (WHERE bowler_wicket)                                     AS wickets,
       ROUND(6.0 * SUM(bowler_runs) / COUNT(*) FILTER (WHERE is_legal), 2)       AS economy,
       ROUND(SUM(bowler_runs)::numeric / NULLIF(COUNT(*) FILTER (WHERE bowler_wicket), 0), 2) AS bowling_average
FROM v_balls
GROUP BY bowler
ORDER BY wickets DESC
LIMIT 10;

-- Q10 | Economy and the death overs | Most economical bowlers (1,500+ legal balls) and their death-over economy
SELECT bowler,
       COUNT(*) FILTER (WHERE is_legal)                                          AS legal_balls,
       ROUND(6.0 * SUM(bowler_runs) / COUNT(*) FILTER (WHERE is_legal), 2)       AS economy,
       ROUND(6.0 * SUM(bowler_runs) FILTER (WHERE phase = 'Death (16-20)')
             / NULLIF(COUNT(*) FILTER (WHERE phase = 'Death (16-20)' AND is_legal), 0), 2) AS death_economy
FROM v_balls
GROUP BY bowler
HAVING COUNT(*) FILTER (WHERE is_legal) >= 1500
ORDER BY economy
LIMIT 10;

-- Q11 | Orange and Purple Cap | Who scored the most runs and took the most wickets in each season?
WITH bat AS (
    SELECT season, batter AS player, SUM(batter_runs) AS runs,
           RANK() OVER (PARTITION BY season ORDER BY SUM(batter_runs) DESC) AS rk
    FROM v_balls GROUP BY season, batter
), bowl AS (
    SELECT season, bowler AS player, COUNT(*) FILTER (WHERE bowler_wicket) AS wickets,
           RANK() OVER (PARTITION BY season ORDER BY COUNT(*) FILTER (WHERE bowler_wicket) DESC,
                                                     SUM(bowler_runs)::numeric / NULLIF(COUNT(*) FILTER (WHERE is_legal), 0)) AS rk
    FROM v_balls GROUP BY season, bowler
)
SELECT b.season, b.player AS orange_cap, b.runs, w.player AS purple_cap, w.wickets
FROM bat b
JOIN bowl w ON w.season = b.season AND w.rk = 1
WHERE b.rk = 1
ORDER BY b.season;

-- Q12 | Highest individual innings | The 10 biggest scores by one batter in one match
SELECT b.batter, b.season, b.batting_team,
       SUM(b.batter_runs)                    AS runs,
       COUNT(*) FILTER (WHERE b.is_faced)    AS balls,
       COUNT(*) FILTER (WHERE b.batter_runs = 6) AS sixes
FROM v_balls b
GROUP BY b.match_id, b.batter, b.season, b.batting_team
ORDER BY runs DESC, balls
LIMIT 10;

-- Q13 | Venues | Average first-innings score and how often the team batting first wins (30+ matches)
WITH first_inn AS (
    SELECT match_id, batting_team, runs FROM v_innings WHERE innings = 1
)
SELECT m.venue,
       COUNT(*)                                                                 AS matches,
       ROUND(AVG(f.runs), 1)                                                    AS avg_first_innings,
       ROUND(100.0 * AVG(CASE WHEN m.result = 'Win' AND m.winner = f.batting_team THEN 1 ELSE 0 END), 1) AS bat_first_won_pct
FROM matches m
JOIN first_inn f USING (match_id)
GROUP BY m.venue
HAVING COUNT(*) >= 30
ORDER BY avg_first_innings DESC;

-- Q14 | Player of the match | Who has won the most player-of-the-match awards?
SELECT player_of_match, COUNT(*) AS awards,
       RANK() OVER (ORDER BY COUNT(*) DESC) AS rank
FROM matches
WHERE player_of_match IS NOT NULL
GROUP BY player_of_match
ORDER BY awards DESC, player_of_match
LIMIT 10;

-- Q15 | Kohli's career | Virat Kohli's runs and strike rate by season, with a running total
SELECT season,
       SUM(batter_runs)                                                        AS runs,
       ROUND(100.0 * SUM(batter_runs) / COUNT(*) FILTER (WHERE is_faced), 2)   AS strike_rate,
       SUM(SUM(batter_runs)) OVER (ORDER BY season)                            AS career_runs
FROM v_balls
WHERE batter = 'V Kohli'
GROUP BY season
ORDER BY season;
