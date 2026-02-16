"""Simple trading simulation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from src.data.candle_builder import Candle


@dataclass(frozen=True)
class SignalEvent:
    symbol: str
    signal_type: str
    strength: str
    confirmations: List[str]
    pivot_index: int
    pivot_ts: object


def simulate_portfolio(
    candles_by_symbol: Dict[str, List[Candle]],
    events_by_symbol: Dict[str, List[SignalEvent]],
    starting_cash: float,
    buy_pct: float,
    sell_pct: float,
) -> Dict[str, Dict[str, float]]:
    results: Dict[str, Dict[str, float]] = {}

    for symbol, candles in candles_by_symbol.items():
        events = events_by_symbol.get(symbol, [])
        if not candles:
            continue

        cash = starting_cash
        shares = 0.0
        buy_count = 0
        sell_count = 0

        sorted_events = sorted(
            events,
            key=lambda event: (event.pivot_ts, 0 if event.signal_type == "bearish" else 1),
        )

        closes = [candle.close for candle in candles]
        for event in sorted_events:
            idx = event.pivot_index
            if idx < 0 or idx >= len(closes):
                continue
            price = closes[idx]
            if price <= 0:
                continue

            if event.signal_type == "bullish":
                budget = cash * buy_pct
                if budget <= 0:
                    continue
                shares += budget / price
                cash -= budget
                buy_count += 1
            else:
                qty = shares * sell_pct
                if qty <= 0:
                    continue
                shares -= qty
                cash += qty * price
                sell_count += 1

        final_price = closes[-1]
        final_value = cash + shares * final_price
        total_return = (final_value - starting_cash) / starting_cash if starting_cash else 0.0

        results[symbol] = {
            "starting_cash": starting_cash,
            "ending_value": final_value,
            "return_pct": total_return * 100,
            "buy_count": float(buy_count),
            "sell_count": float(sell_count),
            "cash": cash,
            "shares": shares,
        }

    return results
