"""
Seed tax rates + rules from the 2026-04-22 global-research JSON as drafts.

Reads scripts/data/research/global_hotel_tax_changes_2026-04-22.json and
inserts each finding's concrete rates/rules into prod as status='draft',
created_by='ai_research_global_2026-04-22'.

Safety features:
- Only seeds rates for jurisdictions that exist in the DB (skips the 6 missing).
- Only seeds flat/percentage rates (skips tiered — needs manual schema review).
- Duplicate check: (jurisdiction_id, tax_category_id, effective_start) in status
  active/draft → skip.
- Uses CATEGORY_CODE_ALIASES from seed_missing_jurisdictions.py for any AI
  category codes that don't match the DB taxonomy.
- Only rules with unambiguous semantics (concrete conditions on BookingContext
  fields + concrete actions) are seeded. Administrative / term / vague rules
  are skipped.

Usage:
  export DATABASE_URL_SYNC=$(railway run --service db printenv DATABASE_PUBLIC_URL)
  python -m scripts.seed_global_research --dry-run        # preview
  python -m scripts.seed_global_research                  # real seed
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import psycopg2
import psycopg2.extras

from scripts.seed_missing_jurisdictions import CATEGORY_CODE_ALIASES

RESEARCH_FILE = Path(__file__).parent / "data" / "research" / "global_hotel_tax_changes_2026-04-22.json"
CREATED_BY = "ai_research_global_2026-04-22"

# Fields we accept as BookingContext conditions (mirror rule_engine.py).
BOOKING_CONTEXT_FIELDS = {
    "jurisdiction_code", "stay_date", "checkout_date", "nightly_rate",
    "nights", "currency", "property_type", "star_rating", "guest_type",
    "guest_age", "guest_nationality", "number_of_guests", "is_marketplace",
    "platform_type", "is_bundled",
    "stay_length_days", "stay_month", "stay_day_of_week", "total_stay_amount",
}


@dataclass
class Stats:
    jurisdictions_matched: int = 0
    jurisdictions_missing: int = 0
    missing_codes: list[str] = field(default_factory=list)
    rates_considered: int = 0
    rates_tiered_skipped: int = 0
    rates_category_missing: int = 0
    rates_duplicate: int = 0
    rates_inserted: int = 0
    rates_would_insert: int = 0
    rules_considered: int = 0
    rules_skipped_vague: int = 0
    rules_skipped_bad_field: int = 0
    rules_duplicate: int = 0
    rules_inserted: int = 0
    rules_would_insert: int = 0


def _get_dsn() -> str:
    for var in ("DATABASE_URL_SYNC", "DATABASE_URL", "DATABASE_PUBLIC_URL"):
        v = os.environ.get(var)
        if v:
            v = v.replace("postgres://", "postgresql://", 1)
            v = v.replace("postgresql+asyncpg://", "postgresql://", 1)
            return v
    return "postgresql://taxlens:taxlens@localhost:5432/taxlens"


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _walk_condition_fields(cond: dict | None) -> list[str]:
    if not cond:
        return []
    out: list[str] = []
    if "field" in cond:
        out.append(cond["field"])
    for r in cond.get("rules") or []:
        if isinstance(r, dict):
            out.extend(_walk_condition_fields(r))
    for key in ("AND", "OR", "and", "or"):
        for r in cond.get(key) or []:
            if isinstance(r, dict):
                out.extend(_walk_condition_fields(r))
    return out


def _resolve_category_id(cur, code: str) -> tuple[int | None, str]:
    """Return (id, resolved_code). id is None if nothing matches."""
    resolved = CATEGORY_CODE_ALIASES.get(code, code)
    cur.execute("SELECT id FROM tax_categories WHERE code = %s", (resolved,))
    row = cur.fetchone()
    if row:
        return row["id"], resolved
    return None, resolved


def _find_existing_rate(cur, jurisdiction_id: int, tax_category_id: int,
                        effective_start: date) -> dict | None:
    """Any active or draft rate with same (jur, cat, effective_start)."""
    cur.execute("""
        SELECT id, status, created_by
        FROM tax_rates
        WHERE jurisdiction_id = %s AND tax_category_id = %s
          AND effective_start = %s
          AND status IN ('active', 'draft')
    """, (jurisdiction_id, tax_category_id, effective_start))
    return cur.fetchone()


def _find_existing_rule(cur, tax_rate_id: int | None, jurisdiction_id: int,
                        name: str) -> dict | None:
    cur.execute("""
        SELECT id, status, created_by
        FROM tax_rules
        WHERE jurisdiction_id = %s AND name = %s
          AND (tax_rate_id = %s OR (tax_rate_id IS NULL AND %s IS NULL))
          AND status IN ('active', 'draft')
    """, (jurisdiction_id, name, tax_rate_id, tax_rate_id))
    return cur.fetchone()


def _build_rate_row(rate: dict, jurisdiction_id: int, category_id: int,
                    reviewed_by: str) -> dict | None:
    """Translate AI rate dict → tax_rates INSERT row. Returns None if rate is unsuitable."""
    rate_type = rate.get("rate_type")
    if rate_type not in ("percentage", "flat"):
        return None  # skip tiered

    effective_start = _parse_date(rate.get("effective_start"))
    if not effective_start:
        return None

    rate_value = rate.get("rate_value")
    if rate_value is None:
        return None

    # AI reports percentages as whole numbers (7.5 = 7.5%).
    # Our DB stores them as fractions (0.075). Convert.
    if rate_type == "percentage":
        rate_value = float(rate_value) / 100.0

    currency_code = rate.get("currency_code")
    # Some rates have currency only in tier details; derive from source_url host if missing? No, skip.
    if rate_type == "flat" and not currency_code:
        return None

    notes_parts = []
    if rate.get("confidence") is not None:
        notes_parts.append(f"confidence={rate['confidence']}")
    if rate.get("source_quote"):
        notes_parts.append(f"quote: {rate['source_quote'][:300]}")
    review_notes = " | ".join(notes_parts) or None

    return {
        "jurisdiction_id": jurisdiction_id,
        "tax_category_id": category_id,
        "rate_type": rate_type,
        "rate_value": rate_value,
        "currency_code": currency_code,
        "tiers": None,
        "tier_type": None,
        "enacted_date": _parse_date(rate.get("enacted_date")),
        "effective_start": effective_start,
        "effective_end": _parse_date(rate.get("effective_end")),
        "applicability_start": None,
        "announcement_date": None,
        "calculation_order": int(rate.get("calculation_order") or 100),
        "base_includes": ["base_amount"],
        "legal_reference": rate.get("legal_reference"),
        "legal_uri": rate.get("legal_uri"),
        "source_url": rate.get("source_url"),
        "authority_name": rate.get("authority_name"),
        "version": 1,
        "status": "draft",
        "created_by": CREATED_BY,
        "reviewed_by": reviewed_by,
        "review_notes": review_notes,
    }


def _build_rule_row(rule: dict, jurisdiction_id: int, tax_rate_id: int | None,
                    reviewed_by: str) -> dict | None:
    """Translate AI rule dict → tax_rules INSERT row. Returns None if unsuitable."""
    if not rule.get("name") or not rule.get("rule_type"):
        return None
    # Require an effective_start (we can default to today if missing)
    effective_start = _parse_date(rule.get("effective_start")) or date.today()

    # Validate condition fields — must reference BookingContext fields only.
    cond = rule.get("conditions")
    if cond:
        used_fields = _walk_condition_fields(cond)
        unknown = [f for f in used_fields if f and f not in BOOKING_CONTEXT_FIELDS]
        if unknown:
            return None  # skip rules we can't actually evaluate

    # Skip vague rules with no conditions AND no action.
    action = rule.get("action") or {}
    if not cond and not action and rule["rule_type"] != "exemption":
        return None

    return {
        "tax_rate_id": tax_rate_id,
        "jurisdiction_id": jurisdiction_id,
        "rule_type": rule["rule_type"],
        "priority": int(rule.get("priority", 0)),
        "name": rule["name"],
        "description": rule.get("description"),
        "conditions": json.dumps(cond or {}),
        "action": json.dumps(action),
        "effective_start": effective_start,
        "effective_end": _parse_date(rule.get("effective_end")),
        "enacted_date": _parse_date(rule.get("enacted_date")),
        "legal_reference": rule.get("legal_reference"),
        "legal_uri": None,
        "authority_name": rule.get("authority_name"),
        "version": 1,
        "status": "draft",
        "created_by": CREATED_BY,
        "reviewed_by": reviewed_by,
    }


def process_finding(cur, finding: dict, reviewed_by: str, dry_run: bool, stats: Stats) -> None:
    jcode = finding["jurisdiction_code"]
    cur.execute("SELECT id, name FROM jurisdictions WHERE code = %s", (jcode,))
    j = cur.fetchone()
    if not j:
        print(f"  [SKIP] {jcode} — not in DB")
        stats.jurisdictions_missing += 1
        stats.missing_codes.append(jcode)
        return
    stats.jurisdictions_matched += 1
    print(f"\n=== {jcode} {j['name']} ===")

    seeded_rates_by_cat: dict[str, int] = {}

    # Rates
    for idx, rate in enumerate(finding.get("rates") or []):
        stats.rates_considered += 1
        raw_code = rate.get("tax_category_code")
        if not raw_code:
            continue

        if rate.get("rate_type") == "tiered":
            stats.rates_tiered_skipped += 1
            print(f"  rate[{idx}] SKIP (tiered): {raw_code}")
            continue

        cat_id, resolved_code = _resolve_category_id(cur, raw_code)
        if cat_id is None:
            stats.rates_category_missing += 1
            print(f"  rate[{idx}] SKIP (category unknown): {raw_code}")
            continue

        row = _build_rate_row(rate, j["id"], cat_id, reviewed_by)
        if row is None:
            print(f"  rate[{idx}] SKIP (missing required fields): {raw_code}")
            continue

        dup = _find_existing_rate(cur, j["id"], cat_id, row["effective_start"])
        if dup:
            stats.rates_duplicate += 1
            print(f"  rate[{idx}] DUP ({resolved_code}): existing rate #{dup['id']} "
                  f"[status={dup['status']}, batch={dup['created_by']}]")
            # Track existing rate so rules can reference it
            seeded_rates_by_cat[resolved_code] = dup["id"]
            continue

        if dry_run:
            print(f"  rate[{idx}] WOULD-INSERT: {resolved_code} {row['rate_type']} "
                  f"{row['rate_value']} {row['currency_code'] or ''} "
                  f"effective {row['effective_start']}")
            stats.rates_would_insert += 1
            continue

        cur.execute("""
            INSERT INTO tax_rates (
                jurisdiction_id, tax_category_id, rate_type, rate_value, currency_code,
                tiers, tier_type, enacted_date, effective_start, effective_end,
                applicability_start, announcement_date, calculation_order, base_includes,
                legal_reference, legal_uri, source_url, authority_name, version, status,
                created_by, reviewed_by, review_notes
            ) VALUES (
                %(jurisdiction_id)s, %(tax_category_id)s, %(rate_type)s, %(rate_value)s, %(currency_code)s,
                %(tiers)s, %(tier_type)s, %(enacted_date)s, %(effective_start)s, %(effective_end)s,
                %(applicability_start)s, %(announcement_date)s, %(calculation_order)s, %(base_includes)s,
                %(legal_reference)s, %(legal_uri)s, %(source_url)s, %(authority_name)s, %(version)s, %(status)s,
                %(created_by)s, %(reviewed_by)s, %(review_notes)s
            ) RETURNING id
        """, row)
        new_id = cur.fetchone()["id"]
        seeded_rates_by_cat[resolved_code] = new_id
        stats.rates_inserted += 1
        print(f"  rate[{idx}] INSERTED #{new_id}: {resolved_code} {row['rate_type']} {row['rate_value']}")

    # Rules
    for idx, rule in enumerate(finding.get("rules") or []):
        stats.rules_considered += 1
        # Skip rules that can't be evaluated
        cond = rule.get("conditions")
        used_fields = _walk_condition_fields(cond or {})
        unknown = [f for f in used_fields if f and f not in BOOKING_CONTEXT_FIELDS]
        if unknown:
            stats.rules_skipped_bad_field += 1
            print(f"  rule[{idx}] SKIP (unknown field {unknown}): {rule.get('name')}")
            continue

        row = _build_rule_row(rule, j["id"], None, reviewed_by)
        if row is None:
            stats.rules_skipped_vague += 1
            print(f"  rule[{idx}] SKIP (vague): {rule.get('name')}")
            continue

        dup = _find_existing_rule(cur, None, j["id"], row["name"])
        if dup:
            stats.rules_duplicate += 1
            print(f"  rule[{idx}] DUP: existing rule #{dup['id']} "
                  f"[status={dup['status']}, batch={dup['created_by']}]")
            continue

        if dry_run:
            print(f"  rule[{idx}] WOULD-INSERT: {row['rule_type']} \"{row['name']}\"")
            stats.rules_would_insert += 1
            continue

        cur.execute("""
            INSERT INTO tax_rules (
                tax_rate_id, jurisdiction_id, rule_type, priority, name, description,
                conditions, action, effective_start, effective_end, enacted_date,
                legal_reference, legal_uri, authority_name, version, status,
                created_by, reviewed_by
            ) VALUES (
                %(tax_rate_id)s, %(jurisdiction_id)s, %(rule_type)s, %(priority)s, %(name)s, %(description)s,
                %(conditions)s, %(action)s, %(effective_start)s, %(effective_end)s, %(enacted_date)s,
                %(legal_reference)s, %(legal_uri)s, %(authority_name)s, %(version)s, %(status)s,
                %(created_by)s, %(reviewed_by)s
            ) RETURNING id
        """, row)
        new_id = cur.fetchone()["id"]
        stats.rules_inserted += 1
        print(f"  rule[{idx}] INSERTED #{new_id}: \"{row['name']}\"")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--research-file", type=Path, default=RESEARCH_FILE)
    p.add_argument("--reviewed-by", default="claude-auto-review@taxlens.io")
    args = p.parse_args()

    data = json.loads(args.research_file.read_text())
    findings = data.get("findings") or []
    print(f"Loaded {len(findings)} findings from {args.research_file.name}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'REAL SEED'}")
    print()

    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    stats = Stats()

    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        for finding in findings:
            process_finding(cur, finding, args.reviewed_by, args.dry_run, stats)

        if not args.dry_run:
            conn.commit()
        cur.close()
    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Jurisdictions matched:         {stats.jurisdictions_matched}")
    print(f"  Jurisdictions missing:         {stats.jurisdictions_missing}")
    if stats.missing_codes:
        print(f"    missing codes: {stats.missing_codes}")
    print(f"  Rates considered:              {stats.rates_considered}")
    print(f"  Rates tiered (skipped):        {stats.rates_tiered_skipped}")
    print(f"  Rates with unknown category:   {stats.rates_category_missing}")
    print(f"  Rates duplicate (skipped):     {stats.rates_duplicate}")
    if args.dry_run:
        print(f"  Rates would-insert:            {stats.rates_would_insert}")
    else:
        print(f"  Rates inserted:                {stats.rates_inserted}")
    print(f"  Rules considered:              {stats.rules_considered}")
    print(f"  Rules with unknown field:      {stats.rules_skipped_bad_field}")
    print(f"  Rules vague (skipped):         {stats.rules_skipped_vague}")
    print(f"  Rules duplicate (skipped):     {stats.rules_duplicate}")
    if args.dry_run:
        print(f"  Rules would-insert:            {stats.rules_would_insert}")
    else:
        print(f"  Rules inserted:                {stats.rules_inserted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
