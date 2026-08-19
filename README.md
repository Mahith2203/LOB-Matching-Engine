# LOB Matching Engine

A price-time priority limit order book matching engine, built from scratch in Python — the same core mechanism real exchanges (NSE, NASDAQ, Binance) use to match buyers and sellers. Includes two simulated trading bots, a FastAPI backend, and a live browser-based order book visualizer.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![Tests](https://img.shields.io/badge/tests-11%20passing-brightgreen)

## Why this project

Most student finance projects stop at valuation (DCF, CAPM) or prediction (LSTM price forecasts). This one goes one level deeper: **how does a trade actually happen?** It implements the core matching logic that sits underneath every exchange and every trading strategy — the mechanism valuation and prediction models eventually have to interact with.

## What it does

- **Order types**: `LIMIT`, `MARKET`, `IOC` (Immediate-Or-Cancel), `FOK` (Fill-Or-Kill)
- **Price-time priority matching**: best price fills first; within the same price, first-in-first-out
- **Partial fills**: large orders can be filled across multiple resting orders and multiple price levels
- **Two bots**:
  - `MarketMaker` — continuously quotes a two-sided market around a random-walking fair value (adds liquidity)
  - `MomentumTrader` — watches the trade tape and takes liquidity in the direction of the recent trend (removes liquidity)
- **Live web UI** — real-time order book depth + trade tape streamed over WebSocket
- **REST API** — submit/cancel orders and query depth programmatically
- **11 unit tests** covering matching correctness, priority rules, and edge cases

## Architecture

```
lob-matching-engine/
├── engine/
│   ├── order.py            # Order & Trade data models, order types/status enums
│   ├── order_book.py       # Price-time priority book (heaps + FIFO deques per price level)
│   └── matching_engine.py  # Core matching logic for all 4 order types
├── bots/
│   ├── market_maker.py     # Liquidity-providing bot
│   └── momentum_trader.py  # Liquidity-taking bot
├── api/
│   └── main.py              # FastAPI REST + WebSocket server
├── frontend/
│   └── index.html            # Live depth chart / trade tape (vanilla JS + WebSocket)
├── tests/
│   └── test_matching_engine.py
└── simulate.py               # Terminal-only demo, no server needed
```

### How matching works

- **Bids** are stored in a max-heap (best price = highest), **asks** in a min-heap (best price = lowest). Within a price level, orders sit in a FIFO deque, so two orders at the same price are filled in arrival order.
- A trade always executes at the **resting order's price** (standard exchange convention) — the order that was already on the book, not the one that just arrived.
- `LIMIT` orders that don't fully fill get placed on the book. `MARKET`, `IOC`, and `FOK` never rest — any unfilled quantity is cancelled.
- `FOK` pre-checks whether the *entire* order can be filled before executing anything — if not, nothing happens at all (all-or-nothing semantics).

## Running it

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2a. Terminal demo (fastest way to see it work)
```bash
python simulate.py --ticks 30 --delay 0.15
```
This runs the market maker + momentum bot against the engine and prints the live order book to your terminal.

### 2b. Web app with live visualizer
```bash
uvicorn api.main:app --reload --port 8000
```
Then open **http://localhost:8000** — you'll see a live-updating order book depth table and trade tape, driven by the bots in the background.

### 3. Run the tests
```bash
pytest tests/ -v
```

### 4. Submit your own orders via the API
```bash
curl -X POST http://localhost:8000/order \
  -H "Content-Type: application/json" \
  -d '{"side": "BUY", "order_type": "LIMIT", "quantity": 10, "price": 100.50}'

curl http://localhost:8000/depth
```

## Sample interview talking points

- **Why a heap for price levels?** O(log n) to find the best price vs O(n) for a naive scan of all price levels every time an order arrives.
- **Why a deque within a price level?** O(1) append/popleft gives correct FIFO time priority without shifting a list.
- **Why does FOK pre-check before executing?** Real exchanges won't let a large all-or-nothing order partially move the book and then get cancelled — that would let it "test" liquidity for free and create phantom price impact.
- **What's missing vs a real exchange?** No margin/risk checks, no self-trade prevention, no persistence/crash recovery, single-threaded (real engines are often lock-free/single-threaded per symbol for determinism, which is actually similar to this design).

## Possible extensions (good "future work" talking points)

- Add a **self-trade prevention** check (reject/cancel if aggressor and resting order belong to the same account)
- Persist trades to a database and compute **VWAP / OHLCV candles**
- Add **STOP** and **STOP-LIMIT** order types
- Benchmark throughput (orders/sec) and publish **latency percentiles (p50/p99)**
- Rewrite the core engine in C++/Rust with Python bindings for a latency comparison write-up

## License

MIT — free to use for your own portfolio/placements.
