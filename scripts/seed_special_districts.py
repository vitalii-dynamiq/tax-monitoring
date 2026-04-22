"""
Seed sub-city / sub-state special tax districts as new jurisdictions + draft rates/rules.

Phase 4 of the special-districts enrichment (plan: binary-rolling-stonebraker.md).
Reads approved research under scripts/data/research_districts/*.json. For each approved
district:
  1. Creates the district as a new Jurisdiction row (jurisdiction_type='district',
     status='active', created_by='ai_research_districts_2026-04-22').
  2. Attaches its rates/rules as status='draft'.
If the parent jurisdiction is missing AND `_meta.create_missing_parent: true` is set
by the reviewer, the seeder also creates a placeholder parent (city or state) before
attaching the district.

## Review gating (same as seed_missing_jurisdictions.py)

A file must have `_meta.reviewed_by` set. Unreviewed files are skipped.

Per-entry rejections:
- District-level: `"rejected": true` on the district object → the entire district
  (jurisdiction + rates + rules) is skipped.
- Rate-level: `"rejected": true` on a rate → skipped, district still created if any
  non-rejected rate/rule survives.
- Rule-level: same.

## Usage

    # Dry-run against prod
    export DATABASE_URL=$(railway run --service db printenv DATABASE_PUBLIC_URL)
    python -m scripts.seed_special_districts --dry-run

    # Real seed against prod
    python -m scripts.seed_special_districts
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
from sqlalchemy.orm import selectinload

from app.db.session import async_session_factory
from app.models.jurisdiction import Jurisdiction
from app.models.tax_category import TaxCategory
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule

# Reuse helpers from the prior enrichment — same mapping + same category-alias tweak
from scripts.seed_missing_jurisdictions import (
    CATEGORY_CODE_ALIASES,
    _build_rate_kwargs,
    _build_rule_kwargs,
    _find_existing_rate,
    _find_existing_rule,
    _lookup_category,
    _parse_date,
    _rate_review_notes,
    _should_skip_rate,
    _should_skip_rule,
)

RESEARCH_DIR = Path(__file__).parent / "data" / "research_districts"
CREATED_BY = "ai_research_districts_2026-04-22"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] seed_districts: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("seed_districts")


async def _lookup_jurisdiction(db: AsyncSession, code: str) -> Jurisdiction | None:
    result = await db.execute(
        select(Jurisdiction).where(Jurisdiction.code == code)
    )
    return result.scalar_one_or_none()


async def _load_state_parent(db: AsyncSession, parent_code: str) -> Jurisdiction | None:
    """For a missing city like US-CA-SCL, find the state US-CA to use as its parent."""
    # Parent code format: COUNTRY-STATE-CITY → state is the second part
    parts = parent_code.split("-")
    if len(parts) < 2:
        return None
    state_code = "-".join(parts[:2])  # e.g. "US-CA"
    return await _lookup_jurisdiction(db, state_code)


def _rate_kwargs_for_district(
    rate: dict,
    jurisdiction_id: int,
    tax_category_id: int,
    reviewed_by: str,
) -> dict:
    """Like _build_rate_kwargs but overrides created_by for this enrichment."""
    kwargs = _build_rate_kwargs(rate, jurisdiction_id, tax_category_id, reviewed_by)
    kwargs["created_by"] = CREATED_BY
    return kwargs


def _rule_kwargs_for_district(
    rule: dict,
    jurisdiction_id: int,
    tax_rate_id: int | None,
    reviewed_by: str,
) -> dict:
    kwargs = _build_rule_kwargs(rule, jurisdiction_id, tax_rate_id, reviewed_by)
    kwargs["created_by"] = CREATED_BY
    return kwargs


async def _find_existing_rate_for_district(
    db: AsyncSession,
    jurisdiction_id: int,
    tax_category_id: int,
    effective_start: date,
) -> TaxRate | None:
    """Version of _find_existing_rate that uses OUR CREATED_BY tag."""
    result = await db.execute(
        select(TaxRate).where(
            TaxRate.jurisdiction_id == jurisdiction_id,
            TaxRate.tax_category_id == tax_category_id,
            TaxRate.effective_start == effective_start,
            TaxRate.created_by == CREATED_BY,
        )
    )
    return result.scalar_one_or_none()


async def _find_existing_rule_for_district(
    db: AsyncSession,
    tax_rate_id: int | None,
    jurisdiction_id: int,
    name: str,
) -> TaxRule | None:
    result = await db.execute(
        select(TaxRule).where(
            TaxRule.tax_rate_id == tax_rate_id,
            TaxRule.jurisdiction_id == jurisdiction_id,
            TaxRule.name == name,
            TaxRule.created_by == CREATED_BY,
        )
    )
    return result.scalar_one_or_none()


async def _ensure_parent(
    db: AsyncSession,
    parent_code: str,
    meta: dict,
    dry_run: bool,
    stats: dict,
) -> Jurisdiction | None:
    """Lookup the parent; optionally create it if missing and reviewer opted in."""
    parent = await _lookup_jurisdiction(db, parent_code)
    if parent is not None:
        return parent

    if not meta.get("create_missing_parent"):
        logger.error(
            "[%s] parent NOT in DB and _meta.create_missing_parent is not set — skipping file",
            parent_code,
        )
        stats["files_missing_parent"] += 1
        return None

    # Need a name to create the parent
    name = meta.get("parent_db_name") or meta.get("parent_name_hint")
    if not name:
        logger.error("[%s] cannot create parent — no name in _meta", parent_code)
        stats["files_missing_parent"] += 1
        return None

    # Infer type + state grandparent
    # Parent codes like US-CA-XXX → city (state grandparent US-CA)
    # Parent codes like US-ID → state (country US)
    parts = parent_code.split("-")
    if len(parts) == 3:
        jtype = "city"
        grand = await _lookup_state_parent(db, parent_code)
        if not grand:
            logger.error("[%s] cannot find state grandparent for new city", parent_code)
            stats["files_missing_parent"] += 1
            return None
        path = f"{grand.path}.{parts[2]}"
        country_code = grand.country_code
        subdivision_code = grand.subdivision_code
        currency_code = grand.currency_code
        timezone = grand.timezone
        parent_id = grand.id
    elif len(parts) == 2:
        jtype = "state"
        country_grand = await _lookup_jurisdiction(db, parts[0])
        if not country_grand:
            logger.error("[%s] cannot find country grandparent", parent_code)
            stats["files_missing_parent"] += 1
            return None
        path = f"{country_grand.path}.{parts[1]}"
        country_code = country_grand.country_code
        subdivision_code = parent_code
        currency_code = country_grand.currency_code
        timezone = country_grand.timezone
        parent_id = country_grand.id
    else:
        logger.error("[%s] cannot infer parent type from code", parent_code)
        stats["files_missing_parent"] += 1
        return None

    if dry_run:
        logger.info(
            "[%s] WOULD-CREATE parent: type=%s, path=%s, name=%r",
            parent_code, jtype, path, name,
        )
        stats["parents_would_create"] += 1
        # Return a synthetic object so downstream can reference an id — but dry-run
        # won't actually create rates/rules that reference it, so using a placeholder
        # is fine for counting.
        return None

    new_parent = Jurisdiction(
        code=parent_code,
        name=name,
        jurisdiction_type=jtype,
        path=path,
        parent_id=parent_id,
        country_code=country_code,
        subdivision_code=subdivision_code,
        timezone=timezone,
        currency_code=currency_code,
        status="active",
        created_by=CREATED_BY,
    )
    db.add(new_parent)
    await db.flush()
    logger.info("[%s] CREATED parent (id=%d, type=%s, path=%s)",
                parent_code, new_parent.id, jtype, new_parent.path)
    stats["parents_created"] += 1
    return new_parent


async def _lookup_state_parent(db, parent_code: str) -> Jurisdiction | None:
    parts = parent_code.split("-")
    if len(parts) < 2:
        return None
    state_code = "-".join(parts[:2])
    return await _lookup_jurisdiction(db, state_code)


async def _upsert_district(
    db: AsyncSession,
    parent: Jurisdiction,
    district: dict,
    reviewed_by: str,
    dry_run: bool,
    stats: dict,
) -> Jurisdiction | None:
    code = district.get("suggested_code")
    path_suffix = district.get("path_suffix")
    name = district.get("name")
    if not (code and path_suffix and name):
        logger.warning("  district SKIP — missing code/path_suffix/name: %s", district.get("name"))
        stats["districts_invalid"] += 1
        return None

    existing = await _lookup_jurisdiction(db, code)
    if existing:
        logger.info("  district exists — %s (id=%d) — reusing for rate/rule attach",
                    code, existing.id)
        stats["districts_existing"] += 1
        return existing

    new_path = f"{parent.path}.{path_suffix}"
    if dry_run:
        logger.info(
            "  district WOULD-CREATE: %s name=%r path=%s parent=%s",
            code, name, new_path, parent.code,
        )
        stats["districts_would_create"] += 1
        return None

    new_district = Jurisdiction(
        code=code,
        name=name,
        jurisdiction_type="district",
        path=new_path,
        parent_id=parent.id,
        country_code=parent.country_code,
        subdivision_code=parent.subdivision_code,
        timezone=parent.timezone,
        currency_code=parent.currency_code,
        status="active",
        created_by=CREATED_BY,
        metadata_={
            "geographic_scope": district.get("geographic_scope"),
            "authority_name": district.get("authority_name"),
            "enabling_statute": district.get("enabling_statute"),
            "source_quote": (district.get("source_quote") or "")[:800],
            "source_url": district.get("source_url"),
            "agent_confidence": district.get("confidence"),
        },
    )
    db.add(new_district)
    await db.flush()
    logger.info("  district CREATED: %s (id=%d, path=%s)", code, new_district.id, new_path)
    stats["districts_created"] += 1
    return new_district


def _should_skip_rate_for_district(rate: dict) -> str | None:
    """District-context skip check: we're seeding fresh, so allow change_type=unchanged.
    Only reject when rejected-in-review, removed, or missing required fields."""
    if rate.get("rejected"):
        return "marked rejected in review"
    if rate.get("change_type") == "removed":
        return "change_type=removed"
    if not rate.get("tax_category_code"):
        return "missing tax_category_code"
    if not rate.get("effective_start"):
        return "missing effective_start"
    if rate.get("rate_type") in ("percentage", "flat") and rate.get("rate_value") is None:
        return f"{rate['rate_type']} rate has no rate_value"
    if rate.get("rate_type") == "tiered" and not rate.get("tiers"):
        return "tiered rate has no tiers"
    return None


def _should_skip_rule_for_district(rule: dict) -> str | None:
    if rule.get("rejected"):
        return "marked rejected in review"
    if rule.get("change_type") == "removed":
        return "change_type=removed"
    if not rule.get("name"):
        return "missing name"
    if not rule.get("effective_start"):
        return "missing effective_start"
    return None


async def _seed_rates_and_rules(
    db: AsyncSession,
    district: Jurisdiction | None,
    payload: dict,  # the district dict
    parent_code_for_log: str,
    reviewed_by: str,
    dry_run: bool,
    stats: dict,
) -> None:
    if district is None and not dry_run:
        logger.warning("  no district to attach to, skipping rates/rules")
        return

    # Fake district id for dry-run: use 0 to avoid DB writes; we just count
    jurisdiction_id = district.id if district else 0

    seeded_rates: dict[str, TaxRate] = {}

    for idx, rate in enumerate(payload.get("rates") or []):
        skip_reason = _should_skip_rate_for_district(rate)
        if skip_reason:
            logger.info("    rate[%d] SKIP — %s", idx, skip_reason)
            stats["rates_skipped"] += 1
            continue

        raw_code = rate["tax_category_code"]
        resolved = CATEGORY_CODE_ALIASES.get(raw_code, raw_code)
        category = await _lookup_category(db, resolved)
        if not category:
            logger.warning(
                "    rate[%d] SKIP — unknown tax_category_code=%s%s",
                idx, raw_code,
                f" (alias→{resolved})" if resolved != raw_code else "",
            )
            stats["rates_skipped"] += 1
            continue

        if not dry_run:
            eff = _parse_date(rate["effective_start"])
            existing = await _find_existing_rate_for_district(
                db, district.id, category.id, eff,
            )
            if existing:
                logger.info("    rate[%d] exists — %s (id=%d)", idx, category.code, existing.id)
                seeded_rates[category.code] = existing
                stats["rates_existing"] += 1
                continue

            kwargs = _rate_kwargs_for_district(rate, district.id, category.id, reviewed_by)
            new_rate = TaxRate(**kwargs)
            db.add(new_rate)
            await db.flush()
            seeded_rates[category.code] = new_rate
            logger.info("    rate[%d] INSERTED — %s (id=%d)", idx, category.code, new_rate.id)
            stats["rates_inserted"] += 1
        else:
            label = f"{rate.get('rate_value')}" if rate.get("rate_type") != "tiered" \
                else f"tiers={len(rate.get('tiers') or [])}"
            logger.info(
                "    rate[%d] WOULD-INSERT — %s %s %s",
                idx, category.code, rate["rate_type"], label,
            )
            stats["rates_would_insert"] += 1

    for idx, rule in enumerate(payload.get("rules") or []):
        skip_reason = _should_skip_rule_for_district(rule)
        if skip_reason:
            logger.info("    rule[%d] SKIP — %s", idx, skip_reason)
            stats["rules_skipped"] += 1
            continue

        ref = rule.get("rate_ref")
        tax_rate_id = None
        if ref and ref in seeded_rates:
            tax_rate_id = seeded_rates[ref].id

        if not dry_run:
            existing = await _find_existing_rule_for_district(
                db, tax_rate_id, district.id, rule["name"],
            )
            if existing:
                logger.info("    rule[%d] exists — %s (id=%d)", idx, rule["name"][:60], existing.id)
                stats["rules_existing"] += 1
                continue

            kwargs = _rule_kwargs_for_district(rule, district.id, tax_rate_id, reviewed_by)
            new_rule = TaxRule(**kwargs)
            db.add(new_rule)
            await db.flush()
            logger.info("    rule[%d] INSERTED — %s (id=%d)", idx, rule["name"][:60], new_rule.id)
            stats["rules_inserted"] += 1
        else:
            link = f"rate={tax_rate_id}" if tax_rate_id else "jurisdiction-wide"
            logger.info(
                "    rule[%d] WOULD-INSERT — %s (type=%s, %s)",
                idx, rule["name"][:60], rule["rule_type"], link,
            )
            stats["rules_would_insert"] += 1


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
        logger.error("[%s] JSON parse error: %s", code, e)
        stats["files_parse_error"] += 1
        return

    meta = payload.get("_meta", {})
    reviewed_by = meta.get("reviewed_by")
    if not reviewed_by:
        logger.info("[%s] SKIP — _meta.reviewed_by not set", code)
        stats["files_unreviewed"] += 1
        return

    parent_code = payload.get("parent_code") or meta.get("parent_code")
    if not parent_code:
        logger.error("[%s] no parent_code in payload", code)
        stats["files_parse_error"] += 1
        return

    parent = await _ensure_parent(db, parent_code, meta, dry_run, stats)
    if parent is None and not (dry_run and meta.get("create_missing_parent")):
        return

    stats["files_reviewed"] += 1
    logger.info("[%s] processing (reviewed_by=%s)", code, reviewed_by)

    for d_idx, district in enumerate(payload.get("districts") or []):
        dname = district.get("name", f"district[{d_idx}]")
        if district.get("rejected"):
            logger.info("  district[%d] %r SKIP — rejected in review", d_idx, dname[:60])
            stats["districts_skipped"] += 1
            continue

        logger.info("  district[%d] %r (%s)", d_idx, dname[:60], district.get("suggested_code"))
        jurisdiction = await _upsert_district(db, parent, district, reviewed_by, dry_run, stats) if parent else None

        # Attach rates/rules (skip if dry-run couldn't resolve parent)
        if parent:
            await _seed_rates_and_rules(
                db, jurisdiction, district, parent_code, reviewed_by, dry_run, stats,
            )


async def main_async(args) -> int:
    research_dir: Path = args.research_dir
    if not research_dir.is_dir():
        logger.error("Research dir does not exist: %s", research_dir)
        return 2

    files = sorted(p for p in research_dir.glob("*.json") if not p.name.startswith("_"))
    if not files:
        logger.error("No research files found")
        return 2

    logger.info("Found %d file(s) in %s (dry_run=%s)", len(files), research_dir, args.dry_run)

    stats = {k: 0 for k in (
        "files_reviewed", "files_unreviewed", "files_parse_error", "files_missing_parent",
        "parents_created", "parents_would_create",
        "districts_created", "districts_existing", "districts_skipped", "districts_invalid",
        "districts_would_create",
        "rates_inserted", "rates_existing", "rates_skipped", "rates_would_insert",
        "rules_inserted", "rules_existing", "rules_skipped", "rules_would_insert",
    )}

    async with async_session_factory() as db:
        try:
            for f in files:
                await seed_from_file(db, f, args.dry_run, stats)
            if not args.dry_run:
                await db.commit()
        except Exception:
            await db.rollback()
            raise

    logger.info("=" * 64)
    for k, v in stats.items():
        logger.info("  %-32s %d", k, v)
    logger.info("=" * 64)
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    p.add_argument("--research-dir", type=Path, default=RESEARCH_DIR)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    return asyncio.run(main_async(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
