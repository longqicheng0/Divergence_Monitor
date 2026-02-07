"""Tests for prompt validation utilities."""

import pytest

from src.ui.prompts import parse_date, parse_date_range_compact, validate_date_range


def test_parse_date_valid() -> None:
    assert parse_date("260115").isoformat() == "2026-01-15"


def test_validate_date_range_ordering() -> None:
    with pytest.raises(ValueError):
        validate_date_range("260116", "260115")


def test_parse_date_range_compact() -> None:
    start, end = parse_date_range_compact("260101260120")
    assert start.isoformat() == "2026-01-01"
    assert end.isoformat() == "2026-01-20"
