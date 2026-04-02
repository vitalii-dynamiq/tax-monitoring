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
    jurisdiction_id: int,
    trigger_type: str,
    triggered_by: str = "system",
    idempotency_key: str | None = None,
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


async def has_running_job(db: AsyncSession, jurisdiction_id: int) -> bool:
    result = await db.execute(
        select(MonitoringJob.id).where(
            MonitoringJob.jurisdiction_id == jurisdiction_id,
            MonitoringJob.status.in_(["pending", "running"]),
        )
    )
    return result.scalar_one_or_none() is not None


# ─── Schedule CRUD ───────────────────────────────────────────────────


async def get_schedule(db: AsyncSession, jurisdiction_code: str) -> MonitoringSchedule | None:
    result = await db.execute(
        select(MonitoringSchedule)
        .join(MonitoringSchedule.jurisdiction)
        .options(selectinload(MonitoringSchedule.jurisdiction))
        .where(Jurisdiction.code == jurisdiction_code)
    )
    return result.scalar_one_or_none()


async def list_schedules(
    db: AsyncSession,
    enabled: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[MonitoringSchedule]:
    query = select(MonitoringSchedule).options(
        selectinload(MonitoringSchedule.jurisdiction)
    )
    if enabled is not None:
        query = query.where(MonitoringSchedule.enabled == enabled)
    query = query.order_by(MonitoringSchedule.id).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


async def upsert_schedule(
    db: AsyncSession,
    jurisdiction_id: int,
    enabled: bool | None = None,
    cadence: str | None = None,
    cron_expression: str | None = None,
) -> MonitoringSchedule:
    result = await db.execute(
        select(MonitoringSchedule)
        .options(selectinload(MonitoringSchedule.jurisdiction))
        .where(MonitoringSchedule.jurisdiction_id == jurisdiction_id)
    )
    schedule = result.scalar_one_or_none()

    if schedule is None:
        schedule = MonitoringSchedule(jurisdiction_id=jurisdiction_id)
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

            # Phase 1: Load jurisdiction data
            t0 = _time.monotonic()
            j_result = await db.execute(
                select(Jurisdiction)
                .options(
                    selectinload(Jurisdiction.tax_rates).joinedload(TaxRate.tax_category),
                    selectinload(Jurisdiction.tax_rules),
                    selectinload(Jurisdiction.monitored_sources),
                )
                .where(Jurisdiction.id == job.jurisdiction_id)
            )
            jurisdiction = j_result.scalar_one_or_none()
            if not jurisdiction:
                raise ValueError(f"Jurisdiction ID {job.jurisdiction_id} not found")

            # Pass all rates/rules (active + draft) so the AI can:
            # 1. Detect changes to active rates (modified, removed, deprecated)
            # 2. Avoid re-detecting draft rates that are already pending review
            current_rates = [
                r for r in jurisdiction.tax_rates
                if r.status in ("active", "draft", "scheduled", "approved")
            ]
            current_rules = [
                r for r in jurisdiction.tax_rules
                if r.status in ("active", "draft", "scheduled", "approved")
            ]
            sources = [s for s in jurisdiction.monitored_sources if s.status == "active"]
            monitored_domains = [s.url for s in sources]
            logger.info(
                "[Job %d] Phase 1 — loaded %s: %d active rates, %d active rules, %d sources (%.1fs)",
                job_id, jurisdiction.code, len(current_rates), len(current_rules),
                len(sources), _time.monotonic() - t0,
            )

            # Phase 2: Call AI agent
            t1 = _time.monotonic()
            logger.info("[Job %d] Phase 2 — starting AI agent research for %s", job_id, jurisdiction.code)
            from app.services.ai_agent_service import TaxMonitoringAgent
            agent = TaxMonitoringAgent()
            ai_result = await agent.research_jurisdiction(
                jurisdiction, current_rates, current_rules, monitored_domains
            )
            logger.info(
                "[Job %d] Phase 2 — AI agent completed in %.1fs: %d rates, %d rules found",
                job_id, _time.monotonic() - t1, len(ai_result.rates), len(ai_result.rules),
            )

            # Phase 3: Process results
            t2 = _time.monotonic()
            from app.services.change_detection_service import process_ai_results
            summary = await process_ai_results(
                db, jurisdiction, ai_result, job_id, current_rates, current_rules
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
            await db.commit()

            total_time = _time.monotonic() - t0
            logger.info(
                "=== MONITORING JOB %d COMPLETED in %.1fs — %d changes detected for %s ===",
                job_id, total_time, summary["changes_detected"], jurisdiction.code,
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
