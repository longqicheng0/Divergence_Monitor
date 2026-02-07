"""SQLite storage for candles and alert deduplication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import sqlite3
from typing import Iterable, List

from src.data.candle_builder import Candle


@dataclass(frozen=True)
class StoredSignal:
    """Represents a stored signal record."""

    signal_id: str
    symbol: str
    timeframe: str
    signal_type: str
    sent_at: datetime


class SQLiteStorage:
    """SQLite storage with simple upsert semantics."""

    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS candles (
                symbol TEXT,
                timeframe TEXT,
                ts DATETIME,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL,
                PRIMARY KEY(symbol, timeframe, ts)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts_sent (
                symbol TEXT,
                timeframe TEXT,
                signal_type TEXT,
                signal_id TEXT PRIMARY KEY,
                sent_at DATETIME
            )
            """
        )
        self._conn.commit()

    def upsert_candles(self, candles: Iterable[Candle]) -> None:
        cursor = self._conn.cursor()
        cursor.executemany(
            """
            INSERT INTO candles (symbol, timeframe, ts, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, timeframe, ts) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume
            """,
            [
                (
                    candle.symbol,
                    candle.timeframe,
                    candle.ts.isoformat(),
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                )
                for candle in candles
            ],
        )
        self._conn.commit()

    def upsert_candle(self, candle: Candle) -> None:
        self.upsert_candles([candle])

    def get_candles(self, symbol: str, timeframe: str, limit: int = 500) -> List[Candle]:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT symbol, timeframe, ts, open, high, low, close, volume
            FROM candles
            WHERE symbol = ? AND timeframe = ?
            ORDER BY ts ASC
            LIMIT ?
            """,
            (symbol, timeframe, limit),
        )
        rows = cursor.fetchall()
        return [
            Candle(
                symbol=row["symbol"],
                timeframe=row["timeframe"],
                ts=datetime.fromisoformat(row["ts"]),
                open=row["open"],
                high=row["high"],
                low=row["low"],
                close=row["close"],
                volume=row["volume"],
            )
            for row in rows
        ]

    def has_sent(self, signal_id: str) -> bool:
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT 1 FROM alerts_sent WHERE signal_id = ?", (signal_id,)
        )
        return cursor.fetchone() is not None

    def mark_sent(
        self, signal_id: str, symbol: str, timeframe: str, signal_type: str
    ) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO alerts_sent (symbol, timeframe, signal_type, signal_id, sent_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (symbol, timeframe, signal_type, signal_id, datetime.utcnow().isoformat()),
        )
        self._conn.commit()
