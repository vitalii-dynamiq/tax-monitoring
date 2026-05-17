"""Triage job runner.

Loads a batch of pending items, runs the TriageAgent (which queues decisions
during its agentic loop), then atomically applies those decisions via the
same approve/reject service functions humans use. Captures full telemetry
into agent_run_turns the same way monitoring/discovery do.
"""
from __future__ import annotations

import asyncio
import logging
import time as _time
import traceback
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.session import async_session_factory
from app.models.detected_change import DetectedChange
from app.models.jurisdiction import Jurisdiction
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule
from app.services.agent_run_recorder import AgentRunRecorder
from app.services.monitoring_job_service import _job_semaphore, get_job
from app.services.monitoring_service import review_change
from app.services.prompts.triage import (
    TRIAGE_SYSTEM_PROMPT,
    PendingItem,
    TriageDecision,
    build_triage_user_prompt,
)

logger = logging.getLogger(__name__)


# Hardcoded conservative thresholds (see plan).
APPROVE_MIN_CONFIDENCE = 0.9
REJECT_MIN_CONFIDENCE = 0.9


# ─── Load pending items ──────────────────────────────────────────────


async def _load_pending_items(
    db: AsyncSession,
    *,
    jurisdiction_code: str | None,
    max_items: int,
) -> list[PendingItem]:
    """Snapshot pending items across the four review queues, oldest first."""

    # Resolve jurisdiction filter (optional)
    juris_filter_ids: set[int] | None = None
    if jurisdiction_code:
        from app.services.jurisdiction_service import get_jurisdiction_by_code

        target = await get_jurisdiction_by_code(db, jurisdiction_code)
        if target is None:
            return []
        # Match the target and (for countries) any descendant by country_code
        if target.jurisdiction_type == "country":
            descendants_q = await db.execute(
                select(Jurisdiction.id).where(
                    Jurisdiction.country_code == target.country_code
                )
            )
            juris_filter_ids = {row[0] for row in descendants_q.all()}
        else:
            juris_filter_ids = {target.id}

    items: list[PendingItem] = []

    def _apply_filter(q):
        if juris_filter_ids is not None:
            q = q.where(Jurisdiction.id.in_(juris_filter_ids))
        return q

    # ── pending jurisdictions ──
    juris_q = select(Jurisdiction).where(Jurisdiction.status == "pending")
    if juris_filter_ids is not None:
        juris_q = juris_q.where(Jurisdiction.id.in_(juris_filter_ids))
    juris_q = juris_q.order_by(Jurisdiction.created_at).limit(max_items)
    for j in (await db.execute(juris_q)).scalars().all():
        meta = j.metadata_ or {}
        items.append(
            PendingItem(
                item_type="jurisdiction",
                item_id=j.id,
                jurisdiction_code=j.code,
                jurisdiction_name=j.name,
                summary=(
                    f"New {j.jurisdiction_type} {j.name} ({j.code}). "
                    f"{meta.get('tax_summary') or 'No tax summary recorded.'}"
                ),
                source_url=meta.get("discovery_source"),
                source_quote=None,
                authority_name=None,
                legal_reference=None,
                ai_confidence=meta.get("discovery_confidence"),
                from_run_id=j.monitoring_job_id,
                extracted_data=meta,
            )
        )

    # ── pending detected_changes ──
    change_q = (
        select(DetectedChange)
        .options(selectinload(DetectedChange.jurisdiction))
        .where(DetectedChange.review_status == "pending")
    )
    if juris_filter_ids is not None:
        change_q = change_q.where(DetectedChange.jurisdiction_id.in_(juris_filter_ids))
    change_q = change_q.order_by(DetectedChange.created_at).limit(max_items)
    for c in (await db.execute(change_q)).scalars().all():
        items.append(
            PendingItem(
                item_type="change",
                item_id=c.id,
                jurisdiction_code=c.jurisdiction.code if c.jurisdiction else None,
                jurisdiction_name=c.jurisdiction.name if c.jurisdiction else None,
                summary=f"{c.change_type}: {(c.extracted_data or {}).get('name', '')}".strip(),
                source_url=c.source_snapshot_url,
                source_quote=c.source_quote,
                authority_name=None,
                legal_reference=None,
                ai_confidence=float(c.confidence) if c.confidence is not None else None,
                from_run_id=c.monitoring_job_id,
                extracted_data=c.extracted_data,
            )
        )

    # ── draft tax_rates ──
    rate_q = (
        select(TaxRate)
        .options(
            selectinload(TaxRate.jurisdiction),
            selectinload(TaxRate.tax_category),
        )
        .join(TaxRate.jurisdiction)
        .where(TaxRate.status == "draft")
    )
    rate_q = _apply_filter(rate_q).order_by(TaxRate.created_at).limit(max_items)
    for r in (await db.execute(rate_q)).scalars().all():
        rate_value = r.rate_value
        if r.rate_type == "percentage" and rate_value is not None:
            value_str = f"{float(rate_value) * 100:.3f}%"
        elif r.rate_type == "flat" and rate_value is not None:
            value_str = f"{rate_value} {r.currency_code or ''}".strip()
        else:
            value_str = "tiered"
        cat_code = r.tax_category.code if r.tax_category else "?"
        items.append(
            PendingItem(
                item_type="rate",
                item_id=r.id,
                jurisdiction_code=r.jurisdiction.code if r.jurisdiction else None,
                jurisdiction_name=r.jurisdiction.name if r.jurisdiction else None,
                summary=f"{cat_code} = {value_str} effective {r.effective_start}",
                source_url=r.source_url,
                source_quote=None,
                authority_name=r.authority_name,
                legal_reference=r.legal_reference,
                ai_confidence=None,
                from_run_id=r.monitoring_job_id,
                extracted_data=None,
            )
        )

    # ── draft tax_rules ──
    rule_q = (
        select(TaxRule)
        .options(selectinload(TaxRule.jurisdiction))
        .join(TaxRule.jurisdiction)
        .where(TaxRule.status == "draft")
    )
    rule_q = _apply_filter(rule_q).order_by(TaxRule.created_at).limit(max_items)
    for r in (await db.execute(rule_q)).scalars().all():
        items.append(
            PendingItem(
                item_type="rule",
                item_id=r.id,
                jurisdiction_code=r.jurisdiction.code if r.jurisdiction else None,
                jurisdiction_name=r.jurisdiction.name if r.jurisdiction else None,
                summary=f"{r.rule_type}: {r.name} (effective {r.effective_start})",
                source_url=None,
                source_quote=None,
                authority_name=r.authority_name,
                legal_reference=r.legal_reference,
                ai_confidence=None,
                from_run_id=r.monitoring_job_id,
                extracted_data={"conditions": r.conditions, "action": r.action},
            )
        )

    # Cap total
    return items[:max_items]


