"""Wait for PostgreSQL to be ready before running migrations."""
import sys
import time

import psycopg2


def wait_for_db(max_retries=60):
    import os
    dsn = os.environ.get(
        "DATABASE_URL_SYNC",
        os.environ.get("DATABASE_URL", "postgresql://taxlens:taxlens@db:5432/taxlens"),
    )
    # Normalize driver prefixes — psycopg2 needs plain postgresql://
    dsn = dsn.replace("postgres://", "postgresql://", 1)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    # Log host being checked (no credentials)
    try:
        from urllib.parse import urlparse
        parsed = urlparse(dsn)
        print(f"[wait_for_db] Connecting to {parsed.hostname}:{parsed.port or 5432} ...")
    except Exception:
        pass

    for i in range(max_retries):
        try:
            conn = psycopg2.connect(dsn, connect_timeout=5)
            conn.close()
            print(f"[wait_for_db] Database ready after {i + 1} attempt(s)")
            return
        except psycopg2.OperationalError as e:
            if i == 0 or (i + 1) % 10 == 0:
                print(f"[wait_for_db] Not ready yet (attempt {i + 1}/{max_retries}): {e}")
            time.sleep(1)
    print(f"[wait_for_db] ERROR: Database not ready after {max_retries} retries", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    wait_for_db()
