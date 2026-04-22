"""
Research accommodation tax data for jurisdictions with no active tax rates.

Phase 1 of the 47-missing-jurisdictions initiative (plan: binary-rolling-stonebraker.md).
Runs TaxMonitoringAgent against each target jurisdiction, writes the raw agent output
to scripts/data/research/{code}.json and a run summary to _index.json.

This script is read-only: it loads jurisdictions from the DB and calls the Anthropic
API. It does NOT insert rates — that's done later by a separate seed script after
human review of the JSON outputs.

Usage:
    # Local dry-run against docker-compose DB
    python -m scripts.research_missing_jurisdictions --codes TH-10-BKK,RU-MOW,UZ-TAS

    # Full prod run (37 cities) against prod DB via public proxy
    DATABASE_URL_SYNC="$(railway run --service db printenv DATABASE_PUBLIC_URL)" \\
    DATABASE_URL="postgresql+asyncpg://${...}" \\
    python -m scripts.research_missing_jurisdictions --all

    # Useful flags
    --codes CODE1,CODE2      comma-separated jurisdiction codes (overrides --all)
    --all                    run against all 37 city-level targets
    --limit N                only process first N (for quick smoke-tests)
    --out-dir PATH           override output directory (default: scripts/data/research)
    --skip-existing          skip jurisdictions that already have a JSON file
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# Raise search and turn limits for this research batch. Set BEFORE importing app.config
# so pydantic-settings picks them up. User can override via explicit env var.
os.environ.setdefault("ANTHROPIC_MAX_SEARCH_USES", "20")
os.environ.setdefault("ANTHROPIC_MAX_AGENT_TURNS", "30")

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402
from app.models.jurisdiction import Jurisdiction  # noqa: E402
from app.services.ai_agent_service import TaxMonitoringAgent  # noqa: E402


# 47 jurisdictions audited as missing active tax rates on 2026-04-21.
# Per plan scope, only the 37 city-level ones are in scope. The 10 state/prefecture
# parents are listed commented-out for traceability but NOT researched — their child
# cities (where rates typically live) are covered instead.
MISSING_CITY_JURISDICTIONS = [
    "AE-RK-RAK",  # RAK City (UAE, Ras Al Khaimah emirate)
    "AM-YER",     # Yerevan (Armenia)
    "AZ-BAK",     # Baku (Azerbaijan)
    "BW-GB",      # Gaborone (Botswana)
    "BW-MN",      # Maun (Botswana)
    "BZ-BZ-BZE",  # Belize City (child of BZ-BZ, which is the state parent)
    "BZ-SC",      # San Pedro (Belize)
    "CI-ABJ",     # Abidjan (Côte d'Ivoire)
    "CM-DLA",     # Douala (Cameroon)
    "CV-RAI",     # Praia (Cape Verde)
    "CV-SAL",     # Sal Island (Cape Verde)
    "DZ-ALG",     # Algiers (Algeria)
    "GT-ANT",     # Antigua Guatemala
    "GT-GUA",     # Guatemala City
    "KG-FRU",     # Bishkek (Kyrgyzstan)
    "KZ-ALA",     # Almaty (Kazakhstan)
    "KZ-NQZ",     # Astana (Kazakhstan)
    "MG-TNR",     # Antananarivo (Madagascar)
    "MN-UBN",     # Ulaanbaatar (Mongolia)
    "MP-SPN",     # Saipan (Northern Mariana Islands)
    "MZ-MPM",     # Maputo (Mozambique)
    "NA-ER",      # Swakopmund (Namibia)
    "NA-KH",      # Windhoek (Namibia)
    "PF-PPT",     # Tahiti/Papeete (French Polynesia)
    "RU-MOW",     # Moscow (Russia)
    "RU-SPE",     # St. Petersburg (Russia)
    "SA-01-RUH",  # Riyadh City (child of SA-01 province)
    "TH-10-BKK",  # Bangkok (Thailand)
    "TJ-DYU",     # Dushanbe (Tajikistan)
    "UG-KLA",     # Kampala (Uganda)
    "UZ-BHK",     # Bukhara (Uzbekistan)
    "UZ-SKD",     # Samarkand (Uzbekistan)
    "UZ-TAS",     # Tashkent (Uzbekistan)
    "VI-STT",     # St. Thomas (US Virgin Islands)
    "VI-STX",     # St. Croix (US Virgin Islands)
    "ZM-LS",      # Lusaka (Zambia)
    "ZM-LVI",     # Livingstone (Zambia)
]
# Excluded state/prefecture parents (out of plan scope): BZ-BZ, FR-IDF, JP-13, JP-17,
# JP-22, JP-26, JP-42, MX-CMX, SA-01, US-AK. Excluded missing country: none listed
# (the 1 missing country is also out of scope per plan).

DEFAULT_OUT_DIR = Path(__file__).parent / "data" / "research"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("research")
# Tame noisy loggers from dependencies.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def _load_jurisdiction(db, code: str) -> Jurisdiction | None:
    """Load a Jurisdiction by code, eagerly pulling monitored_sources."""
    result = await db.execute(
        select(Jurisdiction)
        .where(Jurisdiction.code == code)
        .options(selectinload(Jurisdiction.monitored_sources))
    )
    return result.scalar_one_or_none()


def _collect_monitored_urls(jurisdiction: Jurisdiction) -> list[str]:
    """Extract active monitored source URLs for the agent to prioritize."""
    return [
        src.url
        for src in (jurisdiction.monitored_sources or [])
        if src.status == "active"
    ]


def _write_index(out_dir: Path, entries: list[dict], run_started_at: str) -> None:
    """Write or update _index.json summarizing the run."""
    index_path = out_dir / "_index.json"
    index = {
        "run_started_at": run_started_at,
        "run_completed_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.anthropic_model,
        "max_search_uses": settings.anthropic_max_search_uses,
        "max_agent_turns": settings.anthropic_max_agent_turns,
        "entries": entries,
    }
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True))
    logger.info("Wrote run index: %s", index_path)


async def research_one(
    agent: TaxMonitoringAgent,
    db,
    code: str,
    out_dir: Path,
) -> dict:
    """Run the agent against one jurisdiction, write its JSON, return index entry."""
    entry = {"code": code, "status": "pending", "started_at": datetime.now(timezone.utc).isoformat()}
    started = time.monotonic()

    jurisdiction = await _load_jurisdiction(db, code)
    if not jurisdiction:
        entry.update(status="skipped_not_found", error="Jurisdiction code not found in DB")
        logger.warning("[%s] skipped — not found in DB", code)
        return entry

    monitored_urls = _collect_monitored_urls(jurisdiction)
    entry["monitored_url_count"] = len(monitored_urls)
    logger.info(
        "[%s] %s (%s) — starting research (priority URLs: %d)",
        code, jurisdiction.name, jurisdiction.jurisdiction_type, len(monitored_urls),
    )

    try:
        result = await agent.research_jurisdiction(
            jurisdiction=jurisdiction,
            current_rates=[],
            current_rules=[],
            monitored_urls=monitored_urls,
        )
    except Exception as e:  # noqa: BLE001
        elapsed = time.monotonic() - started
        logger.error(
            "[%s] research FAILED after %.1fs: %s\n%s",
            code, elapsed, e, traceback.format_exc(),
        )
        entry.update(
            status="failed",
            error=f"{type(e).__name__}: {e}",
            elapsed_seconds=round(elapsed, 1),
        )
        return entry

    elapsed = time.monotonic() - started
    out_path = out_dir / f"{code}.json"
    payload = result.model_dump(mode="json")
    payload["_meta"] = {
        "jurisdiction_id": jurisdiction.id,
        "jurisdiction_code": jurisdiction.code,
        "jurisdiction_name": jurisdiction.name,
        "jurisdiction_type": jurisdiction.jurisdiction_type,
        "country_code": jurisdiction.country_code,
        "currency_code": jurisdiction.currency_code,
        "monitored_urls": monitored_urls,
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "model": settings.anthropic_model,
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    logger.info(
        "[%s] DONE in %.1fs: %d rates, %d rules, confidence=%.2f → %s",
        code, elapsed, len(result.rates), len(result.rules),
        result.overall_confidence, out_path.name,
    )
    entry.update(
        status="completed",
        elapsed_seconds=round(elapsed, 1),
        rates_found=len(result.rates),
        rules_found=len(result.rules),
        overall_confidence=result.overall_confidence,
        sources_checked=len(result.sources_checked),
        output_file=str(out_path.relative_to(out_dir.parent.parent.parent)),
    )
    return entry


async def run_research(codes: list[str], out_dir: Path, skip_existing: bool) -> int:
    """Drive the per-jurisdiction research loop. Returns process exit code."""
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY is not set; cannot run research.")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    run_started_at = datetime.now(timezone.utc).isoformat()
    agent = TaxMonitoringAgent()
    entries: list[dict] = []

    async with async_session_factory() as db:
        for idx, code in enumerate(codes, start=1):
            banner = f"[{idx}/{len(codes)}] {code}"
            logger.info("%s %s", "=" * 10, banner)

            if skip_existing and (out_dir / f"{code}.json").exists():
                logger.info("[%s] skipping — output JSON already exists", code)
                entries.append({"code": code, "status": "skipped_existing"})
                continue

            entry = await research_one(agent, db, code, out_dir)
            entries.append(entry)

            # Write index incrementally so partial runs are recoverable.
            _write_index(out_dir, entries, run_started_at)

            # Small pause between jurisdictions to be polite to the API.
            if idx < len(codes):
                await asyncio.sleep(2)

    ok = sum(1 for e in entries if e["status"] == "completed")
    skipped = sum(1 for e in entries if e["status"].startswith("skipped"))
    failed = sum(1 for e in entries if e["status"] == "failed")
    logger.info(
        "Run complete: %d completed, %d skipped, %d failed (total %d)",
        ok, skipped, failed, len(entries),
    )
    return 0 if failed == 0 else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--codes",
        help="Comma-separated jurisdiction codes to research",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Research all 37 city-level targets",
    )
    p.add_argument("--limit", type=int, help="Only process first N targets")
    p.add_argument(
        "--out-dir",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUT_DIR})",
    )
    p.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip jurisdictions that already have an output JSON",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        codes = list(MISSING_CITY_JURISDICTIONS)

    if args.limit:
        codes = codes[: args.limit]

    if not codes:
        logger.error("No jurisdiction codes to process")
        return 2

    logger.info("Targets: %d jurisdiction(s): %s", len(codes), ", ".join(codes))
    logger.info(
        "Config: model=%s, max_search_uses=%d, max_turns=%d, out_dir=%s",
        settings.anthropic_model,
        settings.anthropic_max_search_uses,
        settings.anthropic_max_agent_turns,
        args.out_dir,
    )

    return asyncio.run(run_research(codes, args.out_dir, args.skip_existing))


if __name__ == "__main__":
    sys.exit(main())
