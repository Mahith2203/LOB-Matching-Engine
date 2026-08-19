"""
Matching Engine.

Implements price-time priority matching for LIMIT, MARKET, IOC, and FOK
orders. This mirrors (at a simplified level) how real exchange matching
engines like those at NSE/NASDAQ work:

  - An incoming BUY matches against the lowest-priced resting SELL orders
    first, and vice versa.
  - Within the same price, the order that arrived first gets filled first
    (time priority) -> enforced by the OrderBook's deque (FIFO).
  - A trade always executes at the RESTING order's price (the order that
    was already on the book), never the aggressor's price. This is the
    standard "resting price" convention used by most exchanges.
"""

from itertools import count
from .order import Order, Side, OrderType, OrderStatus, Trade
from .order_book import OrderBook


class MatchingEngine:
    def __init__(self, symbol: str):
        self.book = OrderBook(symbol)
        self.trades: list[Trade] = []
        self._trade_id_counter = count(1)

    def submit(self, order: Order) -> list[Trade]:
        """Process an incoming order. Returns the list of trades it generated."""
        if order.order_type == OrderType.FOK:
            return self._handle_fok(order)
        elif order.order_type == OrderType.IOC:
            return self._match(order, allow_rest=False)
        elif order.order_type == OrderType.MARKET:
            return self._match(order, allow_rest=False)
        elif order.order_type == OrderType.LIMIT:
            return self._match(order, allow_rest=True)
        else:
            raise ValueError(f"Unknown order type {order.order_type}")

    # ---------------- internal matching logic ----------------

    def _opposite_levels(self, side: Side):
        return self.book.ask_levels if side == Side.BUY else self.book.bid_levels

    def _crosses(self, order: Order, resting_price: float) -> bool:
        if order.order_type == OrderType.MARKET:
            return True
        if order.side == Side.BUY:
            return order.price >= resting_price
        return order.price <= resting_price

    def _handle_fok(self, order: Order) -> list[Trade]:
        """FOK: only proceed if the ENTIRE quantity can be filled right now."""
        if not self._can_fully_fill(order):
            order.status = OrderStatus.CANCELLED
            return []
        return self._match(order, allow_rest=False)

    def _can_fully_fill(self, order: Order) -> bool:
        levels = self._opposite_levels(order.side)
        prices = sorted(levels.keys(), reverse=(order.side == Side.SELL)) \
            if order.side == Side.SELL else sorted(levels.keys())
        # For a BUY, walk asks ascending; for a SELL, walk bids descending.
        prices = sorted(levels.keys()) if order.side == Side.BUY else sorted(levels.keys(), reverse=True)

        needed = order.remaining_qty
        for p in prices:
            if not self._crosses(order, p):
                break
            available = sum(o.remaining_qty for o in levels[p])
            needed -= available
            if needed <= 0:
                return True
        return False

    def _match(self, order: Order, allow_rest: bool) -> list[Trade]:
        levels = self._opposite_levels(order.side)
        trades = []

        while order.remaining_qty > 0:
            best_price = self.book.best_ask() if order.side == Side.BUY else self.book.best_bid()
            if best_price is None or not self._crosses(order, best_price):
                break

            queue = levels[best_price]
            while queue and order.remaining_qty > 0:
                resting = queue[0]
                fill_qty = min(order.remaining_qty, resting.remaining_qty)

                trade = Trade(
                    trade_id=next(self._trade_id_counter),
                    price=best_price,
                    quantity=fill_qty,
                    aggressor_side=order.side,
                    resting_order_id=resting.order_id,
                    aggressor_order_id=order.order_id,
                )
                self.trades.append(trade)
                trades.append(trade)

                order.remaining_qty -= fill_qty
                resting.remaining_qty -= fill_qty

                if resting.remaining_qty == 0:
                    resting.status = OrderStatus.FILLED
                    queue.popleft()
                    self.book._order_index.pop(resting.order_id, None)
                else:
                    resting.status = OrderStatus.PARTIALLY_FILLED

            if not queue:
                del levels[best_price]

        # settle final status of the incoming order
        if order.remaining_qty == 0:
            order.status = OrderStatus.FILLED
        elif order.remaining_qty < order.quantity:
            order.status = OrderStatus.PARTIALLY_FILLED
        else:
            order.status = OrderStatus.OPEN

        # LIMIT orders rest on the book if anything is left unfilled
        if allow_rest and order.remaining_qty > 0:
            self.book.add_resting_order(order)
        elif order.remaining_qty > 0:
            # IOC / MARKET / FOK remainder is cancelled, never rests
            if order.status == OrderStatus.OPEN:
                order.status = OrderStatus.CANCELLED

        return trades

    def cancel(self, order_id: int) -> bool:
        return self.book.cancel(order_id)

    def depth(self, levels: int = 10):
        return self.book.depth(levels)

    def recent_trades(self, n: int = 20):
        return [t.to_dict() for t in self.trades[-n:]]
