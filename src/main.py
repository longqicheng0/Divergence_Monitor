"""Main entry point for the divergence monitoring service."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from zoneinfo import ZoneInfo

from src.config import Config
from src.data.alpaca_client import AlpacaConfig, AlpacaDataClient
from src.data.storage import SQLiteStorage
from src.logging_config import get_logger, setup_logging
from src.modes.backtest import run_backtest
from src.modes.live import run_live
from src.ui.prompts import prompt_date_range, prompt_symbols, prompt_timeframe
from src.ui.welcome import build_welcome, select_menu_option


@dataclass(frozen=True)
class CliArgs:
    """Parsed CLI arguments."""

    mode: Optional[str]
    symbols: List[str]
    timeframe: str
    start: Optional[str]
    end: Optional[str]
    daterange: Optional[str]
    interactive: bool


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_args() -> CliArgs:
    parser = argparse.ArgumentParser(description="Divergence monitor")
    parser.add_argument("--mode", choices=["backtest", "live"], help="Run mode")
    parser.add_argument("--symbols", help="Comma-separated symbols")
    parser.add_argument("--timeframe", default="10m", help="Timeframe, e.g. 10m")
    parser.add_argument("--start", help="Start date YYMMDD")
    parser.add_argument("--end", help="End date YYMMDD")
    parser.add_argument("--daterange", help="Date range YYMMDDYYMMDD")
    parser.add_argument(
        "--interactive",
        help="Enable interactive menu (true/false)",
    )
    args = parser.parse_args()

    if args.mode is None:
        interactive = True if args.interactive is None else _parse_bool(args.interactive)
    else:
        interactive = False if args.interactive is None else _parse_bool(args.interactive)

    symbols_value = args.symbols or "SMCI"
    symbols = [symbol.strip().upper() for symbol in symbols_value.split(",") if symbol]
    return CliArgs(
        mode=args.mode,
        symbols=symbols,
        timeframe=args.timeframe,
        start=args.start,
        end=args.end,
        daterange=args.daterange,
        interactive=interactive,
    )


async def main() -> None:
    setup_logging()
    logger = get_logger(__name__)
    args = _parse_args()
    config = Config.from_env()
    logger.info(
        "Starting with mode=%s symbols=%s timeframe=%s db=%s",
        args.mode or "interactive",
        ",".join(args.symbols),
        args.timeframe,
        config.db_path,
    )
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

    if args.interactive and args.mode is None:
        header = build_welcome(
            "Divergence Monitor",
            "Monitors stocks for price vs RSI divergence and confirms with MACD/KDJ.",
        )
        choice = select_menu_option(header)
        if choice == "3":
            logger.info("Goodbye.")
            return
        if choice == "1":
            symbols = prompt_symbols("SMCI")
            timeframe = prompt_timeframe("10m")
            date_range = prompt_date_range(config.timezone)
            await run_backtest(
                config,
                client,
                storage,
                symbols,
                timeframe,
                date_range.start.astimezone(ZoneInfo("UTC")),
                date_range.end.astimezone(ZoneInfo("UTC")),
            )
            return
        if choice == "2":
            symbols = prompt_symbols("SMCI")
            timeframe = prompt_timeframe("10m")
            await run_live(config, client, storage, symbols, timeframe)
            return

    if args.mode == "backtest":
        if args.daterange:
            from src.ui.prompts import parse_date_range_compact, build_datetime_range

            start, end = parse_date_range_compact(args.daterange)
            date_range = build_datetime_range(start, end, config.timezone)
        elif args.start and args.end:
            from src.ui.prompts import validate_date_range, build_datetime_range

            start, end = validate_date_range(args.start, args.end)
            date_range = build_datetime_range(start, end, config.timezone)
        elif args.interactive:
            date_range = prompt_date_range(config.timezone)
        else:
            raise ValueError("Backtest requires --daterange or --start and --end")
        await run_backtest(
            config,
            client,
            storage,
            args.symbols,
            args.timeframe,
            date_range.start.astimezone(ZoneInfo("UTC")),
            date_range.end.astimezone(ZoneInfo("UTC")),
        )
        return

    if args.mode == "live":
        await run_live(config, client, storage, args.symbols, args.timeframe)
        return

    raise ValueError("No mode selected. Use --mode or --interactive.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        setup_logging()
        get_logger(__name__).info("Shutdown requested. Exiting.")
