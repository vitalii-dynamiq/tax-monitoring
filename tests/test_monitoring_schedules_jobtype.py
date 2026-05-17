"""Tests for per-job_type monitoring schedules and bulk operations."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.monitoring_job_service import (
    bulk_update_schedules,
    create_job,
    get_schedule,
    has_running_job,
    list_schedules,
    upsert_schedule,
)
from tests.factories import (
    create_jurisdiction,
    create_monitoring_job,
    create_monitoring_schedule,
)


class TestPerJobTypeSchedules:
    async def test_separate_monitoring_and_discovery_schedules(self, db):
        country = await create_jurisdiction(db, code="DE", path="DE", country_code="DE")
        await db.commit()

        mon = await upsert_schedule(
            db, jurisdiction_id=country.id, enabled=True, cadence="weekly",
            job_type="monitoring",
        )
        disc = await upsert_schedule(
            db, jurisdiction_id=country.id, enabled=False, cadence="monthly",
            job_type="discovery",
        )
        assert mon.id != disc.id
        assert mon.job_type == "monitoring"
        assert disc.job_type == "discovery"

    async def test_upsert_targets_correct_row_by_job_type(self, db):
        country = await create_jurisdiction(db, code="FR", path="FR", country_code="FR")
        await db.commit()

        s1 = await upsert_schedule(
            db, jurisdiction_id=country.id, cadence="daily", job_type="monitoring",
        )
        await db.commit()
        s2 = await upsert_schedule(
            db, jurisdiction_id=country.id, cadence="monthly", job_type="discovery",
        )
        await db.commit()
        s3 = await upsert_schedule(
            db, jurisdiction_id=country.id, cadence="weekly", job_type="monitoring",
        )
        assert s3.id == s1.id
        assert s3.cadence == "weekly"
        # Discovery row untouched
        await db.refresh(s2)
        assert s2.cadence == "monthly"

    async def test_get_schedule_filters_by_job_type(self, db):
        country = await create_jurisdiction(db, code="IT", path="IT", country_code="IT")
        await create_monitoring_schedule(
            db, jurisdiction_id=country.id, cadence="weekly", job_type="monitoring",
        )
        await create_monitoring_schedule(
            db, jurisdiction_id=country.id, cadence="monthly", job_type="discovery",
        )
        await db.commit()

        mon = await get_schedule(db, "IT", job_type="monitoring")
        assert mon is not None and mon.cadence == "weekly"
        disc = await get_schedule(db, "IT", job_type="discovery")
        assert disc is not None and disc.cadence == "monthly"


class TestDiscoveryAutoSeed:
    async def test_discovery_list_seeds_countries(self, db):
        await create_jurisdiction(db, code="ES", path="ES", country_code="ES")
        await create_jurisdiction(db, code="PT", path="PT", country_code="PT")
        # Non-country should not be seeded
        parent = await create_jurisdiction(
            db, code="GR", path="GR", country_code="GR",
        )
        await create_jurisdiction(
            db, code="GR-ATH", name="Athens", jurisdiction_type="city",
            path="GR.ATH", country_code="GR", parent_id=parent.id,
        )
        await db.commit()

        discovery = await list_schedules(db, job_type="discovery")
        codes = sorted(s.jurisdiction.code for s in discovery)
        assert codes == ["ES", "GR", "PT"]
        assert all(s.enabled is False for s in discovery)

    async def test_monitoring_list_seeds_countries(self, db):
        """Regression: monitoring tab must auto-seed one row per country
        the same way discovery does. Caught the '105 schedules' bug."""
        await create_jurisdiction(db, code="ES", path="ES", country_code="ES")
        await create_jurisdiction(db, code="PT", path="PT", country_code="PT")
        # Non-country should not get a monitoring schedule either
        parent = await create_jurisdiction(db, code="GR", path="GR", country_code="GR")
        await create_jurisdiction(
            db, code="GR-ATH", name="Athens", jurisdiction_type="city",
            path="GR.ATH", country_code="GR", parent_id=parent.id,
        )
        await db.commit()

        monitoring = await list_schedules(db, job_type="monitoring")
        codes = sorted(s.jurisdiction.code for s in monitoring)
        assert codes == ["ES", "GR", "PT"]
        assert all(s.enabled is False for s in monitoring)
        assert all(s.cadence == "weekly" for s in monitoring)


class TestHasRunningJobByType:
    async def test_does_not_cross_block(self, db):
        country = await create_jurisdiction(db, code="NL", path="NL", country_code="NL")
        await create_monitoring_job(
            db, jurisdiction_id=country.id, status="running", job_type="monitoring",
        )
        await db.commit()

        assert await has_running_job(db, country.id, job_type="monitoring") is True
        assert await has_running_job(db, country.id, job_type="discovery") is False
        # Without filter, any running job blocks
        assert await has_running_job(db, country.id) is True


class TestBulkUpdateSchedules:
    async def test_bulk_enable_creates_or_updates(self, db):
        j1 = await create_jurisdiction(db, code="AT", path="AT", country_code="AT")
        j2 = await create_jurisdiction(db, code="BE", path="BE", country_code="BE")
        await db.commit()

        updated, errors = await bulk_update_schedules(
            db,
            jurisdiction_codes=["AT", "BE"],
            job_type="monitoring",
            action="enable",
        )
        assert errors == []
        assert len(updated) == 2
        assert all(s.enabled is True for s in updated)

    async def test_bulk_partial_failure(self, db):
        await create_jurisdiction(db, code="CH", path="CH", country_code="CH")
        await db.commit()

        updated, errors = await bulk_update_schedules(
            db,
            jurisdiction_codes=["CH", "ZZ-DOES-NOT-EXIST"],
            job_type="monitoring",
            action="disable",
        )
        assert len(updated) == 1
        assert len(errors) == 1
        assert errors[0]["code"] == "ZZ-DOES-NOT-EXIST"

    async def test_bulk_rejects_discovery_for_non_country(self, db):
        country = await create_jurisdiction(db, code="DK", path="DK", country_code="DK")
        await create_jurisdiction(
            db, code="DK-CPH", name="Copenhagen", jurisdiction_type="city",
            path="DK.CPH", country_code="DK", parent_id=country.id,
        )
        await db.commit()

        updated, errors = await bulk_update_schedules(
            db,
            jurisdiction_codes=["DK", "DK-CPH"],
            job_type="discovery",
            action="enable",
        )
        assert len(updated) == 1 and updated[0].jurisdiction.code == "DK"
        assert len(errors) == 1 and errors[0]["code"] == "DK-CPH"

    async def test_bulk_set_cadence_requires_cadence(self, db):
        with pytest.raises(ValueError, match="cadence is required"):
            await bulk_update_schedules(
                db,
                jurisdiction_codes=["AT"],
                job_type="monitoring",
                action="set_cadence",
                cadence=None,
            )


class TestSchedulerDispatch:
    async def test_dispatch_routes_by_job_type(self, db):
        country = await create_jurisdiction(db, code="NO", path="NO", country_code="NO")
        from datetime import UTC, datetime, timedelta

        past = datetime.now(UTC) - timedelta(minutes=5)
        await create_monitoring_schedule(
            db, jurisdiction_id=country.id, enabled=True, cadence="weekly",
            next_run_at=past, job_type="discovery",
        )
        await db.commit()

        # Patch dispatch targets and session factory to use our test session.
        with patch(
            "app.services.scheduler.async_session_factory"
        ) as mock_factory, patch(
            "app.services.discovery_job_service.run_discovery_job",
            new=AsyncMock(),
        ) as mock_disc, patch(
            "app.services.monitoring_job_service.run_monitoring_job_with_limits",
            new=AsyncMock(),
        ) as mock_mon:
            class _Ctx:
                async def __aenter__(self_inner):
                    return db
                async def __aexit__(self_inner, *_):
                    return False

            mock_factory.return_value = _Ctx()

            from app.services.scheduler import check_due_schedules

            await check_due_schedules()

        # asyncio.create_task fires-and-forgets; the mocked coro should be
        # called once for discovery and not for monitoring.
        # Note: create_task wraps the awaitable, so we assert the coroutine
        # was *invoked* (i.e. the mock has a call recorded).
        assert mock_disc.call_count == 1
        assert mock_mon.call_count == 0

    async def test_create_job_with_discovery_type(self, db):
        country = await create_jurisdiction(db, code="SE", path="SE", country_code="SE")
        await db.commit()

        job = await create_job(
            db, jurisdiction_id=country.id, trigger_type="scheduled",
            job_type="discovery",
        )
        assert job.job_type == "discovery"
