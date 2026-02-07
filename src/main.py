"""Main entry point for the divergence monitoring service."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime
import hashlib
import logging
from typing import Dict, List

from .alerts.discord import build_discord_payload, send_discord_alert
from .config import Config
from .data.alpaca_client import AlpacaConfig, AlpacaDataClient
from .data.candle_builder import Bar, Candle, CandleBuilder
from .data.storage import SQLiteStorage
from .indicators.rsi import compute_rsi
from .strategy.divergence import DivergenceConfig, detect_divergence


@dataclass(frozen=True)
class RuntimeConfig:
    """Runtime parameters for the app."""

    symbols: List[str]
    timeframe: str


def _parse_args() -> RuntimeConfig:
    parser = argparse.ArgumentParser(description="Divergence monitor")
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols")
    parser.add_argument("--timeframe", default="10m", help="Timeframe, e.g. 10m")
    args = parser.parse_args()
    symbols = [symbol.strip().upper() for symbol in args.symbols.split(",") if symbol]
    return RuntimeConfig(symbols=symbols, timeframe=args.timeframe)


def _signal_id(symbol: str, timeframe: str, signal_type: str, pivot_ts: datetime) -> str:
    key = f"{symbol}|{timeframe}|{signal_type}|{pivot_ts.isoformat()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _parse_timeframe_minutes(timeframe: str) -> int:
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
        timeframe_minutes = _parse_timeframe_minutes(runtime.timeframe)
        self._builders: Dict[str, CandleBuilder] = {
            symbol: CandleBuilder(symbol, timeframe_minutes, config.timezone)
            for symbol in runtime.symbols
        }
        self._strategy_config = DivergenceConfig()

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
            self._storage.upsert_candles(candles)

    async def handle_bar(self, bar: Bar) -> None:
        builder = self._builders.get(bar.symbol)
        if not builder:
            return
        closed = builder.update(bar)
        if closed:
            self._storage.upsert_candle(closed)
            await self._evaluate_signals(closed.symbol)

    async def _evaluate_signals(self, symbol: str) -> None:
        candles = self._storage.get_candles(symbol, self._runtime.timeframe, limit=500)
        if len(candles) < 50:
            return

        closes = [candle.close for candle in candles]
        timestamps = [candle.ts for candle in candles]
        rsi = compute_rsi(closes, period=14)
        signal = detect_divergence(
            symbol,
            self._runtime.timeframe,
            closes,
            timestamps,
            rsi,
            self._strategy_config,
        )
        if not signal:
            return

        signal_id = _signal_id(
            signal.symbol, signal.timeframe, signal.signal_type, signal.pivot_2_ts
        )
        if self._storage.has_sent(signal_id):
            return

        payload = build_discord_payload(
            symbol=signal.symbol,
            timeframe=signal.timeframe,
            signal_type=signal.signal_type,
            reason=signal.reason,
            pivot_ts=signal.pivot_2_ts.isoformat(),
        )
        await send_discord_alert(
            self._config.discord_webhook,
            payload,
            dry_run=self._config.dry_run,
        )
        self._storage.mark_sent(
            signal_id, signal.symbol, signal.timeframe, signal.signal_type
        )

    async def run(self) -> None:
        await self.backfill()
        await self._client.stream_bars(self._runtime.symbols, self.handle_bar)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    runtime = _parse_args()
    config = Config.from_env()
    client = AlpacaDataClient(
        AlpacaConfig(
            api_key=config.alpaca_api_key,
            secret_key=config.alpaca_secret_key,
            data_url=config.alpaca_data_url,
            stream_url=config.alpaca_stream_url,
            feed=config.alpaca_feed,
        )
    )
    storage = SQLiteStorage(config.db_path)
    monitor = DivergenceMonitor(config, runtime, storage, client)
    await monitor.run()


if __name__ == "__main__":
    asyncio.run(main())
