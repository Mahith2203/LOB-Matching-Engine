"""
Limit Order Book.

Maintains two sides:
  bids -> buy orders,  best price = HIGHEST price   (max-heap)
  asks -> sell orders, best price = LOWEST price    (min-heap)

Within a price level, orders are stored in a deque (FIFO) so that
time priority is respected -> classic "price-time priority".

Python's heapq is a min-heap, so bid prices are pushed as negative
numbers to simulate a max-heap.
"""

import heapq
from collections import deque, defaultdict
from .order import Side, Order


class OrderBook:
    def __init__(self, symbol: str):
        self.symbol = symbol

        # price -> deque[Order]  (FIFO within a price level)
        self.bid_levels: dict[float, deque[Order]] = defaultdict(deque)
        self.ask_levels: dict[float, deque[Order]] = defaultdict(deque)

        # heaps hold price "keys" only, lazily cleaned when a level empties out
        self._bid_heap: list[float] = []   # stores -price
        self._ask_heap: list[float] = []   # stores +price

        # order_id -> (side, price) for O(1) cancel lookups
        self._order_index: dict[int, tuple[Side, float]] = {}

    # ---------- best price helpers ----------

    def best_bid(self):
        self._clean_heap(self._bid_heap, self.bid_levels, is_bid=True)
        return -self._bid_heap[0] if self._bid_heap else None

    def best_ask(self):
        self._clean_heap(self._ask_heap, self.ask_levels, is_bid=False)
        return self._ask_heap[0] if self._ask_heap else None

    def spread(self):
        bb, ba = self.best_bid(), self.best_ask()
        if bb is None or ba is None:
            return None
        return round(ba - bb, 8)

    def _clean_heap(self, heap, levels, is_bid):
        # pop stale price entries whose level has become empty
        while heap:
            top = -heap[0] if is_bid else heap[0]
            if levels.get(top):
                return
            heapq.heappop(heap)

    # ---------- book mutation ----------

    def add_resting_order(self, order: Order):
        """Place an order (or its remainder) onto the book."""
        levels = self.bid_levels if order.side == Side.BUY else self.ask_levels
        heap = self._bid_heap if order.side == Side.BUY else self._ask_heap

        if order.price not in levels or not levels[order.price]:
            heapq.heappush(heap, -order.price if order.side == Side.BUY else order.price)

        levels[order.price].append(order)
        self._order_index[order.order_id] = (order.side, order.price)

    def cancel(self, order_id: int) -> bool:
        info = self._order_index.get(order_id)
        if not info:
            return False
        side, price = info
        levels = self.bid_levels if side == Side.BUY else self.ask_levels
        dq = levels.get(price)
        if not dq:
            return False
        for o in list(dq):
            if o.order_id == order_id:
                dq.remove(o)
                from .order import OrderStatus
                o.status = OrderStatus.CANCELLED
                del self._order_index[order_id]
                return True
        return False

    # ---------- snapshot for UI / API ----------

    def depth(self, levels: int = 10):
        """Return top-N price levels on each side, aggregated by price."""
        bid_prices = sorted(self.bid_levels.keys(), reverse=True)
        ask_prices = sorted(self.ask_levels.keys())

        bids = [
            {"price": p, "quantity": sum(o.remaining_qty for o in self.bid_levels[p])}
            for p in bid_prices if self.bid_levels[p]
        ][:levels]

        asks = [
            {"price": p, "quantity": sum(o.remaining_qty for o in self.ask_levels[p])}
            for p in ask_prices if self.ask_levels[p]
        ][:levels]

        return {"symbol": self.symbol, "bids": bids, "asks": asks}
