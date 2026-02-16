"""Reporting utilities for backtest visualization."""

from __future__ import annotations

from datetime import datetime
import os
from typing import Iterable, List, Tuple

import matplotlib.pyplot as plt

from src.logging_config import get_logger
from src.data.candle_builder import Candle
from src.indicators.kdj import compute_kdj
from src.indicators.macd import compute_macd
from src.indicators.rsi import compute_rsi
from src.strategy.divergence import DivergenceConfig


SignalPoint = Tuple[str, str, str]  # (pivot_ts_iso, signal_type, strength)


def _draw_candles(
    ax: plt.Axes, candles: List[Candle], positions: List[float], width: float
) -> None:
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    opens = [candle.open for candle in candles]
    closes = [candle.close for candle in candles]

    price_range = max(highs) - min(lows)
    min_body = price_range * 0.001 if price_range else 0.01

    for idx, x in enumerate(positions):
        o = opens[idx]
        c = closes[idx]
        h = highs[idx]
        l = lows[idx]
        color = "#2ecc71" if c >= o else "#e74c3c"

        ax.vlines(x, l, h, color=color, linewidth=1.0, zorder=2)

        lower = min(o, c)
        height = max(abs(c - o), min_body)
        rect = plt.Rectangle(
            (x - width / 2, lower),
            width,
            height,
            facecolor=color,
            edgecolor=color,
            linewidth=0.8,
            zorder=3,
        )
        ax.add_patch(rect)


def plot_backtest_report(
    candles: List[Candle],
    signals: Iterable[SignalPoint],
    timeframe: str,
    config: DivergenceConfig,
) -> None:
    """Plot price series and mark divergence signals.

    Args:
        candles: Candle list in chronological order.
        signals: Iterable of (pivot_ts_iso, signal_type).
        timeframe: Timeframe string (e.g., 10m).
        config: DivergenceConfig for pivot window sizing.
    """

    logger = get_logger(__name__)
    if not candles:
        logger.info("No candles to plot.")
        return

    if os.getenv("BACKTEST_NO_PLOT", "").lower() in {"1", "true", "yes"}:
        logger.info("Plotting disabled via BACKTEST_NO_PLOT.")
        return

    width = 0.7

    fig, (ax_price, ax_rsi, ax_macd, ax_kdj) = plt.subplots(
        nrows=4,
        figsize=(13, 10),
        sharex=True,
        gridspec_kw={"height_ratios": [6, 2, 2, 2]},
    )

    positions = list(range(len(candles)))
    _draw_candles(ax_price, candles, positions, width)

    times = [candle.ts for candle in candles]
    highs = [candle.high for candle in candles]
    lows = [candle.low for candle in candles]
    closes = [candle.close for candle in candles]

    price_range = max(highs) - min(lows)
    padding = price_range * 0.05 if price_range else 1.0
    ax_price.set_ylim(min(lows) - padding, max(highs) + padding)

    ts_to_index = {candle.ts: idx for idx, candle in enumerate(candles)}
    label_offsets = [0.02, 0.05, 0.08]
    for idx, (ts_iso, signal_type, strength) in enumerate(signals):
        pivot_ts = datetime.fromisoformat(ts_iso)
        pivot_index = ts_to_index.get(pivot_ts)
        if pivot_index is None:
            continue
        color = "#27ae60" if signal_type == "bullish" else "#c0392b"
        line_style = "-" if strength == "strong" else "--"
        ax_price.axvline(pivot_index, color=color, linestyle=line_style, linewidth=1.4, alpha=0.85)
        offset = label_offsets[idx % len(label_offsets)]
        ax_price.text(
            pivot_index,
            max(highs) + (price_range * offset if price_range else 0.5),
            f"{signal_type.upper()} ({strength.upper()})",
            color=color,
            fontsize=9,
            rotation=90,
            verticalalignment="bottom",
            horizontalalignment="center",
            bbox={"boxstyle": "round,pad=0.2", "facecolor": "white", "alpha": 0.7, "edgecolor": color},
        )

    ax_price.set_title("Backtest Report: Candlesticks with Divergence Signals")
    ax_price.set_ylabel("Price")
    ax_price.grid(True, linestyle="--", alpha=0.25)

    rsi = compute_rsi(closes, period=14)
    rsi_positions = [pos for pos, value in zip(positions, rsi) if value is not None]
    rsi_values = [value for value in rsi if value is not None]
    ax_rsi.plot(rsi_positions, rsi_values, color="#34495e", linewidth=1.2, label="RSI(14)")
    ax_rsi.axhline(70, color="#e74c3c", linestyle="--", linewidth=1.0, alpha=0.6)
    ax_rsi.axhline(30, color="#27ae60", linestyle="--", linewidth=1.0, alpha=0.6)
    ax_rsi.set_ylim(0, 100)
    ax_rsi.set_ylabel("RSI")
    ax_rsi.grid(True, linestyle="--", alpha=0.25)

    macd_line, signal_line = compute_macd(closes)
    macd_positions = [pos for pos, value in zip(positions, macd_line) if value is not None]
    macd_values = [value for value in macd_line if value is not None]
    signal_values = [value for value in signal_line if value is not None]
    signal_positions = [pos for pos, value in zip(positions, signal_line) if value is not None]

    ax_macd.plot(macd_positions, macd_values, color="#34495e", linewidth=1.2, label="MACD")
    ax_macd.plot(signal_positions, signal_values, color="#9b59b6", linewidth=1.0, label="Signal")
    ax_macd.axhline(0, color="#7f8c8d", linestyle="--", linewidth=1.0, alpha=0.6)
    ax_macd.set_ylabel("MACD")
    ax_macd.grid(True, linestyle="--", alpha=0.25)

    k_values, d_values, _j_values = compute_kdj(closes, highs, lows)
    k_positions = [pos for pos, value in zip(positions, k_values) if value is not None]
    d_positions = [pos for pos, value in zip(positions, d_values) if value is not None]
    k_plot = [value for value in k_values if value is not None]
    d_plot = [value for value in d_values if value is not None]
    ax_kdj.plot(k_positions, k_plot, color="#1abc9c", linewidth=1.2, label="K")
    ax_kdj.plot(d_positions, d_plot, color="#e67e22", linewidth=1.2, label="D")
    ax_kdj.axhline(80, color="#e74c3c", linestyle="--", linewidth=1.0, alpha=0.5)
    ax_kdj.axhline(20, color="#27ae60", linestyle="--", linewidth=1.0, alpha=0.5)
    ax_kdj.set_ylim(0, 100)
    ax_kdj.set_ylabel("KDJ")
    ax_kdj.grid(True, linestyle="--", alpha=0.25)

    tick_step = max(1, len(candles) // 8)
    tick_positions = positions[::tick_step]
    tick_labels = [times[idx].strftime("%Y-%m-%d %H:%M") for idx in tick_positions]
    ax_kdj.set_xticks(tick_positions)
    ax_kdj.set_xticklabels(tick_labels, rotation=30, ha="right")

    plt.tight_layout()
    plt.show()
