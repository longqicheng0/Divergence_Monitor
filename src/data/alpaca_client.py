"""Alpaca REST + WebSocket client for market data."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import json
import logging
from typing import Awaitable, Callable, Dict, Iterable, List

import websockets
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from src.data.candle_builder import Bar

logger = logging.getLogger(__name__)

BarHandler = Callable[[Bar], Awaitable[None]]


@dataclass(frozen=True)
class AlpacaConfig:
    """Configuration for Alpaca data clients."""

    api_key: str
    secret_key: str
    data_url: str
    stream_url: str
    feed: str


class AlpacaDataClient:
    """Alpaca data client that supports REST backfill and WebSocket streaming."""

    def __init__(self, config: AlpacaConfig) -> None:
        self._config = config
        self._rest = StockHistoricalDataClient(
            config.api_key,
            config.secret_key,
            url_override=config.data_url,
        )

    @staticmethod
    def _timeframe_from_str(timeframe: str) -> TimeFrame:
        if timeframe.endswith("m"):
            minutes = int(timeframe[:-1])
            return TimeFrame(minutes, TimeFrameUnit.Minute)
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    def backfill_bars(
        self, symbols: Iterable[str], timeframe: str, limit: int = 500
    ) -> Dict[str, List[Bar]]:
        """Fetch historical bars from Alpaca REST API."""

        request = StockBarsRequest(
            symbol_or_symbols=list(symbols),
            timeframe=self._timeframe_from_str(timeframe),
            limit=limit,
            feed=self._config.feed,
        )
        bars = self._rest.get_stock_bars(request)
        results: Dict[str, List[Bar]] = {symbol: [] for symbol in symbols}
        for symbol, series in bars.data.items():
            results[symbol] = [
                Bar(
                    symbol=symbol,
                    ts=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                )
                for bar in series
            ]
        return results

    def get_bars_range(
        self,
        symbols: Iterable[str],
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> Dict[str, List[Bar]]:
        """Fetch bars for a given time range from Alpaca REST API."""

        request = StockBarsRequest(
            symbol_or_symbols=list(symbols),
            timeframe=self._timeframe_from_str(timeframe),
            start=start,
            end=end,
            feed=self._config.feed,
        )
        bars = self._rest.get_stock_bars(request)
        results: Dict[str, List[Bar]] = {symbol: [] for symbol in symbols}
        for symbol, series in bars.data.items():
            results[symbol] = [
                Bar(
                    symbol=symbol,
                    ts=bar.timestamp,
                    open=float(bar.open),
                    high=float(bar.high),
                    low=float(bar.low),
                    close=float(bar.close),
                    volume=float(bar.volume),
                )
                for bar in series
            ]
        return results

    async def stream_bars(self, symbols: Iterable[str], on_bar: BarHandler) -> None:
        """Stream live bars using Alpaca WebSocket API."""

        symbols_list = list(symbols)
        if not symbols_list:
            raise ValueError("No symbols provided for streaming")

        backoff = 1.0
        max_backoff = 30.0
        while True:
            try:
                async with websockets.connect(self._config.stream_url, ping_interval=20) as ws:
                    await self._authenticate(ws)
                    await self._subscribe(ws, symbols_list)
                    async for message in ws:
                        await self._handle_message(message, on_bar)
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # pragma: no cover - reconnect handling
                logger.exception("Stream error: %s", exc)
                await asyncio.sleep(backoff)
                backoff = min(max_backoff, backoff * 2)

    async def _authenticate(self, ws: websockets.WebSocketClientProtocol) -> None:
        auth_msg = {
            "action": "auth",
            "key": self._config.api_key,
            "secret": self._config.secret_key,
        }
        await ws.send(json.dumps(auth_msg))
        response = await ws.recv()
        logger.debug("Auth response: %s", response)

    async def _subscribe(self, ws: websockets.WebSocketClientProtocol, symbols: List[str]) -> None:
        subscribe_msg = {"action": "subscribe", "bars": symbols}
        await ws.send(json.dumps(subscribe_msg))
        response = await ws.recv()
        logger.debug("Subscribe response: %s", response)

    async def _handle_message(self, message: str, on_bar: BarHandler) -> None:
        payload = json.loads(message)
        if isinstance(payload, dict) and payload.get("T") == "error":
            logger.error("Alpaca error: %s", payload)
            return

        if isinstance(payload, list):
            for item in payload:
                if item.get("T") == "b":
                    bar = Bar(
                        symbol=item["S"],
                        ts=datetime.fromisoformat(item["t"].replace("Z", "+00:00")),
                        open=float(item["o"]),
                        high=float(item["h"]),
                        low=float(item["l"]),
                        close=float(item["c"]),
                        volume=float(item["v"]),
                    )
                    await on_bar(bar)
