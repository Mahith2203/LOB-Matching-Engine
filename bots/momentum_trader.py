"""
Simple Momentum / liquidity-taking bot.

Watches the trade tape; if the last few trades moved up, it buys
(chasing momentum); if they moved down, it sells. Uses IOC orders,
so it only ever takes liquidity that's already resting -> it never
adds new resting orders itself, keeping it a clean "taker" counterpart
to the market maker's "maker" role.
"""

import random
from engine import Order, Side, OrderType, MatchingEngine


class MomentumTrader:
    def __init__(self, engine: MatchingEngine, lookback: int = 4, qty_range=(1, 10)):
        self.engine = engine
        self.lookback = lookback
        self.qty_range = qty_range

    def _signal(self):
        trades = self.engine.trades[-self.lookback:]
        if len(trades) < 2:
            return None
        if trades[-1].price > trades[0].price:
            return Side.BUY
        elif trades[-1].price < trades[0].price:
            return Side.SELL
        return None

    def act(self):
        side = self._signal()
        if side is None:
            return None

        best = self.engine.book.best_ask() if side == Side.BUY else self.engine.book.best_bid()
        if best is None:
            return None

        qty = random.randint(*self.qty_range)
        order = Order(side=side, order_type=OrderType.IOC, price=best, quantity=qty)
        return self.engine.submit(order)
