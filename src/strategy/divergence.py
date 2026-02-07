"""Divergence detection logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from .pivots import find_pivot_highs, find_pivot_lows


@dataclass(frozen=True)
class DivergenceSignal:
    """Represents a divergence signal."""

    symbol: str
    timeframe: str
    signal_type: str
    pivot_1_index: int
    pivot_2_index: int
    pivot_2_ts: datetime
    reason: str


@dataclass(frozen=True)
class DivergenceConfig:
    """Configuration for divergence detection."""

    pivot_left: int = 3
    pivot_right: int = 3
    min_sep_bars: int = 6
    max_sep_bars: int = 60
    min_rsi_delta: float = 3.0


def _select_last_two(pivots: List[int], min_sep: int, max_sep: int) -> Optional[Tuple[int, int]]:
    if len(pivots) < 2:
        return None

    for i in range(len(pivots) - 1, 0, -1):
        pivot_2 = pivots[i]
        for j in range(i - 1, -1, -1):
            pivot_1 = pivots[j]
            sep = pivot_2 - pivot_1
            if min_sep <= sep <= max_sep:
                return pivot_1, pivot_2
    return None


def detect_divergence(
    symbol: str,
    timeframe: str,
    closes: List[float],
    timestamps: List[datetime],
    rsi: List[Optional[float]],
    config: DivergenceConfig,
) -> Optional[DivergenceSignal]:
    """Detect divergence signals between price and RSI.

    Returns:
        DivergenceSignal if a new divergence is detected, else None.
    """

    if len(closes) != len(rsi) or len(closes) != len(timestamps):
        raise ValueError("closes, timestamps, and rsi must have the same length")

    pivot_lows = find_pivot_lows(closes, config.pivot_left, config.pivot_right)
    pivot_highs = find_pivot_highs(closes, config.pivot_left, config.pivot_right)

    low_pair = _select_last_two(
        pivot_lows, config.min_sep_bars, config.max_sep_bars
    )
    if low_pair:
        i1, i2 = low_pair
        rsi1 = rsi[i1]
        rsi2 = rsi[i2]
        if rsi1 is not None and rsi2 is not None:
            price_lower_low = closes[i2] < closes[i1]
            rsi_higher_low = rsi2 >= rsi1 + config.min_rsi_delta
            if price_lower_low and rsi_higher_low:
                reason = (
                    "Bullish divergence: price lower low "
                    f"({closes[i1]:.2f} -> {closes[i2]:.2f}) "
                    "and RSI higher low "
                    f"({rsi1:.2f} -> {rsi2:.2f})."
                )
                return DivergenceSignal(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type="bullish",
                    pivot_1_index=i1,
                    pivot_2_index=i2,
                    pivot_2_ts=timestamps[i2],
                    reason=reason,
                )

    high_pair = _select_last_two(
        pivot_highs, config.min_sep_bars, config.max_sep_bars
    )
    if high_pair:
        i1, i2 = high_pair
        rsi1 = rsi[i1]
        rsi2 = rsi[i2]
        if rsi1 is not None and rsi2 is not None:
            price_higher_high = closes[i2] > closes[i1]
            rsi_lower_high = rsi2 <= rsi1 - config.min_rsi_delta
            if price_higher_high and rsi_lower_high:
                reason = (
                    "Bearish divergence: price higher high "
                    f"({closes[i1]:.2f} -> {closes[i2]:.2f}) "
                    "and RSI lower high "
                    f"({rsi1:.2f} -> {rsi2:.2f})."
                )
                return DivergenceSignal(
                    symbol=symbol,
                    timeframe=timeframe,
                    signal_type="bearish",
                    pivot_1_index=i1,
                    pivot_2_index=i2,
                    pivot_2_ts=timestamps[i2],
                    reason=reason,
                )

    return None
