"""
Unit tests for the tax calculation rule engine.

These tests run without a database by constructing mock SQLAlchemy
model instances directly.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from app.core.rule_engine import (
    BookingContext,
    apply_rules,
    calculate_flat,
    calculate_percentage,
    calculate_taxes,
    calculate_tiered,
    evaluate_conditions,
)

# ─── Helpers to create mock model objects ─────────────────────────────

def make_category(code="occ_pct", name="Occupancy Tax", level_2="percentage"):
    cat = MagicMock()
    cat.code = code
    cat.name = name
    cat.level_2 = level_2
    return cat


def make_jurisdiction(code="US-NY-NYC", name="New York City", jurisdiction_type="city"):
    j = MagicMock()
    j.code = code
    j.name = name
    j.jurisdiction_type = jurisdiction_type
    return j


def make_rate(
    id=1,
    rate_type="percentage",
    rate_value=0.05875,
    category_code="occ_pct",
    category_name="Occupancy Tax",
    category_level_2="percentage",
    jurisdiction_code="US-NY-NYC",
    jurisdiction_type="city",
    calculation_order=100,
    base_includes=None,
    tiers=None,
    tier_type=None,
    legal_reference=None,
    authority_name=None,
    status="active",
):
    rate = MagicMock()
    rate.id = id
    rate.rate_type = rate_type
    rate.rate_value = rate_value
    rate.calculation_order = calculation_order
    rate.base_includes = base_includes or ["base_amount"]
    rate.tiers = tiers
    rate.tier_type = tier_type
    rate.legal_reference = legal_reference
    rate.authority_name = authority_name
    rate.status = status

    rate.tax_category = make_category(category_code, category_name, category_level_2)
    rate.jurisdiction = make_jurisdiction(jurisdiction_code, jurisdiction_type=jurisdiction_type)

    return rate


def make_rule(
    id=1,
    rule_type="exemption",
    priority=100,
    name="Test Rule",
    conditions=None,
    action=None,
    effective_start=date(2020, 1, 1),
    effective_end=None,
):
    rule = MagicMock()
    rule.id = id
    rule.rule_type = rule_type
    rule.priority = priority
    rule.name = name
    rule.conditions = conditions or {}
    rule.action = action or {}
    rule.effective_start = effective_start
    rule.effective_end = effective_end
    return rule


def make_context(**kwargs):
    defaults = {
        "jurisdiction_code": "US-NY-NYC",
        "stay_date": date(2025, 6, 15),
        "checkout_date": date(2025, 6, 18),
        "nightly_rate": Decimal("200"),
        "nights": 3,
        "currency": "USD",
        "property_type": "hotel",
        "number_of_guests": 2,
    }
    defaults.update(kwargs)
    return BookingContext(**defaults)


# ─── BookingContext Tests ─────────────────────────────────────────────

class TestBookingContext:
    def test_stay_length_days(self):
        ctx = make_context(nights=5)
        assert ctx.stay_length_days == 5

    def test_stay_month(self):
        ctx = make_context(stay_date=date(2025, 12, 1))
        assert ctx.stay_month == 12

    def test_total_stay_amount(self):
        ctx = make_context(nightly_rate=Decimal("150"), nights=4)
        assert ctx.total_stay_amount == Decimal("600")

    def test_get_field_existing(self):
        ctx = make_context(property_type="resort")
        assert ctx.get_field("property_type") == "resort"

    def test_get_field_property(self):
        ctx = make_context(nights=7)
        assert ctx.get_field("stay_length_days") == 7

    def test_get_field_missing(self):
        ctx = make_context()
        assert ctx.get_field("nonexistent_field") is None


# ─── Condition Evaluator Tests ────────────────────────────────────────

class TestEvaluateConditions:
    def test_empty_conditions_always_match(self):
        ctx = make_context()
        assert evaluate_conditions({}, ctx) is True
        assert evaluate_conditions({"rules": []}, ctx) is True

    def test_simple_equality(self):
        ctx = make_context(property_type="hotel")
        conditions = {
            "operator": "AND",
            "rules": [{"field": "property_type", "op": "==", "value": "hotel"}],
        }
        assert evaluate_conditions(conditions, ctx) is True

    def test_simple_inequality(self):
        ctx = make_context(property_type="hotel")
        conditions = {
            "operator": "AND",
            "rules": [{"field": "property_type", "op": "==", "value": "hostel"}],
        }
        assert evaluate_conditions(conditions, ctx) is False

    def test_greater_than(self):
        ctx = make_context(nightly_rate=Decimal("300"))
        conditions = {
            "operator": "AND",
            "rules": [{"field": "nightly_rate", "op": ">", "value": 200}],
        }
        assert evaluate_conditions(conditions, ctx) is True

    def test_less_than_or_equal(self):
        ctx = make_context(nights=3)
        conditions = {
            "operator": "AND",
            "rules": [{"field": "stay_length_days", "op": "<=", "value": 3}],
        }
        assert evaluate_conditions(conditions, ctx) is True

    def test_in_operator(self):
        ctx = make_context(property_type="hotel")
        conditions = {
            "operator": "AND",
            "rules": [{"field": "property_type", "op": "in", "value": ["hotel", "resort"]}],
        }
        assert evaluate_conditions(conditions, ctx) is True

    def test_not_in_operator(self):
        ctx = make_context(property_type="hostel")
        conditions = {
            "operator": "AND",
            "rules": [{"field": "property_type", "op": "not_in", "value": ["hotel", "resort"]}],
        }
        assert evaluate_conditions(conditions, ctx) is True

    def test_between_operator(self):
        ctx = make_context(nightly_rate=Decimal("150"))
        conditions = {
            "operator": "AND",
            "rules": [{"field": "nightly_rate", "op": "between", "value": [100, 200]}],
        }
        assert evaluate_conditions(conditions, ctx) is True

    def test_between_outside_range(self):
        ctx = make_context(nightly_rate=Decimal("300"))
        conditions = {
            "operator": "AND",
            "rules": [{"field": "nightly_rate", "op": "between", "value": [100, 200]}],
        }
        assert evaluate_conditions(conditions, ctx) is False

    def test_and_operator_all_true(self):
        ctx = make_context(property_type="hotel", nights=3)
        conditions = {
            "operator": "AND",
            "rules": [
                {"field": "property_type", "op": "==", "value": "hotel"},
                {"field": "stay_length_days", "op": ">=", "value": 2},
            ],
        }
        assert evaluate_conditions(conditions, ctx) is True

    def test_and_operator_one_false(self):
        ctx = make_context(property_type="hotel", nights=1)
        conditions = {
            "operator": "AND",
            "rules": [
                {"field": "property_type", "op": "==", "value": "hotel"},
                {"field": "stay_length_days", "op": ">=", "value": 5},
            ],
        }
        assert evaluate_conditions(conditions, ctx) is False

    def test_or_operator(self):
        ctx = make_context(property_type="hostel")
        conditions = {
            "operator": "OR",
            "rules": [
                {"field": "property_type", "op": "==", "value": "hotel"},
                {"field": "property_type", "op": "==", "value": "hostel"},
            ],
        }
        assert evaluate_conditions(conditions, ctx) is True

    def test_nested_conditions(self):
        ctx = make_context(property_type="hotel", star_rating=5, nights=2)
        conditions = {
            "operator": "AND",
            "rules": [
                {"field": "property_type", "op": "==", "value": "hotel"},
                {
                    "operator": "OR",
                    "rules": [
                        {"field": "star_rating", "op": ">=", "value": 4},
                        {"field": "stay_length_days", "op": ">=", "value": 7},
                    ],
                },
            ],
        }
        assert evaluate_conditions(conditions, ctx) is True

    def test_unknown_operator(self):
        ctx = make_context()
        conditions = {
            "operator": "AND",
            "rules": [{"field": "property_type", "op": "REGEX", "value": "hot.*"}],
        }
        assert evaluate_conditions(conditions, ctx) is False

    def test_null_field_comparison(self):
        ctx = make_context(star_rating=None)
        conditions = {
            "operator": "AND",
            "rules": [{"field": "star_rating", "op": ">", "value": 3}],
        }
        assert evaluate_conditions(conditions, ctx) is False


# ─── Calculator Tests ─────────────────────────────────────────────────

class TestCalculatePercentage:
    def test_basic_percentage(self):
        result = calculate_percentage(Decimal("200"), 0.05875)
        assert result == Decimal("11.75")

    def test_zero_rate(self):
        result = calculate_percentage(Decimal("200"), 0)
        assert result == Decimal("0.00")

    def test_rounding(self):
        # 200 * 0.03333 = 6.666 -> rounds to 6.67
        result = calculate_percentage(Decimal("200"), 0.03333)
        assert result == Decimal("6.67")


class TestCalculateFlat:
    def test_flat_per_night(self):
        result = calculate_flat(
            2.0, nights=3, number_of_guests=1,
            category_level_2="flat_per_night",
        )
        assert result == Decimal("6.00")

    def test_flat_per_person_per_night(self):
        result = calculate_flat(
            2.0, nights=3, number_of_guests=2,
            category_level_2="flat_per_person_per_night",
        )
        assert result == Decimal("12.00")

    def test_per_person_keyword(self):
        result = calculate_flat(
            5.0, nights=2, number_of_guests=3,
            category_level_2="flat_per_person_per_night",
        )
        assert result == Decimal("30.00")


class TestCalculateTiered:
    def test_single_amount_lowest_tier(self):
        tiers = [
            {"min": 0, "max": 10000, "value": 0},
            {"min": 10000, "max": 15000, "value": 100},
            {"min": 15000, "value": 200},
        ]
        # ¥5000/night — below 10000 threshold, value = 0
        result = calculate_tiered(Decimal("5000"), tiers, "single_amount", nights=2)
        assert result == Decimal("0")

    def test_single_amount_middle_tier(self):
        tiers = [
            {"min": 0, "max": 10000, "value": 0},
            {"min": 10000, "max": 15000, "value": 100},
            {"min": 15000, "value": 200},
        ]
        # ¥12000/night — in 10k-15k bracket, ¥100/night
        result = calculate_tiered(Decimal("12000"), tiers, "single_amount", nights=3)
        assert result == Decimal("300.00")

    def test_single_amount_highest_tier(self):
        tiers = [
            {"min": 0, "max": 10000, "value": 0},
            {"min": 10000, "max": 15000, "value": 100},
            {"min": 15000, "value": 200},
        ]
        # ¥20000/night — above 15000, ¥200/night
        result = calculate_tiered(Decimal("20000"), tiers, "single_amount", nights=2)
        assert result == Decimal("400.00")

    def test_threshold_basic(self):
        tiers = [
            {"min": 0, "rate": 0.05},
            {"min": 1000, "rate": 0.12},
            {"min": 7500, "rate": 0.18},
        ]
        # $2000/night — falls in 1000-7500 bracket, 12% of full amount
        result = calculate_tiered(Decimal("2000"), tiers, "threshold", nights=1)
        assert result == Decimal("240.00")

    def test_threshold_highest(self):
        tiers = [
            {"min": 0, "rate": 0.05},
            {"min": 1000, "rate": 0.12},
            {"min": 7500, "rate": 0.18},
        ]
        # $10000/night — above 7500, 18% of full amount
        result = calculate_tiered(Decimal("10000"), tiers, "threshold", nights=1)
        assert result == Decimal("1800.00")

    def test_marginal_rate(self):
        tiers = [
            {"min": 0, "max": 100, "rate": 0.0},
            {"min": 100, "max": 200, "rate": 0.05},
            {"min": 200, "rate": 0.10},
        ]
        # $250/night: first $100 at 0%, next $100 at 5%=$5, remaining $50 at 10%=$5
        result = calculate_tiered(Decimal("250"), tiers, "marginal_rate", nights=1)
        assert result == Decimal("10.00")

    def test_marginal_rate_multiple_nights(self):
        tiers = [
            {"min": 0, "max": 100, "rate": 0.0},
            {"min": 100, "max": 200, "rate": 0.05},
            {"min": 200, "rate": 0.10},
        ]
        # Same rate per night, but 3 nights
        result = calculate_tiered(Decimal("250"), tiers, "marginal_rate", nights=3)
        assert result == Decimal("30.00")

    def test_empty_tiers(self):
        result = calculate_tiered(Decimal("200"), [], "single_amount", nights=1)
        assert result == Decimal("0")

    def test_unknown_tier_type(self):
        tiers = [{"min": 0, "rate": 0.1}]
        result = calculate_tiered(Decimal("200"), tiers, "unknown_type", nights=1)
        assert result == Decimal("0")


# ─── Rule Application Tests ──────────────────────────────────────────

class TestApplyRules:
    def test_no_rules(self):
        ctx = make_context()
        rate = make_rate()
        result = apply_rules([], ctx, rate)
        assert result.is_exempt is False
        assert result.override_rate is None
        assert result.traces == []

    def test_exemption_applies(self):
        ctx = make_context(nights=180)
        rate = make_rate()
        rule = make_rule(
            rule_type="exemption",
            priority=100,
            name="Permanent Resident Exemption",
            conditions={
                "operator": "AND",
                "rules": [{"field": "stay_length_days", "op": ">=", "value": 180}],
            },
        )
        result = apply_rules([rule], ctx, rate)
        assert result.is_exempt is True
        assert result.traces[0].result == "exempted"

    def test_exemption_does_not_apply(self):
        ctx = make_context(nights=5)
        rate = make_rate()
        rule = make_rule(
            rule_type="exemption",
            priority=100,
            name="Permanent Resident Exemption",
            conditions={
                "operator": "AND",
                "rules": [{"field": "stay_length_days", "op": ">=", "value": 180}],
            },
        )
        result = apply_rules([rule], ctx, rate)
        assert result.is_exempt is False
        assert result.traces[0].result == "skipped"

    def test_override_rule(self):
        ctx = make_context(property_type="hostel")
        rate = make_rate()
        rule = make_rule(
            rule_type="override",
            priority=50,
            name="Hostel Reduced Rate",
            conditions={
                "operator": "AND",
                "rules": [{"field": "property_type", "op": "==", "value": "hostel"}],
            },
            action={"rate_value": 0.02},
        )
        result = apply_rules([rule], ctx, rate)
        assert result.is_exempt is False
        assert result.override_rate == Decimal("0.02")
        assert result.traces[0].result == "applied"

    def test_exemption_wins_over_override(self):
        """First matching exemption returns immediately (Catala default logic)."""
        ctx = make_context(nights=200, property_type="hostel")
        rate = make_rate()

        exemption = make_rule(
            id=1,
            rule_type="exemption",
            priority=100,
            name="Long Stay Exemption",
            conditions={
                "operator": "AND",
                "rules": [{"field": "stay_length_days", "op": ">=", "value": 180}],
            },
        )
        override = make_rule(
            id=2,
            rule_type="override",
            priority=50,
            name="Hostel Rate",
            conditions={
                "operator": "AND",
                "rules": [{"field": "property_type", "op": "==", "value": "hostel"}],
            },
            action={"rate_value": 0.02},
        )

        result = apply_rules([exemption, override], ctx, rate)
        assert result.is_exempt is True
        assert result.override_rate is None  # Override never evaluated

    def test_rule_temporal_validity(self):
        """Rules outside their effective date range are skipped."""
        ctx = make_context(stay_date=date(2025, 6, 15))
        rate = make_rate()

        future_rule = make_rule(
            rule_type="exemption",
            priority=100,
            name="Future Exemption",
            conditions={
                "operator": "AND",
                "rules": [{"field": "property_type", "op": "==", "value": "hotel"}],
            },
            effective_start=date(2026, 1, 1),
        )

        result = apply_rules([future_rule], ctx, rate)
        assert result.is_exempt is False
        assert result.traces == []  # Temporally invalid rules produce no trace

    def test_cap_rule(self):
        ctx = make_context()
        rate = make_rate()
        rule = make_rule(
            rule_type="cap",
            priority=50,
            name="Max 10 Nights Cap",
            conditions={},
            action={"max_nights": 10},
        )
        result = apply_rules([rule], ctx, rate)
        assert result.is_exempt is False
        assert result.cap_nights == 10
        assert result.traces[0].rule_type == "cap"
        assert result.traces[0].result == "applied"

    def test_cap_rule_per_person_per_night(self):
        ctx = make_context()
        rate = make_rate()
        rule = make_rule(
            rule_type="cap",
            priority=50,
            name="Paris Unclassified Cap",
            conditions={},
            action={"max_per_person_per_night": 5.0},
        )
        result = apply_rules([rule], ctx, rate)
        assert result.cap_per_person_per_night == Decimal("5.0")
        assert result.traces[0].result == "applied"

    def test_surcharge_rule(self):
        ctx = make_context(property_type="str")
        rate = make_rate()
        rule = make_rule(
            rule_type="surcharge",
            priority=50,
            name="STR Platform Surcharge",
            conditions={
                "operator": "AND",
                "rules": [{"field": "property_type", "op": "==", "value": "str"}],
            },
            action={"rate_value": 0.01},
        )
        result = apply_rules([rule], ctx, rate)
        assert result.is_exempt is False
        assert result.surcharge_rate == Decimal("0.01")
        assert result.traces[0].result == "applied"

    def test_reduction_rule(self):
        ctx = make_context(guest_type="government")
        rate = make_rate()
        rule = make_rule(
            rule_type="reduction",
            priority=50,
            name="Government Employee Reduction",
            conditions={
                "operator": "AND",
                "rules": [{"field": "guest_type", "op": "==", "value": "government"}],
            },
            action={"reduction_percent": 0.5},
        )
        result = apply_rules([rule], ctx, rate)
        assert result.is_exempt is False
        assert result.reduction_pct == Decimal("0.5")
        assert result.traces[0].result == "applied"


# ─── Full Calculation Pipeline Tests ──────────────────────────────────

class TestCalculateTaxes:
    def test_nyc_hotel_basic(self):
        """
        NYC standard hotel scenario: $200/night, 3 nights
        - NY State Sales: 4% of $600 = $24.00
        - NYC Sales: 4.5% of $600 = $27.00
        - NYC Occupancy: 5.875% of $600 = $35.25
        - NYC Flat Fee: $2 × 3 nights = $6.00
        Total: $92.25
        """
        ctx = make_context(nightly_rate=Decimal("200"), nights=3)

        ny_state_sales = make_rate(
            id=1, rate_type="percentage", rate_value=0.04,
            category_code="vat_standard", category_name="NY State Sales Tax",
            jurisdiction_code="US-NY", jurisdiction_type="state",
            calculation_order=10,
        )
        nyc_sales = make_rate(
            id=2, rate_type="percentage", rate_value=0.045,
            category_code="vat_standard", category_name="NYC Sales Tax",
            jurisdiction_code="US-NY-NYC", jurisdiction_type="city",
            calculation_order=20,
        )
        nyc_occupancy = make_rate(
            id=3, rate_type="percentage", rate_value=0.05875,
            category_code="occ_pct", category_name="NYC Hotel Occupancy Tax",
            jurisdiction_code="US-NY-NYC", jurisdiction_type="city",
            calculation_order=30,
        )
        nyc_flat = make_rate(
            id=4, rate_type="flat", rate_value=2.0,
            category_code="occ_flat_night", category_name="NYC $2 Per Room Fee",
            category_level_2="flat_per_night",
            jurisdiction_code="US-NY-NYC", jurisdiction_type="city",
            calculation_order=40,
        )

        rates = [ny_state_sales, nyc_sales, nyc_occupancy, nyc_flat]
        rules_by_rate: dict[int, list] = {}

        result = calculate_taxes(rates, rules_by_rate, ctx)

        assert len(result.components) == 4
        assert result.components[0].tax_amount == Decimal("24.00")
        assert result.components[1].tax_amount == Decimal("27.00")
        assert result.components[2].tax_amount == Decimal("35.25")
        assert result.components[3].tax_amount == Decimal("6.00")
        assert result.total_tax == Decimal("92.25")

    def test_nyc_with_permanent_resident_exemption(self):
        """180+ night stay: NYC occupancy tax should be exempt."""
        ctx = make_context(nightly_rate=Decimal("200"), nights=180)

        nyc_occupancy = make_rate(
            id=3, rate_type="percentage", rate_value=0.05875,
            category_code="occ_pct", category_name="NYC Hotel Occupancy Tax",
            calculation_order=30,
        )

        exemption_rule = make_rule(
            id=1, rule_type="exemption", priority=100,
            name="Permanent Resident Exemption",
            conditions={
                "operator": "AND",
                "rules": [{"field": "stay_length_days", "op": ">=", "value": 180}],
            },
        )

        rates = [nyc_occupancy]
        rules_by_rate = {3: [exemption_rule]}

        result = calculate_taxes(rates, rules_by_rate, ctx)

        assert len(result.components) == 1
        assert result.components[0].tax_amount == Decimal("0")
        assert "EXEMPT" in result.components[0].name

    def test_tokyo_tiered_accommodation_tax(self):
        """
        Tokyo hotel: ¥12000/night, 2 nights
        - Japan Consumption Tax: 10% of ¥24000 = ¥2400
        - Tokyo Accommodation: ¥12000 is in 10k-15k tier → ¥100/night × 2 = ¥200
        Total: ¥2600
        """
        ctx = make_context(
            jurisdiction_code="JP-13-TYO",
            nightly_rate=Decimal("12000"),
            nights=2,
            currency="JPY",
        )

        japan_consumption = make_rate(
            id=1, rate_type="percentage", rate_value=0.10,
            category_code="vat_standard", category_name="Japan Consumption Tax",
            jurisdiction_code="JP", jurisdiction_type="country",
            calculation_order=10,
        )
        tokyo_accommodation = make_rate(
            id=2, rate_type="tiered", rate_value=None,
            category_code="tier_price", category_name="Tokyo Accommodation Tax",
            category_level_2="tiered_by_price",
            jurisdiction_code="JP-13-TYO", jurisdiction_type="city",
            calculation_order=20,
            tiers=[
                {"min": 0, "max": 10000, "value": 0},
                {"min": 10000, "max": 15000, "value": 100},
                {"min": 15000, "value": 200},
            ],
            tier_type="single_amount",
        )

        rates = [japan_consumption, tokyo_accommodation]
        rules_by_rate: dict[int, list] = {}

        result = calculate_taxes(rates, rules_by_rate, ctx)

        assert result.components[0].tax_amount == Decimal("2400.00")
        assert result.components[1].tax_amount == Decimal("200.00")
        assert result.total_tax == Decimal("2600.00")

    def test_cascading_tax(self):
        """Tax-on-tax: second tax uses first tax amount as part of its base."""
        ctx = make_context(nightly_rate=Decimal("100"), nights=1)

        base_tax = make_rate(
            id=1, rate_type="percentage", rate_value=0.10,
            category_code="occ_pct", category_name="Base Tax",
            calculation_order=10,
            base_includes=["base_amount"],
        )
        cascading_tax = make_rate(
            id=2, rate_type="percentage", rate_value=0.05,
            category_code="municipal_pct", category_name="Municipal Surcharge",
            calculation_order=20,
            base_includes=["base_amount", "occ_pct"],  # includes first tax
        )

        rates = [base_tax, cascading_tax]
        rules_by_rate: dict[int, list] = {}

        result = calculate_taxes(rates, rules_by_rate, ctx)

        # Base tax: 10% of $100 = $10
        assert result.components[0].tax_amount == Decimal("10.00")
        # Cascading: 5% of ($100 + $10) = $5.50
        assert result.components[1].tax_amount == Decimal("5.50")
        assert result.total_tax == Decimal("15.50")

    def test_single_rate_no_rules(self):
        """Simple percentage rate with no rules."""
        ctx = make_context(nightly_rate=Decimal("100"), nights=1)

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.07,
            category_code="tourism_pct", category_name="Tourism Tax",
            calculation_order=10,
        )

        result = calculate_taxes([rate], {}, ctx)

        assert len(result.components) == 1
        assert result.components[0].tax_amount == Decimal("7.00")
        assert result.total_tax == Decimal("7.00")
        assert result.effective_rate == Decimal("0.07")

    def test_empty_rates(self):
        """No rates — zero tax."""
        ctx = make_context()
        result = calculate_taxes([], {}, ctx)
        assert result.total_tax == Decimal("0")
        assert result.effective_rate == Decimal("0")
        assert result.components == []

    def test_override_rate_value(self):
        """Override rule changes the effective rate value."""
        ctx = make_context(nightly_rate=Decimal("100"), nights=1, property_type="hostel")

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.10,
            category_code="occ_pct", category_name="Occupancy Tax",
            calculation_order=10,
        )

        override_rule = make_rule(
            id=1, rule_type="override", priority=50,
            name="Hostel Reduced Rate",
            conditions={
                "operator": "AND",
                "rules": [{"field": "property_type", "op": "==", "value": "hostel"}],
            },
            action={"rate_value": 0.05},
        )

        result = calculate_taxes([rate], {1: [override_rule]}, ctx)

        # Override changes rate from 10% to 5%
        assert result.components[0].tax_amount == Decimal("5.00")
        assert result.components[0].rate == 0.05

    def test_amsterdam_percentage_based(self):
        """Amsterdam: 9% VAT + 7% tourist tax on €150/night, 2 nights."""
        ctx = make_context(
            jurisdiction_code="NL-NH-AMS",
            nightly_rate=Decimal("150"),
            nights=2,
            currency="EUR",
        )

        nl_vat = make_rate(
            id=1, rate_type="percentage", rate_value=0.09,
            category_code="vat_reduced", category_name="Netherlands VAT (reduced)",
            jurisdiction_code="NL", jurisdiction_type="country",
            calculation_order=10,
        )
        ams_tourist = make_rate(
            id=2, rate_type="percentage", rate_value=0.07,
            category_code="tourism_pct", category_name="Amsterdam Tourist Tax",
            jurisdiction_code="NL-NH-AMS", jurisdiction_type="city",
            calculation_order=20,
        )

        result = calculate_taxes([nl_vat, ams_tourist], {}, ctx)

        # VAT: 9% of €300 = €27
        assert result.components[0].tax_amount == Decimal("27.00")
        # Tourist tax: 7% of €300 = €21
        assert result.components[1].tax_amount == Decimal("21.00")
        assert result.total_tax == Decimal("48.00")

    def test_flat_per_person_per_night(self):
        """Per-person-per-night flat tax: €3 × 2 guests × 4 nights = €24."""
        ctx = make_context(nightly_rate=Decimal("100"), nights=4, number_of_guests=2)

        rate = make_rate(
            id=1, rate_type="flat", rate_value=3.0,
            category_code="tourism_flat_person_night",
            category_name="Tourist Tax (per person)",
            category_level_2="flat_per_person_per_night",
            calculation_order=10,
        )

        result = calculate_taxes([rate], {}, ctx)

        assert result.components[0].tax_amount == Decimal("24.00")

    def test_flat_per_stay_entry_tax(self):
        """Per-stay entry tax: $10 × 1 (not multiplied by nights)."""
        ctx = make_context(nightly_rate=Decimal("200"), nights=5, number_of_guests=2)

        rate = make_rate(
            id=1, rate_type="flat", rate_value=10.0,
            category_code="entry_tax",
            category_name="Tourism Entry Tax",
            category_level_2="flat_per_stay",
            calculation_order=10,
        )

        result = calculate_taxes([rate], {}, ctx)

        # Per-stay: $10 × 1 = $10 (not × 5 nights)
        assert result.components[0].tax_amount == Decimal("10.00")

    def test_flat_per_person_per_stay(self):
        """Per-person per-stay: $26 × 2 guests = $52 (not multiplied by nights)."""
        ctx = make_context(nightly_rate=Decimal("200"), nights=5, number_of_guests=2)

        rate = make_rate(
            id=1, rate_type="flat", rate_value=26.0,
            category_code="visitax",
            category_name="VISITAX",
            category_level_2="flat_per_person_per_stay",
            calculation_order=10,
        )

        result = calculate_taxes([rate], {}, ctx)

        # Per-person per-stay: $26 × 2 guests = $52
        assert result.components[0].tax_amount == Decimal("52.00")

    def test_jpy_currency_rounding(self):
        """JPY should round to 0 decimal places."""
        ctx = make_context(
            jurisdiction_code="JP-13-TYO",
            nightly_rate=Decimal("12345"),
            nights=1,
            currency="JPY",
        )

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.10,
            category_code="vat_standard", category_name="Consumption Tax",
            jurisdiction_code="JP", jurisdiction_type="country",
            calculation_order=10,
        )

        result = calculate_taxes([rate], {}, ctx)

        # 10% of ¥12345 = ¥1234.5 → rounded to ¥1235 (no decimals)
        assert result.components[0].tax_amount == Decimal("1235")

    def test_bhd_currency_rounding(self):
        """BHD should round to 3 decimal places."""
        ctx = make_context(
            nightly_rate=Decimal("100"),
            nights=1,
            currency="BHD",
        )

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.05,
            category_code="tourism_pct", category_name="Tourism Tax",
            calculation_order=10,
        )

        result = calculate_taxes([rate], {}, ctx)

        # 5% of 100 BHD = 5.000 (3 decimal places)
        assert result.components[0].tax_amount == Decimal("5.000")

    def test_cap_nights_applied_in_calculation(self):
        """Cap rule with max_nights should limit chargeable nights."""
        ctx = make_context(nightly_rate=Decimal("100"), nights=45)

        rate = make_rate(
            id=1, rate_type="flat", rate_value=10.0,
            category_code="tourism_flat",
            category_name="Tourism Fee",
            category_level_2="flat_per_night",
            calculation_order=10,
        )

        cap_rule = make_rule(
            id=1, rule_type="cap", priority=50,
            name="30 Night Cap",
            conditions={},
            action={"max_nights": 30},
        )

        result = calculate_taxes([rate], {1: [cap_rule]}, ctx)

        # Should be capped at 30 nights: $10 × 30 = $300 (not $10 × 45 = $450)
        assert result.components[0].tax_amount == Decimal("300.00")

    def test_reduction_applied_in_calculation(self):
        """Reduction rule should reduce tax by the specified percentage."""
        ctx = make_context(
            nightly_rate=Decimal("100"), nights=2,
            guest_age=15,
        )

        rate = make_rate(
            id=1, rate_type="flat", rate_value=5.0,
            category_code="tourism_flat",
            category_name="City Tax",
            category_level_2="flat_per_night",
            calculation_order=10,
        )

        reduction_rule = make_rule(
            id=1, rule_type="reduction", priority=50,
            name="Youth 50% Reduction",
            conditions={
                "operator": "AND",
                "rules": [{"field": "guest_age", "op": "between", "value": [12, 18]}],
            },
            action={"reduction_percent": 0.5},
        )

        result = calculate_taxes([rate], {1: [reduction_rule]}, ctx)

        # Base: $5 × 2 nights = $10, then 50% reduction = $5
        assert result.components[0].tax_amount == Decimal("5.00")

    def test_surcharge_applied_in_calculation(self):
        """Surcharge rule should add additional tax on top of base."""
        ctx = make_context(
            nightly_rate=Decimal("200"), nights=1,
            is_marketplace=True, property_type="short_term_rental",
        )

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.04,
            category_code="occ_pct", category_name="Occupancy Tax",
            calculation_order=10,
        )

        surcharge_rule = make_rule(
            id=1, rule_type="surcharge", priority=50,
            name="Platform STR Surcharge",
            conditions={
                "operator": "AND",
                "rules": [
                    {"field": "is_marketplace", "op": "==", "value": True},
                    {"field": "property_type", "op": "==", "value": "short_term_rental"},
                ],
            },
            action={"rate_value": 0.05},
        )

        result = calculate_taxes([rate], {1: [surcharge_rule]}, ctx)

        # Base tax: 4% of $200 = $8
        # Surcharge: 5% of $200 = $10
        # Total component: $18
        assert result.components[0].tax_amount == Decimal("18.00")

    def test_cap_per_person_per_night_in_calculation(self):
        """Cap with max_per_person_per_night limits the total tax."""
        ctx = make_context(
            nightly_rate=Decimal("200"), nights=3, number_of_guests=2,
        )

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.05,
            category_code="tourism_pct", category_name="Unclassified Tourist Tax",
            calculation_order=10,
        )

        cap_rule = make_rule(
            id=1, rule_type="cap", priority=50,
            name="Max €5/person/night",
            conditions={},
            action={"max_per_person_per_night": 5.0},
        )

        result = calculate_taxes([rate], {1: [cap_rule]}, ctx)

        # Without cap: 5% of (200 × 3) = $30
        # Cap: €5 × 3 nights × 2 guests = €30
        # In this case they're equal, so let's test with higher rate
        assert result.components[0].tax_amount == Decimal("30.00")

    def test_cap_per_person_per_night_actually_caps(self):
        """Cap per person per night should actually limit when tax exceeds cap."""
        ctx = make_context(
            nightly_rate=Decimal("500"), nights=2, number_of_guests=1,
        )

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.05,
            category_code="tourism_pct", category_name="Tourist Tax",
            calculation_order=10,
        )

        cap_rule = make_rule(
            id=1, rule_type="cap", priority=50,
            name="Max €5/person/night",
            conditions={},
            action={"max_per_person_per_night": 5.0},
        )

        result = calculate_taxes([rate], {1: [cap_rule]}, ctx)

        # Without cap: 5% of (500 × 2) = $50
        # Cap: €5 × 2 nights × 1 guest = €10
        assert result.components[0].tax_amount == Decimal("10.00")


# ─── Bug Fix & New Capability Tests ──────────────────────────────

class TestMultipleReductionsStack:
    """Bug fix: multiple reductions should compound multiplicatively."""

    def test_two_reductions_stack_multiplicatively(self):
        """75% off-season + 50% long-stay = 1 - (0.25 * 0.50) = 87.5% total."""
        ctx = make_context(
            stay_date=date(2025, 12, 15),
            nights=10,
        )
        rate = make_rate()

        seasonal_rule = make_rule(
            id=1, rule_type="reduction", priority=90,
            name="Off-Season 75% Reduction",
            conditions={
                "operator": "OR",
                "rules": [
                    {"field": "stay_month", "op": ">=", "value": 11},
                    {"field": "stay_month", "op": "<=", "value": 3},
                ],
            },
            action={"reduction_percent": 0.75},
        )
        longstay_rule = make_rule(
            id=2, rule_type="reduction", priority=80,
            name="Long-Stay 50% Reduction",
            conditions={
                "operator": "AND",
                "rules": [{"field": "stay_length_days", "op": ">", "value": 8}],
            },
            action={"reduction_percent": 0.5},
        )

        result = apply_rules([seasonal_rule, longstay_rule], ctx, rate)
        assert result.reduction_pct == Decimal("0.875")
        assert len([t for t in result.traces if t.result == "applied"]) == 2

    def test_stacked_reductions_in_calculation(self):
        """Full pipeline: €4/night × 3 nights = €12, then 87.5% reduction = €1.50."""
        ctx = make_context(
            stay_date=date(2025, 12, 15),
            nightly_rate=Decimal("100"),
            nights=10,
            currency="EUR",
        )

        rate = make_rate(
            id=1, rate_type="flat", rate_value=4.0,
            category_code="eco_flat",
            category_name="Eco Tax",
            category_level_2="flat_per_night",
            calculation_order=10,
        )

        seasonal_rule = make_rule(
            id=1, rule_type="reduction", priority=90,
            name="Off-Season 75%",
            conditions={
                "operator": "OR",
                "rules": [
                    {"field": "stay_month", "op": ">=", "value": 11},
                    {"field": "stay_month", "op": "<=", "value": 3},
                ],
            },
            action={"reduction_percent": 0.75},
        )
        longstay_rule = make_rule(
            id=2, rule_type="reduction", priority=80,
            name="Long-Stay 50%",
            conditions={
                "operator": "AND",
                "rules": [{"field": "stay_length_days", "op": ">", "value": 8}],
            },
            action={"reduction_percent": 0.5},
        )

        result = calculate_taxes([rate], {1: [seasonal_rule, longstay_rule]}, ctx)

        # €4 × 10 nights = €40, then 87.5% reduction → €40 × 0.125 = €5.00
        assert result.components[0].tax_amount == Decimal("5.00")


class TestMultipleCapsCompose:
    """Bug fix: multiple caps should use the most restrictive."""

    def test_two_night_caps_use_minimum(self):
        ctx = make_context(nights=30)
        rate = make_rate()

        cap_21 = make_rule(
            id=1, rule_type="cap", priority=80,
            name="21-Night Cap",
            conditions={}, action={"max_nights": 21},
        )
        cap_28 = make_rule(
            id=2, rule_type="cap", priority=70,
            name="28-Night Cap",
            conditions={}, action={"max_nights": 28},
        )

        result = apply_rules([cap_21, cap_28], ctx, rate)
        assert result.cap_nights == 21  # Most restrictive

    def test_two_amount_caps_use_minimum(self):
        ctx = make_context()
        rate = make_rate()

        cap_50 = make_rule(
            id=1, rule_type="cap", priority=80,
            name="Max $50",
            conditions={}, action={"max_amount": 50},
        )
        cap_100 = make_rule(
            id=2, rule_type="cap", priority=70,
            name="Max $100",
            conditions={}, action={"max_amount": 100},
        )

        result = apply_rules([cap_50, cap_100], ctx, rate)
        assert result.cap_amount == Decimal("50")


class TestMultipleSurchargesStack:
    """Bug fix: multiple surcharges should stack additively."""

    def test_two_surcharges_add(self):
        ctx = make_context(is_marketplace=True, property_type="short_term_rental")
        rate = make_rate()

        marketplace_surcharge = make_rule(
            id=1, rule_type="surcharge", priority=80,
            name="Marketplace +1.5%",
            conditions={
                "operator": "AND",
                "rules": [{"field": "is_marketplace", "op": "==", "value": True}],
            },
            action={"rate_value": 0.015},
        )
        str_surcharge = make_rule(
            id=2, rule_type="surcharge", priority=70,
            name="STR +2%",
            conditions={
                "operator": "AND",
                "rules": [{"field": "property_type", "op": "==", "value": "short_term_rental"}],
            },
            action={"rate_value": 0.02},
        )

        result = apply_rules([marketplace_surcharge, str_surcharge], ctx, rate)
        assert result.surcharge_rate == Decimal("0.035")  # 1.5% + 2% = 3.5%

    def test_stacked_surcharges_in_calculation(self):
        """Full pipeline: 8% base + 1.5% + 2% surcharges."""
        ctx = make_context(
            nightly_rate=Decimal("200"), nights=1,
            is_marketplace=True, property_type="short_term_rental",
        )

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.08,
            category_code="occ_pct", category_name="PST",
            calculation_order=10,
        )

        marketplace_surcharge = make_rule(
            id=1, rule_type="surcharge", priority=80,
            name="Marketplace +1.5%",
            conditions={
                "operator": "AND",
                "rules": [{"field": "is_marketplace", "op": "==", "value": True}],
            },
            action={"rate_value": 0.015},
        )
        str_surcharge = make_rule(
            id=2, rule_type="surcharge", priority=70,
            name="STR +2%",
            conditions={
                "operator": "AND",
                "rules": [{"field": "property_type", "op": "==", "value": "short_term_rental"}],
            },
            action={"rate_value": 0.02},
        )

        result = calculate_taxes([rate], {1: [marketplace_surcharge, str_surcharge]}, ctx)

        # Base tax: 8% of $200 = $16
        # Surcharges: 3.5% of $200 = $7
        # Total: $23
        assert result.components[0].tax_amount == Decimal("23.00")


class TestMinAmountFloor:
    """New capability: minimum tax amount."""

    def test_min_amount_applied(self):
        ctx = make_context(nightly_rate=Decimal("20"), nights=1)

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.05,
            category_code="tourism_pct", category_name="Tourism Tax",
            calculation_order=10,
        )

        min_rule = make_rule(
            id=1, rule_type="cap", priority=50,
            name="Minimum $3/night",
            conditions={}, action={"min_amount": 3.0},
        )

        result = calculate_taxes([rate], {1: [min_rule]}, ctx)

        # Without floor: 5% of $20 = $1, but minimum is $3
        assert result.components[0].tax_amount == Decimal("3.00")

    def test_min_amount_not_applied_when_tax_is_higher(self):
        ctx = make_context(nightly_rate=Decimal("200"), nights=1)

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.05,
            category_code="tourism_pct", category_name="Tourism Tax",
            calculation_order=10,
        )

        min_rule = make_rule(
            id=1, rule_type="cap", priority=50,
            name="Minimum $3/night",
            conditions={}, action={"min_amount": 3.0},
        )

        result = calculate_taxes([rate], {1: [min_rule]}, ctx)

        # 5% of $200 = $10, which is > $3, so no floor applied
        assert result.components[0].tax_amount == Decimal("10.00")

    def test_min_amount_not_applied_when_exempt(self):
        """Minimum floor should NOT apply when fully exempt (tax = 0)."""
        ctx = make_context(nightly_rate=Decimal("20"), nights=180)

        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.05,
            category_code="tourism_pct", category_name="Tourism Tax",
            calculation_order=10,
        )

        exemption = make_rule(
            id=1, rule_type="exemption", priority=100,
            name="Long Stay Exemption",
            conditions={
                "operator": "AND",
                "rules": [{"field": "stay_length_days", "op": ">=", "value": 180}],
            },
        )

        # This min rule is on same rate but shouldn't apply since exempt
        result = calculate_taxes([rate], {1: [exemption]}, ctx)
        assert result.components[0].tax_amount == Decimal("0")


class TestDayOfWeekCondition:
    """New capability: day-of-week condition field."""

    def test_friday_is_day_4(self):
        # 2025-06-13 is a Friday
        ctx = make_context(stay_date=date(2025, 6, 13))
        assert ctx.stay_day_of_week == 4

    def test_saturday_is_day_5(self):
        ctx = make_context(stay_date=date(2025, 6, 14))
        assert ctx.stay_day_of_week == 5

    def test_monday_is_day_0(self):
        ctx = make_context(stay_date=date(2025, 6, 16))
        assert ctx.stay_day_of_week == 0

    def test_weekend_surcharge_applies_on_friday(self):
        ctx = make_context(stay_date=date(2025, 6, 13))  # Friday
        rate = make_rate()

        weekend_rule = make_rule(
            id=1, rule_type="surcharge", priority=50,
            name="Weekend Surcharge",
            conditions={
                "operator": "AND",
                "rules": [{"field": "stay_day_of_week", "op": "in", "value": [4, 5]}],
            },
            action={"rate_value": 0.02},
        )

        result = apply_rules([weekend_rule], ctx, rate)
        assert result.surcharge_rate == Decimal("0.02")

    def test_weekend_surcharge_skipped_on_tuesday(self):
        ctx = make_context(stay_date=date(2025, 6, 17))  # Tuesday
        rate = make_rate()

        weekend_rule = make_rule(
            id=1, rule_type="surcharge", priority=50,
            name="Weekend Surcharge",
            conditions={
                "operator": "AND",
                "rules": [{"field": "stay_day_of_week", "op": "in", "value": [4, 5]}],
            },
            action={"rate_value": 0.02},
        )

        result = apply_rules([weekend_rule], ctx, rate)
        assert result.surcharge_rate is None
        assert result.traces[0].result == "skipped"


class TestThresholdTierType:
    """Test threshold tier type with real seed-data-style tiers."""

    def test_threshold_low_bracket(self):
        """Below TRY 500 → 2% rate."""
        ctx = make_context(
            nightly_rate=Decimal("300"), nights=2, currency="TRY",
        )

        rate = make_rate(
            id=1, rate_type="tiered", rate_value=None,
            category_code="tier_threshold",
            category_name="Accommodation Tax (threshold)",
            category_level_2="tiered_by_price",
            calculation_order=10,
            tiers=[
                {"min": 0, "max": 500, "rate": 0.02},
                {"min": 500, "max": 1500, "rate": 0.04},
                {"min": 1500, "rate": 0.06},
            ],
            tier_type="threshold",
        )

        result = calculate_taxes([rate], {}, ctx)
        # 2% of (300 × 2) = 12.00
        assert result.components[0].tax_amount == Decimal("12.00")

    def test_threshold_mid_bracket(self):
        """TRY 800 → 4% rate (500-1500 bracket)."""
        ctx = make_context(
            nightly_rate=Decimal("800"), nights=1, currency="TRY",
        )

        rate = make_rate(
            id=1, rate_type="tiered", rate_value=None,
            category_code="tier_threshold",
            category_name="Accommodation Tax",
            category_level_2="tiered_by_price",
            calculation_order=10,
            tiers=[
                {"min": 0, "max": 500, "rate": 0.02},
                {"min": 500, "max": 1500, "rate": 0.04},
                {"min": 1500, "rate": 0.06},
            ],
            tier_type="threshold",
        )

        result = calculate_taxes([rate], {}, ctx)
        # 4% of 800 = 32.00
        assert result.components[0].tax_amount == Decimal("32.00")

    def test_threshold_high_bracket(self):
        """TRY 2000 → 6% rate."""
        ctx = make_context(
            nightly_rate=Decimal("2000"), nights=1, currency="TRY",
        )

        rate = make_rate(
            id=1, rate_type="tiered", rate_value=None,
            category_code="tier_threshold",
            category_name="Accommodation Tax",
            category_level_2="tiered_by_price",
            calculation_order=10,
            tiers=[
                {"min": 0, "max": 500, "rate": 0.02},
                {"min": 500, "max": 1500, "rate": 0.04},
                {"min": 1500, "rate": 0.06},
            ],
            tier_type="threshold",
        )

        result = calculate_taxes([rate], {}, ctx)
        # 6% of 2000 = 120.00
        assert result.components[0].tax_amount == Decimal("120.00")


# ═══════════════════════════════════════════════════════════════════
#  EDGE CASES & ROBUSTNESS
# ═══════════════════════════════════════════════════════════════════


class TestEdgeCaseEmptyTiers:
    """Tiered rate with empty or missing tier list should return 0."""

    def test_empty_tiers_list(self):
        ctx = make_context(nightly_rate=Decimal("100"), nights=1, currency="USD")
        rate = make_rate(
            id=1, rate_type="tiered", rate_value=None,
            category_code="tier_empty", category_name="Empty Tier",
            category_level_2="tiered_by_price", calculation_order=10,
            tiers=[], tier_type="single_amount",
        )
        result = calculate_taxes([rate], {}, ctx)
        assert result.total_tax == Decimal("0")
        # Component is still added but with zero amount
        assert all(c.tax_amount == Decimal("0") for c in result.components)

    def test_none_tiers(self):
        ctx = make_context(nightly_rate=Decimal("100"), nights=1, currency="USD")
        rate = make_rate(
            id=1, rate_type="tiered", rate_value=None,
            category_code="tier_none", category_name="None Tier",
            category_level_2="tiered_by_price", calculation_order=10,
            tiers=None, tier_type="single_amount",
        )
        result = calculate_taxes([rate], {}, ctx)
        assert result.total_tax == Decimal("0")


class TestEdgeCaseZeroRate:
    """Zero rate should produce zero tax."""

    def test_zero_percentage(self):
        ctx = make_context(nightly_rate=Decimal("200"), nights=3, currency="USD")
        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.0,
            category_code="zero_pct", category_name="Zero Tax",
            category_level_2="percentage",
        )
        result = calculate_taxes([rate], {}, ctx)
        assert result.total_tax == Decimal("0")

    def test_zero_flat(self):
        ctx = make_context(nightly_rate=Decimal("200"), nights=3, currency="USD")
        rate = make_rate(
            id=1, rate_type="flat", rate_value=0.0,
            category_code="zero_flat", category_name="Zero Flat",
            category_level_2="flat_per_night",
        )
        result = calculate_taxes([rate], {}, ctx)
        assert result.total_tax == Decimal("0")


class TestEdgeCaseZeroNightlyRate:
    """Zero nightly rate should not crash and produce zero tax."""

    def test_zero_nightly_rate(self):
        ctx = make_context(nightly_rate=Decimal("0"), nights=3, currency="USD")
        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.14975,
            category_code="occ_pct", category_name="Occ Tax",
            category_level_2="percentage",
        )
        result = calculate_taxes([rate], {}, ctx)
        assert result.total_tax == Decimal("0")
        assert result.effective_rate == Decimal("0")


class TestEdgeCaseJPYRounding:
    """JPY has 0 decimal places — taxes should be rounded to whole numbers."""

    def test_jpy_rounds_to_whole(self):
        ctx = make_context(nightly_rate=Decimal("9999"), nights=1, currency="JPY")
        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.10,
            category_code="vat", category_name="VAT",
            category_level_2="percentage",
        )
        result = calculate_taxes([rate], {}, ctx)
        # 9999 * 0.10 = 999.9 → rounds to 1000 (JPY)
        assert result.total_tax == Decimal("1000")


class TestEdgeCaseLargeValues:
    """Very large rate values should not overflow or crash."""

    def test_large_nightly_rate(self):
        ctx = make_context(
            nightly_rate=Decimal("999999.99"), nights=365, currency="USD",
        )
        rate = make_rate(
            id=1, rate_type="percentage", rate_value=0.25,
            category_code="vat", category_name="VAT",
            category_level_2="percentage",
        )
        result = calculate_taxes([rate], {}, ctx)
        # Should not crash, result should be positive
        assert result.total_tax > Decimal("0")
        assert result.effective_rate > Decimal("0")


class TestEdgeCaseNoneRateValue:
    """Percentage or flat rate with None rate_value should produce 0 tax."""

    def test_none_rate_value_percentage(self):
        ctx = make_context(nightly_rate=Decimal("100"), nights=1, currency="USD")
        rate = make_rate(
            id=1, rate_type="percentage", rate_value=None,
            category_code="null_pct", category_name="Null Pct",
            category_level_2="percentage",
        )
        result = calculate_taxes([rate], {}, ctx)
        assert result.total_tax == Decimal("0")
