"""Pivot detection utilities."""

from __future__ import annotations

from typing import List


def find_pivot_lows(values: List[float], left: int, right: int) -> List[int]:
    """Find pivot low indices using a window method."""

    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")

    pivots: List[int] = []
    for i in range(left, len(values) - right):
        window = values[i - left : i + right + 1]
        if values[i] == min(window):
            pivots.append(i)
    return pivots


def find_pivot_highs(values: List[float], left: int, right: int) -> List[int]:
    """Find pivot high indices using a window method."""

    if left < 1 or right < 1:
        raise ValueError("left and right must be >= 1")

    pivots: List[int] = []
    for i in range(left, len(values) - right):
        window = values[i - left : i + right + 1]
        if values[i] == max(window):
            pivots.append(i)
    return pivots
