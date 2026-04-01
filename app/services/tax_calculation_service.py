from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rule_engine import BookingContext, CalculationResult, calculate_taxes
from app.schemas.tax_calculation import (
    BatchCalculationRequest,
    BatchCalculationResponse,
    BatchCalculationResult,
    RuleTraceEntry,
    TaxBreakdown,
    TaxCalculationRequest,
    TaxCalculationResponse,
    TaxComponent,
)
from app.services.jurisdiction_service import get_jurisdiction_with_ancestors
from app.services.tax_rate_service import get_active_rates_for_jurisdiction, get_rules_for_rates


async def calculate_tax(
    db: AsyncSession,
    request: TaxCalculationRequest,
) -> TaxCalculationResponse:
    """Main tax calculation endpoint logic."""

    # 1. Resolve jurisdiction chain (all ancestors + self)
    jurisdictions = await get_jurisdiction_with_ancestors(db, request.jurisdiction_code)
    if not jurisdictions:
        raise ValueError(f"Jurisdiction not found: {request.jurisdiction_code}")

    jurisdiction_ids = [j.id for j in jurisdictions]
    target_jurisdiction = jurisdictions[-1]

    # 2. Get all active rates for the jurisdiction chain on the stay date
    rates = await get_active_rates_for_jurisdiction(db, jurisdiction_ids, request.stay_date)

    # 3. Get rules for those rates (both rate-specific and jurisdiction-level)
    rate_ids = [r.id for r in rates]
    rules_by_rate, jurisdiction_rules = await get_rules_for_rates(
        db, rate_ids, request.stay_date, jurisdiction_ids=jurisdiction_ids
    )

    # Merge jurisdiction-level rules into each rate's rule list.
    # Smart filtering: rules that override/reduce a percentage rate value
    # should only apply to percentage-type rates (not flat fees/service charges).
    for rate in rates:
        jur_rules = jurisdiction_rules.get(rate.jurisdiction_id, [])
        if not jur_rules:
            continue
        applicable = []
        for rule in jur_rules:
            action = rule.action or {}
            is_pct_rule = "override_rate" in action or "reduction_percent" in action
            if is_pct_rule and rate.rate_type != "percentage":
                continue  # Don't apply percentage overrides to flat-rate taxes
            applicable.append(rule)
        existing = rules_by_rate.get(rate.id, [])
        rules_by_rate[rate.id] = existing + applicable

    # 4. Build booking context
    context = BookingContext(
        jurisdiction_code=request.jurisdiction_code,
        stay_date=request.stay_date,
        checkout_date=request.checkout_date,
        nightly_rate=request.nightly_rate,
        nights=request.nights,
        currency=request.currency,
        property_type=request.property_type,
        star_rating=request.star_rating,
        guest_type=request.guest_type,
        guest_age=request.guest_age,
        guest_nationality=request.guest_nationality,
        number_of_guests=request.number_of_guests,
        is_marketplace=request.is_marketplace,
        platform_type=request.platform_type,
        is_bundled=request.is_bundled,
    )

    # 5. Run calculation
    calc_result: CalculationResult = calculate_taxes(rates, rules_by_rate, context)

    # 6. Build response
    subtotal = request.nightly_rate * request.nights

    return TaxCalculationResponse(
        calculation_id=calc_result.calculation_id,
        jurisdiction={
            "code": target_jurisdiction.code,
            "name": target_jurisdiction.name,
            "path": target_jurisdiction.path,
        },
        input={
            "nightly_rate": float(request.nightly_rate),
            "nights": request.nights,
            "subtotal": float(subtotal),
            "currency": request.currency,
            "property_type": request.property_type,
        },
        tax_breakdown=TaxBreakdown(
            components=[
                TaxComponent(
                    name=c.name,
                    category_code=c.category_code,
                    jurisdiction_code=c.jurisdiction_code,
                    jurisdiction_level=c.jurisdiction_level,
                    rate=c.rate,
                    rate_type=c.rate_type,
                    taxable_amount=c.taxable_amount,
                    tax_amount=c.tax_amount,
                    legal_reference=c.legal_reference,
                    authority=c.authority,
                )
                for c in calc_result.components
            ],
            total_tax=calc_result.total_tax,
            effective_rate=calc_result.effective_rate,
            currency=request.currency,
        ),
        total_with_tax=subtotal + calc_result.total_tax,
        rules_applied=[
            RuleTraceEntry(
                rule_id=rt.rule_id,
                name=rt.name,
                rule_type=rt.rule_type,
                result=rt.result,
            )
            for rt in calc_result.rules_traced
        ],
        collection_info=_build_collection_info(rates),
        calculated_at=datetime.now(UTC),
    )


def _build_collection_info(rates):
    """Build collection info from rate metadata."""
    from app.schemas.tax_calculation import CollectionInfo

    platform_collects = any(
        getattr(r, "collection_model", None) == "platform" for r in rates
    )
    has_total_consideration = any(
        getattr(r, "taxable_amount_rule", None) == "total_consideration" for r in rates
    )

    notes = []
    if platform_collects:
        notes.append("Platform/marketplace must collect and remit taxes in this jurisdiction")
    if has_total_consideration:
        notes.append("Tax is calculated on total guest consideration (including OTA markup)")

    # Determine overall collection model
    models = set(getattr(r, "collection_model", "property") or "property" for r in rates)
    if "platform" in models:
        who = "platform" if models == {"platform"} else "both"
    elif "guest" in models:
        who = "guest"
    else:
        who = "property"

    return CollectionInfo(
        who_collects=who,
        taxable_base="total_consideration" if has_total_consideration else "room_rate",
        platform_must_collect=platform_collects,
        notes=notes,
    )


async def calculate_tax_batch(
    db: AsyncSession,
    request: BatchCalculationRequest,
) -> BatchCalculationResponse:
    results = []
    for i, calc_req in enumerate(request.calculations):
        try:
            response = await calculate_tax(db, calc_req)
            results.append(BatchCalculationResult(
                id=str(i),
                total_tax=response.tax_breakdown.total_tax,
                effective_rate=response.tax_breakdown.effective_rate,
                components=response.tax_breakdown.components,
            ))
        except Exception as e:
            results.append(BatchCalculationResult(
                id=str(i),
                total_tax=Decimal("0"),
                effective_rate=Decimal("0"),
                components=[],
                error=str(e),
            ))

    return BatchCalculationResponse(results=results)
