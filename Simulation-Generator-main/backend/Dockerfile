# Multi-stage: builder → base → app | celery.
# Same image content, different entrypoint.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# Dependency layer, cached independently of source changes.
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev


FROM python:3.12-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /uvx /bin/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/src ./src


FROM base AS app

COPY backend/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]


FROM base AS celery

# Command comes from docker-compose so the queue/concurrency stay visible there.
CMD ["uv", "run", "--no-sync", "celery", "-A", "src.worker", "worker", "-l", "info"]
