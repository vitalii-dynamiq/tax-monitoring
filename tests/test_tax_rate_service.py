"""
Tests for app/services/tax_rate_service.py.

Uses async SQLite fixtures from conftest.py and factory helpers from factories.py.
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.schemas.tax_rate import RateType, TaxRateCreate
from app.services.tax_rate_service import (
    create_rate,
    create_rates_bulk,
    get_active_rates_for_jurisdiction,
    get_all_rates,
    get_rate_by_id,
    get_rules_for_rates,
    update_rate_status,
)
from tests.factories import (
    create_jurisdiction,
    create_tax_category,
    create_tax_rate,
    create_tax_rule,
    seed_nyc_hierarchy,
)

pytestmark = pytest.mark.asyncio


# ─── Helpers ─────────────────────────────────────────────────────────


async def _setup_two_jurisdictions(db):
    """Create two jurisdictions (US, CA) with one category and one rate each."""
    us = await create_jurisdiction(db, code="US", name="United States")
    ca = await create_jurisdiction(
        db, code="CA", name="Canada", country_code="CA", currency_code="CAD",
    )
    cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")

    rate_us = await create_tax_rate(
        db, jurisdiction_id=us.id, tax_category_id=cat.id,
        rate_type="percentage", rate_value=0.05, status="active",
        effective_start=date(2024, 1, 1), calculation_order=100,
    )
    rate_ca = await create_tax_rate(
        db, jurisdiction_id=ca.id, tax_category_id=cat.id,
        rate_type="percentage", rate_value=0.03, status="draft",
        effective_start=date(2024, 6, 1), calculation_order=100,
    )
    await db.flush()
    return us, ca, cat, rate_us, rate_ca


# ─── get_all_rates ───────────────────────────────────────────────────


class TestGetAllRates:
    async def test_no_filters_returns_all(self, db):
        us, ca, cat, rate_us, rate_ca = await _setup_two_jurisdictions(db)

        rates = await get_all_rates(db)

        assert len(rates) == 2
        ids = {r.id for r in rates}
        assert rate_us.id in ids
        assert rate_ca.id in ids

    async def test_filter_by_jurisdiction_code(self, db):
        us, ca, cat, rate_us, rate_ca = await _setup_two_jurisdictions(db)

        rates = await get_all_rates(db, jurisdiction_code="US")

        assert len(rates) == 1
        assert rates[0].id == rate_us.id

    async def test_filter_by_category_code(self, db):
        us, _, _, rate_us, _ = await _setup_two_jurisdictions(db)
        other_cat = await create_tax_category(
            db, code="flat_fee", name="Flat Fee",
            level_0="accommodation", level_1="flat", level_2="per_night",
        )
        rate_flat = await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=other_cat.id,
            rate_type="flat", rate_value=2.0, calculation_order=200,
        )
        await db.flush()

        rates = await get_all_rates(db, category_code="flat_fee")

        assert len(rates) == 1
        assert rates[0].id == rate_flat.id

    async def test_filter_by_status(self, db):
        us, ca, cat, rate_us, rate_ca = await _setup_two_jurisdictions(db)

        rates = await get_all_rates(db, status="draft")

        assert len(rates) == 1
        assert rates[0].id == rate_ca.id

    async def test_filter_by_effective_date(self, db):
        us, ca, cat, rate_us, rate_ca = await _setup_two_jurisdictions(db)

        # Date before CA rate starts -> only US rate
        rates = await get_all_rates(db, effective_date=date(2024, 3, 1))

        assert len(rates) == 1
        assert rates[0].id == rate_us.id

    async def test_filter_by_effective_date_includes_both(self, db):
        us, ca, cat, rate_us, rate_ca = await _setup_two_jurisdictions(db)

        # Date after both rates start
        rates = await get_all_rates(db, effective_date=date(2024, 7, 1))

        assert len(rates) == 2

    async def test_effective_date_respects_end(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id,
            effective_start=date(2023, 1, 1), effective_end=date(2024, 1, 1),
        )
        await db.flush()

        # After the end date -> should be excluded
        rates = await get_all_rates(db, effective_date=date(2024, 6, 1))

        assert len(rates) == 0

    async def test_limit_and_offset(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")

        for i in range(5):
            await create_tax_rate(
                db, jurisdiction_id=us.id, tax_category_id=cat.id,
                rate_value=float(i), calculation_order=100 + i,
            )
        await db.flush()

        page1 = await get_all_rates(db, limit=2, offset=0)
        page2 = await get_all_rates(db, limit=2, offset=2)
        page3 = await get_all_rates(db, limit=2, offset=4)

        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1


# ─── get_rate_by_id ──────────────────────────────────────────────────


class TestGetRateById:
    async def test_found(self, db):
        data = await seed_nyc_hierarchy(db)
        rate = data["rate_pct"]

        result = await get_rate_by_id(db, rate.id)

        assert result is not None
        assert result.id == rate.id
        assert result.rate_type == "percentage"

    async def test_not_found(self, db):
        result = await get_rate_by_id(db, 99999)

        assert result is None


# ─── get_active_rates_for_jurisdiction ───────────────────────────────


class TestGetActiveRatesForJurisdiction:
    async def test_rate_in_range(self, db):
        data = await seed_nyc_hierarchy(db)
        nyc = data["nyc"]

        rates = await get_active_rates_for_jurisdiction(
            db, [nyc.id], stay_date=date(2025, 6, 15),
        )

        assert len(rates) == 2
        ids = {r.id for r in rates}
        assert data["rate_pct"].id in ids
        assert data["rate_flat"].id in ids

    async def test_expired_rate_filtered_out(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")

        await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id,
            effective_start=date(2023, 1, 1), effective_end=date(2024, 1, 1),
            status="active",
        )
        current = await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id,
            effective_start=date(2024, 1, 1),
            status="active", calculation_order=200,
        )
        await db.flush()

        rates = await get_active_rates_for_jurisdiction(
            db, [us.id], stay_date=date(2024, 6, 1),
        )

        assert len(rates) == 1
        assert rates[0].id == current.id

    async def test_not_yet_effective_filtered_out(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")

        await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id,
            effective_start=date(2026, 1, 1), status="active",
        )
        await db.flush()

        rates = await get_active_rates_for_jurisdiction(
            db, [us.id], stay_date=date(2025, 6, 1),
        )

        assert len(rates) == 0

    async def test_draft_status_filtered_out(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")

        await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id,
            effective_start=date(2024, 1, 1), status="draft",
        )
        await db.flush()

        rates = await get_active_rates_for_jurisdiction(
            db, [us.id], stay_date=date(2025, 6, 1),
        )

        assert len(rates) == 0

    async def test_multiple_jurisdictions_in_chain(self, db):
        data = await seed_nyc_hierarchy(db)
        us, ny, nyc = data["us"], data["ny"], data["nyc"]

        # Add a state-level rate to NY
        cat = data["occ_pct_cat"]
        state_rate = await create_tax_rate(
            db, jurisdiction_id=ny.id, tax_category_id=cat.id,
            rate_type="percentage", rate_value=0.04,
            effective_start=date(2024, 1, 1), status="active",
            calculation_order=50,
        )
        await db.commit()

        # Query the full chain [us, ny, nyc]
        rates = await get_active_rates_for_jurisdiction(
            db, [us.id, ny.id, nyc.id], stay_date=date(2025, 6, 15),
        )

        ids = {r.id for r in rates}
        # Child overrides parent for same tax_category: NYC rate_pct
        # overrides NY state_rate (same occ_pct category). rate_flat
        # has a different category so it's kept.
        assert data["rate_pct"].id in ids  # NYC occ_pct overrides NY occ_pct
        assert data["rate_flat"].id in ids  # different category, kept
        assert state_rate.id not in ids  # overridden by deeper NYC rate

    async def test_rates_ordered_by_calculation_order(self, db):
        data = await seed_nyc_hierarchy(db)
        nyc = data["nyc"]

        rates = await get_active_rates_for_jurisdiction(
            db, [nyc.id], stay_date=date(2025, 6, 15),
        )

        orders = [r.calculation_order for r in rates]
        assert orders == sorted(orders)


# ─── get_rules_for_rates ─────────────────────────────────────────────


class TestGetRulesForRates:
    async def test_rules_grouped_by_rate_id(self, db):
        data = await seed_nyc_hierarchy(db)
        rate_pct = data["rate_pct"]
        rate_flat = data["rate_flat"]
        nyc = data["nyc"]

        # The seed already creates one rule for rate_pct.
        # Add a rule for rate_flat as well.
        rule_flat = await create_tax_rule(
            db, jurisdiction_id=nyc.id, rule_type="surcharge",
            name="Weekend Surcharge", priority=50,
            conditions={"field": "stay_day_of_week", "op": "in", "value": [5, 6]},
            action={"type": "add_flat", "value": 1.0},
            effective_start=date(2024, 1, 1), tax_rate_id=rate_flat.id,
        )
        await db.commit()

        rules_map, _jurisdiction_rules = await get_rules_for_rates(
            db, [rate_pct.id, rate_flat.id], stay_date=date(2025, 6, 15),
        )

        assert rate_pct.id in rules_map
        assert rate_flat.id in rules_map
        assert len(rules_map[rate_pct.id]) >= 1
        assert len(rules_map[rate_flat.id]) >= 1

        # Verify the right rules landed in the right bucket
        flat_rule_ids = {r.id for r in rules_map[rate_flat.id]}
        assert rule_flat.id in flat_rule_ids

    async def test_no_rules_returns_empty_dict(self, db):
        rules_map = await get_rules_for_rates(db, [], stay_date=date(2025, 6, 15))

        assert rules_map == {}

    async def test_no_matching_rules_for_rate(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        rate = await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id,
        )
        await db.flush()

        rules_map = await get_rules_for_rates(
            db, [rate.id], stay_date=date(2025, 6, 15),
        )

        # Rate exists but has no rules -> rate_id absent from dict
        assert rate.id not in rules_map

    async def test_expired_rules_filtered_out(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        rate = await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id,
        )

        await create_tax_rule(
            db, jurisdiction_id=us.id, name="Old Rule",
            effective_start=date(2022, 1, 1), effective_end=date(2023, 1, 1),
            tax_rate_id=rate.id,
        )
        await db.flush()

        rules_map = await get_rules_for_rates(
            db, [rate.id], stay_date=date(2025, 6, 15),
        )

        assert rate.id not in rules_map

    async def test_rules_ordered_by_priority_desc(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        rate = await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id,
        )

        await create_tax_rule(
            db, jurisdiction_id=us.id, name="Low Priority",
            priority=10, tax_rate_id=rate.id,
        )
        await create_tax_rule(
            db, jurisdiction_id=us.id, name="High Priority",
            priority=200, tax_rate_id=rate.id,
        )
        await create_tax_rule(
            db, jurisdiction_id=us.id, name="Mid Priority",
            priority=50, tax_rate_id=rate.id,
        )
        await db.flush()

        rules_map = await get_rules_for_rates(
            db, [rate.id], stay_date=date(2025, 6, 15),
        )

        priorities = [r.priority for r in rules_map[rate.id]]
        assert priorities == sorted(priorities, reverse=True)


# ─── create_rate ─────────────────────────────────────────────────────


class TestCreateRate:
    async def test_creates_with_correct_fields(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        await db.flush()

        schema = TaxRateCreate(
            jurisdiction_code="US",
            tax_category_code="occ_pct",
            rate_type=RateType.percentage,
            rate_value=0.07,
            currency_code="USD",
            effective_start=date(2025, 1, 1),
            effective_end=date(2026, 12, 31),
            calculation_order=150,
            legal_reference="Tax Code Section 11-2501",
            source_url="https://example.gov/tax",
            authority_name="NYC Dept of Finance",
            status="draft",
            created_by="test_user",
        )

        rate = await create_rate(db, schema)

        assert rate.id is not None
        assert rate.jurisdiction_id == us.id
        assert rate.tax_category_id == cat.id
        assert rate.rate_type == "percentage"
        assert float(rate.rate_value) == pytest.approx(0.07)
        assert rate.currency_code == "USD"
        assert rate.effective_start == date(2025, 1, 1)
        assert rate.effective_end == date(2026, 12, 31)
        assert rate.calculation_order == 150
        assert rate.legal_reference == "Tax Code Section 11-2501"
        assert rate.source_url == "https://example.gov/tax"
        assert rate.authority_name == "NYC Dept of Finance"
        assert rate.status == "draft"
        assert rate.created_by == "test_user"

    async def test_create_rate_logs_audit_entry(self, db):
        await create_jurisdiction(db, code="US", name="United States")
        await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        await db.flush()

        schema = TaxRateCreate(
            jurisdiction_code="US",
            tax_category_code="occ_pct",
            rate_type=RateType.percentage,
            rate_value=0.05,
            effective_start=date(2025, 1, 1),
            created_by="auditor",
        )

        rate = await create_rate(db, schema)

        result = await db.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "tax_rate",
                AuditLog.entity_id == rate.id,
                AuditLog.action == "create",
            )
        )
        log = result.scalar_one_or_none()

        assert log is not None
        assert log.changed_by == "auditor"
        assert log.change_source == "api"
        assert log.new_values["jurisdiction_code"] == "US"
        assert log.new_values["tax_category_code"] == "occ_pct"
        assert log.new_values["rate_type"] == "percentage"
        assert log.new_values["status"] == "active"

    async def test_create_rate_invalid_jurisdiction(self, db):
        await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        await db.flush()

        schema = TaxRateCreate(
            jurisdiction_code="NONEXISTENT",
            tax_category_code="occ_pct",
            rate_type=RateType.percentage,
            rate_value=0.05,
            effective_start=date(2025, 1, 1),
        )

        with pytest.raises(ValueError, match="Jurisdiction not found"):
            await create_rate(db, schema)

    async def test_create_rate_invalid_category(self, db):
        await create_jurisdiction(db, code="US", name="United States")
        await db.flush()

        schema = TaxRateCreate(
            jurisdiction_code="US",
            tax_category_code="NONEXISTENT",
            rate_type=RateType.percentage,
            rate_value=0.05,
            effective_start=date(2025, 1, 1),
        )

        with pytest.raises(ValueError, match="Tax category not found"):
            await create_rate(db, schema)


# ─── create_rates_bulk ───────────────────────────────────────────────


class TestCreateRatesBulk:
    async def test_creates_multiple_rates(self, db):
        await create_jurisdiction(db, code="US", name="United States")
        await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        await create_tax_category(
            db, code="flat_fee", name="Flat Fee",
            level_0="accommodation", level_1="flat", level_2="per_night",
        )
        await db.flush()

        schemas = [
            TaxRateCreate(
                jurisdiction_code="US",
                tax_category_code="occ_pct",
                rate_type=RateType.percentage,
                rate_value=0.05,
                effective_start=date(2025, 1, 1),
            ),
            TaxRateCreate(
                jurisdiction_code="US",
                tax_category_code="flat_fee",
                rate_type=RateType.flat,
                rate_value=3.50,
                effective_start=date(2025, 1, 1),
            ),
        ]

        rates = await create_rates_bulk(db, schemas)

        assert len(rates) == 2
        assert rates[0].rate_type == "percentage"
        assert rates[1].rate_type == "flat"
        assert all(r.id is not None for r in rates)


# ─── update_rate_status ──────────────────────────────────────────────


class TestUpdateRateStatus:
    async def test_approve_draft_to_active(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        rate = await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id, status="draft",
        )
        await db.flush()

        updated = await update_rate_status(
            db, rate.id, new_status="active",
            reviewed_by="admin@example.com",
            review_notes="Verified against official gazette",
        )

        assert updated is not None
        assert updated.status == "active"
        assert updated.reviewed_by == "admin@example.com"
        assert updated.reviewed_at is not None
        assert updated.review_notes == "Verified against official gazette"

    async def test_reject_draft_to_rejected(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        rate = await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id, status="draft",
        )
        await db.flush()

        updated = await update_rate_status(
            db, rate.id, new_status="rejected",
            reviewed_by="reviewer@example.com",
            review_notes="Rate value incorrect",
        )

        assert updated is not None
        assert updated.status == "rejected"
        assert updated.reviewed_by == "reviewer@example.com"
        assert updated.review_notes == "Rate value incorrect"

    async def test_audit_log_entry_created(self, db):
        us = await create_jurisdiction(db, code="US", name="United States")
        cat = await create_tax_category(db, code="occ_pct", name="Occupancy Tax")
        rate = await create_tax_rate(
            db, jurisdiction_id=us.id, tax_category_id=cat.id, status="draft",
        )
        await db.flush()

        await update_rate_status(
            db, rate.id, new_status="active",
            reviewed_by="admin@example.com",
            review_notes="Approved after review",
        )

        result = await db.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "tax_rate",
                AuditLog.entity_id == rate.id,
                AuditLog.action == "status_change",
            )
        )
        log = result.scalar_one_or_none()

        assert log is not None
        assert log.old_values == {"status": "draft"}
        assert log.new_values == {"status": "active"}
        assert log.changed_by == "admin@example.com"
        assert log.change_source == "api"
        assert log.change_reason == "Approved after review"

    async def test_update_nonexistent_rate_returns_none(self, db):
        result = await update_rate_status(
            db, 99999, new_status="active",
            reviewed_by="admin@example.com",
        )

        assert result is None
