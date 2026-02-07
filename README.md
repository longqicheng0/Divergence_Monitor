# Divergence_Monitor

Beginner‑friendly guide to run a Python app that watches US stocks, builds 10‑minute candles, detects RSI divergence, and uses MACD + KDJ as confirmation filters before sending Discord alerts.

## What you need

- Python 3.10 or newer
- An Alpaca account (for market data)
- A Discord webhook URL

## Quick overview

1. Install dependencies.
2. Add environment variables.
3. Run the app.

## Step 1: Install dependencies

Open a terminal in this project folder and run:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Step 2: Set environment variables

Create a file named .env in the project’s top folder (the same folder as README.md). You can also use Alpaca.env if you prefer. Then copy this list and fill in your values:

```
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_FEED=iex
ALPACA_DATA_URL=https://data.alpaca.markets
ALPACA_STREAM_URL=wss://stream.data.alpaca.markets/v2/iex
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DRY_RUN=false
TIMEZONE=America/Toronto
SQLITE_PATH=./divergence_monitor.db
```

Tip: set DRY_RUN=true to print the Discord payload instead of sending.

## Step 3: Run the app

### Interactive mode (recommended for beginners)

Just run the app with no mode flags and follow the menu:

# Divergence_Monitor

Beginner‑friendly guide to run a Python app that watches US stocks, builds 10‑minute candles, detects **RSI divergence**, and confirms with **MACD + KDJ** before sending Discord alerts.

## What you need

- Python 3.9+ (3.10+ recommended)
- An Alpaca account (market data)
- A Discord webhook URL (optional if DRY_RUN=true)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

## Environment setup

Create a .env file in the project root (same folder as this README). You can also use Alpaca.env.

```
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_FEED=iex
ALPACA_DATA_URL=https://data.alpaca.markets
ALPACA_STREAM_URL=wss://stream.data.alpaca.markets/v2/iex
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DRY_RUN=false
TIMEZONE=America/Toronto
SQLITE_PATH=./divergence_monitor.db
```

Tip: set DRY_RUN=true to print the Discord payload instead of sending.

## Run (interactive)

```bash
python -m src.main
```

Use the arrow keys and Enter to choose an option. Date input format is **YYMMDDYYMMDD** (e.g., 260101260120).

## Run (non‑interactive)

Live monitoring:

```bash
python -m src.main --mode live --symbols SMCI --timeframe 10m
```

Backtest:

```bash
python -m src.main --mode backtest --symbols SMCI --timeframe 10m --daterange 260101260120
```

## Strategy logic (current)

- **Primary trigger (required): RSI divergence**
	- Bullish: price lower low + RSI higher low
	- Bearish: price higher high + RSI lower high
- **Confirmations (optional):**
	- MACD: histogram rising (bullish) / falling (bearish), or MACD line above/below signal line
	- KDJ (9,3,3): K crosses D or K/D < 30 turning up (bullish); K crosses below D or K/D > 70 turning down (bearish)
- **Signal strength:**
	- STRONG: both MACD and KDJ confirm
	- NORMAL: only one confirms
	- Discarded: none confirm

## Charts

Backtest produces a report chart with candlesticks, RSI, MACD, and KDJ (K/D only). Signals are labeled as STRONG or NORMAL.

## Tests

```bash
python -m pytest
```

## Troubleshooting

- **403 / authentication errors:** check Alpaca keys and feed permissions.
- **No live data:** markets may be closed; try during regular market hours.
- **No signals:** confirm date range and ensure enough candles for indicator warm‑up.
