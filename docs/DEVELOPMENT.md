# Development

## Development Dependencies

Install with development dependencies:

```shell
uv sync --group dev
```

This includes:

- pytest & pytest-asyncio
- httpx (for testing)
- mypy
- ruff
- pre-commit

## Running the Application

The application can be run with any ASGI server. For development:

```bash
uv run python -m app.main
```

## Testing

Run tests with pytest:

```shell
uv run pytest
```

## Debug Mode

Enable debug mode to access OpenAPI documentation:

```bash
export DEBUG=true
```

Visit `http://localhost:8000/schema` for the OpenAPI spec or
`http://localhost:8000/schema/swagger` for a UI.

## Code Quality Tools

The project uses pre-commit hooks for code quality:

- ruff: Fast Python linter and formatter
- mypy: Static type checking
- pre-commit-hooks: Standard checks (trailing whitespace, merge conflicts, etc.)
- prettier: Standardize various documentation formatting

Run checks manually:

```shell
# Run all pre-commit hooks
uv run pre-commit install
uv run pre-commit run --all-files

# Run ruff
uv run ruff check .
uv run ruff format .

# Run mypy
uv run mypy app
```

## Pre-commit Hook Failures

If commits are blocked by pre-commit:

```bash
# Fix issues automatically where possible
uv run pre-commit run --all-files

# Skip hooks in emergency (not recommended)
git commit --no-verify
```

## Type Checking Errors

Mypy is configured with strict mode. To investigate type issues:

```bash
uv run mypy app --show-error-codes
```
