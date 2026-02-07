# Divergence_Monitor

Beginner‑friendly guide to run a Python app that watches US stocks, builds 10‑minute candles, detects RSI divergence, and sends Discord alerts only when a new signal appears.

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
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Step 2: Set environment variables

Create a file named .env in the project’s top folder (the same folder as README.md). Then copy this list and fill in your values:

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

```bash
python -m src.main --symbols SMCI --timeframe 10m
```

## What happens next

- The app backfills the last ~500 10‑minute bars from Alpaca.
- It connects to the live stream and updates the current candle.
- When a candle closes, it checks for divergence signals.
- New signals are sent to Discord and recorded in SQLite to avoid duplicates.

## Changing symbols later

You can add more symbols by separating them with commas, for example:

```bash
python -m src.main --symbols SMCI,AAPL,MSFT --timeframe 10m
```

## Tests (optional)

If you want to run tests:

```bash
pytest
```
