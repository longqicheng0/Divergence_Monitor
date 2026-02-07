"""Tests for divergence detection."""

from datetime import datetime, timedelta, timezone

from src.strategy.divergence import DivergenceConfig, detect_divergence


def test_bullish_divergence() -> None:
    now = datetime.now(timezone.utc)
    closes = [10, 9, 8, 9, 7, 8, 9, 10]
    timestamps = [now + timedelta(minutes=10 * i) for i in range(len(closes))]
    rsi = [30, 28, 25, 27, 29, 31, 33, 35]
    macd_line = [0.1, 0.0, -0.5, -0.2, 0.2, 0.4, 0.6, 0.8]
    macd_signal = [0.0] * len(closes)
    macd_hist = [m - s for m, s in zip(macd_line, macd_signal)]
    k_values = [20, 21, 22, 23, 24, 25, 26, 27]
    d_values = [19, 20, 21, 22, 23, 24, 25, 26]
    config = DivergenceConfig(
        pivot_left=1,
        pivot_right=1,
        min_sep_bars=2,
        max_sep_bars=10,
        min_rsi_delta=2.0,
        use_macd=False,
        use_kdj=False,
    )

    signal = detect_divergence(
        "SMCI",
        "10m",
        closes,
        timestamps,
        rsi,
        macd_line,
        macd_signal,
        macd_hist,
        k_values,
        d_values,
        config,
    )
    assert signal is not None
    assert signal.signal_type == "bullish"


def test_bearish_divergence() -> None:
    now = datetime.now(timezone.utc)
    closes = [10, 11, 10, 12, 11, 13, 12, 11]
    timestamps = [now + timedelta(minutes=10 * i) for i in range(len(closes))]
    rsi = [70, 72, 68, 66, 65, 64, 63, 62]
    macd_line = [0.5, 0.8, 0.4, 0.6, 0.2, 0.0, -0.1, -0.2]
    macd_signal = [0.0] * len(closes)
    macd_hist = [m - s for m, s in zip(macd_line, macd_signal)]
    k_values = [80, 79, 78, 77, 76, 75, 74, 73]
    d_values = [79, 78, 77, 76, 75, 74, 73, 72]
    config = DivergenceConfig(
        pivot_left=1,
        pivot_right=1,
        min_sep_bars=2,
        max_sep_bars=10,
        min_rsi_delta=2.0,
        use_macd=False,
        use_kdj=False,
    )

    signal = detect_divergence(
        "SMCI",
        "10m",
        closes,
        timestamps,
        rsi,
        macd_line,
        macd_signal,
        macd_hist,
        k_values,
        d_values,
        config,
    )
    assert signal is not None
    assert signal.signal_type == "bearish"


def test_rsi_with_macd_confirmation() -> None:
    now = datetime.now(timezone.utc)
    closes = [10, 9, 8, 9, 7, 8, 9, 10]
    timestamps = [now + timedelta(minutes=10 * i) for i in range(len(closes))]
    rsi = [30, 28, 25, 27, 29, 31, 33, 35]
    macd_line = [-0.5, -0.4, -0.6, -0.2, 0.1, 0.2, 0.4, 0.6]
    macd_signal = [-0.6] * len(closes)
    macd_hist = [m - s for m, s in zip(macd_line, macd_signal)]
    k_values = [20] * len(closes)
    d_values = [20] * len(closes)
    config = DivergenceConfig(
        pivot_left=1,
        pivot_right=1,
        min_sep_bars=2,
        max_sep_bars=10,
        min_rsi_delta=2.0,
        use_macd=True,
        use_kdj=False,
    )

    signal = detect_divergence(
        "SMCI",
        "10m",
        closes,
        timestamps,
        rsi,
        macd_line,
        macd_signal,
        macd_hist,
        k_values,
        d_values,
        config,
    )
    assert signal is not None
    assert "macd" in signal.confirmations


def test_rsi_with_kdj_confirmation() -> None:
    now = datetime.now(timezone.utc)
    closes = [10, 9, 8, 9, 7, 8, 9, 10]
    timestamps = [now + timedelta(minutes=10 * i) for i in range(len(closes))]
    rsi = [30, 28, 25, 27, 29, 31, 33, 35]
    macd_line = [0.0] * len(closes)
    macd_signal = [0.0] * len(closes)
    macd_hist = [0.0] * len(closes)
    k_values = [25, 26, 27, 28, 29, 30, 32, 35]
    d_values = [24, 25, 26, 27, 28, 29, 30, 31]
    config = DivergenceConfig(
        pivot_left=1,
        pivot_right=1,
        min_sep_bars=2,
        max_sep_bars=10,
        min_rsi_delta=2.0,
        use_macd=False,
        use_kdj=True,
    )

    signal = detect_divergence(
        "SMCI",
        "10m",
        closes,
        timestamps,
        rsi,
        macd_line,
        macd_signal,
        macd_hist,
        k_values,
        d_values,
        config,
    )
    assert signal is not None
    assert "kdj" in signal.confirmations


def test_rsi_rejected_without_confirmation() -> None:
    now = datetime.now(timezone.utc)
    closes = [10, 9, 8, 9, 7, 8, 9, 10]
    timestamps = [now + timedelta(minutes=10 * i) for i in range(len(closes))]
    rsi = [30, 28, 25, 27, 29, 31, 33, 35]
    macd_line = [0.0] * len(closes)
    macd_signal = [0.0] * len(closes)
    macd_hist = [0.0] * len(closes)
    k_values = [50] * len(closes)
    d_values = [50] * len(closes)
    config = DivergenceConfig(
        pivot_left=1,
        pivot_right=1,
        min_sep_bars=2,
        max_sep_bars=10,
        min_rsi_delta=2.0,
        use_macd=True,
        use_kdj=True,
        require_both_confirmations=True,
    )

    signal = detect_divergence(
        "SMCI",
        "10m",
        closes,
        timestamps,
        rsi,
        macd_line,
        macd_signal,
        macd_hist,
        k_values,
        d_values,
        config,
    )
    assert signal is None
