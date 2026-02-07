"""MACD indicator implementation (optional)."""

from __future__ import annotations

from typing import List, Optional, Tuple


def _ema(values: List[float], period: int) -> List[Optional[float]]:
    if period <= 0:
        raise ValueError("period must be positive")

    ema: List[Optional[float]] = [None] * len(values)
    if not values:
        return ema

    multiplier = 2 / (period + 1)
    ema[0] = values[0]
    for i in range(1, len(values)):
        prev = ema[i - 1] if ema[i - 1] is not None else values[i - 1]
        ema[i] = (values[i] - prev) * multiplier + prev
    return ema


def compute_macd(
    closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> Tuple[List[Optional[float]], List[Optional[float]]]:
    """Compute MACD line and signal line.

    Returns:
        Tuple of (macd_line, signal_line).
    """

    if fast >= slow:
        raise ValueError("fast period must be less than slow period")

    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line: List[Optional[float]] = [None] * len(closes)
    for i in range(len(closes)):
        if ema_fast[i] is None or ema_slow[i] is None:
            macd_line[i] = None
        else:
            macd_line[i] = ema_fast[i] - ema_slow[i]

    signal_line = _ema([v or 0.0 for v in macd_line], signal)
    return macd_line, signal_line
