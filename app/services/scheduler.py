import asyncio
import logging
from datetime import UTC, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.config import settings
from app.db.session import async_session_factory
from app.models.monitoring_schedule import MonitoringSchedule

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


async def check_due_schedules() -> None:
    """Check for schedules that are due and trigger monitoring jobs."""
    try:
        async with async_session_factory() as db:
            now = datetime.now(UTC)
            result = await db.execute(
                select(MonitoringSchedule).where(
                    MonitoringSchedule.enabled.is_(True),
                    MonitoringSchedule.next_run_at <= now,
                )
            )
            due_schedules = list(result.scalars().all())

            if not due_schedules:
                return

            logger.info("Found %d due monitoring schedules", len(due_schedules))

            from app.services.monitoring_job_service import (
                _compute_next_run,
                create_job,
                has_running_job,
                run_monitoring_job_with_limits,
            )

            for schedule in due_schedules:
                try:
                    # Skip if already has a running job
                    if await has_running_job(db, schedule.jurisdiction_id):
                        logger.info(
                            "Skipping schedule %d — already has a running job",
                            schedule.id,
                        )
                        # If schedule is stuck more than 1 hour past due, advance it
                        if schedule.next_run_at and schedule.next_run_at < now - timedelta(hours=1):
                            schedule.next_run_at = _compute_next_run(
                                schedule.cadence, schedule.cron_expression
                            )
                            await db.commit()
                        continue

                    job = await create_job(
                        db,
                        jurisdiction_id=schedule.jurisdiction_id,
                        trigger_type="scheduled",
                        triggered_by="scheduler",
                    )

                    # Advance schedule to next run time
                    schedule.last_run_at = now
                    schedule.next_run_at = _compute_next_run(
                        schedule.cadence, schedule.cron_expression
                    )
                    await db.commit()

                    # Dispatch job in background
                    asyncio.create_task(run_monitoring_job_with_limits(job.id))
                    logger.info(
                        "Dispatched scheduled monitoring job %d for schedule %d",
                        job.id,
                        schedule.id,
                    )

                except Exception as e:
                    logger.error(
                        "Failed to dispatch schedule %d: %s",
                        schedule.id,
                        e,
                        exc_info=True,
                    )
                    # Don't let one schedule failure stop others
                    continue

    except Exception as e:
        logger.error("Error in check_due_schedules: %s", e, exc_info=True)


def start_scheduler() -> None:
    """Start the APScheduler if Anthropic API key is configured."""
    if not settings.anthropic_api_key:
        logger.warning(
            "ANTHROPIC_API_KEY not configured — monitoring scheduler will not start. "
            "Set ANTHROPIC_API_KEY in .env to enable scheduled monitoring."
        )
        return

    scheduler.add_job(
        check_due_schedules,
        IntervalTrigger(seconds=settings.monitoring_scheduler_interval_seconds),
        id="check_due_schedules",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Monitoring scheduler started (interval=%ds, model=%s)",
        settings.monitoring_scheduler_interval_seconds,
        settings.anthropic_model,
    )


def stop_scheduler() -> None:
    """Gracefully stop the scheduler."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Monitoring scheduler stopped")
