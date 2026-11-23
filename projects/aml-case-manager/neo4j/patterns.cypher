// The same graph and pattern queries for a Neo4j 5 server (load the data first with neo4j/load_neo4j.py).
// Parameters are passed by the driver: $min, $drift, $win_start, $win_end, $min_n, $max_n.

// 1. Uniqueness on account ids: every MERGE finds its account through the index instead of scanning all accounts
CREATE CONSTRAINT account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE;

// 2. Cycles, 3 hops (the 4- and 5-hop versions add r3, r4 the same way): each hop later than the one before,
//    within 24 hours of it, with amounts within 25% of the first hop
MATCH (a0:Account)-[r0:SENT]->(a1:Account)-[r1:SENT]->(a2:Account)-[r2:SENT]->(a0)
WHERE r0.amount >= $min
  AND r0.ts < r1.ts AND r1.ts <= r0.ts + duration({hours: 24})
  AND r1.ts < r2.ts AND r2.ts <= r1.ts + duration({hours: 24})
  AND abs(r1.amount - r0.amount) <= $drift * r0.amount
  AND abs(r2.amount - r0.amount) <= $drift * r0.amount
  AND a0 <> a1 AND a1 <> a2 AND a0 <> a2
RETURN [a0.id, a1.id, a2.id] AS accounts, [r0.tid, r1.tid, r2.tid] AS transfers;

// The variable-length form from the project guide, capped at 5 hops; use it only with a LIMIT and a time window
MATCH p = (a:Account)-[:SENT*3..5]->(a)
WHERE all(i IN range(0, size(relationships(p)) - 2)
      WHERE relationships(p)[i].ts < relationships(p)[i + 1].ts)
RETURN [n IN nodes(p) | n.id] AS accounts, [r IN relationships(p) | r.amount] AS amounts
LIMIT 100;

// 3. Fan-in: many different accounts sending to one account in a time window
MATCH (src:Account)-[t:SENT]->(dst:Account)
WHERE t.ts >= datetime($win_start) AND t.ts < datetime($win_end) AND t.amount >= $min
WITH dst, count(DISTINCT src) AS senders, sum(t.amount) AS total, collect(t.tid) AS transfers
WHERE senders >= $min_n
RETURN dst.id AS account, senders, total, transfers ORDER BY senders DESC;

// 4. Fan-out: one account sending to many different accounts in a time window (capped to leave out payroll)
MATCH (src:Account)-[t:SENT]->(dst:Account)
WHERE t.ts >= datetime($win_start) AND t.ts < datetime($win_end) AND t.amount >= $min
WITH src, count(DISTINCT dst) AS receivers, sum(t.amount) AS total, collect(t.tid) AS transfers
WHERE receivers >= $min_n AND receivers <= $max_n
RETURN src.id AS account, receivers, total, transfers ORDER BY receivers DESC;
