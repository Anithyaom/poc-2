#!/bin/bash
set -e

# `migrate` only — never `makemigrations`. A running image must not invent
# schema nobody reviewed.
echo "Running database migrations..."
uv run --no-sync tortoise migrate

echo "Starting FastAPI application..."
exec uv run --no-sync uvicorn src.main:app \
  --host 0.0.0.0 --port "${APP_PORT:-8000}" \
  --workers "${WORKERS:-4}" --loop uvloop --http httptools
