"""Tests for the triage runner — load batch + apply decisions."""

from decimal import Decimal

import pytest

from app.models.detected_change import DetectedChange
from app.services.prompts.triage import TriageDecision
from app.services.triage_job_service import _apply_decisions, _load_pending_items


async def _seed(db):
    from tests.factories import (
        create_jurisdiction,
        create_monitoring_job,
        create_tax_category,
        create_tax_rate,
        create_tax_rule,
    )

    country = await create_jurisdiction(db, code="DE", path="DE", country_code="DE")
    job = await create_monitoring_job(db, jurisdiction_id=country.id, status="completed")
    cat = await create_tax_category(db, code="city_tax_de", name="DE city tax")

    # Pending jurisdiction (from discovery)
    pending_juris = await create_jurisdiction(
        db, code="DE-BLN", name="Berlin", jurisdiction_type="city",
        path="DE.BLN", country_code="DE", parent_id=country.id,
        status="pending",
    )
    pending_juris.metadata_ = {
        "tax_summary": "Berlin charges 5% city tax",
        "discovery_source": "https://www.berlin.de/tax",
        "discovery_confidence": 0.92,
    }
    pending_juris.monitoring_job_id = job.id

    # Draft rate
    draft_rate = await create_tax_rate(
        db, jurisdiction_id=country.id, tax_category_id=cat.id,
        rate_value=0.05, status="draft",
    )
    draft_rate.monitoring_job_id = job.id
    draft_rate.source_url = "https://example.gov/de"
    draft_rate.authority_name = "DE Tax Authority"

    # Draft rule
    draft_rule = await create_tax_rule(
        db, jurisdiction_id=country.id, name="Children exempt", rule_type="exemption",
        status="draft",
    )

    # Pending detected_change linked to the draft rate
    change = DetectedChange(
        jurisdiction_id=country.id,
        change_type="new_tax",
        extracted_data={"name": "city_tax_de"},
        confidence=Decimal("0.85"),
        source_quote="The tax is 5%",
        applied_rate_id=draft_rate.id,
        review_status="pending",
        monitoring_job_id=job.id,
    )
    db.add(change)
    await db.flush()

    return {
        "country": country, "job": job, "draft_rate": draft_rate,
        "draft_rule": draft_rule, "pending_juris": pending_juris, "change": change,
    }


class TestLoadPendingItems:
    async def test_loads_all_four_types(self, db):
        seed = await _seed(db)
        await db.commit()

        items = await _load_pending_items(db, jurisdiction_code=None, max_items=50)
        types = sorted(it.item_type for it in items)
        assert types == ["change", "jurisdiction", "rate", "rule"]
        # Pending jurisdiction surfaces with the discovery metadata
        juris_item = next(it for it in items if it.item_type == "jurisdiction")
        assert juris_item.item_id == seed["pending_juris"].id
        assert juris_item.source_url == "https://www.berlin.de/tax"
        assert juris_item.ai_confidence == pytest.approx(0.92)

    async def test_filter_by_country_includes_descendants(self, db):
        seed = await _seed(db)
        await db.commit()

        items = await _load_pending_items(db, jurisdiction_code="DE", max_items=50)
        # All seeded items belong to DE or its descendants
        assert len(items) >= 4


