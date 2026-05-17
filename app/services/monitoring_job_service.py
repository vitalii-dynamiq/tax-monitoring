from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.session import async_session_factory
from app.models.jurisdiction import Jurisdiction
from app.models.monitoring_job import MonitoringJob
from app.models.monitoring_schedule import MonitoringSchedule
from app.models.tax_rate import TaxRate

logger = logging.getLogger(__name__)

_job_semaphore = asyncio.Semaphore(settings.monitoring_max_concurrent_jobs)


# ─── CRUD helpers ────────────────────────────────────────────────────


async def create_job(
    db: AsyncSession,
    jurisdiction_id: int | None,
    trigger_type: str,
    triggered_by: str = "system",
    idempotency_key: str | None = None,
    job_type: str = "monitoring",
) -> MonitoringJob:
    """Create a new monitoring job. Returns existing job if idempotency_key conflicts."""
    if idempotency_key:
        existing = await db.execute(
            select(MonitoringJob)
            .options(selectinload(MonitoringJob.jurisdiction))
            .where(MonitoringJob.idempotency_key == idempotency_key)
        )
        found = existing.scalar_one_or_none()
        if found:
            return found

    job = MonitoringJob(
        jurisdiction_id=jurisdiction_id,
        job_type=job_type,
        trigger_type=trigger_type,
        triggered_by=triggered_by,
        idempotency_key=idempotency_key,
    )
    db.add(job)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Race condition: another request created the same idempotency_key
        result = await db.execute(
            select(MonitoringJob)
            .options(selectinload(MonitoringJob.jurisdiction))
            .where(MonitoringJob.idempotency_key == idempotency_key)
        )
        return result.scalar_one()
    return job


async def get_job(db: AsyncSession, job_id: int) -> MonitoringJob | None:
    result = await db.execute(
        select(MonitoringJob)
        .options(selectinload(MonitoringJob.jurisdiction))
        .where(MonitoringJob.id == job_id)
    )
    return result.scalar_one_or_none()


