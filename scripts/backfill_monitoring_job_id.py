"""Backfill `monitoring_job_id` on legacy AI-produced rows.

Runs added the FK column after some agent runs had already populated
jurisdictions / tax_rates / tax_rules / detected_changes without it.
This script reconstructs the back-reference from existing breadcrumbs:

  1. jurisdictions.metadata->>'discovery_job_id'      → jurisdictions.monitoring_job_id
  2. tax_rates created by ai_discovery                → inherit from parent jurisdiction
  3. tax_rates / tax_rules created by ai_monitoring   → parse audit_log change_reason
  4. detected_changes                                  → inherit from applied rate/rule

Idempotent. Default is --dry-run; pass --apply to commit.

Usage:
  python -m scripts.backfill_monitoring_job_id            # dry run (default)
  python -m scripts.backfill_monitoring_job_id --apply    # commit
"""
from __future__ import annotations

import argparse
import os
import sys

import psycopg2

# Each tuple is (title, SQL with RETURNING). Tested against Postgres.
STEPS: list[tuple[str, str]] = [
    (
        "Jurisdictions: metadata.discovery_job_id → monitoring_job_id",
        """
        UPDATE jurisdictions j
        SET monitoring_job_id = (j.metadata->>'discovery_job_id')::bigint
        WHERE j.monitoring_job_id IS NULL
          AND j.metadata ? 'discovery_job_id'
          AND (j.metadata->>'discovery_job_id') ~ '^[0-9]+$'
          AND EXISTS (
              SELECT 1 FROM monitoring_jobs
              WHERE id = (j.metadata->>'discovery_job_id')::bigint
          )
        RETURNING j.id;
        """,
    ),
    (
        "tax_rates created by ai_discovery: inherit from parent jurisdiction",
        """
        UPDATE tax_rates r
        SET monitoring_job_id = j.monitoring_job_id
        FROM jurisdictions j
        WHERE r.jurisdiction_id = j.id
          AND r.monitoring_job_id IS NULL
          AND r.created_by = 'ai_discovery'
          AND j.monitoring_job_id IS NOT NULL
        RETURNING r.id;
        """,
    ),
    (
        "tax_rates created by ai_monitoring: parse audit_log change_reason",
        """
        UPDATE tax_rates r
        SET monitoring_job_id = sub.job_id
        FROM (
          SELECT entity_id,
                 (regexp_match(change_reason, 'job #(\\d+)'))[1]::bigint AS job_id
          FROM audit_log
          WHERE entity_type = 'tax_rate'
            AND change_source = 'ai_monitoring'
            AND change_reason ~ 'job #\\d+'
        ) sub
        WHERE r.id = sub.entity_id
          AND r.monitoring_job_id IS NULL
          AND EXISTS (SELECT 1 FROM monitoring_jobs WHERE id = sub.job_id)
        RETURNING r.id;
        """,
    ),
    (
        "tax_rules created by ai_monitoring: parse audit_log change_reason",
        """
        UPDATE tax_rules r
        SET monitoring_job_id = sub.job_id
        FROM (
          SELECT entity_id,
                 (regexp_match(change_reason, 'job #(\\d+)'))[1]::bigint AS job_id
          FROM audit_log
          WHERE entity_type = 'tax_rule'
            AND change_source = 'ai_monitoring'
            AND change_reason ~ 'job #\\d+'
        ) sub
        WHERE r.id = sub.entity_id
          AND r.monitoring_job_id IS NULL
          AND EXISTS (SELECT 1 FROM monitoring_jobs WHERE id = sub.job_id)
        RETURNING r.id;
        """,
    ),
    (
        "detected_changes: inherit from applied_rate_id",
        """
        UPDATE detected_changes c
        SET monitoring_job_id = r.monitoring_job_id
        FROM tax_rates r
        WHERE c.applied_rate_id = r.id
          AND c.monitoring_job_id IS NULL
          AND r.monitoring_job_id IS NOT NULL
        RETURNING c.id;
        """,
    ),
    (
        "detected_changes: inherit from applied_rule_id",
        """
        UPDATE detected_changes c
        SET monitoring_job_id = r.monitoring_job_id
        FROM tax_rules r
        WHERE c.applied_rule_id = r.id
          AND c.monitoring_job_id IS NULL
          AND r.monitoring_job_id IS NOT NULL
        RETURNING c.id;
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


def run(apply: bool) -> int:
    """Returns total rows affected across all steps."""
    dsn = _resolve_dsn()
    print(f"Connecting to {dsn.split('@')[-1]}")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"Mode: {mode}\n")

    # All steps run inside one transaction so cascading inheritance works
    # in both dry-run and apply modes (step 2 reads step 1's changes, etc.).
    total = 0
    for title, sql in STEPS:
        with conn.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            n = len(rows)
            total += n
            print(f"[{mode}] {title}: {n} rows")

    if apply:
        conn.commit()
        print("\nCommitted.")
    else:
        conn.rollback()
    conn.close()
    print(f"\nTotal rows backfilled: {total}")
    if not apply:
        print("(Dry run — no changes committed. Pass --apply to do it.)")
    return total


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
