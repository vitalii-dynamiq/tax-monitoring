"""
Tests for the tax calculation service.

End-to-end tests that exercise the full calculation pipeline
(jurisdiction resolution -> rate lookup -> rule application -> calculation)
against a real in-memory database.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.schemas.tax_calculation import BatchCalculationRequest, TaxCalculationRequest
from app.services.tax_calculation_service import calculate_tax, calculate_tax_batch
from tests.factories import (
    create_jurisdiction,
    create_tax_category,
    create_tax_rate,
    seed_nyc_hierarchy,
)


class TestCalculateTax:
    async def test_basic_percentage_tax(self, db):
        """Calculate a simple percentage tax for NYC."""
        await seed_nyc_hierarchy(db)

        request = TaxCalculationRequest(
            jurisdiction_code="US-NY-NYC",
            stay_date=date(2025, 6, 15),
            nightly_rate=Decimal("200"),
            currency="USD",
            nights=3,
        )
        result = await calculate_tax(db, request)

        assert result.jurisdiction["code"] == "US-NY-NYC"
        assert result.tax_breakdown.total_tax > 0
        assert result.tax_breakdown.currency == "USD"
        assert len(result.tax_breakdown.components) >= 1
        # Percentage component: 200 * 3 * 0.05875 = 35.25
        pct_component = next(
            c for c in result.tax_breakdown.components
            if c.category_code == "occ_pct"
        )
        assert pct_component.tax_amount == Decimal("35.25")

    async def test_flat_rate_per_night(self, db):
        """Flat rate is multiplied by number of nights."""
        await seed_nyc_hierarchy(db)

        request = TaxCalculationRequest(
            jurisdiction_code="US-NY-NYC",
            stay_date=date(2025, 6, 15),
            nightly_rate=Decimal("200"),
            currency="USD",
            nights=3,
        )
        result = await calculate_tax(db, request)

        flat_component = next(
            c for c in result.tax_breakdown.components
            if c.category_code == "city_tax_flat"
        )
        # $2.00 * 3 nights = $6.00
        assert flat_component.tax_amount == Decimal("6.00")

    async def test_total_includes_all_components(self, db):
        """Total tax is sum of all components."""
        await seed_nyc_hierarchy(db)

        request = TaxCalculationRequest(
            jurisdiction_code="US-NY-NYC",
            stay_date=date(2025, 6, 15),
            nightly_rate=Decimal("200"),
            currency="USD",
            nights=3,
        )
        result = await calculate_tax(db, request)

        expected_total = sum(c.tax_amount for c in result.tax_breakdown.components)
        assert result.tax_breakdown.total_tax == expected_total

    async def test_total_with_tax_includes_subtotal(self, db):
        """total_with_tax = subtotal + total_tax."""
        await seed_nyc_hierarchy(db)

        request = TaxCalculationRequest(
            jurisdiction_code="US-NY-NYC",
            stay_date=date(2025, 6, 15),
            nightly_rate=Decimal("200"),
            currency="USD",
            nights=3,
        )
        result = await calculate_tax(db, request)

        subtotal = Decimal("200") * 3
        assert result.total_with_tax == subtotal + result.tax_breakdown.total_tax

    async def test_exemption_rule_applied(self, db):
        """Long stay exemption zeros out the rate."""
        await seed_nyc_hierarchy(db)

        request = TaxCalculationRequest(
            jurisdiction_code="US-NY-NYC",
            stay_date=date(2025, 1, 1),
            checkout_date=date(2025, 7, 1),
            nightly_rate=Decimal("150"),
            currency="USD",
            nights=181,
        )
        result = await calculate_tax(db, request)

        # The exemption rule is linked to the occ_pct rate via tax_rate_id
        pct_component = next(
            c for c in result.tax_breakdown.components
            if c.category_code == "occ_pct"
        )
        assert pct_component.tax_amount == Decimal("0")
        assert "EXEMPT" in pct_component.name

        # Verify rule trace shows exemption
        exempt_trace = [r for r in result.rules_applied if r.result == "exempted"]
        assert len(exempt_trace) >= 1

    async def test_unknown_jurisdiction_raises(self, db):
        """Requesting a nonexistent jurisdiction raises ValueError."""
        request = TaxCalculationRequest(
            jurisdiction_code="XX-NOPE",
            stay_date=date(2025, 6, 15),
            nightly_rate=Decimal("100"),
            currency="USD",
            nights=1,
        )
        with pytest.raises(ValueError, match="Jurisdiction not found"):
            await calculate_tax(db, request)

    async def test_no_rates_returns_zero_tax(self, db):
        """Jurisdiction with no rates returns zero total tax."""
        await create_jurisdiction(
            db, code="ZZ", name="Empty Country", jurisdiction_type="country",
            path="ZZ", country_code="ZZ", currency_code="USD",
        )
        await db.commit()

        request = TaxCalculationRequest(
            jurisdiction_code="ZZ",
            stay_date=date(2025, 6, 15),
            nightly_rate=Decimal("100"),
            currency="USD",
            nights=1,
        )
        result = await calculate_tax(db, request)
        assert result.tax_breakdown.total_tax == Decimal("0")
        assert len(result.tax_breakdown.components) == 0

    async def test_expired_rate_excluded(self, db):
        """Rates with effective_end before stay_date are excluded."""
        j = await create_jurisdiction(
            db, code="EX", name="Expired", jurisdiction_type="country",
            path="EX", country_code="EX", currency_code="USD",
        )
        cat = await create_tax_category(
            db, code="ex_pct", name="Expired Tax",
            level_0="accommodation", level_1="occupancy", level_2="percentage",
        )
        await create_tax_rate(
            db, jurisdiction_id=j.id, tax_category_id=cat.id,
            rate_type="percentage", rate_value=0.10,
            effective_start=date(2020, 1, 1), effective_end=date(2024, 12, 31),
            status="active",
        )
        await db.commit()

        request = TaxCalculationRequest(
            jurisdiction_code="EX",
            stay_date=date(2025, 6, 15),
            nightly_rate=Decimal("100"),
            currency="USD",
            nights=1,
        )
        result = await calculate_tax(db, request)
        assert result.tax_breakdown.total_tax == Decimal("0")


class TestCalculateTaxBatch:
    async def test_batch_mixed_results(self, db):
        """Batch with one valid and one invalid request."""
        await seed_nyc_hierarchy(db)

        request = BatchCalculationRequest(calculations=[
            TaxCalculationRequest(
                jurisdiction_code="US-NY-NYC",
                stay_date=date(2025, 6, 15),
                nightly_rate=Decimal("200"),
                currency="USD",
                nights=3,
            ),
            TaxCalculationRequest(
                jurisdiction_code="XX-NOPE",
                stay_date=date(2025, 6, 15),
                nightly_rate=Decimal("100"),
                currency="USD",
                nights=1,
            ),
        ])
        result = await calculate_tax_batch(db, request)

        assert len(result.results) == 2
        # First succeeds
        assert result.results[0].total_tax > 0
        assert result.results[0].error is None
        # Second fails gracefully
        assert result.results[1].total_tax == Decimal("0")
        assert result.results[1].error is not None
        assert "not found" in result.results[1].error

    async def test_batch_all_succeed(self, db):
        """Batch where all requests succeed."""
        await seed_nyc_hierarchy(db)

        request = BatchCalculationRequest(calculations=[
            TaxCalculationRequest(
                jurisdiction_code="US-NY-NYC",
                stay_date=date(2025, 6, 15),
                nightly_rate=Decimal("100"),
                currency="USD",
                nights=1,
            ),
            TaxCalculationRequest(
                jurisdiction_code="US-NY-NYC",
                stay_date=date(2025, 6, 15),
                nightly_rate=Decimal("300"),
                currency="USD",
                nights=2,
            ),
        ])
        result = await calculate_tax_batch(db, request)

        assert all(r.error is None for r in result.results)
        assert all(r.total_tax > 0 for r in result.results)
