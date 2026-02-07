# Contributing

Thanks for contributing.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Run

```bash
python -m src.main
```

## Tests

```bash
python -m pytest
```

## Formatting & Linting

```bash
python -m black src tests
python -m ruff src tests
```

## Notes

- Keep changes small and focused.
- Do not commit secrets or .env files.
- Update UPDATE_SUMMARY.txt with a new version line for code changes.
