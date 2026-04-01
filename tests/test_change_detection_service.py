"""
Tests for the change detection service.

Covers pure helpers (_parse_date, _convert_rate_value, _find_matching_rate,
_find_matching_rule) and async DB functions (_create_draft_rate,
_create_draft_rule, process_ai_results).
"""

from datetime import date

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.detected_change import DetectedChange
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule
from app.services.change_detection_service import (
    _convert_rate_value,
    _create_draft_rate,
    _create_draft_rule,
    _find_matching_rate,
    _find_matching_rule,
    _parse_date,
    process_ai_results,
)
from app.services.prompts.output_schema import (
    AIExtractedRate,
    AIExtractedRule,
    AIMonitoringResult,
)
from tests.factories import (
    create_tax_rate,
    create_tax_rule,
    seed_nyc_hierarchy,
)

# ─── Helpers for building Pydantic test objects ────────────────────


def _make_extracted_rate(
    *,
    change_type: str = "new",
    tax_category_code: str = "occ_pct",
    rate_type: str = "percentage",
    rate_value: float | None = 5.875,
    effective_start: str = "2025-07-01",
    source_quote: str = "The new occupancy tax rate is 5.875%.",
    confidence: float = 0.90,
    **kwargs,
) -> AIExtractedRate:
    return AIExtractedRate(
        change_type=change_type,
        tax_category_code=tax_category_code,
        rate_type=rate_type,
        rate_value=rate_value,
        effective_start=effective_start,
        source_quote=source_quote,
        confidence=confidence,
        **kwargs,
    )


def _make_extracted_rule(
    *,
    change_type: str = "new",
    rule_type: str = "exemption",
    name: str = "Long Stay Exemption",
    effective_start: str = "2025-07-01",
    source_quote: str = "Stays exceeding 180 days are exempt.",
    confidence: float = 0.85,
    **kwargs,
) -> AIExtractedRule:
    return AIExtractedRule(
        change_type=change_type,
        rule_type=rule_type,
        name=name,
        effective_start=effective_start,
        source_quote=source_quote,
        confidence=confidence,
        **kwargs,
    )


# ─── _parse_date ───────────────────────────────────────────────────


class TestParseDate:
    def test_valid_iso_date(self):
        result = _parse_date("2025-03-15")
        assert result == date(2025, 3, 15)

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_date("") is None


# ─── _convert_rate_value ───────────────────────────────────────────


class TestConvertRateValue:
    def test_percentage_divided_by_100(self):
        extracted = _make_extracted_rate(
            rate_type="percentage", rate_value=5.875, change_type="unchanged",
        )
        assert _convert_rate_value(extracted) == pytest.approx(0.05875)

    def test_flat_stored_as_is(self):
        extracted = _make_extracted_rate(
            rate_type="flat",
            rate_value=2.50,
            change_type="unchanged",
        )
        assert _convert_rate_value(extracted) == pytest.approx(2.50)

    def test_none_value_returns_none(self):
        extracted = _make_extracted_rate(
            rate_type="tiered",
            rate_value=None,
            change_type="unchanged",
            tiers=[{"min": 0, "max": 100, "rate_value": 2.0}],
        )
        assert _convert_rate_value(extracted) is None


# ─── _find_matching_rate ───────────────────────────────────────────