class TestApplyDecisions:
    async def test_approve_rate_and_reject_rule(self, db):
        seed = await _seed(db)
        await db.commit()

        decisions = [
            TriageDecision(
                item_type="rate", item_id=seed["draft_rate"].id,
                action="approved", reasoning="Source verified", confidence=0.95,
                source_verified_url="https://example.gov/de",
            ),
            TriageDecision(
                item_type="rule", item_id=seed["draft_rule"].id,
                action="rejected", reasoning="Source contradicts",
                confidence=0.95,
            ),
        ]
        batch_ids = {
            "rate": {seed["draft_rate"].id},
            "rule": {seed["draft_rule"].id},
            "jurisdiction": set(), "change": set(),
        }
        summary = await _apply_decisions(db, decisions, batch_ids, job_id=seed["job"].id)
        await db.commit()

        assert summary["approved"] == 1
        assert summary["rejected"] == 1
        assert summary["deferred"] == 0

        await db.refresh(seed["draft_rate"])
        await db.refresh(seed["draft_rule"])
        assert seed["draft_rate"].status == "active"
        assert seed["draft_rule"].status == "rejected"
        # reviewed_by stamped as ai_triage
        assert seed["draft_rate"].reviewed_by == "ai_triage"

    async def test_low_confidence_approval_downgrades_to_deferred(self, db):
        seed = await _seed(db)
        await db.commit()

        decisions = [
            TriageDecision(
                item_type="rate", item_id=seed["draft_rate"].id,
                action="approved", reasoning="Mostly sure", confidence=0.6,
                source_verified_url="https://example.gov/de",
            ),
        ]
        batch_ids = {
            "rate": {seed["draft_rate"].id}, "rule": set(),
            "jurisdiction": set(), "change": set(),
        }
        summary = await _apply_decisions(db, decisions, batch_ids, job_id=seed["job"].id)
        assert summary["approved"] == 0
        assert summary["deferred"] == 1
        assert summary["skipped_low_confidence"] == 1
        await db.refresh(seed["draft_rate"])
        assert seed["draft_rate"].status == "draft"  # unchanged

    async def test_invalid_id_skipped_not_applied(self, db):
        seed = await _seed(db)
        await db.commit()

        decisions = [
            TriageDecision(
                item_type="rate", item_id=99999,  # not in batch
                action="approved", reasoning="hallucinated", confidence=0.95,
                source_verified_url="https://x.gov",
            ),
        ]
        batch_ids = {
            "rate": {seed["draft_rate"].id}, "rule": set(),
            "jurisdiction": set(), "change": set(),
        }
        summary = await _apply_decisions(db, decisions, batch_ids, job_id=seed["job"].id)
        assert summary["approved"] == 0
        assert summary["invalid_ids"] == [{"item_type": "rate", "item_id": 99999}]
        await db.refresh(seed["draft_rate"])
        assert seed["draft_rate"].status == "draft"

    async def test_duplicate_decision_logged_once(self, db):
        seed = await _seed(db)
        await db.commit()

        decisions = [
            TriageDecision(
                item_type="rate", item_id=seed["draft_rate"].id,
                action="approved", reasoning="ok", confidence=0.95,
                source_verified_url="https://x.gov",
            ),
            TriageDecision(
                item_type="rate", item_id=seed["draft_rate"].id,
                action="rejected", reasoning="oops", confidence=0.95,
            ),
        ]
        batch_ids = {
            "rate": {seed["draft_rate"].id}, "rule": set(),
            "jurisdiction": set(), "change": set(),
        }
        summary = await _apply_decisions(db, decisions, batch_ids, job_id=seed["job"].id)
        assert summary["approved"] == 1
        assert summary["rejected"] == 0
        assert summary["duplicate_decisions"] == [
            {"item_type": "rate", "item_id": seed["draft_rate"].id},
        ]

    async def test_approve_jurisdiction(self, db):
        seed = await _seed(db)
        await db.commit()

        decisions = [
            TriageDecision(
                item_type="jurisdiction", item_id=seed["pending_juris"].id,
                action="approved", reasoning="DE-BLN tax confirmed by Berlin official site",
                confidence=0.95, source_verified_url="https://www.berlin.de/tax",
            ),
        ]
        batch_ids = {
            "jurisdiction": {seed["pending_juris"].id},
            "rate": set(), "rule": set(), "change": set(),
        }
        summary = await _apply_decisions(db, decisions, batch_ids, job_id=seed["job"].id)
        await db.commit()
        assert summary["approved"] == 1
        await db.refresh(seed["pending_juris"])
        assert seed["pending_juris"].status == "active"
