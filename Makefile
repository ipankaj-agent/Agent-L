install:
	uv install --no-cache

lint:
	uv run ruff check src tests

typecheck:
	uv run mypy src tests

test:
	uv run pytest

playwright-install:
	uv run playwright install

clean:
	rm -rf .pytest_cache build dist __pycache__
