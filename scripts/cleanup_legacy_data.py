"""Idempotent cleanup of legacy data ahead of country-scoped monitoring.

Steps:
  1. Cancel stuck pending/running monitoring_jobs older than 1 hour
  2. Delete failed monitoring_jobs older than 30 days
  3. Delete pending jurisdictions older than 30 days that were never reviewed
  4. Delete the XX-TEST jurisdiction row (test data)
  5. Delete sub-country monitoring schedules (job_type='monitoring' on non-countries)

Default is --dry-run. Pass --apply to actually perform the changes.

Usage:
  python -m scripts.cleanup_legacy_data            # dry run (default)
  python -m scripts.cleanup_legacy_data --apply    # do it
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg2

STEPS = [
    (
        # Job timeout is 900s (15 min). Anything still pending/running after
        # 30 minutes is definitively stuck — the worker can't recover it.
        "Cancel stuck pending/running jobs >30min",
        """
        UPDATE monitoring_jobs
        SET status='failed',
            completed_at=NOW(),
            error_message=COALESCE(error_message, '') || ' [cancelled by cleanup: stuck > 30min]'
        WHERE status IN ('pending', 'running')
          AND created_at < NOW() - INTERVAL '30 minutes'
        RETURNING id;
        """,
    ),
    (
        "Delete failed monitoring_jobs older than 30 days",
        """
        DELETE FROM monitoring_jobs
        WHERE status='failed'
          AND created_at < NOW() - INTERVAL '30 days'
        RETURNING id;
        """,
    ),
    (
        "Delete pending jurisdictions older than 30 days (and their schedules/jobs)",
        # FKs are ON DELETE CASCADE (turns) or SET NULL (entities), but
        # monitoring_schedules.jurisdiction_id has no cascade — clear them first.
        """
        DELETE FROM monitoring_schedules
        WHERE jurisdiction_id IN (
          SELECT id FROM jurisdictions
          WHERE status='pending' AND created_at < NOW() - INTERVAL '30 days'
        );
        DELETE FROM monitoring_jobs
        WHERE jurisdiction_id IN (
          SELECT id FROM jurisdictions
          WHERE status='pending' AND created_at < NOW() - INTERVAL '30 days'
        );
        DELETE FROM jurisdictions
        WHERE status='pending'
          AND created_at < NOW() - INTERVAL '30 days'
        RETURNING id, code;
        """,
    ),
    (
        "Delete XX-TEST test jurisdiction (cascade schedules + jobs)",
        """
        DELETE FROM monitoring_schedules
        WHERE jurisdiction_id IN (SELECT id FROM jurisdictions WHERE code='XX-TEST');
        DELETE FROM monitoring_jobs
        WHERE jurisdiction_id IN (SELECT id FROM jurisdictions WHERE code='XX-TEST');
        DELETE FROM jurisdictions WHERE code='XX-TEST' RETURNING id, code;
        """,
    ),
    (
        "Delete sub-country monitoring schedules",
        """
        DELETE FROM monitoring_schedules
        WHERE job_type='monitoring'
          AND jurisdiction_id IN (
            SELECT id FROM jurisdictions WHERE jurisdiction_type != 'country'
          )
        RETURNING id;
        """,
    ),
    (
        # Pre-telemetry runs: no model, no token usage. We don't keep these
        # because their Produced tab is empty and their Conversation tab is
        # blank; they confuse operators. agent_run_turns cascade-deletes.
        "Delete legacy pre-telemetry monitoring_jobs (no model, no tokens)",
        """
        DELETE FROM monitoring_jobs
        WHERE model IS NULL
          AND total_input_tokens = 0
        RETURNING id;
        """,
    ),
]


def _resolve_dsn() -> str:
    dsn = os.environ.get(
        "DATABASE_URL_SYNC",
        os.environ.get(
            "DATABASE_URL",
            "postgresql://taxlens:taxlens@localhost:5433/taxlens",
        ),
    )
    dsn = dsn.replace("postgres://", "postgresql://", 1)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    return dsn


def run(apply: bool) -> None:
    dsn = _resolve_dsn()
    print(f"Connecting to {dsn.split('@')[-1]}")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"Mode: {mode}\n")

    total = 0
    for title, sql in STEPS:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            n = len(rows)
            total += n
            print(f"[{mode}] {title}: {n} rows")
            if n > 0 and n <= 10:
                for r in rows:
                    print(f"  - {r}")
            elif n > 10:
                print(f"  - (first 5) {rows[:5]}")
        if apply:
            conn.commit()
        else:
            conn.rollback()

    conn.close()
    print(f"\nTotal rows affected: {total}")
    if not apply:
        print("(Dry run — no changes committed. Pass --apply to do it.)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually apply changes. Default is dry-run.",
    )
    args = parser.parse_args()
    run(apply=args.apply)


if __name__ == "__main__":
    sys.exit(main())
