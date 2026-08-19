"""
FastAPI app that exposes the matching engine over REST + WebSocket.

- REST:  submit orders, cancel orders, fetch a depth/trades snapshot
- WS:    /ws/orderbook  streams live book + trade updates every tick,
         driven by a background market-maker + momentum-trader simulation

Run with:  uvicorn api.main:app --reload --port 8000
"""

import asyncio
import json
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from engine import MatchingEngine, Order, Side, OrderType
from bots.market_maker import MarketMaker
from bots.momentum_trader import MomentumTrader

app = FastAPI(title="LOB Matching Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SYMBOL = "DEMO"
engine = MatchingEngine(SYMBOL)
maker = MarketMaker(engine, fair_value=100.0)
taker = MomentumTrader(engine)

connected_clients: set[WebSocket] = set()


class OrderRequest(BaseModel):
    side: str            # "BUY" or "SELL"
    order_type: str       # "LIMIT" | "MARKET" | "IOC" | "FOK"
    quantity: int
    price: Optional[float] = None


@app.get("/")
def root():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "..", "frontend")), name="static")


@app.post("/order")
def submit_order(req: OrderRequest):
    order = Order(
        side=Side(req.side.upper()),
        order_type=OrderType(req.order_type.upper()),
        quantity=req.quantity,
        price=req.price,
    )
    trades = engine.submit(order)
    return {
        "order": order.to_dict(),
        "trades": [t.to_dict() for t in trades],
    }


@app.delete("/order/{order_id}")
def cancel_order(order_id: int):
    ok = engine.cancel(order_id)
    return {"cancelled": ok}


@app.get("/depth")
def get_depth(levels: int = 10):
    return engine.depth(levels)


@app.get("/trades")
def get_trades(n: int = 20):
    return engine.recent_trades(n)


@app.websocket("/ws/orderbook")
async def orderbook_stream(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)
    try:
        while True:
            await asyncio.sleep(3600)  # keep the connection open; server pushes data via broadcast loop
    except WebSocketDisconnect:
        connected_clients.discard(ws)


async def broadcast_loop():
    """Background task: runs the bot simulation and pushes book snapshots to all clients."""
    tick = 0
    while True:
        await asyncio.sleep(0.7)
        tick += 1

        if tick % 3 == 0:
            maker.quote()
        taker.act()

        payload = {
            "type": "snapshot",
            "depth": engine.depth(10),
            "trades": engine.recent_trades(15),
            "spread": engine.book.spread(),
            "best_bid": engine.book.best_bid(),
            "best_ask": engine.book.best_ask(),
        }
        stale = []
        for client in connected_clients:
            try:
                await client.send_text(json.dumps(payload))
            except Exception:
                stale.append(client)
        for c in stale:
            connected_clients.discard(c)


@app.on_event("startup")
async def startup_event():
    maker.quote()
    asyncio.create_task(broadcast_loop())