class TestFindMatchingRate:
    @pytest.mark.asyncio
    async def test_match_found_by_category_code(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rate(
            tax_category_code="occ_pct", change_type="changed",
        )
        # seed["rate_pct"] is active with category code "occ_pct"
        result = _find_matching_rate(extracted, [seed["rate_pct"], seed["rate_flat"]])
        assert result is not None
        assert result.id == seed["rate_pct"].id

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rate(
            tax_category_code="vat_standard", change_type="new",
        )
        result = _find_matching_rate(extracted, [seed["rate_pct"], seed["rate_flat"]])
        assert result is None

    @pytest.mark.asyncio
    async def test_inactive_rate_not_matched(self, db):
        """Only active rates should be returned."""
        seed = await seed_nyc_hierarchy(db)
        # Create an inactive rate with the same category
        inactive_rate = await create_tax_rate(
            db,
            jurisdiction_id=seed["nyc"].id,
            tax_category_id=seed["occ_pct_cat"].id,
            rate_type="percentage",
            rate_value=0.04,
            status="superseded",
        )
        await db.flush()

        extracted = _make_extracted_rate(
            tax_category_code="occ_pct", change_type="changed",
        )
        # When list contains only the inactive rate, no match should be found
        result = _find_matching_rate(extracted, [inactive_rate])
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_rates_picks_active_one(self, db):
        """When multiple rates exist for the same category, pick the active one."""
        seed = await seed_nyc_hierarchy(db)
        inactive_rate = await create_tax_rate(
            db,
            jurisdiction_id=seed["nyc"].id,
            tax_category_id=seed["occ_pct_cat"].id,
            rate_type="percentage",
            rate_value=0.04,
            status="superseded",
        )
        await db.flush()

        extracted = _make_extracted_rate(
            tax_category_code="occ_pct", change_type="changed",
        )
        # Both inactive and active in list; active should be matched
        result = _find_matching_rate(
            extracted, [inactive_rate, seed["rate_pct"]]
        )
        assert result is not None
        assert result.id == seed["rate_pct"].id
        assert result.status == "active"


# ─── _find_matching_rule ──────────────────────────────────────────


class TestFindMatchingRule:
    @pytest.mark.asyncio
    async def test_match_found_by_name_and_type(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rule(
            name="Long Stay Exemption",
            rule_type="exemption",
            change_type="changed",
        )
        result = _find_matching_rule(extracted, [seed["rule_exempt"]])
        assert result is not None
        assert result.id == seed["rule_exempt"].id

    @pytest.mark.asyncio
    async def test_no_match_returns_none(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rule(
            name="Nonexistent Rule",
            rule_type="exemption",
            change_type="new",
        )
        result = _find_matching_rule(extracted, [seed["rule_exempt"]])
        assert result is None

    @pytest.mark.asyncio
    async def test_wrong_rule_type_no_match(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rule(
            name="Long Stay Exemption",
            rule_type="surcharge",  # different type
            change_type="changed",
        )
        result = _find_matching_rule(extracted, [seed["rule_exempt"]])
        assert result is None

    @pytest.mark.asyncio
    async def test_inactive_rule_not_matched(self, db):
        seed = await seed_nyc_hierarchy(db)
        inactive_rule = await create_tax_rule(
            db,
            jurisdiction_id=seed["nyc"].id,
            rule_type="exemption",
            name="Long Stay Exemption",
            status="superseded",
        )
        await db.flush()

        extracted = _make_extracted_rule(
            name="Long Stay Exemption",
            rule_type="exemption",
            change_type="changed",
        )
        result = _find_matching_rule(extracted, [inactive_rule])
        assert result is None


# ─── _create_draft_rate ────────────────────────────────────────────


class TestCreateDraftRate:
    @pytest.mark.asyncio
    async def test_new_rate_version_1(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rate(
            change_type="new",
            tax_category_code="occ_pct",
            rate_type="percentage",
            rate_value=6.0,
        )
        draft = await _create_draft_rate(
            db, seed["nyc"], extracted, current_rate=None, job_id=1
        )
        assert draft is not None
        assert draft.version == 1
        assert draft.supersedes_id is None
        assert draft.status == "draft"
        assert draft.created_by == "ai_monitoring"
        assert float(draft.rate_value) == pytest.approx(0.06)  # 6.0 / 100

    @pytest.mark.asyncio
    async def test_changed_rate_version_incremented(self, db):
        seed = await seed_nyc_hierarchy(db)
        current = seed["rate_pct"]  # version=1

        extracted = _make_extracted_rate(
            change_type="changed",
            tax_category_code="occ_pct",
            rate_type="percentage",
            rate_value=6.5,
        )
        draft = await _create_draft_rate(
            db, seed["nyc"], extracted, current_rate=current, job_id=1
        )
        assert draft is not None
        assert draft.version == current.version + 1
        assert draft.supersedes_id == current.id
        assert float(draft.rate_value) == pytest.approx(0.065)

    @pytest.mark.asyncio
    async def test_missing_category_returns_none(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rate(
            change_type="new",
            tax_category_code="nonexistent_code",
            rate_type="percentage",
            rate_value=3.0,
        )
        draft = await _create_draft_rate(
            db, seed["nyc"], extracted, current_rate=None, job_id=1
        )
        assert draft is None

    @pytest.mark.asyncio
    async def test_flat_rate_stored_as_is(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rate(
            change_type="new",
            tax_category_code="city_tax_flat",
            rate_type="flat",
            rate_value=3.50,
            currency_code="USD",
        )
        draft = await _create_draft_rate(
            db, seed["nyc"], extracted, current_rate=None, job_id=1
        )
        assert draft is not None
        assert float(draft.rate_value) == pytest.approx(3.50)

    @pytest.mark.asyncio
    async def test_audit_log_created(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rate(
            change_type="new",
            tax_category_code="occ_pct",
            rate_type="percentage",
            rate_value=5.0,
        )
        draft = await _create_draft_rate(
            db, seed["nyc"], extracted, current_rate=None, job_id=42
        )
        assert draft is not None

        result = await db.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "tax_rate",
                AuditLog.entity_id == draft.id,
            )
        )
        log = result.scalar_one()
        assert log.action == "create"
        assert log.changed_by == "ai_monitoring"
        assert "42" in log.change_reason


# ─── _create_draft_rule ───────────────────────────────────────────


class TestCreateDraftRule:
    @pytest.mark.asyncio
    async def test_new_rule_version_1(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rule(
            change_type="new",
            rule_type="exemption",
            name="Diplomatic Exemption",
            description="Foreign diplomats are exempt.",
            conditions={"field": "guest_type", "operator": "==", "value": "diplomat"},
            action={"type": "exempt"},
        )
        draft = await _create_draft_rule(
            db, seed["nyc"], extracted, current_rule=None, job_id=1
        )
        assert draft is not None
        assert draft.version == 1
        assert draft.supersedes_id is None
        assert draft.status == "draft"
        assert draft.created_by == "ai_monitoring"
        assert draft.name == "Diplomatic Exemption"
        assert draft.rule_type == "exemption"

    @pytest.mark.asyncio
    async def test_changed_rule_version_incremented(self, db):
        seed = await seed_nyc_hierarchy(db)
        current = seed["rule_exempt"]  # version=1

        extracted = _make_extracted_rule(
            change_type="changed",
            rule_type="exemption",
            name="Long Stay Exemption",
            description="Updated: stays over 90 days are exempt.",
            conditions={"field": "stay_length_days", "operator": ">=", "value": 90},
            action={"type": "exempt"},
        )
        draft = await _create_draft_rule(
            db, seed["nyc"], extracted, current_rule=current, job_id=2
        )
        assert draft.version == current.version + 1
        assert draft.supersedes_id == current.id

    @pytest.mark.asyncio
    async def test_audit_log_created(self, db):
        seed = await seed_nyc_hierarchy(db)
        extracted = _make_extracted_rule(
            change_type="new",
            rule_type="cap",
            name="Nightly Cap",
        )
        draft = await _create_draft_rule(
            db, seed["nyc"], extracted, current_rule=None, job_id=99
        )
        result = await db.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "tax_rule",
                AuditLog.entity_id == draft.id,
            )
        )
        log = result.scalar_one()
        assert log.action == "create"
        assert log.changed_by == "ai_monitoring"
        assert "99" in log.change_reason


# ─── process_ai_results ───────────────────────────────────────────


class TestProcessAiResults:
    @pytest.mark.asyncio
    async def test_new_rate_creates_draft_and_detected_change(self, db):
        seed = await seed_nyc_hierarchy(db)
        ai_result = AIMonitoringResult(
            jurisdiction_code="US-NY-NYC",
            summary="New tourism levy detected.",
            rates=[
                _make_extracted_rate(
                    change_type="new",
                    tax_category_code="occ_pct",
                    rate_type="percentage",
                    rate_value=7.0,
                ),
            ],
            rules=[],
            sources_checked=["https://nyc.gov/tax"],
            overall_confidence=0.9,
        )
        summary = await process_ai_results(
            db,
            seed["nyc"],
            ai_result,
            job_id=10,
            current_rates=[seed["rate_pct"]],
            current_rules=[],
        )
        assert summary["rates_created"] == 1
        assert summary["changes_detected"] == 1

        # A DetectedChange record should exist with change_type "new_tax"
        result = await db.execute(
            select(DetectedChange).where(
                DetectedChange.jurisdiction_id == seed["nyc"].id
            )
        )
        change = result.scalar_one()
        assert change.change_type == "new_tax"
        assert change.applied_rate_id is not None
        assert float(change.confidence) == pytest.approx(0.90)

    @pytest.mark.asyncio
    async def test_changed_rate_creates_versioned_draft(self, db):
        seed = await seed_nyc_hierarchy(db)
        ai_result = AIMonitoringResult(
            jurisdiction_code="US-NY-NYC",
            summary="Occupancy tax rate increased.",
            rates=[
                _make_extracted_rate(
                    change_type="changed",
                    tax_category_code="occ_pct",
                    rate_type="percentage",
                    rate_value=6.5,
                ),
            ],
            rules=[],
            sources_checked=["https://nyc.gov/tax"],
            overall_confidence=0.85,
        )
        summary = await process_ai_results(
            db,
            seed["nyc"],
            ai_result,
            job_id=11,
            current_rates=[seed["rate_pct"]],
            current_rules=[],
        )
        assert summary["rates_created"] == 1
        assert summary["changes_detected"] == 1

        # The draft rate should be versioned
        result = await db.execute(
            select(TaxRate).where(
                TaxRate.status == "draft",
                TaxRate.jurisdiction_id == seed["nyc"].id,
            )
        )
        draft = result.scalar_one()
        assert draft.version == seed["rate_pct"].version + 1
        assert draft.supersedes_id == seed["rate_pct"].id

        # DetectedChange should be "rate_change"
        result = await db.execute(
            select(DetectedChange).where(
                DetectedChange.jurisdiction_id == seed["nyc"].id
            )
        )
        change = result.scalar_one()
        assert change.change_type == "rate_change"
        assert change.applied_rate_id == draft.id

    @pytest.mark.asyncio
    async def test_removed_rate_creates_repeal_without_draft(self, db):
        seed = await seed_nyc_hierarchy(db)
        ai_result = AIMonitoringResult(
            jurisdiction_code="US-NY-NYC",
            summary="Flat city tax has been repealed.",
            rates=[
                _make_extracted_rate(
                    change_type="removed",
                    tax_category_code="city_tax_flat",
                    rate_type="flat",
                    rate_value=None,
                ),
            ],
            rules=[],
            sources_checked=["https://nyc.gov/tax"],
            overall_confidence=0.80,
        )
        summary = await process_ai_results(
            db,
            seed["nyc"],
            ai_result,
            job_id=12,
            current_rates=[seed["rate_flat"]],
            current_rules=[],
        )
        assert summary["removals_flagged"] == 1
        assert summary["rates_created"] == 0  # No new draft created
        assert summary["changes_detected"] == 1

        # DetectedChange should be "repeal" pointing to the existing rate
        result = await db.execute(
            select(DetectedChange).where(
                DetectedChange.jurisdiction_id == seed["nyc"].id
            )
        )
        change = result.scalar_one()
        assert change.change_type == "repeal"
        assert change.applied_rate_id == seed["rate_flat"].id

    @pytest.mark.asyncio
    async def test_unchanged_rate_skipped(self, db):
        seed = await seed_nyc_hierarchy(db)
        ai_result = AIMonitoringResult(
            jurisdiction_code="US-NY-NYC",
            summary="No changes found.",
            rates=[
                _make_extracted_rate(
                    change_type="unchanged",
                    tax_category_code="occ_pct",
                    rate_type="percentage",
                    rate_value=5.875,
                ),
            ],
            rules=[],
            sources_checked=["https://nyc.gov/tax"],
            overall_confidence=0.95,
        )
        summary = await process_ai_results(
            db,
            seed["nyc"],
            ai_result,
            job_id=13,
            current_rates=[seed["rate_pct"]],
            current_rules=[],
        )
        assert summary["rates_created"] == 0
        assert summary["changes_detected"] == 0
        assert summary["rules_created"] == 0

    @pytest.mark.asyncio
    async def test_no_changes_creates_audit_log(self, db):
        seed = await seed_nyc_hierarchy(db)
        ai_result = AIMonitoringResult(
            jurisdiction_code="US-NY-NYC",
            summary="All rates confirmed unchanged.",
            rates=[
                _make_extracted_rate(
                    change_type="unchanged",
                    tax_category_code="occ_pct",
                    rate_type="percentage",
                    rate_value=5.875,
                ),
            ],
            rules=[],
            sources_checked=["https://nyc.gov/tax"],
            overall_confidence=0.95,
        )
        summary = await process_ai_results(
            db,
            seed["nyc"],
            ai_result,
            job_id=14,
            current_rates=[seed["rate_pct"]],
            current_rules=[],
        )
        assert summary["changes_detected"] == 0

        # An audit log entry should record the "no changes" outcome
        result = await db.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "jurisdiction",
                AuditLog.entity_id == seed["nyc"].id,
                AuditLog.action == "monitoring_no_changes",
            )
        )
        log = result.scalar_one()
        assert "14" in log.change_reason
        assert "All rates confirmed unchanged." in log.change_reason

    @pytest.mark.asyncio
    async def test_new_rule_creates_draft_and_detected_change(self, db):
        seed = await seed_nyc_hierarchy(db)
        ai_result = AIMonitoringResult(
            jurisdiction_code="US-NY-NYC",
            summary="New surcharge rule found.",
            rates=[],
            rules=[
                _make_extracted_rule(
                    change_type="new",
                    rule_type="surcharge",
                    name="Peak Season Surcharge",
                    description="10% surcharge during summer months.",
                    conditions={"field": "month", "operator": "in", "value": [6, 7, 8]},
                    action={"type": "surcharge", "surcharge_pct": 10},
                ),
            ],
            sources_checked=["https://nyc.gov/tax"],
            overall_confidence=0.88,
        )
        summary = await process_ai_results(
            db,
            seed["nyc"],
            ai_result,
            job_id=15,
            current_rates=[],
            current_rules=[],
        )
        assert summary["rules_created"] == 1
        assert summary["changes_detected"] == 1

        result = await db.execute(
            select(DetectedChange).where(
                DetectedChange.jurisdiction_id == seed["nyc"].id
            )
        )
        change = result.scalar_one()
        assert change.change_type == "new_tax"
        assert change.applied_rule_id is not None

    @pytest.mark.asyncio
    async def test_changed_rule_creates_versioned_draft(self, db):
        seed = await seed_nyc_hierarchy(db)
        ai_result = AIMonitoringResult(
            jurisdiction_code="US-NY-NYC",
            summary="Long stay exemption threshold lowered.",
            rates=[],
            rules=[
                _make_extracted_rule(
                    change_type="changed",
                    rule_type="exemption",
                    name="Long Stay Exemption",
                    description="Now 90-day threshold.",
                    conditions={"field": "stay_length_days", "operator": ">=", "value": 90},
                    action={"type": "exempt"},
                ),
            ],
            sources_checked=["https://nyc.gov/tax"],
            overall_confidence=0.82,
        )
        summary = await process_ai_results(
            db,
            seed["nyc"],
            ai_result,
            job_id=16,
            current_rates=[],
            current_rules=[seed["rule_exempt"]],
        )
        assert summary["rules_created"] == 1
        assert summary["changes_detected"] == 1

        result = await db.execute(
            select(TaxRule).where(
                TaxRule.status == "draft",
                TaxRule.jurisdiction_id == seed["nyc"].id,
            )
        )
        draft = result.scalar_one()
        assert draft.version == seed["rule_exempt"].version + 1
        assert draft.supersedes_id == seed["rule_exempt"].id

        result = await db.execute(
            select(DetectedChange).where(
                DetectedChange.jurisdiction_id == seed["nyc"].id
            )
        )
        change = result.scalar_one()
        assert change.change_type == "exemption_change"

    @pytest.mark.asyncio
    async def test_removed_rule_creates_repeal(self, db):
        seed = await seed_nyc_hierarchy(db)
        ai_result = AIMonitoringResult(
            jurisdiction_code="US-NY-NYC",
            summary="Long stay exemption repealed.",
            rates=[],
            rules=[
                _make_extracted_rule(
                    change_type="removed",
                    rule_type="exemption",
                    name="Long Stay Exemption",
                ),
            ],
            sources_checked=["https://nyc.gov/tax"],
            overall_confidence=0.78,
        )
        summary = await process_ai_results(
            db,
            seed["nyc"],
            ai_result,
            job_id=17,
            current_rates=[],
            current_rules=[seed["rule_exempt"]],
        )
        assert summary["removals_flagged"] == 1
        assert summary["rules_created"] == 0

        result = await db.execute(
            select(DetectedChange).where(
                DetectedChange.jurisdiction_id == seed["nyc"].id
            )
        )
        change = result.scalar_one()
        assert change.change_type == "repeal"
        assert change.applied_rule_id == seed["rule_exempt"].id

    @pytest.mark.asyncio
    async def test_summary_fields(self, db):
        seed = await seed_nyc_hierarchy(db)
        ai_result = AIMonitoringResult(
            jurisdiction_code="US-NY-NYC",
            summary="Mixed results.",
            rates=[
                _make_extracted_rate(
                    change_type="new",
                    tax_category_code="occ_pct",
                    rate_type="percentage",
                    rate_value=7.0,
                ),
            ],
            rules=[
                _make_extracted_rule(
                    change_type="new",
                    rule_type="cap",
                    name="Nightly Cap",
                ),
            ],
            sources_checked=["https://nyc.gov/tax", "https://nyc.gov/finance"],
            overall_confidence=0.88,
        )
        summary = await process_ai_results(
            db,
            seed["nyc"],
            ai_result,
            job_id=18,
            current_rates=[],
            current_rules=[],
        )
        assert summary["sources_checked"] == 2
        assert summary["overall_confidence"] == pytest.approx(0.88)
        assert summary["summary"] == "Mixed results."
        assert summary["rates_created"] == 1
        assert summary["rules_created"] == 1
        assert summary["changes_detected"] == 2