async def list_jobs(
    db: AsyncSession,
    jurisdiction_code: str | None = None,
    job_type: str | None = None,
    status: str | None = None,
    trigger_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[MonitoringJob]:
    query = select(MonitoringJob).options(selectinload(MonitoringJob.jurisdiction))
    if jurisdiction_code:
        query = query.join(MonitoringJob.jurisdiction).where(
            Jurisdiction.code == jurisdiction_code
        )
    if job_type:
        query = query.where(MonitoringJob.job_type == job_type)
    if status:
        query = query.where(MonitoringJob.status == status)
    if trigger_type:
        query = query.where(MonitoringJob.trigger_type == trigger_type)
    query = query.order_by(MonitoringJob.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


async def has_running_job(
    db: AsyncSession,
    jurisdiction_id: int,
    job_type: str | None = None,
) -> bool:
    query = select(MonitoringJob.id).where(
        MonitoringJob.jurisdiction_id == jurisdiction_id,
        MonitoringJob.status.in_(["pending", "running"]),
    )
    if job_type is not None:
        query = query.where(MonitoringJob.job_type == job_type)
    result = await db.execute(query)
    return result.scalar_one_or_none() is not None


# ─── Schedule CRUD ───────────────────────────────────────────────────


async def get_schedule(
    db: AsyncSession,
    jurisdiction_code: str,
    job_type: str = "monitoring",
) -> MonitoringSchedule | None:
    result = await db.execute(
        select(MonitoringSchedule)
        .join(MonitoringSchedule.jurisdiction)
        .options(selectinload(MonitoringSchedule.jurisdiction))
        .where(
            Jurisdiction.code == jurisdiction_code,
            MonitoringSchedule.job_type == job_type,
        )
    )
    schedule = result.scalar_one_or_none()
    if schedule is not None:
        await _attach_last_run_status(db, [schedule])
    return schedule


async def _ensure_country_schedules(db: AsyncSession, *, job_type: str) -> None:
    """Lazily create disabled schedules of `job_type` for every country lacking one.

    Used by both job types now that monitoring is country-scoped (mirror of the
    discovery seed). Idempotent — safe on every list_schedules call.

    Default cadence: monthly for discovery, weekly for monitoring.
    """
    existing_q = await db.execute(
        select(MonitoringSchedule.jurisdiction_id).where(
            MonitoringSchedule.job_type == job_type
        )
    )
    existing_ids = {row[0] for row in existing_q.all()}

    countries_q = await db.execute(
        select(Jurisdiction.id).where(Jurisdiction.jurisdiction_type == "country")
    )
    country_ids = [row[0] for row in countries_q.all()]
    missing = [cid for cid in country_ids if cid not in existing_ids]
    if not missing:
        return

    default_cadence = "monthly" if job_type == "discovery" else "weekly"
    for cid in missing:
        db.add(
            MonitoringSchedule(
                jurisdiction_id=cid,
                job_type=job_type,
                enabled=False,
                cadence=default_cadence,
            )
        )
    await db.flush()




async def _attach_last_run_status(
    db: AsyncSession, schedules: list[MonitoringSchedule]
) -> None:
    """Populate transient `last_run_status` and `failed_in_last_24h` on each schedule.

    `last_run_status` = status of the most recent job for (jurisdiction, job_type).
    `failed_in_last_24h` = there is at least one failed job for (jurisdiction, job_type)
    whose completed_at is within the last 24 hours.

    Sets transient attributes (not columns). Pydantic's `from_attributes` will read
    them when building the response.
    """
    if not schedules:
        return

    juris_ids = {s.jurisdiction_id for s in schedules}

    # ── most-recent status per (jurisdiction, job_type) ──
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import and_, func

    row_num = func.row_number().over(
        partition_by=(MonitoringJob.jurisdiction_id, MonitoringJob.job_type),
        order_by=MonitoringJob.created_at.desc(),
    ).label("rn")
    sub = (
        select(
            MonitoringJob.jurisdiction_id,
            MonitoringJob.job_type,
            MonitoringJob.status,
            row_num,
        )
        .where(MonitoringJob.jurisdiction_id.in_(juris_ids))
        .subquery()
    )
    result = await db.execute(
        select(sub.c.jurisdiction_id, sub.c.job_type, sub.c.status).where(sub.c.rn == 1)
    )
    latest = {(jid, jtype): status for jid, jtype, status in result.all()}

    # ── any failed job in the last 24h per (jurisdiction, job_type) ──
    since = datetime.now(UTC) - timedelta(hours=24)
    failed_q = await db.execute(
        select(MonitoringJob.jurisdiction_id, MonitoringJob.job_type)
        .where(
            and_(
                MonitoringJob.jurisdiction_id.in_(juris_ids),
                MonitoringJob.status == "failed",
                MonitoringJob.completed_at >= since,
            )
        )
        .distinct()
    )
    failed_pairs = {(jid, jtype) for jid, jtype in failed_q.all()}

    for s in schedules:
        key = (s.jurisdiction_id, s.job_type)
        s.last_run_status = latest.get(key)  # type: ignore[attr-defined]
        s.failed_in_last_24h = key in failed_pairs  # type: ignore[attr-defined]


async def list_schedules(
    db: AsyncSession,
    enabled: bool | None = None,
    job_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[MonitoringSchedule]:
    # Both monitoring and discovery are country-scoped now. Seed a row per
    # country lazily so the tabs always show the full country list.
    if job_type in ("discovery", "monitoring"):
        await _ensure_country_schedules(db, job_type=job_type)
        await db.commit()

    query = select(MonitoringSchedule).options(
        selectinload(MonitoringSchedule.jurisdiction)
    )
    if enabled is not None:
        query = query.where(MonitoringSchedule.enabled == enabled)
    if job_type is not None:
        query = query.where(MonitoringSchedule.job_type == job_type)
    query = query.order_by(MonitoringSchedule.id).limit(limit).offset(offset)
    result = await db.execute(query)
    schedules = list(result.scalars().all())
    await _attach_last_run_status(db, schedules)
    return schedules


async def upsert_schedule(
    db: AsyncSession,
    jurisdiction_id: int,
    enabled: bool | None = None,
    cadence: str | None = None,
    cron_expression: str | None = None,
    job_type: str = "monitoring",
) -> MonitoringSchedule:
    result = await db.execute(
        select(MonitoringSchedule)
        .options(selectinload(MonitoringSchedule.jurisdiction))
        .where(
            MonitoringSchedule.jurisdiction_id == jurisdiction_id,
            MonitoringSchedule.job_type == job_type,
        )
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        schedule = MonitoringSchedule(jurisdiction_id=jurisdiction_id, job_type=job_type)
        db.add(schedule)

    if enabled is not None:
        schedule.enabled = enabled
    if cadence is not None:
        schedule.cadence = cadence
    if cron_expression is not None:
        schedule.cron_expression = cron_expression

    # Compute next_run_at if enabled
    if schedule.enabled:
        schedule.next_run_at = _compute_next_run(schedule.cadence, schedule.cron_expression)
    else:
        schedule.next_run_at = None

    await db.flush()
    return schedule


async def bulk_update_schedules(
    db: AsyncSession,
    jurisdiction_codes: list[str],
    job_type: str,
    action: str,
    cadence: str | None = None,
    cron_expression: str | None = None,
) -> tuple[list[MonitoringSchedule], list[dict]]:
    """Bulk enable/disable or change cadence on schedules for the given codes.

    Returns (updated, errors). Each error: {"code": str, "message": str}.
    Per-row failures do not abort the batch.
    """
    if action not in {"enable", "disable", "set_cadence"}:
        raise ValueError(f"Unknown bulk action: {action}")
    if action == "set_cadence":
        if not cadence:
            raise ValueError("cadence is required for set_cadence action")
        if cadence == "custom" and not cron_expression:
            raise ValueError("cron_expression is required when cadence is 'custom'")
        if cron_expression and not validate_cron_expression(cron_expression):
            raise ValueError(f"Invalid cron expression: '{cron_expression}'")

    juris_q = await db.execute(
        select(Jurisdiction).where(Jurisdiction.code.in_(jurisdiction_codes))
    )
    juris_by_code = {j.code: j for j in juris_q.scalars().all()}

    updated: list[MonitoringSchedule] = []
    errors: list[dict] = []

    for code in jurisdiction_codes:
        juris = juris_by_code.get(code)
        if not juris:
            errors.append({"code": code, "message": "Jurisdiction not found"})
            continue
        if job_type in ("discovery", "monitoring") and juris.jurisdiction_type != "country":
            errors.append(
                {
                    "code": code,
                    "message": f"{job_type.capitalize()} only supported for countries",
                }
            )
            continue

        try:
            if action == "enable":
                schedule = await upsert_schedule(
                    db, jurisdiction_id=juris.id, enabled=True, job_type=job_type
                )
            elif action == "disable":
                schedule = await upsert_schedule(
                    db, jurisdiction_id=juris.id, enabled=False, job_type=job_type
                )
            else:  # set_cadence
                schedule = await upsert_schedule(
                    db,
                    jurisdiction_id=juris.id,
                    cadence=cadence,
                    cron_expression=cron_expression,
                    job_type=job_type,
                )
            # Eager-load relationship so the response can include jurisdiction_code.
            schedule.jurisdiction = juris
            updated.append(schedule)
        except Exception as e:
            errors.append({"code": code, "message": str(e)})

    return updated, errors


def _compute_next_run(cadence: str, cron_expression: str | None = None) -> datetime:
    """Compute the next run time based on cadence."""
    from croniter import croniter

    cron_map = {
        "daily": "0 3 * * *",       # 3 AM daily
        "weekly": "0 3 * * 1",      # 3 AM Monday
        "monthly": "0 3 1 * *",     # 3 AM first of month
    }

    expr = cron_expression if cadence == "custom" else cron_map.get(cadence, "0 3 * * 1")
    cron = croniter(expr, datetime.now(UTC))
    return cron.get_next(datetime)


def validate_cron_expression(expr: str) -> bool:
    """Check if a cron expression is valid."""
    try:
        from croniter import croniter
        return croniter.is_valid(expr)
    except Exception:
        return False


# ─── Job execution ───────────────────────────────────────────────────


async def run_monitoring_job(job_id: int) -> None:
    """Execute a monitoring job. Runs as a background task with its own DB session."""
    import time as _time

    async with async_session_factory() as db:
        try:
            job = await get_job(db, job_id)
            if not job:
                logger.error("Monitoring job %d not found in DB", job_id)
                return

            logger.info("=== MONITORING JOB %d START ===", job_id)

            # Mark as running
            job.status = "running"
            job.started_at = datetime.now(UTC)
            await db.commit()

            # Phase 1: Load country + ALL descendants + all rates/rules across them
            t0 = _time.monotonic()
            country = await db.get(Jurisdiction, job.jurisdiction_id)
            if not country:
                raise ValueError(f"Jurisdiction ID {job.jurisdiction_id} not found")
            if country.jurisdiction_type != "country":
                raise ValueError(
                    f"{country.code} is not a country. Monitoring is country-scoped."
                )

            # All descendants (states + cities + …) under this country
            descendants_q = await db.execute(
                select(Jurisdiction).where(
                    Jurisdiction.country_code == country.country_code,
                    Jurisdiction.id != country.id,
                )
            )
            descendants = list(descendants_q.scalars().all())
            jurisdiction_ids = [country.id] + [d.id for d in descendants]

            # All current rates + rules across the entire tree
            rates_q = await db.execute(
                select(TaxRate)
                .options(selectinload(TaxRate.tax_category))
                .where(
                    TaxRate.jurisdiction_id.in_(jurisdiction_ids),
                    TaxRate.status.in_(("active", "draft", "scheduled", "approved")),
                )
            )
            current_rates = list(rates_q.scalars().all())

            from app.models.tax_rule import TaxRule as _TaxRule
            rules_q = await db.execute(
                select(_TaxRule).where(
                    _TaxRule.jurisdiction_id.in_(jurisdiction_ids),
                    _TaxRule.status.in_(("active", "draft", "scheduled", "approved")),
                )
            )
            current_rules = list(rules_q.scalars().all())

            from app.models.monitored_source import MonitoredSource
            sources_q = await db.execute(
                select(MonitoredSource).where(
                    MonitoredSource.jurisdiction_id.in_(jurisdiction_ids),
                    MonitoredSource.status == "active",
                )
            )
            sources = list(sources_q.scalars().all())
            logger.info(
                "[Job %d] Phase 1 — country=%s descendants=%d rates=%d rules=%d "
                "sources=%d (%.1fs)",
                job_id, country.code, len(descendants), len(current_rates),
                len(current_rules), len(sources), _time.monotonic() - t0,
            )

            # Phase 2: Call AI agent (country-scoped)
            t1 = _time.monotonic()
            logger.info("[Job %d] Phase 2 — starting agent for %s", job_id, country.code)
            from app.services.agent_run_recorder import AgentRunRecorder
            from app.services.agents import get_agent
            from app.services.prompts.tax_monitoring import SYSTEM_PROMPT, build_user_prompt

            user_prompt = build_user_prompt(
                country, descendants, current_rates, current_rules, sources
            )
            recorder = AgentRunRecorder(
                model=settings.anthropic_model,
                system_prompt=SYSTEM_PROMPT,
                initial_user_prompt=user_prompt,
            )
            agent = get_agent("tax_monitoring")
            ai_result = await agent.run(
                user_prompt=user_prompt,
                recorder=recorder,
                log_label=country.code,
            )
            logger.info(
                "[Job %d] Phase 2 — agent done in %.1fs: %d rates, %d rules",
                job_id, _time.monotonic() - t1, len(ai_result.rates), len(ai_result.rules),
            )

            # Phase 3: Process results — per-rate / per-rule jurisdiction routing
            t2 = _time.monotonic()
            from app.services.change_detection_service import process_ai_results
            jurisdictions_by_code = {country.code: country, **{d.code: d for d in descendants}}
            summary = await process_ai_results(
                db, country, ai_result, job_id, current_rates, current_rules,
                jurisdictions_by_code=jurisdictions_by_code,
            )
            logger.info(
                "[Job %d] Phase 3 — change detection completed in %.1fs: %s",
                job_id, _time.monotonic() - t2, summary,
            )

            # Phase 4: Finalize
            for source in sources:
                source.last_checked_at = datetime.now(UTC)

            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            job.changes_detected = summary["changes_detected"]
            job.result_summary = summary

            # Persist agent-run telemetry (turns, totals, cost).
            try:
                await recorder.flush(db, job.id)
            except Exception:
                logger.exception("[Job %d] Failed to flush recorder; continuing.", job_id)

            await db.commit()

            total_time = _time.monotonic() - t0
            logger.info(
                "=== MONITORING JOB %d COMPLETED in %.1fs — %d changes detected for %s ===",
                job_id, total_time, summary["changes_detected"], country.code,
            )

        except Exception as e:
            logger.error("Job %d failed: %s", job_id, e, exc_info=True)
            # Use a fresh session to update the job status — current session may be dirty
            try:
                async with async_session_factory() as err_db:
                    err_job = await get_job(err_db, job_id)
                    if err_job and err_job.status in ("pending", "running"):
                        err_job.status = "failed"
                        err_job.completed_at = datetime.now(UTC)
                        err_job.error_message = str(e)[:2000]
                        err_job.error_traceback = traceback.format_exc()[:5000]
                        # Persist any turns captured before the failure
                        recorder_local = locals().get("recorder")
                        if recorder_local is not None and recorder_local.turns:
                            try:
                                await recorder_local.flush(err_db, job_id)
                            except Exception:
                                logger.exception(
                                    "[Job %d] Recorder flush failed on error path", job_id
                                )
                        await err_db.commit()
            except Exception:
                logger.error("Failed to update job %d status after error", job_id, exc_info=True)


async def run_monitoring_job_with_limits(job_id: int) -> None:
    """Run a monitoring job with concurrency and timeout limits."""
    async with _job_semaphore:
        try:
            await asyncio.wait_for(
                run_monitoring_job(job_id),
                timeout=settings.monitoring_job_timeout_seconds,
            )
        except TimeoutError:
            logger.error("Job %d timed out after %ds", job_id, settings.monitoring_job_timeout_seconds)
            try:
                async with async_session_factory() as db:
                    job = await get_job(db, job_id)
                    if job and job.status in ("pending", "running"):
                        job.status = "failed"
                        job.completed_at = datetime.now(UTC)
                        job.error_message = (
                            f"Job timed out after {settings.monitoring_job_timeout_seconds} seconds"
                        )
                        await db.commit()
            except Exception:
                logger.error("Failed to update timed-out job %d", job_id, exc_info=True)
