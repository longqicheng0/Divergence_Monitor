"""Configuration loading for Divergence Monitor."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Optional

from dotenv import find_dotenv, load_dotenv


def _load_env_files() -> None:
    """Load environment variables from .env or Alpaca.env if present."""

    load_dotenv(find_dotenv(), override=False)
    project_root = Path(__file__).resolve().parents[1]
    alpaca_env = project_root / "Alpaca.env"
    if alpaca_env.exists():
        load_dotenv(alpaca_env, override=False)


_load_env_files()


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from environment variables."""

    alpaca_api_key: str
    alpaca_secret_key: str
    alpaca_data_url: str
    alpaca_stream_url: str
    alpaca_feed: str
    discord_webhook: Optional[str]
    dry_run: bool
    timezone: str
    db_path: str

    @staticmethod
    def _get_env_bool(name: str, default: bool = False) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.

        Raises:
            ValueError: If required variables are missing.
        """

        alpaca_api_key = os.getenv("ALPACA_API_KEY", "").strip()
        alpaca_secret_key = os.getenv("ALPACA_SECRET_KEY", "").strip()
        alpaca_data_url = os.getenv("ALPACA_DATA_URL", "https://data.alpaca.markets")
        alpaca_feed = os.getenv("ALPACA_FEED", "iex")
        alpaca_stream_url = os.getenv(
            "ALPACA_STREAM_URL", f"wss://stream.data.alpaca.markets/v2/{alpaca_feed}"
        )
        discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
        dry_run = cls._get_env_bool("DRY_RUN", default=False)
        timezone = os.getenv("TIMEZONE", "America/Toronto")
        db_path = os.getenv("SQLITE_PATH", "./divergence_monitor.db")

        if not alpaca_api_key or not alpaca_secret_key:
            raise ValueError("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY")

        if not discord_webhook and not dry_run:
            raise ValueError("Missing DISCORD_WEBHOOK_URL (or set DRY_RUN=true)")

        return cls(
            alpaca_api_key=alpaca_api_key,
            alpaca_secret_key=alpaca_secret_key,
            alpaca_data_url=alpaca_data_url,
            alpaca_stream_url=alpaca_stream_url,
            alpaca_feed=alpaca_feed,
            discord_webhook=discord_webhook,
            dry_run=dry_run,
            timezone=timezone,
            db_path=db_path,
        )
