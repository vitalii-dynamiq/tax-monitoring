"""Wait for PostgreSQL to be ready before running migrations."""
import sys
import time

import psycopg2


def wait_for_db(max_retries=30):
    import os
    dsn = os.environ.get(
        "DATABASE_URL_SYNC",
        os.environ.get("DATABASE_URL", "postgresql://taxlens:taxlens@db:5432/taxlens"),
    )
    # Normalize driver prefixes — psycopg2 needs plain postgresql://
    dsn = dsn.replace("postgres://", "postgresql://", 1)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    for i in range(max_retries):
        try:
            conn = psycopg2.connect(dsn)
            conn.close()
            print(f"Database ready after {i + 1} attempt(s)")
            return
        except psycopg2.OperationalError:
            time.sleep(1)
    print(f"Database not ready after {max_retries} retries", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    wait_for_db()
