"""KDJ indicator implementation."""

from __future__ import annotations

from typing import List, Optional, Tuple


def compute_kdj(
    closes: List[float],
    highs: List[float],
    lows: List[float],
    period: int = 9,
    k_smooth: int = 3,
    d_smooth: int = 3,
) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
    """Compute KDJ indicator values.

    Args:
        closes: Close prices.
        highs: High prices.
        lows: Low prices.
        period: Lookback period for RSV.
        k_smooth: Smoothing for K.
        d_smooth: Smoothing for D.

    Returns:
        Tuple of (K, D, J) lists with None for insufficient data.
    """

    if not (len(closes) == len(highs) == len(lows)):
        raise ValueError("closes, highs, and lows must have the same length")
    if period <= 0:
        raise ValueError("period must be positive")

    k_values: List[Optional[float]] = [None] * len(closes)
    d_values: List[Optional[float]] = [None] * len(closes)
    j_values: List[Optional[float]] = [None] * len(closes)

    k_prev = 50.0
    d_prev = 50.0
    k_factor = 1 / k_smooth
    d_factor = 1 / d_smooth

    for i in range(len(closes)):
        if i + 1 < period:
            continue
        window_high = max(highs[i + 1 - period : i + 1])
        window_low = min(lows[i + 1 - period : i + 1])
        if window_high == window_low:
            rsv = 50.0
        else:
            rsv = (closes[i] - window_low) / (window_high - window_low) * 100.0

        k_current = (1 - k_factor) * k_prev + k_factor * rsv
        d_current = (1 - d_factor) * d_prev + d_factor * k_current
        j_current = 3 * k_current - 2 * d_current

        k_values[i] = k_current
        d_values[i] = d_current
        j_values[i] = j_current

        k_prev = k_current
        d_prev = d_current

    return k_values, d_values, j_values
