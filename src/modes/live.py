"""Live monitoring mode using Alpaca WebSocket streaming."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
from typing import Dict, List

from src.alerts.discord import build_discord_payload, send_discord_alert
from src.config import Config
from src.data.alpaca_client import AlpacaDataClient
from src.data.candle_builder import Bar, Candle, CandleBuilder
from src.data.storage import SQLiteStorage
from src.indicators.kdj import compute_kdj
from src.indicators.macd import compute_macd
from src.indicators.rsi import compute_rsi
from src.logging_config import get_logger
from src.strategy.divergence import DivergenceConfig, detect_divergence


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime parameters for live mode."""

    symbols: List[str]
    timeframe: str


def signal_id(symbol: str, timeframe: str, signal_type: str, pivot_ts: datetime) -> str:
    """Compute a stable signal ID for deduping alerts."""

    key = f"{symbol}|{timeframe}|{signal_type}|{pivot_ts.isoformat()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def parse_timeframe_minutes(timeframe: str) -> int:
    """Parse timeframe string into minutes."""

    if timeframe.endswith("m"):
        return int(timeframe[:-1])
    raise ValueError(f"Unsupported timeframe: {timeframe}")


class DivergenceMonitor:
    """Core service that streams data and triggers alerts."""

    def __init__(
        self,
        config: Config,
        runtime: RuntimeConfig,
        storage: SQLiteStorage,
        client: AlpacaDataClient,
    ) -> None:
        self._config = config
        self._runtime = runtime
        self._storage = storage
        self._client = client
        timeframe_minutes = parse_timeframe_minutes(runtime.timeframe)
        self._builders: Dict[str, CandleBuilder] = {
            symbol: CandleBuilder(symbol, timeframe_minutes, config.timezone)
            for symbol in runtime.symbols
        }
        self._strategy_config = DivergenceConfig(use_macd=True, use_kdj=True)
        self._logger = get_logger(__name__)
        self._bar_count = 0

    async def backfill(self) -> None:
        backfill = self._client.backfill_bars(self._runtime.symbols, self._runtime.timeframe)
        for symbol, bars in backfill.items():
            candles = [
                Candle(
                    symbol=symbol,
                    timeframe=self._runtime.timeframe,
                    ts=bar.ts,
                    open=bar.open,
                    high=bar.high,
                    low=bar.low,
                    close=bar.close,
                    volume=bar.volume,
                )
                for bar in bars
            ]
            if candles:
                self._storage.upsert_candles(candles)

    async def handle_bar(self, bar: Bar) -> None:
        builder = self._builders.get(bar.symbol)
        if not builder:
            return
        closed = builder.update(bar)
        if closed:
            self._bar_count += 1
            self._logger.info(
                "Candle closed %s %s %s O:%.2f H:%.2f L:%.2f C:%.2f V:%.0f",
                closed.symbol,
                closed.timeframe,
                closed.ts.isoformat(),
                closed.open,
                closed.high,
                closed.low,
                closed.close,
                closed.volume,
            )
            if self._bar_count % 30 == 0:
                self._logger.info("Heartbeat: processed %s closed candles", self._bar_count)
            self._storage.upsert_candle(closed)
            await self._evaluate_signals(closed.symbol)

    async def _evaluate_signals(self, symbol: str) -> None:
        candles = self._storage.get_candles(symbol, self._runtime.timeframe, limit=500)
        if len(candles) < 50:
            return

        closes = [candle.close for candle in candles]
        highs = [candle.high for candle in candles]
        lows = [candle.low for candle in candles]
        timestamps = [candle.ts for candle in candles]
        rsi = compute_rsi(closes, period=14)
        macd_line, macd_signal = compute_macd(closes)
        macd_hist = [
            (line - sig) if line is not None and sig is not None else None
            for line, sig in zip(macd_line, macd_signal)
        ]
        k_values, d_values, _j_values = compute_kdj(closes, highs, lows)
        signal = detect_divergence(
            symbol,
            self._runtime.timeframe,
            closes,
            timestamps,
            rsi,
            macd_line,
            macd_signal,
            macd_hist,
            k_values,
            d_values,
            self._strategy_config,
        )
        if not signal:
            return

        signal_key = signal_id(
            signal.symbol, signal.timeframe, signal.signal_type, signal.pivot_2_ts
        )
        if self._storage.has_sent(signal_key):
            return

        confirmations = ",".join(signal.confirmations) if signal.confirmations else "none"
        self._logger.info(
            "Signal %s %s %s confirmations=%s %s",
            signal.symbol,
            signal.signal_type.upper(),
            signal.strength.upper(),
            confirmations,
            signal.reason,
        )

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
            self._config.discord_webhook,
            payload,
            dry_run=self._config.dry_run,
        )
        self._storage.mark_sent(
            signal_key, signal.symbol, signal.timeframe, signal.signal_type
        )

    async def run(self) -> None:
        await self.backfill()
        await self._client.stream_bars(self._runtime.symbols, self.handle_bar)


async def run_live(
    config: Config,
    client: AlpacaDataClient,
    storage: SQLiteStorage,
    symbols: List[str],
    timeframe: str,
) -> None:
    """Run live monitoring mode."""

    runtime = RuntimeConfig(symbols=symbols, timeframe=timeframe)
    monitor = DivergenceMonitor(config, runtime, storage, client)
    await monitor.run()
