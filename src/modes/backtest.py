"""Historical backtest mode using Alpaca REST data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean, median
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
from src.simulations.trade_simulator import SignalEvent, simulate_portfolio
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


def _confirmation_bucket(confirmations: List[str]) -> str:
    if "macd" in confirmations and "kdj" in confirmations:
        return "macd+kdj"
    if "macd" in confirmations:
        return "macd_only"
    if "kdj" in confirmations:
        return "kdj_only"
    return "none"


def _log_accuracy_metrics(
    candles_by_symbol: Dict[str, List[Candle]],
    events_by_symbol: Dict[str, List[SignalEvent]],
    horizons: List[int],
    logger,
    label: str,
) -> None:
    returns_by: Dict[str, Dict[str, Dict[int, List[float]]]] = {
        "bullish": {},
        "bearish": {},
    }

    def _add_return(direction: str, bucket: str, horizon: int, value: float) -> None:
        returns_by.setdefault(direction, {}).setdefault(bucket, {}).setdefault(horizon, []).append(value)

    for symbol, events in events_by_symbol.items():
        candles = candles_by_symbol.get(symbol, [])
        if not candles:
            continue
        closes = [candle.close for candle in candles]
        for event in events:
            entry_index = event.pivot_index
            if entry_index >= len(closes):
                continue
            entry_price = closes[entry_index]
            bucket = _confirmation_bucket(event.confirmations)
            for horizon in horizons:
                exit_index = entry_index + horizon
                if exit_index >= len(closes):
                    continue
                exit_price = closes[exit_index]
                if event.signal_type == "bullish":
                    ret = (exit_price - entry_price) / entry_price
                else:
                    ret = (entry_price - exit_price) / entry_price
                _add_return(event.signal_type, bucket, horizon, ret)
                _add_return(event.signal_type, "all", horizon, ret)

    logger.info("Accuracy metrics (%s, returns are directionally adjusted)", label)
    for direction, buckets in returns_by.items():
        logger.info("%s signals:", direction.capitalize())
        for bucket, horizon_map in buckets.items():
            for horizon, returns in horizon_map.items():
                if not returns:
                    continue
                hits = sum(1 for value in returns if value > 0)
                hit_rate = hits / len(returns)
                avg_ret = mean(returns)
                med_ret = median(returns)
                logger.info(
                    "  %s h=%s count=%s hit_rate=%.1f%% avg=%.3f%% median=%.3f%%",
                    bucket,
                    horizon,
                    len(returns),
                    hit_rate * 100,
                    avg_ret * 100,
                    med_ret * 100,
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
    rsi_only_strategy = DivergenceConfig(use_macd=False, use_kdj=False)
    signal_points: List[Tuple[str, str, str]] = []
    events_by_symbol: Dict[str, List[SignalEvent]] = {symbol: [] for symbol in symbols}
    raw_events_by_symbol: Dict[str, List[SignalEvent]] = {symbol: [] for symbol in symbols}
    seen_signals: set[str] = set()
    seen_raw_signals: set[str] = set()

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
            logger.debug(
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
            raw_signal = detect_divergence(
                symbol,
                timeframe,
                closes,
                timestamps,
                rsi,
                None,
                None,
                None,
                None,
                None,
                rsi_only_strategy,
            )
            if raw_signal:
                if len(closes) - 1 == raw_signal.pivot_2_index + rsi_only_strategy.pivot_right:
                    raw_key = signal_id(
                        raw_signal.symbol,
                        raw_signal.timeframe,
                        raw_signal.signal_type,
                        raw_signal.pivot_2_ts,
                    )
                    if raw_key not in seen_raw_signals:
                        seen_raw_signals.add(raw_key)
                        raw_events_by_symbol.setdefault(raw_signal.symbol, []).append(
                            SignalEvent(
                                symbol=raw_signal.symbol,
                                signal_type=raw_signal.signal_type,
                                strength=raw_signal.strength,
                                confirmations=raw_signal.confirmations,
                                pivot_index=raw_signal.pivot_2_index,
                                pivot_ts=raw_signal.pivot_2_ts,
                            )
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
            events_by_symbol.setdefault(signal.symbol, []).append(
                SignalEvent(
                    symbol=signal.symbol,
                    signal_type=signal.signal_type,
                    strength=signal.strength,
                    confirmations=signal.confirmations,
                    pivot_index=signal.pivot_2_index,
                    pivot_ts=signal.pivot_2_ts,
                )
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
        _log_accuracy_metrics(
            candles_by_symbol,
            events_by_symbol,
            horizons=[3, 6],
            logger=logger,
            label="confirmed (RSI + MACD/KDJ)",
        )
        _log_accuracy_metrics(
            candles_by_symbol,
            raw_events_by_symbol,
            horizons=[3, 6],
            logger=logger,
            label="RSI-only (no confirmations)",
        )
        confirmed_results = simulate_portfolio(
            candles_by_symbol,
            events_by_symbol,
            starting_cash=1000.0,
            buy_pct=1.0,
            sell_pct=1.0,
        )
        rsi_only_results = simulate_portfolio(
            candles_by_symbol,
            raw_events_by_symbol,
            starting_cash=1000.0,
            buy_pct=1.0,
            sell_pct=1.0,
        )
        for symbol, result in confirmed_results.items():
            logger.info(
                "Simulation (confirmed, sell=100%%) %s: start=$%.2f end=$%.2f return=%.2f%% buys=%s sells=%s cash=$%.2f shares=%.4f",
                symbol,
                result["starting_cash"],
                result["ending_value"],
                result["return_pct"],
                int(result["buy_count"]),
                int(result["sell_count"]),
                result["cash"],
                result["shares"],
            )
        for symbol, result in rsi_only_results.items():
            logger.info(
                "Simulation (RSI-only, sell=100%%) %s: start=$%.2f end=$%.2f return=%.2f%% buys=%s sells=%s cash=$%.2f shares=%.4f",
                symbol,
                result["starting_cash"],
                result["ending_value"],
                result["return_pct"],
                int(result["buy_count"]),
                int(result["sell_count"]),
                result["cash"],
                result["shares"],
            )
        plot_backtest_report(all_candles, signal_points, timeframe, strategy)
    return summary
