"""Tests for divergence detection."""

from datetime import datetime, timedelta, timezone

from src.strategy.divergence import DivergenceConfig, detect_divergence


def test_bullish_divergence() -> None:
    now = datetime.now(timezone.utc)
    closes = [10, 9, 8, 9, 7, 8, 9, 10]
    timestamps = [now + timedelta(minutes=10 * i) for i in range(len(closes))]
    rsi = [30, 28, 25, 27, 29, 31, 33, 35]
    config = DivergenceConfig(pivot_left=1, pivot_right=1, min_sep_bars=2, max_sep_bars=10, min_rsi_delta=2.0)

    signal = detect_divergence("SMCI", "10m", closes, timestamps, rsi, config)
    assert signal is not None
    assert signal.signal_type == "bullish"


def test_bearish_divergence() -> None:
    now = datetime.now(timezone.utc)
    closes = [10, 11, 10, 12, 11, 13, 12, 11]
    timestamps = [now + timedelta(minutes=10 * i) for i in range(len(closes))]
    rsi = [70, 72, 68, 66, 65, 64, 63, 62]
    config = DivergenceConfig(pivot_left=1, pivot_right=1, min_sep_bars=2, max_sep_bars=10, min_rsi_delta=2.0)

    signal = detect_divergence("SMCI", "10m", closes, timestamps, rsi, config)
    assert signal is not None
    assert signal.signal_type == "bearish"
