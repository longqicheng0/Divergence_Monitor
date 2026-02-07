"""Tests for pivot detection."""

from src.strategy.pivots import find_pivot_highs, find_pivot_lows


def test_pivot_lows() -> None:
    values = [5, 4, 3, 4, 5, 2, 3, 4]
    pivots = find_pivot_lows(values, left=1, right=1)
    assert pivots == [2, 5]


def test_pivot_highs() -> None:
    values = [1, 3, 2, 4, 1, 5, 3]
    pivots = find_pivot_highs(values, left=1, right=1)
    assert pivots == [1, 3, 5]
