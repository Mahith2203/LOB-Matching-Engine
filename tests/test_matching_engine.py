import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from engine import MatchingEngine, Order, Side, OrderType, OrderStatus


def make_engine():
    return MatchingEngine("TEST")


def test_limit_order_rests_when_no_cross():
    eng = make_engine()
    order = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100, quantity=10)
    trades = eng.submit(order)
    assert trades == []
    assert eng.book.best_bid() == 100
    assert order.status == OrderStatus.OPEN


def test_simple_full_match():
    eng = make_engine()
    sell = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=100, quantity=10)
    eng.submit(sell)

    buy = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100, quantity=10)
    trades = eng.submit(buy)

    assert len(trades) == 1
    assert trades[0].price == 100
    assert trades[0].quantity == 10
    assert buy.status == OrderStatus.FILLED
    assert sell.status == OrderStatus.FILLED
    assert eng.book.best_bid() is None
    assert eng.book.best_ask() is None


def test_partial_fill_leaves_remainder_on_book():
    eng = make_engine()
    sell = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=100, quantity=5)
    eng.submit(sell)

    buy = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100, quantity=12)
    trades = eng.submit(buy)

    assert trades[0].quantity == 5
    assert buy.status == OrderStatus.PARTIALLY_FILLED
    assert buy.remaining_qty == 7
    assert eng.book.best_bid() == 100  # remainder now resting


def test_price_time_priority():
    """Earlier order at the same price must fill first."""
    eng = make_engine()
    sell1 = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=100, quantity=5)
    sell2 = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=100, quantity=5)
    eng.submit(sell1)
    eng.submit(sell2)

    buy = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100, quantity=5)
    trades = eng.submit(buy)

    assert trades[0].resting_order_id == sell1.order_id
    assert sell1.status == OrderStatus.FILLED
    assert sell2.status == OrderStatus.OPEN


def test_price_priority_over_time():
    """A better-priced order must fill before an earlier but worse-priced one."""
    eng = make_engine()
    sell_worse = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=101, quantity=5)
    sell_better = Order(side=Side.SELL, order_type=OrderType.LIMIT, price=100, quantity=5)
    eng.submit(sell_worse)
    eng.submit(sell_better)  # arrives second but has the better (lower) price

    buy = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=101, quantity=5)
    trades = eng.submit(buy)

    assert trades[0].price == 100
    assert trades[0].resting_order_id == sell_better.order_id


def test_market_order_sweeps_book():
    eng = make_engine()
    eng.submit(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=100, quantity=5))
    eng.submit(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=101, quantity=5))

    buy = Order(side=Side.BUY, order_type=OrderType.MARKET, quantity=8)
    trades = eng.submit(buy)

    assert len(trades) == 2
    assert trades[0].price == 100
    assert trades[0].quantity == 5
    assert trades[1].price == 101
    assert trades[1].quantity == 3
    assert buy.status == OrderStatus.FILLED


def test_ioc_cancels_unfilled_remainder():
    eng = make_engine()
    eng.submit(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=100, quantity=3))

    buy = Order(side=Side.BUY, order_type=OrderType.IOC, price=100, quantity=10)
    trades = eng.submit(buy)

    assert trades[0].quantity == 3
    assert buy.remaining_qty == 7
    assert buy.status == OrderStatus.PARTIALLY_FILLED
    assert eng.book.best_bid() is None  # never rested


def test_fok_all_or_nothing_success():
    eng = make_engine()
    eng.submit(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=100, quantity=5))
    eng.submit(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=100, quantity=5))

    buy = Order(side=Side.BUY, order_type=OrderType.FOK, price=100, quantity=10)
    trades = eng.submit(buy)

    assert buy.status == OrderStatus.FILLED
    assert sum(t.quantity for t in trades) == 10


def test_fok_all_or_nothing_failure():
    eng = make_engine()
    eng.submit(Order(side=Side.SELL, order_type=OrderType.LIMIT, price=100, quantity=5))

    buy = Order(side=Side.BUY, order_type=OrderType.FOK, price=100, quantity=10)
    trades = eng.submit(buy)

    assert trades == []
    assert buy.status == OrderStatus.CANCELLED
    # the resting sell order must be untouched
    assert eng.book.best_ask() == 100


def test_cancel_order():
    eng = make_engine()
    order = Order(side=Side.BUY, order_type=OrderType.LIMIT, price=100, quantity=5)
    eng.submit(order)
    assert eng.cancel(order.order_id) is True
    assert eng.book.best_bid() is None
    assert eng.cancel(order.order_id) is False  # already gone


def test_depth_snapshot_aggregates_by_price():
    eng = make_engine()
    eng.submit(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=99, quantity=5))
    eng.submit(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=99, quantity=3))
    eng.submit(Order(side=Side.BUY, order_type=OrderType.LIMIT, price=98, quantity=10))

    depth = eng.depth()
    assert depth["bids"][0]["price"] == 99
    assert depth["bids"][0]["quantity"] == 8
    assert depth["bids"][1]["price"] == 98


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
