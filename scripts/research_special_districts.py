"""
Research special-purpose tax districts within US cities (and Idaho state).

Phase 2 of the special-districts enrichment (plan: binary-rolling-stonebraker.md).
For each of the 10 parent jurisdictions, runs a tailored Anthropic agent with the
district-discovery prompt and writes structured output to
`scripts/data/research_districts/{parent_code}.json`.

Unlike `research_missing_jurisdictions.py`, this one:
- Uses a different prompt (SYSTEM_PROMPT from prompts/special_districts.py)
- Handles parents that don't exist in the DB yet (stubs for Santa Clara + Arlington TX)
- Emits a different output schema (AIDistrictDiscoveryResult, not AIMonitoringResult)

Usage:
    python -m scripts.research_special_districts --codes US-CA-SDG
    python -m scripts.research_special_districts --all
    python -m scripts.research_special_districts --limit 2 --skip-existing
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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Raise search and turn budgets for this batch
os.environ.setdefault("ANTHROPIC_MAX_SEARCH_USES", "25")
os.environ.setdefault("ANTHROPIC_MAX_AGENT_TURNS", "30")

import anthropic  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.config import settings  # noqa: E402
from app.db.session import async_session_factory  # noqa: E402
from app.models.jurisdiction import Jurisdiction  # noqa: E402
from app.services.prompts.special_districts import (  # noqa: E402
    SYSTEM_PROMPT,
    AIDistrictDiscoveryResult,
    build_user_prompt,
)


@dataclass(frozen=True)
class ParentTarget:
    code: str
    name_hint: str
    state_hint: str | None
    country_hint: str = "United States"
    # Reviewer disambiguation note — flows into the research JSON for context
    scope_note: str | None = None


TARGETS: list[ParentTarget] = [
    ParentTarget("US-CA-SDG", "San Diego", "California"),
    ParentTarget("US-CA-SCL", "Santa Clara", "California",
                 scope_note="City of Santa Clara (Levi's Stadium / 49ers), NOT Santa Clara County."),
    ParentTarget("US-ID", "Idaho", None, scope_note="Idaho state-wide: cover ALL auditorium districts (Boise, Pocatello-Chubbuck, Idaho Falls, Sun Valley)."),
    ParentTarget("US-TX-AUS", "Austin", "Texas"),
    ParentTarget("US-TX-ARL", "Arlington", "Texas",
                 scope_note="Arlington, TX (AT&T Stadium / Globe Life Field), NOT Arlington VA."),
    ParentTarget("US-CA-SJC", "San Jose", "California"),
    ParentTarget("US-NY-NYC", "New York City", "New York"),
    ParentTarget("US-CA-LAX", "Los Angeles", "California"),
    ParentTarget("US-CA-SFO", "San Francisco", "California"),
    ParentTarget("US-FL-MIA", "Miami-Dade County", "Florida",
                 scope_note="Miami-Dade County. Miami Beach (US-FL-MIB) is a separate parent — if you find Miami Beach TIDs, still report them (reviewer will relocate to MIB)."),
]

DEFAULT_OUT_DIR = Path(__file__).parent / "data" / "research_districts"
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("research_districts")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def _load_parent(db, code: str) -> Jurisdiction | None:
    """Load the parent with its existing tax rates eagerly joined."""
    result = await db.execute(
        select(Jurisdiction)
        .where(Jurisdiction.code == code)
        .options(selectinload(Jurisdiction.tax_rates))
    )
    j = result.scalar_one_or_none()
    if j is not None:
        # Force-load tax_rates.tax_category for the prompt formatter
        _ = [r.tax_category for r in j.tax_rates]
    return j


async def _call_api(
    client: anthropic.AsyncAnthropic,
    messages: list[dict],
    tools: list[dict],
) -> anthropic.types.Message:
    """Anthropic call with retry on transient failures. Mirrors ai_agent_service._call_api."""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return await client.messages.create(
                model=settings.anthropic_model,
                max_tokens=settings.anthropic_max_tokens,
                system=SYSTEM_PROMPT,
                messages=messages,
                tools=tools,
                timeout=settings.anthropic_timeout_seconds,
            )
        except anthropic.RateLimitError as e:
            last_error = e
            wait = RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning("Rate limited (attempt %d), retry in %.1fs", attempt + 1, wait)
            await asyncio.sleep(wait)
        except anthropic.APIConnectionError as e:
            last_error = e
            wait = RETRY_BASE_DELAY * (2 ** attempt)
            logger.warning("Connection error (attempt %d): %s, retry in %.1fs", attempt + 1, e, wait)
            await asyncio.sleep(wait)
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                last_error = e
                wait = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("API %d (attempt %d), retry in %.1fs", e.status_code, attempt + 1, wait)
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError(f"API failed after {MAX_RETRIES} retries: {last_error}") from last_error


async def run_agent(
    client: anthropic.AsyncAnthropic,
    parent: Jurisdiction | None,
    target: ParentTarget,
) -> AIDistrictDiscoveryResult:
    """Agentic loop: call API, handle web_search + report tool, return structured result."""
    existing_rates = parent.tax_rates if parent is not None else []

    user_prompt = build_user_prompt(
        parent=parent,
        parent_code=target.code,
        parent_name_hint=target.name_hint,
        parent_state_hint=target.state_hint,
        parent_country_hint=target.country_hint,
        existing_rates=existing_rates,
    )
    if target.scope_note:
        user_prompt += f"\n\n## Scope Note from Reviewer\n{target.scope_note}"

    tools = [
        {
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": settings.anthropic_max_search_uses,
        },
        {
            "name": "report_district_findings",
            "description": (
                "Report the complete set of special tax districts discovered within "
                "the parent jurisdiction. Call this tool ONLY after research is complete. "
                "Include ALL districts found, with full rate/rule details and sources."
            ),
            "input_schema": AIDistrictDiscoveryResult.model_json_schema(),
        },
    ]

    messages: list[dict] = [{"role": "user", "content": user_prompt}]
    max_turns = settings.anthropic_max_agent_turns

    logger.info(
        "[%s] Starting agent (model=%s, max_turns=%d, max_searches=%d)",
        target.code, settings.anthropic_model, max_turns, settings.anthropic_max_search_uses,
    )

    for turn in range(max_turns):
        response = await _call_api(client, messages, tools)
        tool_calls = [b.name for b in response.content if b.type == "tool_use"]
        logger.info(
            "[%s] Turn %d/%d: stop_reason=%s, tools=%s, in=%s, out=%s",
            target.code, turn + 1, max_turns, response.stop_reason, tool_calls or "none",
            response.usage.input_tokens if response.usage else "?",
            response.usage.output_tokens if response.usage else "?",
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "report_district_findings":
                raw = block.input
                # Resilience: Claude occasionally stringifies nested list fields.
                # Detect and json.loads() them before validation.
                if isinstance(raw, dict):
                    for field in ("districts", "sources_checked"):
                        if isinstance(raw.get(field), str):
                            try:
                                raw[field] = json.loads(raw[field])
                                logger.warning(
                                    "[%s] recovered stringified %s field via json.loads",
                                    target.code, field,
                                )
                            except json.JSONDecodeError:
                                pass
                try:
                    result = AIDistrictDiscoveryResult.model_validate(raw)
                except Exception as e:
                    logger.error("[%s] Parse error: %s\nRaw: %s", target.code, e, raw)
                    raise ValueError(f"Invalid structured output: {e}") from e
                logger.info(
                    "[%s] DONE after %d turns: %d districts, confidence=%.2f",
                    target.code, turn + 1, len(result.districts), result.overall_confidence,
                )
                return result

        if response.stop_reason == "end_turn":
            messages.append({"role": "assistant", "content": response.content})
            messages.append({
                "role": "user",
                "content": "You have finished your research. Call report_district_findings now with all districts you found.",
            })
            continue

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if (block.type == "tool_use"
                        and block.name not in ("report_district_findings", "web_search")):
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": "Tool not available.",
                    })
            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            continue

    raise RuntimeError(f"[{target.code}] Exhausted {max_turns} turns without report")


def _write_index(out_dir: Path, entries: list[dict], run_started_at: str) -> None:
    index = {
        "run_started_at": run_started_at,
        "run_completed_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.anthropic_model,
        "max_search_uses": settings.anthropic_max_search_uses,
        "max_agent_turns": settings.anthropic_max_agent_turns,
        "entries": entries,
    }
    (out_dir / "_index.json").write_text(json.dumps(index, indent=2, sort_keys=True))


async def research_one(
    client: anthropic.AsyncAnthropic,
    db,
    target: ParentTarget,
    out_dir: Path,
) -> dict:
    entry = {
        "code": target.code,
        "name_hint": target.name_hint,
        "status": "pending",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    started = time.monotonic()
    parent = await _load_parent(db, target.code)
    entry["parent_exists_in_db"] = parent is not None
    if parent is None:
        logger.info("[%s] parent NOT in DB — using stub. %s", target.code, target.name_hint)

    try:
        result = await run_agent(client, parent, target)
    except Exception as e:  # noqa: BLE001
        elapsed = time.monotonic() - started
        logger.error("[%s] FAILED after %.1fs: %s\n%s", target.code, elapsed, e, traceback.format_exc())
        entry.update(status="failed", error=f"{type(e).__name__}: {e}", elapsed_seconds=round(elapsed, 1))
        return entry

    elapsed = time.monotonic() - started
    out_path = out_dir / f"{target.code}.json"
    payload = result.model_dump(mode="json")
    payload["_meta"] = {
        "parent_code": target.code,
        "parent_name_hint": target.name_hint,
        "parent_state_hint": target.state_hint,
        "parent_exists_in_db": parent is not None,
        "parent_db_name": parent.name if parent else None,
        "parent_db_path": parent.path if parent else None,
        "scope_note": target.scope_note,
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "model": settings.anthropic_model,
    }
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    logger.info(
        "[%s] wrote %s: %d districts, conf=%.2f, %.1fs",
        target.code, out_path.name, len(result.districts), result.overall_confidence, elapsed,
    )
    entry.update(
        status="completed",
        elapsed_seconds=round(elapsed, 1),
        districts_found=len(result.districts),
        total_rates=sum(len(d.rates) for d in result.districts),
        total_rules=sum(len(d.rules) for d in result.districts),
        overall_confidence=result.overall_confidence,
        output_file=out_path.name,
    )
    return entry


async def run_research(targets: list[ParentTarget], out_dir: Path, skip_existing: bool) -> int:
    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY is not set")
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    run_started_at = datetime.now(timezone.utc).isoformat()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    entries: list[dict] = []

    async with async_session_factory() as db:
        for idx, target in enumerate(targets, start=1):
            logger.info("%s [%d/%d] %s (%s)", "=" * 10, idx, len(targets), target.code, target.name_hint)
            if skip_existing and (out_dir / f"{target.code}.json").exists():
                logger.info("[%s] skipping (file exists)", target.code)
                entries.append({"code": target.code, "status": "skipped_existing"})
                continue
            entry = await research_one(client, db, target, out_dir)
            entries.append(entry)
            _write_index(out_dir, entries, run_started_at)
            if idx < len(targets):
                await asyncio.sleep(2)

    ok = sum(1 for e in entries if e["status"] == "completed")
    skipped = sum(1 for e in entries if e["status"].startswith("skipped"))
    failed = sum(1 for e in entries if e["status"] == "failed")
    total_districts = sum(e.get("districts_found", 0) for e in entries)
    logger.info(
        "DONE: %d ok, %d skipped, %d failed | %d districts found total",
        ok, skipped, failed, total_districts,
    )
    return 0 if failed == 0 else 1


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--codes", help="Comma-separated parent jurisdiction codes")
    g.add_argument("--all", action="store_true", help="Run against all 10 targets")
    p.add_argument("--limit", type=int, help="Only process first N targets")
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    p.add_argument("--skip-existing", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.codes:
        codes = {c.strip() for c in args.codes.split(",") if c.strip()}
        targets = [t for t in TARGETS if t.code in codes]
        missing = codes - {t.code for t in TARGETS}
        if missing:
            logger.error("Unknown codes (not in TARGETS): %s", ", ".join(sorted(missing)))
            return 2
    else:
        targets = list(TARGETS)
    if args.limit:
        targets = targets[: args.limit]
    if not targets:
        logger.error("No targets to process")
        return 2

    logger.info("Targets: %s", [t.code for t in targets])
    logger.info(
        "Config: model=%s, max_search=%d, max_turns=%d",
        settings.anthropic_model,
        settings.anthropic_max_search_uses,
        settings.anthropic_max_agent_turns,
    )
    return asyncio.run(run_research(targets, args.out_dir, args.skip_existing))


if __name__ == "__main__":
    sys.exit(main())
