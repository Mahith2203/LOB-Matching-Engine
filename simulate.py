"""
Standalone CLI demo — no server needed.

Runs the market maker + momentum trader against the matching engine for
N ticks and prints the order book depth and trade tape to the terminal.
Good for a quick sanity check or a terminal-only interview demo.

Usage:
    python simulate.py --ticks 30
"""

import argparse
import time

from engine import MatchingEngine
from bots.market_maker import MarketMaker
from bots.momentum_trader import MomentumTrader


def print_book(engine, tick):
    depth = engine.depth(5)
    print(f"\n--- tick {tick} | best bid {engine.book.best_bid()} "
          f"| best ask {engine.book.best_ask()} | spread {engine.book.spread()} ---")
    print(f"{'BIDS':>20} | {'ASKS':<20}")
    for i in range(max(len(depth['bids']), len(depth['asks']))):
        b = depth['bids'][i] if i < len(depth['bids']) else None
        a = depth['asks'][i] if i < len(depth['asks']) else None
        bstr = f"{b['quantity']:>5} @ {b['price']:<8.2f}" if b else " " * 16
        astr = f"{a['price']:<8.2f} @ {a['quantity']:<5}" if a else ""
        print(f"{bstr:>20} | {astr:<20}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticks", type=int, default=25)
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args()

    engine = MatchingEngine("DEMO")
    maker = MarketMaker(engine, fair_value=100.0)
    taker = MomentumTrader(engine)

    maker.quote()

    for tick in range(1, args.ticks + 1):
        if tick % 3 == 0:
            maker.quote()
        taker.act()
        print_book(engine, tick)
        time.sleep(args.delay)

    print(f"\nTotal trades executed: {len(engine.trades)}")
    if engine.trades:
        vwap = sum(t.price * t.quantity for t in engine.trades) / sum(t.quantity for t in engine.trades)
        print(f"VWAP: {vwap:.4f}")


if __name__ == "__main__":
    main()
