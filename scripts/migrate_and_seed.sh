#!/bin/sh
set -e

echo "[startup] Waiting for database..."
python -m scripts.wait_for_db

echo "[startup] Running migrations..."
alembic upgrade head

echo "[startup] Seeding admin user..."
python -m scripts.seed_admin_user

echo "[startup] Done — starting server."
