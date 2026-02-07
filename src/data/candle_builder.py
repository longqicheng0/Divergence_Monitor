"""Candle aggregation utilities."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Candle:
    """Represents an OHLCV candle."""

    symbol: str
    timeframe: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Bar:
    """Represents a raw bar from a data provider."""

    symbol: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class CandleBuilder:
    """Aggregates smaller bars into a target timeframe candle."""

    def __init__(self, symbol: str, timeframe_minutes: int, timezone: str) -> None:
        self.symbol = symbol
        self.timeframe_minutes = timeframe_minutes
        self.timeframe = f"{timeframe_minutes}m"
        self.tz = ZoneInfo(timezone)
        self._current: Optional[Candle] = None
        self._bucket_start: Optional[datetime] = None

    def _align_bucket_start(self, ts: datetime) -> datetime:
        localized = ts.astimezone(self.tz)
        minute = (localized.minute // self.timeframe_minutes) * self.timeframe_minutes
        bucket = localized.replace(minute=minute, second=0, microsecond=0)
        return bucket

    def update(self, bar: Bar) -> Optional[Candle]:
        """Update the current candle with a new bar.

        Returns:
            The closed candle if the incoming bar starts a new bucket.
        """

        bucket_start = self._align_bucket_start(bar.ts)
        if self._bucket_start is None:
            self._bucket_start = bucket_start
            self._current = Candle(
                symbol=self.symbol,
                timeframe=self.timeframe,
                ts=bucket_start,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
            return None

        if bucket_start > self._bucket_start:
            closed = self._current
            self._bucket_start = bucket_start
            self._current = Candle(
                symbol=self.symbol,
                timeframe=self.timeframe,
                ts=bucket_start,
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
            )
            return closed

        if self._current is None:
            return None

        self._current = Candle(
            symbol=self.symbol,
            timeframe=self.timeframe,
            ts=self._current.ts,
            open=self._current.open,
            high=max(self._current.high, bar.high),
            low=min(self._current.low, bar.low),
            close=bar.close,
            volume=self._current.volume + bar.volume,
        )
        return None

    def finalize(self) -> Optional[Candle]:
        """Return the last in-progress candle (if any)."""

        return self._current
