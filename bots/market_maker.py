"""
Simple Market Maker bot.

Continuously quotes a two-sided market around a reference "fair value"
that random-walks over time. This is deliberately simple (no inventory
skew, no adverse-selection protection) -> the point is to keep the book
populated with realistic bid/ask levels so the matching engine and the
momentum bot have something to trade against.
"""

import random
from engine import Order, Side, OrderType, MatchingEngine


class MarketMaker:
    def __init__(self, engine: MatchingEngine, fair_value: float = 100.0,
                 spread: float = 0.20, levels: int = 3, qty_range=(5, 20)):
        self.engine = engine
        self.fair_value = fair_value
        self.spread = spread
        self.levels = levels
        self.qty_range = qty_range
        self.my_order_ids: list[int] = []

    def _drift_fair_value(self):
        self.fair_value += random.uniform(-0.15, 0.15)
        self.fair_value = round(max(self.fair_value, 1.0), 2)

    def cancel_all(self):
        for oid in self.my_order_ids:
            self.engine.cancel(oid)
        self.my_order_ids.clear()

    def quote(self):
        """Cancel old quotes and place a fresh ladder of bid/ask orders."""
        self.cancel_all()
        self._drift_fair_value()

        for i in range(self.levels):
            offset = self.spread / 2 + i * 0.10
            qty = random.randint(*self.qty_range)

            bid_price = round(self.fair_value - offset, 2)
            ask_price = round(self.fair_value + offset, 2)

            bid = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=bid_price, quantity=qty)
            ask = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=ask_price, quantity=qty)

            self.engine.submit(bid)
            self.engine.submit(ask)
            self.my_order_ids += [bid.order_id, ask.order_id]
