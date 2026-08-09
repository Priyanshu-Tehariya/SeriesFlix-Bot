#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] Running Alembic migrations..."
alembic upgrade head

echo "[entrypoint] Starting bot..."
exec python -m bot.main
