run:
	python -m src.main

backtest:
	python -m src.main --mode backtest --symbols SMCI --timeframe 10m --daterange 260101260120

test:
	python -m pytest

format:
	python -m black src tests

lint:
	python -m ruff src tests
