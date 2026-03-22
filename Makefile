.PHONY: sync lock run test lint format

sync:
uv sync --dev

lock:
uv lock

run:
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
uv run pytest

lint:
uv run ruff check .

format:
uv run ruff check . --fix
