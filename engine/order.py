"""
Order data model.

Supports the order types that real exchanges expose:
- LIMIT : rest on the book at a specified price until matched or cancelled
- MARKET: execute immediately at the best available price(s), no resting
- IOC   : Immediate-Or-Cancel -> fill whatever is possible right now, cancel the rest
- FOK   : Fill-Or-Kill        -> fill the ENTIRE order immediately, or cancel all of it
"""

from dataclasses import dataclass, field
from enum import Enum
from itertools import count
import time


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    IOC = "IOC"
    FOK = "FOK"


class OrderStatus(str, Enum):
    OPEN = "OPEN"                 # resting on the book, unfilled or partially filled
    FILLED = "FILLED"             # fully executed
    PARTIALLY_FILLED = "PARTIALLY_FILLED"  # some qty executed, rest cancelled (IOC) or resting (LIMIT)
    CANCELLED = "CANCELLED"       # cancelled before any fill (e.g. failed FOK, explicit cancel)


_id_counter = count(1)


@dataclass
class Order:
    side: Side
    order_type: OrderType
    quantity: int
    price: float = None  # None for MARKET orders
    order_id: int = field(default_factory=lambda: next(_id_counter))
    timestamp: float = field(default_factory=time.time)
    remaining_qty: int = None
    status: OrderStatus = OrderStatus.OPEN

    def __post_init__(self):
        if self.remaining_qty is None:
            self.remaining_qty = self.quantity
        if self.order_type == OrderType.MARKET and self.price is not None:
            raise ValueError("MARKET orders must not specify a price")
        if self.order_type in (OrderType.LIMIT, OrderType.IOC, OrderType.FOK) and self.price is None:
            raise ValueError(f"{self.order_type} orders require a price")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")

    @property
    def filled_qty(self) -> int:
        return self.quantity - self.remaining_qty

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "price": self.price,
            "quantity": self.quantity,
            "remaining_qty": self.remaining_qty,
            "status": self.status.value,
            "timestamp": self.timestamp,
        }


@dataclass
class Trade:
    trade_id: int
    price: float
    quantity: int
    aggressor_side: Side       # side of the order that arrived and caused the match
    resting_order_id: int
    aggressor_order_id: int
    timestamp: float = field(default_factory=time.time)

    def to_dict(self):
        return {
            "trade_id": self.trade_id,
            "price": self.price,
            "quantity": self.quantity,
            "aggressor_side": self.aggressor_side.value,
            "resting_order_id": self.resting_order_id,
            "aggressor_order_id": self.aggressor_order_id,
            "timestamp": self.timestamp,
        }
