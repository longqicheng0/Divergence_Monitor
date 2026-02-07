"""Divergence detection logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from src.strategy.pivots import find_pivot_highs, find_pivot_lows


@dataclass(frozen=True)
class DivergenceSignal:
    """Represents a divergence signal."""

    symbol: str
    timeframe: str
    signal_type: str
    strength: str
    confirmations: List[str]
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
    use_macd: bool = False
    use_kdj: bool = False
    require_both_confirmations: bool = False


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
    macd_line: Optional[List[Optional[float]]],
    macd_signal: Optional[List[Optional[float]]],
    macd_hist: Optional[List[Optional[float]]],
    k_values: Optional[List[Optional[float]]],
    d_values: Optional[List[Optional[float]]],
    config: DivergenceConfig,
) -> Optional[DivergenceSignal]:
    """Detect divergence signals between price and RSI with confirmations.

    Returns:
        DivergenceSignal if a new divergence is detected, else None.
    """

    if len(closes) != len(rsi) or len(closes) != len(timestamps):
        raise ValueError("closes, timestamps, and rsi must have the same length")

    if config.use_macd:
        if macd_line is None or macd_signal is None or macd_hist is None:
            raise ValueError("MACD confirmations require macd_line, macd_signal, macd_hist")
        if len(macd_line) != len(closes) or len(macd_signal) != len(closes) or len(macd_hist) != len(closes):
            raise ValueError("MACD arrays must match closes length")

    if config.use_kdj:
        if k_values is None or d_values is None:
            raise ValueError("KDJ confirmations require k_values and d_values")
        if len(k_values) != len(closes) or len(d_values) != len(closes):
            raise ValueError("KDJ arrays must match closes length")

    pivot_lows = find_pivot_lows(closes, config.pivot_left, config.pivot_right)
    pivot_highs = find_pivot_highs(closes, config.pivot_left, config.pivot_right)

    low_pair = _select_last_two(pivot_lows, config.min_sep_bars, config.max_sep_bars)
    if low_pair:
        i1, i2 = low_pair
        rsi1 = rsi[i1]
        rsi2 = rsi[i2]
        if rsi1 is not None and rsi2 is not None:
            price_lower_low = closes[i2] < closes[i1]
            rsi_higher_low = rsi2 >= rsi1 + config.min_rsi_delta
            if price_lower_low and rsi_higher_low:
                confirmations = _confirmations(
                    "bullish",
                    i2,
                    config,
                    macd_line,
                    macd_signal,
                    macd_hist,
                    k_values,
                    d_values,
                )
                strength = _strength_from(confirmations, config)
                if strength is None:
                    return None
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
                    strength=strength,
                    confirmations=confirmations,
                    pivot_1_index=i1,
                    pivot_2_index=i2,
                    pivot_2_ts=timestamps[i2],
                    reason=reason,
                )

    high_pair = _select_last_two(pivot_highs, config.min_sep_bars, config.max_sep_bars)
    if high_pair:
        i1, i2 = high_pair
        rsi1 = rsi[i1]
        rsi2 = rsi[i2]
        if rsi1 is not None and rsi2 is not None:
            price_higher_high = closes[i2] > closes[i1]
            rsi_lower_high = rsi2 <= rsi1 - config.min_rsi_delta
            if price_higher_high and rsi_lower_high:
                confirmations = _confirmations(
                    "bearish",
                    i2,
                    config,
                    macd_line,
                    macd_signal,
                    macd_hist,
                    k_values,
                    d_values,
                )
                strength = _strength_from(confirmations, config)
                if strength is None:
                    return None
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
                    strength=strength,
                    confirmations=confirmations,
                    pivot_1_index=i1,
                    pivot_2_index=i2,
                    pivot_2_ts=timestamps[i2],
                    reason=reason,
                )

    return None


def _strength_from(confirmations: List[str], config: DivergenceConfig) -> Optional[str]:
    if not config.use_macd and not config.use_kdj:
        return "normal"

    if config.require_both_confirmations:
        if config.use_macd and config.use_kdj:
            return "strong" if {"macd", "kdj"}.issubset(confirmations) else None
        if config.use_macd:
            return "strong" if "macd" in confirmations else None
        if config.use_kdj:
            return "strong" if "kdj" in confirmations else None

    if "macd" in confirmations and "kdj" in confirmations:
        return "strong"
    if confirmations:
        return "normal"
    return None


def _confirmations(
    direction: str,
    pivot_index: int,
    config: DivergenceConfig,
    macd_line: Optional[List[Optional[float]]],
    macd_signal: Optional[List[Optional[float]]],
    macd_hist: Optional[List[Optional[float]]],
    k_values: Optional[List[Optional[float]]],
    d_values: Optional[List[Optional[float]]],
) -> List[str]:
    confirmations: List[str] = []
    current_index = None
    if macd_line is not None:
        current_index = len(macd_line) - 1
    elif k_values is not None:
        current_index = len(k_values) - 1

    if current_index is None or current_index < pivot_index:
        return confirmations

    if config.use_macd:
        if _macd_confirms(direction, current_index, macd_line, macd_signal, macd_hist):
            confirmations.append("macd")

    if config.use_kdj:
        if _kdj_confirms(direction, current_index, k_values, d_values):
            confirmations.append("kdj")

    return confirmations


def _macd_confirms(
    direction: str,
    idx: int,
    macd_line: Optional[List[Optional[float]]],
    macd_signal: Optional[List[Optional[float]]],
    macd_hist: Optional[List[Optional[float]]],
) -> bool:
    if macd_line is None or macd_signal is None or macd_hist is None:
        return False
    if idx <= 0:
        return False
    line = macd_line[idx]
    signal = macd_signal[idx]
    hist = macd_hist[idx]
    prev_hist = macd_hist[idx - 1]
    if line is None or signal is None or hist is None or prev_hist is None:
        return False

    if direction == "bullish":
        return hist > prev_hist or line > signal
    return hist < prev_hist or line < signal


def _kdj_confirms(
    direction: str,
    idx: int,
    k_values: Optional[List[Optional[float]]],
    d_values: Optional[List[Optional[float]]],
) -> bool:
    if k_values is None or d_values is None or idx <= 0:
        return False

    k_now = k_values[idx]
    d_now = d_values[idx]
    k_prev = k_values[idx - 1]
    d_prev = d_values[idx - 1]
    if k_now is None or d_now is None or k_prev is None or d_prev is None:
        return False

    if direction == "bullish":
        cross = k_prev <= d_prev and k_now > d_now
        turn = k_now > k_prev and d_now > d_prev and k_now < 30 and d_now < 30
        return cross or turn

    cross = k_prev >= d_prev and k_now < d_now
    turn = k_now < k_prev and d_now < d_prev and k_now > 70 and d_now > 70
    return cross or turn
