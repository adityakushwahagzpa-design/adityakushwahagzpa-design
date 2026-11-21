// Load the exported network into Neo4j, then run investigator queries.
// Copy accounts.csv and transfers.csv into the database's "import" folder first.

CREATE CONSTRAINT account_id IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE;

LOAD CSV WITH HEADERS FROM 'file:///accounts.csv' AS row
MERGE (a:Account {id: row.account_id})
SET a.kind = row.kind, a.opened = date(row.opened), a.ruleScore = toInteger(toFloat(row.rule_score));

LOAD CSV WITH HEADERS FROM 'file:///transfers.csv' AS row
MATCH (s:Account {id: row.src}), (d:Account {id: row.dst})
MERGE (s)-[t:SENT]->(d)
SET t.total = toFloat(row.total), t.count = toInteger(row.count);

// 1. Round-tripping: loops of 4-6 accounts where every hop moved over ₹1 lakh
MATCH p = (a:Account)-[:SENT*4..6]->(a)
WHERE all(r IN relationships(p) WHERE r.total > 100000)
RETURN [n IN nodes(p) | n.id] AS loop, reduce(s = 0, r IN relationships(p) | s + r.total) AS moved
ORDER BY moved DESC LIMIT 10;

// 2. Fan-in collectors: accounts paid by 10+ different senders that also have a high rule score
MATCH (s:Account)-[:SENT]->(c:Account)
WITH c, count(DISTINCT s) AS senders
WHERE senders >= 10 AND c.ruleScore >= 60
RETURN c.id, senders, c.ruleScore ORDER BY senders DESC;

// 3. Everything within two hops of one suspicious account (for an investigation view)
MATCH p = (x:Account {id: 'X0000'})-[:SENT*1..2]-(n)
RETURN p LIMIT 100;
