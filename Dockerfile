FROM python:3.12-slim AS base

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 1000 app && \
    useradd --uid 1000 --gid app --shell /bin/bash --create-home app

WORKDIR /opt/app

# ---------------------------------------------------------------------------
# Build stage: install dependencies
# ---------------------------------------------------------------------------
FROM base AS build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# Runtime stage
# ---------------------------------------------------------------------------
FROM base AS runtime

COPY --from=build /opt/app /opt/app

ENV PATH="/opt/app/.venv/bin:$PATH" \
    RUNTIME=production

EXPOSE 8000

USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/v1/healthz')"]

ENTRYPOINT ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