# ─── Apply queued decisions ──────────────────────────────────────────


async def _apply_decisions(
    db: AsyncSession,
    decisions: list[TriageDecision],
    batch_ids_by_type: dict[str, set[int]],
    job_id: int,
) -> dict[str, Any]:
    """Apply queued decisions atomically, returning per-type counts + errors."""
    from app.api.tax_rules import _update_rule_status
    from app.services.tax_rate_service import update_rate_status

    counts = {
        "approved": 0,
        "rejected": 0,
        "deferred": 0,
        "skipped_stale": 0,
        "skipped_low_confidence": 0,
    }
    invalid: list[dict] = []
    duplicates: list[dict] = []
    errors: list[dict] = []

    seen: set[tuple[str, int]] = set()
    note_suffix = f" [via triage job #{job_id}]"

    for d in decisions:
        key = (d.item_type, d.item_id)

        # Guard: id must be in the snapshot we sent
        if d.item_id not in batch_ids_by_type.get(d.item_type, set()):
            invalid.append({"item_type": d.item_type, "item_id": d.item_id})
            continue

        # Guard: only the first decision per id wins
        if key in seen:
            duplicates.append({"item_type": d.item_type, "item_id": d.item_id})
            continue
        seen.add(key)

        # Safety: downgrade low-confidence approvals/rejects to deferred
        action = d.action
        if (
            action == "approved"
            and (d.confidence is None or d.confidence < APPROVE_MIN_CONFIDENCE)
        ):
            action = "deferred"
            counts["skipped_low_confidence"] += 1
        if (
            action == "rejected"
            and (d.confidence is None or d.confidence < REJECT_MIN_CONFIDENCE)
        ):
            action = "deferred"
            counts["skipped_low_confidence"] += 1

        if action == "deferred":
            counts["deferred"] += 1
            continue

        target_status = "active" if action == "approved" else "rejected"
        notes = (d.reasoning or "")[:1500] + note_suffix

        try:
            if d.item_type == "rate":
                updated = await update_rate_status(
                    db, d.item_id, target_status, "ai_triage", notes
                )
                if not updated:
                    counts["skipped_stale"] += 1
                    continue
            elif d.item_type == "rule":
                updated = await _update_rule_status(
                    db, d.item_id, target_status, "ai_triage", notes
                )
                if not updated:
                    counts["skipped_stale"] += 1
                    continue
            elif d.item_type == "jurisdiction":
                from app.services.jurisdiction_service import (
                    update_jurisdiction_status,
                )

                target_juris = await db.get(Jurisdiction, d.item_id)
                if target_juris is None:
                    counts["skipped_stale"] += 1
                    continue
                updated = await update_jurisdiction_status(
                    db,
                    target_juris.code,
                    target_status,
                    "ai_triage",
                    notes,
                )
                if not updated:
                    counts["skipped_stale"] += 1
                    continue
            elif d.item_type == "change":
                review_status = "approved" if action == "approved" else "rejected"
                updated = await review_change(
                    db, d.item_id, review_status, "ai_triage", notes
                )
                if not updated:
                    counts["skipped_stale"] += 1
                    continue
            else:
                invalid.append({"item_type": d.item_type, "item_id": d.item_id})
                continue
            counts[action] += 1
        except Exception as e:
            logger.exception(
                "Triage job %d: failed to apply decision %s#%d", job_id, d.item_type, d.item_id
            )
            errors.append(
                {"item_type": d.item_type, "item_id": d.item_id, "error": str(e)[:300]}
            )

    summary: dict[str, Any] = dict(counts)
    summary["total_decisions"] = len(decisions)
    if invalid:
        summary["invalid_ids"] = invalid
    if duplicates:
        summary["duplicate_decisions"] = duplicates
    if errors:
        summary["errors"] = errors
    return summary


