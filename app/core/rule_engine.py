"""
Tax calculation rule engine.

Follows Catala's default-logic pattern: base rates apply unless
a higher-priority exception (exemption/override) overrides them.

Inspired by OpenFisca scale types for tiered rate calculations.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import uuid4

from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule

# ─── Currency Rounding ──────────────────────────────────────────────

# ISO 4217 minor-unit exceptions (most currencies use 2 decimal places)
CURRENCY_DECIMALS: dict[str, int] = {
    # 0 decimal places
    "BIF": 0, "CLP": 0, "DJF": 0, "GNF": 0, "ISK": 0, "JPY": 0,
    "KMF": 0, "KRW": 0, "PYG": 0, "RWF": 0, "UGX": 0, "UYI": 0,
    "VND": 0, "VUV": 0, "XAF": 0, "XOF": 0, "XPF": 0,
    # 3 decimal places
    "BHD": 3, "IQD": 3, "JOD": 3, "KWD": 3, "LYD": 3, "OMR": 3,
    "TND": 3,
}


def _get_currency_decimals(currency: str) -> int:
    """Return the number of decimal places for a currency code."""
    return CURRENCY_DECIMALS.get(currency.upper(), 2)


@dataclass
class BookingContext:
    """All attributes available for rule condition evaluation."""

    jurisdiction_code: str
    stay_date: date
    checkout_date: date | None
    nightly_rate: Decimal
    nights: int
    currency: str
    property_type: str = "hotel"
    star_rating: int | None = None
    guest_type: str = "standard"
    guest_age: int | None = None
    guest_nationality: str | None = None
    number_of_guests: int = 1
    is_marketplace: bool = False
    platform_type: str = "direct"
    is_bundled: bool = False

    @property
    def stay_length_days(self) -> int:
        return self.nights

    @property
    def stay_month(self) -> int:
        return self.stay_date.month

    @property
    def stay_day_of_week(self) -> int:
        """0=Monday, 6=Sunday (ISO weekday)."""
        return self.stay_date.weekday()

    @property
    def total_stay_amount(self) -> Decimal:
        return self.nightly_rate * self.nights

    def get_field(self, field_name: str) -> Any:
        """Get a field value by name for condition evaluation."""
        # Check regular attributes and properties via the class descriptor
        if field_name in {
            "stay_length_days", "stay_month", "total_stay_amount",
            "stay_day_of_week",
        }:
            return getattr(self, field_name)
        if hasattr(self, field_name):
            return getattr(self, field_name)
        return None


@dataclass
class TaxComponentResult:
    name: str
    category_code: str
    jurisdiction_code: str
    jurisdiction_level: str
    rate: float | None
    rate_type: str
    taxable_amount: Decimal | None
    tax_amount: Decimal
    legal_reference: str | None
    authority: str | None


@dataclass
class RuleTrace:
    rule_id: int
    name: str
    rule_type: str
    result: str  # "applied", "skipped", "exempted"


@dataclass
class RuleApplicationResult:
    is_exempt: bool = False
    override_rate: Decimal | None = None
    cap_nights: int | None = None
    cap_amount: Decimal | None = None
    cap_per_night: Decimal | None = None
    cap_per_person_per_night: Decimal | None = None
    surcharge_rate: Decimal | None = None
    reduction_pct: Decimal | None = None
    min_amount: Decimal | None = None
    traces: list[RuleTrace] = field(default_factory=list)


@dataclass
class CalculationResult:
    calculation_id: str
    components: list[TaxComponentResult] = field(default_factory=list)
    rules_traced: list[RuleTrace] = field(default_factory=list)
    total_tax: Decimal = Decimal("0")
    effective_rate: Decimal = Decimal("0")


# ─── Condition Evaluator ─────────────────────────────────────────────

OPERATORS: dict[str, Any] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a is not None and a > b,
    ">=": lambda a, b: a is not None and a >= b,
    "<": lambda a, b: a is not None and a < b,
    "<=": lambda a, b: a is not None and a <= b,
    "in": lambda a, b: a in b if b else False,
    "not_in": lambda a, b: a not in b if b else True,
    "between": lambda a, b: a is not None and len(b) == 2 and b[0] <= a <= b[1],
}


def evaluate_conditions(conditions: dict, context: BookingContext) -> bool:
    """
    Evaluate JSONB conditions against a booking context.
    Supports nested AND/OR groups.
    """
    if not conditions or not conditions.get("rules"):
        return True  # Empty conditions = always matches

    operator = conditions.get("operator", "AND")
    rules = conditions.get("rules", [])
    results = []

    for rule in rules:
        if "operator" in rule:
            # Nested group
            results.append(evaluate_conditions(rule, context))
        else:
            field_name = rule.get("field", "")
            field_value = context.get_field(field_name)
            op_name = rule.get("op", "==")
            compare_value = rule.get("value")

            op_fn = OPERATORS.get(op_name)
            if op_fn is None:
                results.append(False)
                continue

            # Convert Decimal for numeric comparisons
            if isinstance(field_value, Decimal) and isinstance(compare_value, (int, float)):
                compare_value = Decimal(str(compare_value))
            if isinstance(field_value, (int, float)) and isinstance(compare_value, (int, float)):
                # Normalize both to same type for comparison
                pass
            # Handle between with Decimal conversion
            if op_name == "between" and isinstance(compare_value, list):
                if isinstance(field_value, Decimal):
                    compare_value = [Decimal(str(v)) for v in compare_value]

            try:
                results.append(op_fn(field_value, compare_value))
            except (TypeError, ValueError):
                results.append(False)

    if operator == "AND":
        return all(results)
    elif operator == "OR":
        return any(results)
    return False


# ─── Tax Calculators ─────────────────────────────────────────────────

def _round_tax(amount: Decimal, currency: str = "USD") -> Decimal:
    """Round to the correct number of decimal places for the currency."""
    decimals = _get_currency_decimals(currency)
    if decimals == 0:
        return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    quantizer = Decimal(10) ** -decimals  # 0.01 for 2, 0.001 for 3
    return amount.quantize(quantizer, rounding=ROUND_HALF_UP)


def calculate_percentage(base: Decimal, rate_value: float, currency: str = "USD") -> Decimal:
    return _round_tax(base * Decimal(str(rate_value)), currency)


def calculate_flat(
    rate_value: float,
    nights: int,
    number_of_guests: int,
    category_level_2: str,
    currency: str = "USD",
) -> Decimal:
    """Calculate flat-rate taxes (per night, per person per night, per stay, etc.)."""
    amount = Decimal(str(rate_value))

    # Per-stay charges (entry taxes, one-time fees) — multiplier is 1
    if "per_stay" in category_level_2 or "per_entry" in category_level_2:
        multiplier = 1
    else:
        multiplier = nights

    if "per_person" in category_level_2:
        multiplier *= number_of_guests

    return _round_tax(amount * multiplier, currency)


def calculate_tiered(
    nightly_rate: Decimal,
    tiers: list[dict],
    tier_type: str,
    nights: int,
    number_of_guests: int = 1,
    currency: str = "USD",
    category_level_2: str = "",
    star_rating: int | None = None,
) -> Decimal:
    """
    OpenFisca-inspired scale calculation.

    single_amount: returns flat amount for matching bracket (Tokyo style)
    threshold: rate changes entirely above threshold (India GST style)
    marginal_rate: different rate per bracket portion (income tax style)
    """
    if not tiers:
        return Decimal("0")

    # Use star_rating as bracket key for star-based tiers, nightly_rate otherwise
    bracket_key = (
        Decimal(str(star_rating)) if "by_star" in category_level_2 and star_rating is not None
        else nightly_rate
    )

    match tier_type:
        case "single_amount":
            for tier in tiers:
                tier_min = Decimal(str(tier.get("min", 0)))
                tier_max = tier.get("max")
                if tier_max is None or bracket_key < Decimal(str(tier_max)):
                    if bracket_key >= tier_min:
                        base = Decimal(str(tier["value"])) * nights
                        if "per_person" in category_level_2:
                            base *= number_of_guests
                        return _round_tax(base, currency)
            return Decimal("0")

        case "threshold":
            for tier in reversed(tiers):
                if nightly_rate >= Decimal(str(tier.get("min", 0))):
                    return _round_tax(nightly_rate * nights * Decimal(str(tier["rate"])), currency)
            return Decimal("0")

        case "marginal_rate":
            total = Decimal("0")
            remaining = nightly_rate
            for tier in tiers:
                tier_min = Decimal(str(tier.get("min", 0)))
                tier_max = tier.get("max")
                if tier_max is not None:
                    bracket_size = Decimal(str(tier_max)) - tier_min
                else:
                    bracket_size = remaining
                taxable = min(remaining, bracket_size)
                total += taxable * Decimal(str(tier["rate"]))
                remaining -= taxable
                if remaining <= 0:
                    break
            return _round_tax(total * nights, currency)

        case _:
            return Decimal("0")


# ─── Rule Application ────────────────────────────────────────────────

def apply_rules(
    rules: list[TaxRule],
    context: BookingContext,
    rate: TaxRate,
) -> RuleApplicationResult:
    """
    Apply tax rules to a rate following Catala default logic.

    Returns the full RuleApplicationResult with exemptions, overrides,
    caps, surcharges, and reductions.

    Rules are evaluated in priority order (highest first).
    First matching exemption wins and short-circuits.
    """
    result = RuleApplicationResult()

    # Sort by priority descending (highest priority first)
    sorted_rules = sorted(rules, key=lambda r: r.priority, reverse=True)

    for rule in sorted_rules:
        # Check temporal validity
        if rule.effective_start > context.stay_date:
            continue
        if rule.effective_end and rule.effective_end <= context.stay_date:
            continue

        matches = evaluate_conditions(rule.conditions, context)

        if not matches:
            result.traces.append(RuleTrace(
                rule_id=rule.id, name=rule.name, rule_type=rule.rule_type, result="skipped"
            ))
            continue

        action = rule.action or {}

        match rule.rule_type:
            case "exemption":
                result.is_exempt = True
                result.traces.append(RuleTrace(
                    rule_id=rule.id, name=rule.name, rule_type="exemption", result="exempted"
                ))
                return result  # First matching exemption wins

            case "override":
                result.override_rate = Decimal(str(action.get("rate_value", 0)))
                result.traces.append(RuleTrace(
                    rule_id=rule.id, name=rule.name, rule_type="override", result="applied"
                ))

            case "cap":
                # Multiple caps compose — most restrictive (min) wins
                if "max_nights" in action:
                    v = action["max_nights"]
                    result.cap_nights = min(result.cap_nights, v) if result.cap_nights is not None else v
                if "max_amount" in action:
                    v = Decimal(str(action["max_amount"]))
                    result.cap_amount = min(result.cap_amount, v) if result.cap_amount is not None else v
                if "max_per_night" in action:
                    v = Decimal(str(action["max_per_night"]))
                    result.cap_per_night = min(result.cap_per_night, v) if result.cap_per_night is not None else v
                if "max_per_person_per_night" in action:
                    v = Decimal(str(action["max_per_person_per_night"]))
                    result.cap_per_person_per_night = min(result.cap_per_person_per_night, v) if result.cap_per_person_per_night is not None else v
                if "min_amount" in action:
                    v = Decimal(str(action["min_amount"]))
                    result.min_amount = max(result.min_amount, v) if result.min_amount is not None else v
                result.traces.append(RuleTrace(
                    rule_id=rule.id, name=rule.name, rule_type="cap", result="applied"
                ))

            case "surcharge":
                # Multiple surcharges stack additively
                new_rate = Decimal(str(action.get("rate_value", 0)))
                if result.surcharge_rate is not None:
                    result.surcharge_rate += new_rate
                else:
                    result.surcharge_rate = new_rate
                result.traces.append(RuleTrace(
                    rule_id=rule.id, name=rule.name, rule_type="surcharge", result="applied"
                ))

            case "reduction":
                # Multiple reductions stack multiplicatively:
                # effective = 1 - (1-r1)*(1-r2)
                new_pct = Decimal(str(action.get("reduction_percent", 0)))
                if result.reduction_pct is not None:
                    result.reduction_pct = Decimal("1") - (
                        (Decimal("1") - result.reduction_pct) * (Decimal("1") - new_pct)
                    )
                else:
                    result.reduction_pct = new_pct
                result.traces.append(RuleTrace(
                    rule_id=rule.id, name=rule.name, rule_type="reduction", result="applied"
                ))

            case "condition":
                result.traces.append(RuleTrace(
                    rule_id=rule.id, name=rule.name, rule_type="condition", result="applied"
                ))

            case _:
                result.traces.append(RuleTrace(
                    rule_id=rule.id, name=rule.name, rule_type=rule.rule_type, result="applied"
                ))

    return result


# ─── Main Calculation ─────────────────────────────────────────────────

def calculate_taxes(
    rates: list[TaxRate],
    rules_by_rate: dict[int, list[TaxRule]],
    context: BookingContext,
) -> CalculationResult:
    """
    Main tax calculation pipeline.

    1. Rates are ordered by calculation_order
    2. For each rate, rules are evaluated (exemptions, overrides, caps, reductions, surcharges)
    3. Tax is calculated based on type (percentage, flat, tiered)
    4. Rule effects (caps, reductions, surcharges) are applied to the tax amount
    5. Cascading taxes use accumulated results as base
    """
    currency = context.currency
    result = CalculationResult(calculation_id=str(uuid4()))
    accumulated_taxes: dict[str, Decimal] = {}

    # Sort rates by calculation order
    sorted_rates = sorted(rates, key=lambda r: r.calculation_order)

    for rate in sorted_rates:
        rate_rules = rules_by_rate.get(rate.id, [])

        # Apply rules — returns full result with caps, surcharges, reductions
        rule_result = apply_rules(rate_rules, context, rate)
        result.rules_traced.extend(rule_result.traces)

        if rule_result.is_exempt:
            result.components.append(TaxComponentResult(
                name=f"{rate.tax_category.name} (EXEMPT)",
                category_code=rate.tax_category.code,
                jurisdiction_code=rate.jurisdiction.code,
                jurisdiction_level=rate.jurisdiction.jurisdiction_type,
                rate=float(rate.rate_value) if rate.rate_value else None,
                rate_type=rate.rate_type,
                taxable_amount=None,
                tax_amount=Decimal("0"),
                legal_reference=rate.legal_reference,
                authority=rate.authority_name,
            ))
            continue

        # Determine effective rate value (override takes precedence)
        effective_rate_value = (
            float(rule_result.override_rate) if rule_result.override_rate is not None
            else float(rate.rate_value) if rate.rate_value is not None
            else 0
        )

        # Apply cap on nights if a cap rule limits the chargeable nights
        effective_nights = context.nights
        if rule_result.cap_nights is not None:
            effective_nights = min(context.nights, rule_result.cap_nights)

        # Determine tax base
        base = context.nightly_rate * effective_nights
        if rate.base_includes:
            for tax_key in rate.base_includes:
                if tax_key != "base_amount" and tax_key in accumulated_taxes:
                    base += accumulated_taxes[tax_key]

        # Calculate tax amount
        category = rate.tax_category
        match rate.rate_type:
            case "percentage":
                tax_amount = calculate_percentage(base, effective_rate_value, currency)
            case "flat":
                tax_amount = calculate_flat(
                    effective_rate_value,
                    effective_nights,
                    context.number_of_guests,
                    category.level_2,
                    currency,
                )
            case "tiered":
                tax_amount = calculate_tiered(
                    context.nightly_rate,
                    rate.tiers or [],
                    rate.tier_type or "single_amount",
                    effective_nights,
                    context.number_of_guests,
                    currency,
                    category.level_2,
                    context.star_rating,
                )
            case _:
                tax_amount = Decimal("0")

        # Apply reduction (e.g., 50% reduction for ages 12-18)
        if rule_result.reduction_pct is not None and rule_result.reduction_pct > 0:
            tax_amount = _round_tax(
                tax_amount * (Decimal("1") - rule_result.reduction_pct),
                currency,
            )

        # Apply surcharge (additional percentage on top)
        if rule_result.surcharge_rate is not None and rule_result.surcharge_rate > 0:
            surcharge = _round_tax(base * rule_result.surcharge_rate, currency)
            tax_amount += surcharge

        # Apply amount caps
        if rule_result.cap_amount is not None:
            tax_amount = min(tax_amount, rule_result.cap_amount)

        if rule_result.cap_per_night is not None:
            max_total = _round_tax(
                rule_result.cap_per_night * effective_nights,
                currency,
            )
            tax_amount = min(tax_amount, max_total)

        if rule_result.cap_per_person_per_night is not None:
            max_total = _round_tax(
                rule_result.cap_per_person_per_night * effective_nights * context.number_of_guests,
                currency,
            )
            tax_amount = min(tax_amount, max_total)

        # Apply minimum tax floor (only if tax > 0, i.e. not exempt)
        if rule_result.min_amount is not None and tax_amount > 0:
            tax_amount = max(tax_amount, rule_result.min_amount)

        # Store for cascading
        accumulated_taxes[category.code] = tax_amount

        result.components.append(TaxComponentResult(
            name=rate.tax_category.name,
            category_code=rate.tax_category.code,
            jurisdiction_code=rate.jurisdiction.code,
            jurisdiction_level=rate.jurisdiction.jurisdiction_type,
            rate=effective_rate_value,
            rate_type=rate.rate_type,
            taxable_amount=base if rate.rate_type == "percentage" else None,
            tax_amount=tax_amount,
            legal_reference=rate.legal_reference,
            authority=rate.authority_name,
        ))

    result.total_tax = sum(c.tax_amount for c in result.components)
    subtotal = context.nightly_rate * context.nights
    result.effective_rate = (
        _round_tax(result.total_tax / subtotal, currency) if subtotal > 0 else Decimal("0")
    )

    return result
