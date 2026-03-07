.PHONY: dev install test lint clean run

# Development install (editable)
dev:
	pip install -e .

# Standard install
install:
	pip install .

# Run the application
run:
	python -m lazycron

# Run tests
test:
	python -m pytest tests/ -v

# Run tests with coverage
coverage:
	python -m pytest tests/ -v --cov=lazycron --cov-report=term-missing

# Lint with ruff (if installed)
lint:
	python -m ruff check lazycron/ tests/

# Format with ruff (if installed)
fmt:
	python -m ruff format lazycron/ tests/

# Type check with mypy (if installed)
typecheck:
	python -m mypy lazycron/

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Build distribution
build: clean
	python -m build

# Run unittest directly (no pytest needed)
unittest:
	python -m unittest discover -s tests -v
