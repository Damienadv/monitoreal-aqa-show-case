# syntax=docker/dockerfile:1.7
# Multi-stage build: base (deps) → api (production) → tests (dev + test deps).

# ---------- base ----------
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv (pinned)
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

# ---------- api ----------
FROM base AS api

COPY src ./src
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --retries=5 --start-period=5s \
    CMD curl -fsS http://localhost:8000/health || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "mock_server.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ---------- tests ----------
FROM base AS tests

RUN uv sync --frozen
COPY src ./src
COPY tests ./tests
COPY docs ./docs

CMD ["uv", "run", "pytest", "-v"]
