"""
Tests for monitoring job service (CRUD, schedules, job lifecycle).
"""

from datetime import UTC, datetime

from app.services.monitoring_job_service import (
    _compute_next_run,
    create_job,
    get_job,
    get_schedule,
    has_running_job,
    list_jobs,
    list_schedules,
    upsert_schedule,
    validate_cron_expression,
)
from tests.factories import create_jurisdiction, create_monitoring_job, create_monitoring_schedule


class TestCreateJob:
    async def test_basic_creation(self, db):
        j = await create_jurisdiction(db)
        await db.commit()

        job = await create_job(db, jurisdiction_id=j.id, trigger_type="manual")
        assert job.id is not None
        assert job.status == "pending"
        assert job.trigger_type == "manual"
        assert job.jurisdiction_id == j.id

    async def test_idempotency_key_dedup(self, db):
        j = await create_jurisdiction(db)
        await db.commit()

        job1 = await create_job(
            db, jurisdiction_id=j.id, trigger_type="manual",
            idempotency_key="key-123",
        )
        await db.commit()

        job2 = await create_job(
            db, jurisdiction_id=j.id, trigger_type="manual",
            idempotency_key="key-123",
        )
        assert job2.id == job1.id  # Returns existing


class TestGetJob:
    async def test_found(self, db):
        j = await create_jurisdiction(db)
        job = await create_monitoring_job(db, jurisdiction_id=j.id)
        await db.commit()

        found = await get_job(db, job.id)
        assert found is not None
        assert found.id == job.id

    async def test_not_found(self, db):
        found = await get_job(db, 99999)
        assert found is None


class TestListJobs:
    async def test_empty(self, db):
        jobs = await list_jobs(db)
        assert jobs == []

    async def test_filter_by_status(self, db):
        j = await create_jurisdiction(db)
        await create_monitoring_job(db, jurisdiction_id=j.id, status="pending")
        await create_monitoring_job(db, jurisdiction_id=j.id, status="completed")
        await db.commit()

        pending = await list_jobs(db, status="pending")
        assert len(pending) == 1
        assert pending[0].status == "pending"

    async def test_filter_by_trigger_type(self, db):
        j = await create_jurisdiction(db)
        await create_monitoring_job(db, jurisdiction_id=j.id, trigger_type="manual")
        await create_monitoring_job(db, jurisdiction_id=j.id, trigger_type="scheduled")
        await db.commit()

        manual = await list_jobs(db, trigger_type="manual")
        assert len(manual) == 1
        assert manual[0].trigger_type == "manual"

    async def test_pagination(self, db):
        j = await create_jurisdiction(db)
        for _ in range(5):
            await create_monitoring_job(db, jurisdiction_id=j.id)
        await db.commit()

        page = await list_jobs(db, limit=2, offset=0)
        assert len(page) == 2


class TestHasRunningJob:
    async def test_no_jobs(self, db):
        j = await create_jurisdiction(db)
        await db.commit()
        assert await has_running_job(db, j.id) is False

    async def test_pending_job(self, db):
        j = await create_jurisdiction(db)
        await create_monitoring_job(db, jurisdiction_id=j.id, status="pending")
        await db.commit()
        assert await has_running_job(db, j.id) is True

    async def test_running_job(self, db):
        j = await create_jurisdiction(db)
        await create_monitoring_job(db, jurisdiction_id=j.id, status="running")
        await db.commit()
        assert await has_running_job(db, j.id) is True

    async def test_completed_job_not_running(self, db):
        j = await create_jurisdiction(db)
        await create_monitoring_job(db, jurisdiction_id=j.id, status="completed")
        await db.commit()
        assert await has_running_job(db, j.id) is False


class TestSchedules:
    async def test_upsert_creates_new(self, db):
        j = await create_jurisdiction(db)
        await db.commit()

        schedule = await upsert_schedule(
            db, jurisdiction_id=j.id, enabled=True, cadence="daily",
        )
        assert schedule.id is not None
        assert schedule.enabled is True
        assert schedule.cadence == "daily"
        assert schedule.next_run_at is not None

    async def test_upsert_updates_existing(self, db):
        j = await create_jurisdiction(db)
        await db.commit()

        s1 = await upsert_schedule(db, jurisdiction_id=j.id, cadence="daily")
        await db.commit()
        s2 = await upsert_schedule(db, jurisdiction_id=j.id, cadence="weekly")
        assert s2.id == s1.id
        assert s2.cadence == "weekly"

    async def test_disabled_schedule_has_no_next_run(self, db):
        j = await create_jurisdiction(db)
        await db.commit()

        schedule = await upsert_schedule(
            db, jurisdiction_id=j.id, enabled=False, cadence="daily",
        )
        assert schedule.next_run_at is None

    async def test_get_schedule(self, db):
        j = await create_jurisdiction(db)
        await create_monitoring_schedule(db, jurisdiction_id=j.id, cadence="weekly")
        await db.commit()

        found = await get_schedule(db, "US")
        assert found is not None
        assert found.cadence == "weekly"

    async def test_get_schedule_not_found(self, db):
        found = await get_schedule(db, "XX-NOPE")
        assert found is None

    async def test_list_schedules_empty(self, db):
        schedules = await list_schedules(db)
        assert schedules == []

    async def test_list_schedules_filter_enabled(self, db):
        j1 = await create_jurisdiction(db, code="AA", name="A", path="AA", country_code="AA")
        j2 = await create_jurisdiction(db, code="BB", name="B", path="BB", country_code="BB")
        await create_monitoring_schedule(db, jurisdiction_id=j1.id, enabled=True)
        await create_monitoring_schedule(db, jurisdiction_id=j2.id, enabled=False)
        await db.commit()

        enabled = await list_schedules(db, enabled=True)
        assert len(enabled) == 1


class TestComputeNextRun:
    def test_daily(self):
        next_run = _compute_next_run("daily")
        assert next_run > datetime.now(UTC)

    def test_weekly(self):
        next_run = _compute_next_run("weekly")
        assert next_run > datetime.now(UTC)

    def test_monthly(self):
        next_run = _compute_next_run("monthly")
        assert next_run > datetime.now(UTC)

    def test_custom_cron(self):
        next_run = _compute_next_run("custom", "0 6 * * 1,4")
        assert next_run > datetime.now(UTC)


class TestValidateCronExpression:
    def test_valid(self):
        assert validate_cron_expression("0 3 * * *") is True
        assert validate_cron_expression("0 6 * * 1,4") is True
        assert validate_cron_expression("*/5 * * * *") is True

    def test_invalid(self):
        assert validate_cron_expression("not a cron") is False
        assert validate_cron_expression("") is False
