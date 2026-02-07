"""Tests for backtest pipeline on synthetic data."""

import asyncio
from datetime import datetime, timedelta, timezone

from src.config import Config
from src.data.alpaca_client import AlpacaDataClient
from src.data.candle_builder import Bar
from src.data.storage import SQLiteStorage
from src.modes.backtest import run_backtest


class FakeClient(AlpacaDataClient):
    """Fake Alpaca client for tests."""

    def __init__(self, bars):
        self._bars = bars

    def get_bars_range(self, symbols, timeframe, start, end):
        return {symbol: list(self._bars) for symbol in symbols}


def test_backtest_pipeline_runs() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = []
    price = 100.0
    for i in range(120):
        ts = start + timedelta(minutes=i)
        price += 0.1 if i % 5 else -0.2
        bars.append(
            Bar(
                symbol="SMCI",
                ts=ts,
                open=price - 0.1,
                high=price + 0.2,
                low=price - 0.3,
                close=price,
                volume=1000 + i,
            )
        )

    config = Config(
        alpaca_api_key="test",
        alpaca_secret_key="test",
        alpaca_data_url="https://data.alpaca.markets",
        alpaca_stream_url="wss://stream.data.alpaca.markets/v2/iex",
        alpaca_feed="iex",
        discord_webhook=None,
        dry_run=True,
        timezone="America/Toronto",
        db_path=":memory:",
    )
    storage = SQLiteStorage(":memory:")
    client = FakeClient(bars)

    summary = asyncio.run(
        run_backtest(
            config=config,
            client=client,
            storage=storage,
            symbols=["SMCI"],
            timeframe="10m",
            start=start,
            end=start + timedelta(hours=4),
        )
    )

    assert summary.candles_processed > 0
