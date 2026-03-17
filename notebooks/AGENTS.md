# AGENTS.md

Guidelines for AI agents working in this PSA (Prefeitura de Santo André) data analysis repository.

## Build & Run Commands

This project uses `uv` for Python package management:

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate

# Run a marimo notebook interactively
uv run marimo edit <notebook>.py

# Run a notebook as a script
uv run python <notebook>.py

# Add a new dependency
uv add <package>
```

## Testing

This project does not have a formal test suite yet. When adding tests:

```bash
# Run all tests (when they exist)
uv run pytest

# Run a single test file
uv run pytest tests/test_specific.py

# Run a single test function
uv run pytest tests/test_specific.py::test_function_name -v
```

## Linting & Formatting

When lint/format tools are configured:

```bash
# Format code
uv run ruff format .

# Check linting
uv run ruff check .

# Fix auto-fixable lint issues
uv run ruff check . --fix

# Type checking (if mypy is added)
uv run mypy .
```

## Code Style Guidelines

### Imports
- Group imports: standard library, third-party, local
- Prefer explicit imports over `from module import *`
- Use `import polars as pl` (preferred over pandas)
- Type hint imports from `typing` module when needed

### Type Hints
- Use type hints for function signatures: `def func(param: str) -> int:`
- Use `pl.Expr` for polars expression functions
- Type hints are encouraged but not strictly enforced

### Naming Conventions
- **Variables/functions**: `snake_case`
- **Constants**: `UPPER_CASE`
- **Files**: `snake_case.py`
- Column names in dataframes: `snake_case` (after normalization)

### Code Structure
- Notebooks are marimo `.py` files using `@app.cell` decorator pattern
- Each cell is a standalone unit that returns variables needed by other cells
- Place helper functions in their own cells for reusability

### Error Handling
- Use try/except for network operations (see minio_import.py pattern)
- Catch specific exceptions before generic ones
- Return meaningful error messages for debugging

### Data Processing
- **Primary library**: polars (preferred over pandas)
- Use polars expressions (`pl.col()`, `.alias()`) for transformations
- Chain dataframe operations with method chaining
- Normalize column names: lowercase, snake_case, remove accents

### Documentation
- Add docstrings for utility functions explaining purpose and parameters
- Use Google-style or plain docstrings (not strict)
- Keep comments minimal; code should be self-explanatory

### Environment Variables
- Load from `.env` using `python-dotenv`
- Required env vars for MinIO: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`

### Notebook Patterns
- Each notebook starts with `app = marimo.App(width="medium"|"full")`
- Import standard library modules first, then third-party
- Return tuple of variables from each cell to make them available downstream
- Use `if __name__ == "__main__": app.run()` at end

## Project-Specific Conventions

- Data files go in `dados/` directory (CSV, JSON geospatial data)
- Date parsing format: `%Y/%m/%d %H:%M:%S` for Brazilian dates
- Coordinate columns: `longitude`, `latitude`
- Text normalization: strip accents, lowercase, replace spaces with underscores
- Do not edit `__marimo__/session/` files (auto-generated)
