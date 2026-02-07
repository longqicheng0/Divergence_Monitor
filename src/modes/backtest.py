"""Historical backtest mode using Alpaca REST data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Tuple

from src.alerts.discord import build_discord_payload, send_discord_alert
from src.config import Config
from src.data.alpaca_client import AlpacaDataClient
from src.data.candle_builder import Bar, Candle, CandleBuilder
from src.data.storage import SQLiteStorage
from src.indicators.kdj import compute_kdj
from src.indicators.macd import compute_macd
from src.indicators.rsi import compute_rsi
from src.logging_config import get_logger
from src.modes.live import parse_timeframe_minutes, signal_id
from src.strategy.divergence import DivergenceConfig, detect_divergence
from src.ui.report import plot_backtest_report


@dataclass(frozen=True)
class BacktestSummary:
    """Summary stats for backtest."""

    candles_processed: int
    bullish_signals: int
    bearish_signals: int
    first_ts: Optional[datetime]
    last_ts: Optional[datetime]


def _aggregate_bars(
    symbol: str,
    bars: Iterable[Bar],
    timeframe_minutes: int,
    timezone: str,
) -> List[Candle]:
    builder = CandleBuilder(symbol, timeframe_minutes, timezone)
    candles: List[Candle] = []
    for bar in bars:
        closed = builder.update(bar)
        if closed:
            candles.append(closed)
    tail = builder.finalize()
    if tail:
        candles.append(tail)
    return candles


def _compute_summary(candles: List[Candle], bullish: int, bearish: int) -> BacktestSummary:
    first_ts = candles[0].ts if candles else None
    last_ts = candles[-1].ts if candles else None
    return BacktestSummary(
        candles_processed=len(candles),
        bullish_signals=bullish,
        bearish_signals=bearish,
        first_ts=first_ts,
        last_ts=last_ts,
    )


async def run_backtest(
    config: Config,
    client: AlpacaDataClient,
    storage: SQLiteStorage,
    symbols: List[str],
    timeframe: str,
    start: datetime,
    end: datetime,
) -> BacktestSummary:
    """Run historical backtest mode.

    Uses Alpaca REST to fetch 1m bars, aggregates to requested timeframe,
    stores candles in SQLite, and evaluates divergence signals walk-forward.
    """

    logger = get_logger(__name__)

    timeframe_minutes = parse_timeframe_minutes(timeframe)
    bars_by_symbol = client.get_bars_range(symbols, "1m", start, end)

    if all(not bars for bars in bars_by_symbol.values()):
        logger.info("No market data returned for the selected range.")
        return BacktestSummary(0, 0, 0, None, None)

    candles_by_symbol: Dict[str, List[Candle]] = {}
    for symbol, bars in bars_by_symbol.items():
        if not bars:
            continue
        candles = _aggregate_bars(symbol, bars, timeframe_minutes, config.timezone)
        candles_by_symbol[symbol] = candles
        if candles:
            storage.upsert_candles(candles)

    bullish_count = 0
    bearish_count = 0
    bullish_strong = 0
    bullish_normal = 0
    bearish_strong = 0
    bearish_normal = 0
    strategy = DivergenceConfig(use_macd=True, use_kdj=True)
    signal_points: List[Tuple[str, str, str]] = []
    seen_signals: set[str] = set()

    for symbol, candles in candles_by_symbol.items():
        closes: List[float] = []
        highs: List[float] = []
        lows: List[float] = []
        timestamps: List[datetime] = []
        for candle in candles:
            closes.append(candle.close)
            highs.append(candle.high)
            lows.append(candle.low)
            timestamps.append(candle.ts)
            logger.info(
                "Candle processed %s %s %s O:%.2f H:%.2f L:%.2f C:%.2f V:%.0f",
                symbol,
                timeframe,
                candle.ts.isoformat(),
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
            )
            if len(closes) < 50:
                continue
            rsi = compute_rsi(closes, period=14)
            macd_line, macd_signal = compute_macd(closes)
            macd_hist = [
                (line - sig) if line is not None and sig is not None else None
                for line, sig in zip(macd_line, macd_signal)
            ]
            k_values, d_values, _j_values = compute_kdj(closes, highs, lows)
            signal = detect_divergence(
                symbol,
                timeframe,
                closes,
                timestamps,
                rsi,
                macd_line,
                macd_signal,
                macd_hist,
                k_values,
                d_values,
                strategy,
            )
            if not signal:
                continue

            if len(closes) - 1 != signal.pivot_2_index + strategy.pivot_right:
                continue

            signal_key = signal_id(
                signal.symbol, signal.timeframe, signal.signal_type, signal.pivot_2_ts
            )
            if signal_key in seen_signals:
                continue

            seen_signals.add(signal_key)
            signal_points.append(
                (signal.pivot_2_ts.isoformat(), signal.signal_type, signal.strength)
            )
            if signal.signal_type == "bullish":
                bullish_count += 1
                if signal.strength == "strong":
                    bullish_strong += 1
                else:
                    bullish_normal += 1
            else:
                bearish_count += 1
                if signal.strength == "strong":
                    bearish_strong += 1
                else:
                    bearish_normal += 1

            if storage.has_sent(signal_key):
                continue

            payload = build_discord_payload(
                symbol=signal.symbol,
                timeframe=signal.timeframe,
                signal_type=signal.signal_type,
                strength=signal.strength,
                confirmations=signal.confirmations,
                reason=signal.reason,
                pivot_ts=signal.pivot_2_ts.isoformat(),
            )
            await send_discord_alert(
                config.discord_webhook,
                payload,
                dry_run=config.dry_run,
            )
            storage.mark_sent(
                signal_key, signal.symbol, signal.timeframe, signal.signal_type
            )
            confirmations = ",".join(signal.confirmations) if signal.confirmations else "none"
            logger.info(
                "%s %s %s confirmations=%s %s",
                signal.symbol,
                signal.signal_type.upper(),
                signal.strength.upper(),
                confirmations,
                signal.reason,
            )

    all_candles = [candle for candles in candles_by_symbol.values() for candle in candles]
    summary = _compute_summary(all_candles, bullish_count, bearish_count)
    logger.info("Backtest summary")
    logger.info("Candles processed: %s", summary.candles_processed)
    logger.info("Bullish signals: %s", summary.bullish_signals)
    logger.info("  - Strong: %s", bullish_strong)
    logger.info("  - Normal: %s", bullish_normal)
    logger.info("Bearish signals: %s", summary.bearish_signals)
    logger.info("  - Strong: %s", bearish_strong)
    logger.info("  - Normal: %s", bearish_normal)
    if summary.first_ts and summary.last_ts:
        logger.info("First timestamp: %s", summary.first_ts.isoformat())
        logger.info("Last timestamp: %s", summary.last_ts.isoformat())
    if all_candles:
        plot_backtest_report(all_candles, signal_points, timeframe, strategy)
    return summary
