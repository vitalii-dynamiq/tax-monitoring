#!/bin/sh
set -e

echo "[startup] Waiting for database..."
python -m scripts.wait_for_db

echo "[startup] Running migrations..."
alembic upgrade head

echo "[startup] Seeding admin user..."
python -m scripts.seed_admin_user

echo "[startup] Starting server on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
