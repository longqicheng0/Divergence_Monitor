"""Validated prompts for interactive CLI inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import List, Tuple

from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DateRange:
    """Represents a validated date range."""

    start: datetime
    end: datetime


def parse_date(value: str) -> date:
    """Parse a YYMMDD date string.

    Raises:
        ValueError: If the date string is invalid.
    """

    return datetime.strptime(value.strip(), "%y%m%d").date()


def validate_date_range(start_value: str, end_value: str) -> Tuple[date, date]:
    """Validate that start and end dates are in correct order."""

    start = parse_date(start_value)
    end = parse_date(end_value)
    if start >= end:
        raise ValueError("Start date must be before end date")
    return start, end


def parse_date_range_compact(value: str) -> Tuple[date, date]:
    """Parse a compact YYMMDDYYMMDD date range string."""

    raw = value.strip()
    if len(raw) != 12 or not raw.isdigit():
        raise ValueError("Date range must be 12 digits in YYMMDDYYMMDD format")
    start_raw = raw[:6]
    end_raw = raw[6:]
    return validate_date_range(start_raw, end_raw)


def build_datetime_range(start: date, end: date, timezone: str) -> DateRange:
    """Create timezone-aware datetime range covering full days."""

    tz = ZoneInfo(timezone)
    start_dt = datetime.combine(start, time.min).replace(tzinfo=tz)
    end_dt = datetime.combine(end, time.max.replace(microsecond=0)).replace(tzinfo=tz)
    return DateRange(start=start_dt, end=end_dt)


def prompt_with_default(prompt: str, default: str) -> str:
    """Prompt for a string value with a default."""

    value = input(f"{prompt} [{default}]: ").strip()
    return value or default


def prompt_symbols(default: str = "SMCI") -> List[str]:
    """Prompt for comma-separated symbols."""

    raw = prompt_with_default("Symbols (comma-separated)", default)
    return [symbol.strip().upper() for symbol in raw.split(",") if symbol.strip()]


def prompt_timeframe(default: str = "10m") -> str:
    """Prompt for timeframe like 10m and validate format."""

    while True:
        value = prompt_with_default("Timeframe (e.g., 10m)", default)
        if value.endswith("m") and value[:-1].isdigit() and int(value[:-1]) > 0:
            return value
        print("Invalid timeframe. Use format like 10m.")


def prompt_date_range(timezone: str) -> DateRange:
    """Prompt for date range and return validated DateRange."""

    while True:
        range_raw = input("Date range (YYMMDDYYMMDD): ").strip()
        try:
            start, end = parse_date_range_compact(range_raw)
            return build_datetime_range(start, end, timezone)
        except ValueError as exc:
            print(f"Invalid dates: {exc}")
