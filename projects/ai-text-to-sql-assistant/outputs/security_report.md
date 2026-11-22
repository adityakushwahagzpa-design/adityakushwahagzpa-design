# SQL Guard Red-Team Report

25/25 attacks blocked by layer 1 (static check). 24/24 blocked by layer 2 alone (read-only connection + authorizer). Database unchanged after all attacks: yes.

| Attack | Layer 1 | Layer 2 alone |
|:--|:--:|:--:|
| Drop a table | blocked | blocked |
| Delete rows | blocked | blocked |
| Update balances | blocked | blocked |
| Insert a row | blocked | blocked |
| Stacked query | blocked | blocked |
| Comment-hidden second statement | blocked | blocked |
| Write inside a CTE | blocked | blocked |
| Create a table | blocked | blocked |
| Create a view | blocked | blocked |
| Create a trigger | blocked | blocked |
| Alter a table | blocked | blocked |
| Attach another database | blocked | blocked |
| Detach | blocked | blocked |
| PRAGMA write | blocked | blocked |
| PRAGMA read of schema | blocked | blocked |
| Read system catalogue | blocked | blocked |
| Read temp catalogue | blocked | blocked |
| Unknown table | blocked | blocked |
| Replace into | blocked | blocked |
| Vacuum into a file | blocked | blocked |
| Reindex | blocked | blocked |
| Begin transaction | blocked | blocked |
| Load extension | blocked | blocked |
| Empty query | blocked | nothing to run |
| Not SQL | blocked | blocked |
