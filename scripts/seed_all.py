"""Run all seed scripts in order.

Intended for a one-time run after first Railway deployment:
  railway run --service api python -m scripts.seed_all

Skips if the database already has jurisdiction data.
"""
import os
import sys

import psycopg2


def db_already_seeded(dsn: str) -> bool:
    dsn = dsn.replace("postgres://", "postgresql://", 1)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = psycopg2.connect(dsn)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM tax_jurisdictions")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count > 0


def run_module(module: str) -> None:
    print(f"\n[seed_all] Running {module} ...")
    import importlib
    mod = importlib.import_module(module)
    if hasattr(mod, "main"):
        mod.main()
    else:
        # Some scripts run on import; re-running is safe since they're idempotent
        pass


SEED_MODULES = [
    "scripts.seed_data",
    "scripts.seed_countries",
    "scripts.seed_enhancement",
    "scripts.seed_enhancement_v2",
    "scripts.seed_enhancement_v3",
    "scripts.seed_etg_markets",
    "scripts.seed_expansion",
    "scripts.seed_missing_rates",
    "scripts.seed_subjurisdictions",
    "scripts.seed_critical_gaps",
    "scripts.seed_comprehensive_rates",
    "scripts.seed_final_fixes",
    "scripts.seed_regulatory_sources",
]


def main() -> None:
    dsn = os.environ.get(
        "DATABASE_URL_SYNC",
        os.environ.get("DATABASE_URL", "postgresql://taxlens:taxlens@localhost:5432/taxlens"),
    )

    if db_already_seeded(dsn):
        print("[seed_all] Database already has jurisdiction data — skipping full seed.")
        print("[seed_all] To force re-seed, truncate tax_jurisdictions first.")
        return

    print("[seed_all] Starting full data seed...")
    errors = []
    for module in SEED_MODULES:
        try:
            run_module(module)
        except Exception as exc:
            print(f"[seed_all] WARNING: {module} failed: {exc}", file=sys.stderr)
            errors.append((module, exc))

    print(f"\n[seed_all] Done. {len(SEED_MODULES) - len(errors)}/{len(SEED_MODULES)} modules succeeded.")
    if errors:
        for mod, exc in errors:
            print(f"  FAILED: {mod}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
