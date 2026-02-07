"""Relative Strength Index (RSI) implementation."""

from __future__ import annotations

from typing import List, Optional


def compute_rsi(closes: List[float], period: int = 14) -> List[Optional[float]]:
    """Compute RSI using Wilder's smoothing.

    Args:
        closes: List of close prices.
        period: RSI period.

    Returns:
        A list of RSI values with None for insufficient data.
    """

    if period <= 0:
        raise ValueError("period must be positive")

    rsi: List[Optional[float]] = [None] * len(closes)
    if len(closes) < period + 1:
        return rsi

    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change >= 0:
            gains += change
        else:
            losses -= change

    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))

    return rsi
