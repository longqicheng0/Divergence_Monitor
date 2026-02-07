"""Tests for signal ID hashing."""

from datetime import datetime, timezone

from src.modes.live import signal_id


def test_signal_id_is_deterministic() -> None:
    ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    first = signal_id("SMCI", "10m", "bullish", ts)
    second = signal_id("SMCI", "10m", "bullish", ts)
    assert first == second


def test_signal_id_changes_with_type() -> None:
    ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    bullish = signal_id("SMCI", "10m", "bullish", ts)
    bearish = signal_id("SMCI", "10m", "bearish", ts)
    assert bullish != bearish
