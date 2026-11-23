# Stock Exchange Matching Engine | Python, WebSockets, React, PostgreSQL

A miniature stock exchange: a limit order book that matches buy and sell orders with price-time priority, a FastAPI server that streams the live book to a React front end over WebSockets, and a background writer that stores every trade in PostgreSQL in batches.

| | |
|:--|:--|
| **What was built** | An order book for limit orders, market orders and cancellations; a server with REST endpoints and a WebSocket feed; a React order book showing the top 10 price levels on each side, recent trades and an order form; a trader simulator; and batched trade storage in PostgreSQL |
| **How it was checked** | 9 rule tests (one per matching rule) plus 200 random sequences of 300 orders each, with cancels and market orders, compared trade by trade against a slow, obviously correct reference engine: 209 of 209 tests pass |
| **Key result** | The engine matches about **480,000–580,000 orders a second** in pure Python with no network or database. Over HTTP with the server, simulator and PostgreSQL running, throughput is about 700 orders a second, so the network, not the matching, is the bottleneck. In a 2,000-order live run, all 1,571 trades reached PostgreSQL with the same count and volume as the engine |

![Live order book](outputs/order_book_ui.png)

## How Matching Works

| Rule | In the code |
|:--|:--|
| Best price first: bids from the highest price down, asks from the lowest price up | Two heaps keyed by `-price` for bids and `price` for asks |
| Same price: the order that arrived first fills first | A sequence number is the second key in each heap |
| A limit order trades only at its price or better; the rest waits in the book | The loop stops when prices no longer cross, then the remainder is pushed onto the heap |
| A market order trades at the best prices available; the rest is dropped | Market orders (`price = None`) are never added to the book |
| Every trade happens at the price of the order already waiting in the book | The trade records the resting order's price, not the incoming order's |
| Cancels are cheap | The order is marked inactive and removed lazily when it reaches the top of the heap |

Prices are whole numbers of paise (₹100.25 = 10025), never floats, so 0.1 + 0.2 rounding errors cannot creep into prices.

## Results

| Benchmark (1 million orders, no network or database) | Trades | Orders per second |
|:--|--:|--:|
| Limit orders only | 776,217 | 478,883 |
| Realistic mix: 70% limit, 15% market, 15% cancels | 775,292 | 582,880 |
| Same mix, with trades handed to the database queue | 775,292 | 373,530 |

Full numbers: [outputs/benchmark.json](outputs/benchmark.json). Speeds depend on the machine.

## Project Structure

| File | What it does |
|:--|:--|
| [engine/order_book.py](engine/order_book.py) | The order book: `submit`, `cancel`, `depth`, `best_bid`, `best_ask` |
| [engine/reference.py](engine/reference.py) | A slow reference engine (sorted lists, re-sorted on every order) used only to check the real one |
| [tests/test_order_book.py](tests/test_order_book.py) | Rule tests and 200 randomised comparisons with the reference engine |
| [server/app.py](server/app.py) | FastAPI: `POST /api/orders`, `DELETE /api/orders/{id}`, `GET /api/book`, WebSocket `/ws`; serves the React app |
| [server/schema.sql](server/schema.sql) | The PostgreSQL `trades` table |
| [server/simulate_traders.py](server/simulate_traders.py) | Sends random limit orders, market orders and cancels around a moving mid price |
| [frontend/src/main.jsx](frontend/src/main.jsx) | React order book, recent trades and order form, updated over the WebSocket |
| [benchmark.py](benchmark.py) | Orders-per-second benchmark |

## Run It Yourself

```bash
pip install -r requirements.txt
python -m pytest -q                         # 209 tests
python benchmark.py                         # orders per second

createdb exchange                           # optional: store trades in PostgreSQL
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/exchange python server/app.py
# open http://127.0.0.1:8000, then in another terminal:
python server/simulate_traders.py --orders 2000 --rate 50
```

The built React app is in `frontend/dist`. To change the front end: `cd frontend && npm install && npm run build`.

## Mistakes This Avoids

- Prices stored as floats: prices are integers in paise.
- Ignoring time priority: same-price orders fill in arrival order, and a test checks it.
- Trading at the incoming order's price: trades use the resting order's price, and a test checks it.
- Leaving part of a market order in the book: the unfilled part is dropped, and a test checks it.
- Writing to the database inside the matching loop: trades go to a queue and a background thread inserts them in batches.

## Limitations

- One instrument, one process, and the book lives in memory, so a restart empties it (trades already stored in PostgreSQL remain).
- No user accounts, balances or risk checks before an order is accepted.

**Tools:** Python, FastAPI, WebSockets, React (Vite), PostgreSQL, pytest
