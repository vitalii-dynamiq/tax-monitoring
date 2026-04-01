"""Create the default admin user if one does not already exist.

Run automatically on every API startup via migrate_and_seed.sh — idempotent.

Credentials:
  Email:    admin@taxlens.io
  Password: $ADMIN_PASSWORD env var (default: TaxLens2025!)
"""
import hashlib
import os
import secrets
import sys

import psycopg2


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}${hashed}"


def main() -> None:
    dsn = os.environ.get(
        "DATABASE_URL_SYNC",
        os.environ.get("DATABASE_URL", "postgresql://taxlens:taxlens@localhost:5432/taxlens"),
    )
    # Normalize postgres:// → postgresql://  (Railway injects postgres://)
    dsn = dsn.replace("postgres://", "postgresql://", 1)
    # Strip asyncpg driver prefix if present (sync psycopg2 doesn't need it)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)

    email = "admin@taxlens.io"
    password = os.environ.get("ADMIN_PASSWORD", "TaxLens2025!")

    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        print(f"[seed_admin_user] Admin user {email!r} already exists — skipping.")
        cur.close()
        conn.close()
        return

    pw_hash = hash_password(password)
    cur.execute(
        """
        INSERT INTO users (email, password_hash, role, is_active, failed_login_attempts)
        VALUES (%s, %s, 'admin', TRUE, 0)
        """,
        (email, pw_hash),
    )
    print(f"[seed_admin_user] Created admin user: {email}")
    if password == "TaxLens2025!":
        print("[seed_admin_user] WARNING: using default password — set ADMIN_PASSWORD env var!")

    cur.close()
    conn.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[seed_admin_user] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
