"""
Tests for the monitoring service (sources, changes, review).
"""

import pytest

from app.schemas.monitoring import DetectedChangeCreate, MonitoredSourceCreate
from app.services.monitoring_service import (
    create_change,
    create_source,
    get_all_changes,
    get_all_sources,
    get_change_by_id,
    get_source_by_id,
    review_change,
)
from tests.factories import create_detected_change, create_jurisdiction, create_monitored_source


class TestMonitoredSources:
    async def test_create_source_with_jurisdiction(self, db):
        j = await create_jurisdiction(db, code="US", name="United States")
        await db.commit()

        data = MonitoredSourceCreate(
            jurisdiction_code="US",
            url="https://example.gov/taxes",
            source_type="government",
        )
        source = await create_source(db, data)
        assert source.url == "https://example.gov/taxes"
        assert source.jurisdiction_id == j.id
        assert source.source_type == "government"

    async def test_create_source_unknown_jurisdiction_raises(self, db):
        data = MonitoredSourceCreate(
            jurisdiction_code="XX-NOPE",
            url="https://example.com",
            source_type="news",
        )
        with pytest.raises(ValueError, match="Jurisdiction not found"):
            await create_source(db, data)

    async def test_get_all_sources_empty(self, db):
        sources = await get_all_sources(db)
        assert sources == []

    async def test_get_all_sources_returns_all(self, db):
        j = await create_jurisdiction(db)
        await create_monitored_source(db, jurisdiction_id=j.id, url="https://a.gov")
        await create_monitored_source(db, jurisdiction_id=j.id, url="https://b.gov")
        await db.commit()

        sources = await get_all_sources(db)
        assert len(sources) == 2

    async def test_get_all_sources_filter_by_jurisdiction(self, db):
        j1 = await create_jurisdiction(db, code="AA", name="A", path="AA", country_code="AA")
        j2 = await create_jurisdiction(db, code="BB", name="B", path="BB", country_code="BB")
        await create_monitored_source(db, jurisdiction_id=j1.id, url="https://a.gov")
        await create_monitored_source(db, jurisdiction_id=j2.id, url="https://b.gov")
        await db.commit()

        sources = await get_all_sources(db, jurisdiction_code="AA")
        assert len(sources) == 1
        assert sources[0].url == "https://a.gov"

    async def test_get_source_by_id(self, db):
        j = await create_jurisdiction(db)
        source = await create_monitored_source(db, jurisdiction_id=j.id)
        await db.commit()

        found = await get_source_by_id(db, source.id)
        assert found is not None
        assert found.id == source.id

    async def test_get_source_by_id_not_found(self, db):
        found = await get_source_by_id(db, 99999)
        assert found is None


class TestDetectedChanges:
    async def test_create_change(self, db):
        j = await create_jurisdiction(db)
        await db.commit()

        data = DetectedChangeCreate(
            jurisdiction_code="US",
            change_type="new_tax",
            extracted_data={"rate_type": "percentage", "rate_value": 5.0},
            confidence=0.9,
            source_quote="Tax is 5%.",
        )
        change = await create_change(db, data)
        assert change.change_type == "new_tax"
        assert change.confidence == pytest.approx(0.9, abs=0.01)
        assert change.jurisdiction_id == j.id

    async def test_get_all_changes_empty(self, db):
        changes = await get_all_changes(db)
        assert changes == []

    async def test_get_all_changes_filter_by_review_status(self, db):
        j = await create_jurisdiction(db)
        await create_detected_change(db, jurisdiction_id=j.id, review_status="pending")
        await create_detected_change(db, jurisdiction_id=j.id, review_status="approved")
        await db.commit()

        pending = await get_all_changes(db, review_status="pending")
        assert len(pending) == 1
        assert pending[0].review_status == "pending"

    async def test_get_change_by_id(self, db):
        j = await create_jurisdiction(db)
        change = await create_detected_change(db, jurisdiction_id=j.id)
        await db.commit()

        found = await get_change_by_id(db, change.id)
        assert found is not None

    async def test_get_change_by_id_not_found(self, db):
        found = await get_change_by_id(db, 99999)
        assert found is None


class TestReviewChange:
    async def test_approve_change(self, db):
        j = await create_jurisdiction(db)
        change = await create_detected_change(db, jurisdiction_id=j.id, review_status="pending")
        await db.commit()

        result = await review_change(db, change.id, "approved", reviewed_by="admin")
        assert result is not None
        assert result.review_status == "approved"
        assert result.reviewed_by == "admin"
        assert result.reviewed_at is not None

    async def test_reject_change_with_notes(self, db):
        j = await create_jurisdiction(db)
        change = await create_detected_change(db, jurisdiction_id=j.id)
        await db.commit()

        result = await review_change(
            db, change.id, "rejected",
            reviewed_by="admin", review_notes="Duplicate entry",
        )
        assert result.review_status == "rejected"
        assert result.review_notes == "Duplicate entry"

    async def test_review_nonexistent_returns_none(self, db):
        result = await review_change(db, 99999, "approved")
        assert result is None