# ─── Job entry points ────────────────────────────────────────────────


async def run_triage_job(job_id: int) -> None:
    """Load batch, run TriageAgent, apply queued decisions."""
    recorder: AgentRunRecorder | None = None
    async with async_session_factory() as db:
        try:
            job = await get_job(db, job_id)
            if not job:
                logger.error("Triage job %d not found", job_id)
                return

            logger.info("=== TRIAGE JOB %d START ===", job_id)
            job.status = "running"
            job.started_at = datetime.now(UTC)
            await db.commit()

            # Optional filters embedded in result_summary at creation time
            opts = (job.result_summary or {}).get("triage_options") or {}
            jurisdiction_code = opts.get("jurisdiction_code")
            max_items = int(opts.get("max_items") or 50)

            # Phase 1: snapshot pending items
            t0 = _time.monotonic()
            items = await _load_pending_items(
                db,
                jurisdiction_code=jurisdiction_code,
                max_items=max_items,
            )
            batch_ids_by_type: dict[str, set[int]] = {}
            for it in items:
                batch_ids_by_type.setdefault(it.item_type, set()).add(it.item_id)
            logger.info(
                "[Job %d] Phase 1 — loaded %d pending items (jurisdiction_code=%r) (%.1fs)",
                job_id, len(items), jurisdiction_code, _time.monotonic() - t0,
            )

            if not items:
                job.status = "completed"
                job.completed_at = datetime.now(UTC)
                job.changes_detected = 0
                job.result_summary = {
                    "approved": 0, "rejected": 0, "deferred": 0,
                    "skipped_stale": 0, "skipped_low_confidence": 0,
                    "total_decisions": 0,
                    "note": "No pending items in scope.",
                    "triage_options": opts,
                }
                await db.commit()
                logger.info("=== TRIAGE JOB %d COMPLETED — no items in scope ===", job_id)
                return

            # Phase 2: run agent
            t1 = _time.monotonic()
            user_prompt = build_triage_user_prompt(items)
            recorder = AgentRunRecorder(
                model=settings.anthropic_model,
                system_prompt=TRIAGE_SYSTEM_PROMPT,
                initial_user_prompt=user_prompt,
            )

            # Persist the prompts NOW so operators can inspect them while the
            # job is still running. The recorder.flush() at the end re-sets
            # the same values + the usage totals — idempotent.
            job.model = settings.anthropic_model
            job.system_prompt = TRIAGE_SYSTEM_PROMPT
            job.initial_user_prompt = user_prompt
            await db.commit()

            # Construct TriageAgent directly (not via get_agent) so we can
            # pass the batch_size and let the agent nudge itself toward
            # report_triage_complete once every item has a decision.
            from app.services.agents.triage import TriageAgent
            agent = TriageAgent(batch_size=len(items))
            report = await agent.run(
                user_prompt=user_prompt,
                recorder=recorder,
                log_label=f"triage#{job_id}",
            )
            logger.info(
                "[Job %d] Phase 2 — agent done in %.1fs: report=%s, queued=%d decisions",
                job_id, _time.monotonic() - t1, report.summary[:80], len(agent.decisions),
            )

            # Phase 3: apply decisions atomically
            t2 = _time.monotonic()
            apply_summary = await _apply_decisions(
                db, agent.decisions, batch_ids_by_type, job_id
            )
            logger.info(
                "[Job %d] Phase 3 — applied decisions in %.1fs: %s",
                job_id, _time.monotonic() - t2, apply_summary,
            )

            # Phase 4: finalize
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            job.changes_detected = (
                apply_summary["approved"] + apply_summary["rejected"]
            )
            job.result_summary = {
                **apply_summary,
                "agent_summary": report.summary,
                "agent_items_reviewed": report.items_reviewed,
                "batch_size": len(items),
                "triage_options": opts,
            }

            try:
                await recorder.flush(db, job.id)
            except Exception:
                logger.exception("[Job %d] Failed to flush recorder; continuing.", job_id)

            await db.commit()
            logger.info(
                "=== TRIAGE JOB %d COMPLETED — approved=%d rejected=%d deferred=%d ===",
                job_id, apply_summary["approved"],
                apply_summary["rejected"], apply_summary["deferred"],
            )

        except Exception as e:
            logger.error("Triage job %d failed: %s", job_id, e, exc_info=True)
            try:
                async with async_session_factory() as err_db:
                    err_job = await get_job(err_db, job_id)
                    if err_job and err_job.status in ("pending", "running"):
                        err_job.status = "failed"
                        err_job.completed_at = datetime.now(UTC)
                        err_job.error_message = str(e)[:2000]
                        err_job.error_traceback = traceback.format_exc()[:5000]
                        if recorder is not None and recorder.turns:
                            try:
                                await recorder.flush(err_db, job_id)
                            except Exception:
                                logger.exception(
                                    "Triage job %d recorder flush failed on error path",
                                    job_id,
                                )
                        await err_db.commit()
            except Exception:
                logger.error(
                    "Failed to update triage job %d status after error",
                    job_id, exc_info=True,
                )


async def run_triage_job_with_limits(job_id: int) -> None:
    """Wrap run_triage_job with the existing concurrency limit + timeout."""
    async with _job_semaphore:
        try:
            await asyncio.wait_for(
                run_triage_job(job_id),
                timeout=settings.monitoring_job_timeout_seconds,
            )
        except TimeoutError:
            logger.error(
                "Triage job %d timed out after %ds",
                job_id, settings.monitoring_job_timeout_seconds,
            )
            try:
                async with async_session_factory() as db:
                    job = await get_job(db, job_id)
                    if job and job.status in ("pending", "running"):
                        job.status = "failed"
                        job.completed_at = datetime.now(UTC)
                        job.error_message = (
                            f"Triage job timed out after "
                            f"{settings.monitoring_job_timeout_seconds} seconds"
                        )
                        await db.commit()
            except Exception:
                logger.error("Failed to update timed-out triage job %d", job_id, exc_info=True)
