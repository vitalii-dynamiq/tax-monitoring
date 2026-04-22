"""
Seed tax rates/rules from AI-research output JSON files as DRAFT status.

Phase 3 of the 47-missing-jurisdictions initiative (plan: binary-rolling-stonebraker.md).
Reads research outputs under scripts/data/research/*.json and idempotently inserts
approved rates/rules with status='draft', created_by='ai_research_2026-04-21'.

## Review Gate

A research JSON is ELIGIBLE for seeding only if its `_meta.reviewed_by` field is set
to a non-empty string. Unreviewed files are skipped.

Within an eligible file:
- Every rate/rule is seeded UNLESS it has `"rejected": true` at the top level.
- Any field the reviewer edits in place is honored (e.g. tweaking `calculation_order`,
  fixing `legal_reference` typos).
- Rates/rules with `change_type != "new"` are skipped (these would only appear if the
  research was re-run against partially-seeded data).

## Idempotency

- Rates: unique on (jurisdiction_id, tax_category_id, effective_start, created_by).
  Re-running the script will NOT duplicate rows.
- Rules: unique on (tax_rate_id, name, created_by).

## Usage

    # Dry-run: print what WOULD be seeded, no DB writes
    python -m scripts.seed_missing_jurisdictions --dry-run

    # Seed to local docker-compose
    python -m scripts.seed_missing_jurisdictions

    # Seed to prod (after review is complete)
    set -a; source .env; set +a
    export DATABASE_URL=$(railway run --service db printenv DATABASE_PUBLIC_URL)
    python -m scripts.seed_missing_jurisdictions
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.jurisdiction import Jurisdiction
from app.models.tax_category import TaxCategory
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule

RESEARCH_DIR = Path(__file__).parent / "data" / "research"
CREATED_BY = "ai_research_2026-04-21"

# The agent's output_schema.py advertises some category codes (city_tax_flat, bed_tax, etc.)
# that don't exist in our seeded TaxCategory taxonomy. Normalize to the closest existing
# code before DB lookup. Keys are what the agent returns; values are the actual DB codes.
CATEGORY_CODE_ALIASES = {
    "city_tax_flat": "municipal_flat",
    "city_tax_pct": "municipal_pct",
    "bed_tax": "occ_flat_person_night",   # bed/pillow taxes are per-person-per-night
    "occ_flat": "occ_flat_night",         # default to per-night (could be per-person — reviewer can override)
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] seed: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed")


def _parse_date(value: Any) -> date | None:
    """Accept ISO date string or None; return date or None."""
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        logger.warning("Could not parse date: %r", value)
        return None


async def _lookup_jurisdiction(db: AsyncSession, code: str) -> Jurisdiction | None:
    result = await db.execute(
        select(Jurisdiction).where(Jurisdiction.code == code)
    )
    return result.scalar_one_or_none()


async def _lookup_category(db: AsyncSession, code: str) -> TaxCategory | None:
    result = await db.execute(select(TaxCategory).where(TaxCategory.code == code))
    return result.scalar_one_or_none()


async def _find_existing_rate(
    db: AsyncSession,
    jurisdiction_id: int,
    tax_category_id: int,
    effective_start: date,
) -> TaxRate | None:
    """Idempotency check for draft rates keyed on (jurisdiction, category, effective, created_by)."""
    result = await db.execute(
        select(TaxRate).where(
            TaxRate.jurisdiction_id == jurisdiction_id,
            TaxRate.tax_category_id == tax_category_id,
            TaxRate.effective_start == effective_start,
            TaxRate.created_by == CREATED_BY,
        )
    )
    return result.scalar_one_or_none()


async def _find_existing_rule(
    db: AsyncSession,
    tax_rate_id: int | None,
    jurisdiction_id: int,
    name: str,
) -> TaxRule | None:
    """Idempotency check for draft rules keyed on (rate, name, created_by)."""
    result = await db.execute(
        select(TaxRule).where(
            TaxRule.tax_rate_id == tax_rate_id,
            TaxRule.jurisdiction_id == jurisdiction_id,
            TaxRule.name == name,
            TaxRule.created_by == CREATED_BY,
        )
    )
    return result.scalar_one_or_none()


def _should_skip_rate(rate: dict, code: str) -> str | None:
    """Return skip reason or None if rate should be seeded."""
    if rate.get("rejected"):
        return "marked rejected in review"
    if rate.get("change_type") not in ("new", "changed"):
        return f"change_type={rate.get('change_type')}"
    if not rate.get("tax_category_code"):
        return "missing tax_category_code"
    if not rate.get("effective_start"):
        return "missing effective_start"
    if rate.get("rate_type") in ("percentage", "flat") and rate.get("rate_value") is None:
        return f"{rate['rate_type']} rate has no rate_value"
    if rate.get("rate_type") == "tiered" and not rate.get("tiers"):
        return "tiered rate has no tiers"
    return None


def _should_skip_rule(rule: dict) -> str | None:
    if rule.get("rejected"):
        return "marked rejected in review"
    if rule.get("change_type") not in ("new", "changed"):
        return f"change_type={rule.get('change_type')}"
    if not rule.get("name"):
        return "missing name"
    if not rule.get("effective_start"):
        return "missing effective_start"
    return None


def _build_rate_kwargs(
    rate: dict,
    jurisdiction_id: int,
    tax_category_id: int,
    reviewed_by: str,
) -> dict:
    """Translate AIExtractedRate dict → TaxRate kwargs."""
    rate_value = rate.get("rate_value")
    # AI reports 5.5 for 5.5%. Our DB stores percentages as fractions (0.055).
    # Convert for percentage types.
    if rate.get("rate_type") == "percentage" and rate_value is not None:
        rate_value = float(rate_value) / 100.0

    return {
        "jurisdiction_id": jurisdiction_id,
        "tax_category_id": tax_category_id,
        "rate_type": rate["rate_type"],
        "rate_value": rate_value,
        "currency_code": rate.get("currency_code"),
        "tiers": rate.get("tiers"),
        "tier_type": rate.get("tier_type"),
        "calculation_order": rate.get("calculation_order") or 100,
        "base_includes": ["base_amount"],
        "effective_start": _parse_date(rate["effective_start"]),
        "effective_end": _parse_date(rate.get("effective_end")),
        "enacted_date": _parse_date(rate.get("enacted_date")),
        "legal_reference": rate.get("legal_reference"),
        "legal_uri": rate.get("legal_uri"),
        "source_url": rate.get("source_url"),
        "authority_name": rate.get("authority_name"),
        "status": "draft",
        "created_by": CREATED_BY,
        "reviewed_by": reviewed_by,
        "review_notes": _rate_review_notes(rate),
    }


def _rate_review_notes(rate: dict) -> str:
    """Capture source quote and agent confidence for reviewer context."""
    pieces = []
    if rate.get("confidence") is not None:
        pieces.append(f"agent_confidence={rate['confidence']}")
    if rate.get("source_quote"):
        q = rate["source_quote"][:400]
        pieces.append(f"source_quote: {q}")
    return " | ".join(pieces) if pieces else None


def _build_rule_kwargs(
    rule: dict,
    jurisdiction_id: int,
    tax_rate_id: int | None,
    reviewed_by: str,
) -> dict:
    return {
        "tax_rate_id": tax_rate_id,
        "jurisdiction_id": jurisdiction_id,
        "rule_type": rule["rule_type"],
        "priority": rule.get("priority", 0),
        "name": rule["name"],
        "description": rule.get("description"),
        "conditions": rule.get("conditions") or {},
        "action": rule.get("action") or {},
        "effective_start": _parse_date(rule["effective_start"]),
        "effective_end": _parse_date(rule.get("effective_end")),
        "enacted_date": _parse_date(rule.get("enacted_date")),
        "legal_reference": rule.get("legal_reference"),
        "authority_name": rule.get("authority_name"),
        "status": "draft",
        "created_by": CREATED_BY,
        "reviewed_by": reviewed_by,
    }


async def _match_rate_for_rule(
    db: AsyncSession,
    rule: dict,
    jurisdiction_id: int,
    seeded_rates: dict[str, TaxRate],
) -> TaxRate | None:
    """
    Match a rule to its owning rate. Prefer explicit link via `rate_ref` (tax_category_code)
    if the user added one during review; otherwise match by tax_category_code if unambiguous;
    otherwise the rule is jurisdiction-wide (tax_rate_id=null).
    """
    ref = rule.get("rate_ref")  # optional reviewer-added field: e.g. "vat_standard"
    if ref:
        if ref in seeded_rates:
            return seeded_rates[ref]
        # Try DB lookup by category code
        cat = await _lookup_category(db, ref)
        if cat:
            result = await db.execute(
                select(TaxRate).where(
                    TaxRate.jurisdiction_id == jurisdiction_id,
                    TaxRate.tax_category_id == cat.id,
                    TaxRate.created_by == CREATED_BY,
                )
            )
            return result.scalars().first()
    # No explicit ref: leave tax_rate_id null (rule applies jurisdiction-wide)
    return None


async def seed_from_file(
    db: AsyncSession,
    json_path: Path,
    dry_run: bool,
    stats: dict,
) -> None:
    code = json_path.stem
    try:
        payload = json.loads(json_path.read_text())
    except Exception as e:
        logger.error("[%s] failed to parse JSON: %s", code, e)
        stats["files_parse_error"] += 1
        return

    meta = payload.get("_meta", {})
    reviewed_by = meta.get("reviewed_by")
    if not reviewed_by:
        logger.info("[%s] SKIP — _meta.reviewed_by not set", code)
        stats["files_unreviewed"] += 1
        return

    jurisdiction_code = payload.get("jurisdiction_code") or meta.get("jurisdiction_code")
    if not jurisdiction_code:
        logger.error("[%s] no jurisdiction_code in payload", code)
        stats["files_parse_error"] += 1
        return

    jurisdiction = await _lookup_jurisdiction(db, jurisdiction_code)
    if not jurisdiction:
        logger.error("[%s] jurisdiction %s not found in DB", code, jurisdiction_code)
        stats["files_no_jurisdiction"] += 1
        return

    stats["files_reviewed"] += 1
    logger.info("[%s] processing (reviewed_by=%s)", code, reviewed_by)

    # ── Rates ──────────────────────────────────────────────
    seeded_rates: dict[str, TaxRate] = {}  # keyed by tax_category_code for rule linkage
    for idx, rate in enumerate(payload.get("rates") or []):
        skip_reason = _should_skip_rate(rate, code)
        if skip_reason:
            logger.info("[%s]   rate[%d] SKIP — %s", code, idx, skip_reason)
            stats["rates_skipped"] += 1
            continue

        raw_code = rate["tax_category_code"]
        resolved_code = CATEGORY_CODE_ALIASES.get(raw_code, raw_code)
        category = await _lookup_category(db, resolved_code)
        if not category:
            logger.warning(
                "[%s]   rate[%d] SKIP — unknown tax_category_code=%s%s",
                code, idx, raw_code,
                f" (tried alias → {resolved_code})" if resolved_code != raw_code else "",
            )
            stats["rates_skipped"] += 1
            continue
        if resolved_code != raw_code:
            logger.info(
                "[%s]   rate[%d] category alias: %s → %s",
                code, idx, raw_code, resolved_code,
            )

        effective_start = _parse_date(rate["effective_start"])
        existing = await _find_existing_rate(
            db, jurisdiction.id, category.id, effective_start,
        )
        if existing:
            logger.info(
                "[%s]   rate[%d] exists — %s (id=%d) — reusing for rule linkage",
                code, idx, category.code, existing.id,
            )
            seeded_rates[category.code] = existing
            stats["rates_existing"] += 1
            continue

        kwargs = _build_rate_kwargs(rate, jurisdiction.id, category.id, reviewed_by)
        if dry_run:
            logger.info(
                "[%s]   rate[%d] WOULD-INSERT — %s %s %s",
                code, idx, category.code, rate["rate_type"],
                rate.get("rate_value") if rate.get("rate_type") != "tiered" else f"tiers={len(rate.get('tiers') or [])}",
            )
            stats["rates_would_insert"] += 1
        else:
            new_rate = TaxRate(**kwargs)
            db.add(new_rate)
            await db.flush()
            seeded_rates[category.code] = new_rate
            logger.info(
                "[%s]   rate[%d] INSERTED — %s (id=%d)",
                code, idx, category.code, new_rate.id,
            )
            stats["rates_inserted"] += 1

    # ── Rules ──────────────────────────────────────────────
    for idx, rule in enumerate(payload.get("rules") or []):
        skip_reason = _should_skip_rule(rule)
        if skip_reason:
            logger.info("[%s]   rule[%d] SKIP — %s", code, idx, skip_reason)
            stats["rules_skipped"] += 1
            continue

        owning_rate = await _match_rate_for_rule(db, rule, jurisdiction.id, seeded_rates)
        tax_rate_id = owning_rate.id if owning_rate else None

        existing = await _find_existing_rule(
            db, tax_rate_id, jurisdiction.id, rule["name"],
        )
        if existing:
            logger.info(
                "[%s]   rule[%d] exists — %s (id=%d)",
                code, idx, rule["name"], existing.id,
            )
            stats["rules_existing"] += 1
            continue

        kwargs = _build_rule_kwargs(rule, jurisdiction.id, tax_rate_id, reviewed_by)
        if dry_run:
            logger.info(
                "[%s]   rule[%d] WOULD-INSERT — %s (type=%s, rate_link=%s)",
                code, idx, rule["name"], rule["rule_type"],
                f"rate_id={tax_rate_id}" if tax_rate_id else "jurisdiction-wide",
            )
            stats["rules_would_insert"] += 1
        else:
            new_rule = TaxRule(**kwargs)
            db.add(new_rule)
            await db.flush()
            logger.info(
                "[%s]   rule[%d] INSERTED — %s (id=%d)",
                code, idx, rule["name"], new_rule.id,
            )
            stats["rules_inserted"] += 1


async def main_async(args) -> int:
    research_dir: Path = args.research_dir
    if not research_dir.is_dir():
        logger.error("Research directory does not exist: %s", research_dir)
        return 2

    json_files = sorted(
        p for p in research_dir.glob("*.json") if not p.name.startswith("_")
    )
    if not json_files:
        logger.error("No research JSON files found in %s", research_dir)
        return 2

    logger.info(
        "Found %d research file(s) in %s (dry_run=%s)",
        len(json_files), research_dir, args.dry_run,
    )

    stats = {k: 0 for k in (
        "files_reviewed", "files_unreviewed", "files_parse_error", "files_no_jurisdiction",
        "rates_inserted", "rates_existing", "rates_skipped", "rates_would_insert",
        "rules_inserted", "rules_existing", "rules_skipped", "rules_would_insert",
    )}

    async with async_session_factory() as db:
        try:
            for json_path in json_files:
                await seed_from_file(db, json_path, args.dry_run, stats)
            if not args.dry_run:
                await db.commit()
        except Exception:
            await db.rollback()
            raise

    logger.info("=" * 60)
    for k, v in stats.items():
        logger.info("  %-28s %d", k, v)
    logger.info("=" * 60)

    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument(
        "--research-dir",
        type=Path,
        default=RESEARCH_DIR,
        help=f"Directory of research JSONs (default: {RESEARCH_DIR})",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be seeded without touching the DB",
    )
    return p.parse_args()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
