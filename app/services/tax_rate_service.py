from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.tax_category import TaxCategory
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule
from app.schemas.tax_rate import TaxRateCreate
from app.services.audit_service import log_change
from app.services.jurisdiction_service import get_jurisdiction_by_code


async def get_all_rates(
    db: AsyncSession,
    jurisdiction_code: str | None = None,
    category_code: str | None = None,
    status: str | None = None,
    effective_date: date | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TaxRate]:
    query = (
        select(TaxRate)
        .options(joinedload(TaxRate.tax_category), joinedload(TaxRate.jurisdiction))
    )

    if jurisdiction_code:
        from app.models.jurisdiction import Jurisdiction
        query = query.join(TaxRate.jurisdiction).where(Jurisdiction.code == jurisdiction_code)
    if category_code:
        query = query.join(TaxRate.tax_category).where(TaxCategory.code == category_code)
    if status:
        query = query.where(TaxRate.status == status)
    if effective_date:
        query = query.where(
            TaxRate.effective_start <= effective_date,
            (TaxRate.effective_end.is_(None)) | (TaxRate.effective_end > effective_date),
        )

    query = query.order_by(TaxRate.calculation_order).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.unique().scalars().all())


async def get_active_rates_for_jurisdiction(
    db: AsyncSession,
    jurisdiction_ids: list[int],
    stay_date: date,
) -> list[TaxRate]:
    """Get all active rates for a set of jurisdictions on a given date.

    When multiple rates exist for the same jurisdiction + category (e.g. an old
    rate and a newer superseding rate both within the date window), only the one
    with the latest effective_start is kept.  This allows new rates to be added
    without manually setting effective_end on the old rate.
    """
    query = (
        select(TaxRate)
        .options(joinedload(TaxRate.tax_category), joinedload(TaxRate.jurisdiction))
        .where(
            TaxRate.jurisdiction_id.in_(jurisdiction_ids),
            TaxRate.status == "active",
            TaxRate.effective_start <= stay_date,
            (TaxRate.effective_end.is_(None)) | (TaxRate.effective_end > stay_date),
        )
        .order_by(TaxRate.calculation_order)
    )
    result = await db.execute(query)
    all_rates = list(result.unique().scalars().all())

    # Deduplicate: for each (jurisdiction_id, tax_category_id) keep only the
    # rate with the latest effective_start.  This ensures that when a new rate
    # supersedes an old one the old rate is automatically excluded.
    best: dict[tuple[int, int], TaxRate] = {}
    for rate in all_rates:
        key = (rate.jurisdiction_id, rate.tax_category_id)
        existing = best.get(key)
        if existing is None or rate.effective_start > existing.effective_start:
            best[key] = rate
    deduped = list(best.values())

    # Hierarchical override: when child jurisdiction has the same tax_category
    # as a parent, the child's rate overrides (not stacks on top of) the parent.
    # jurisdiction_ids is ordered ancestors-first → child-last, so higher index = deeper.
    depth_map = {jid: i for i, jid in enumerate(jurisdiction_ids)}
    category_best: dict[int, TaxRate] = {}
    for rate in deduped:
        cat_id = rate.tax_category_id
        existing = category_best.get(cat_id)
        if existing is None:
            category_best[cat_id] = rate
        else:
            existing_depth = depth_map.get(existing.jurisdiction_id, 0)
            current_depth = depth_map.get(rate.jurisdiction_id, 0)
            if current_depth > existing_depth:
                category_best[cat_id] = rate
    deduped = sorted(category_best.values(), key=lambda r: r.calculation_order)
    return deduped


async def get_rules_for_rates(
    db: AsyncSession,
    rate_ids: list[int],
    stay_date: date,
    jurisdiction_ids: list[int] | None = None,
) -> dict[int, list[TaxRule]]:
    """Get active rules for a set of rates, grouped by rate_id.

    Rules are fetched from two sources:
    1. Rate-specific rules (tax_rate_id IN rate_ids)
    2. Jurisdiction-level rules (tax_rate_id IS NULL, jurisdiction_id IN jurisdiction_ids)

    Jurisdiction-level rules are applied to EVERY rate within that jurisdiction,
    which is the correct behaviour for exemptions, overrides, and caps that
    target the booking context rather than a specific rate.
    """
    from sqlalchemy import or_

    if not rate_ids and not jurisdiction_ids:
        return {}

    conditions = []
    if rate_ids:
        conditions.append(TaxRule.tax_rate_id.in_(rate_ids))
    if jurisdiction_ids:
        conditions.append(
            (TaxRule.tax_rate_id.is_(None)) & (TaxRule.jurisdiction_id.in_(jurisdiction_ids))
        )

    query = (
        select(TaxRule)
        .where(
            or_(*conditions),
            TaxRule.status == "active",
            TaxRule.effective_start <= stay_date,
            (TaxRule.effective_end.is_(None)) | (TaxRule.effective_end > stay_date),
        )
        .order_by(TaxRule.priority.desc())
    )
    result = await db.execute(query)
    rules = list(result.scalars().all())

    # Build lookup: rate_id -> list[TaxRule]
    # Rate-specific rules go under their rate_id.
    # Jurisdiction-level rules (tax_rate_id=NULL) go under every rate_id
    # that belongs to the same jurisdiction.
    rules_by_rate: dict[int, list[TaxRule]] = {}

    # Index which rates belong to which jurisdiction (needed for mapping)
    # We'll receive this from the caller via rate_ids -> we need rate objects.
    # Instead, collect jurisdiction-level rules separately and merge later.
    rate_specific: list[TaxRule] = []
    jurisdiction_rules: dict[int, list[TaxRule]] = {}  # jurisdiction_id -> rules

    for rule in rules:
        if rule.tax_rate_id is not None:
            rate_specific.append(rule)
        else:
            jurisdiction_rules.setdefault(rule.jurisdiction_id, []).append(rule)

    # Assign rate-specific rules
    for rule in rate_specific:
        rules_by_rate.setdefault(rule.tax_rate_id, []).append(rule)

    return rules_by_rate, jurisdiction_rules


async def get_rate_by_id(db: AsyncSession, rate_id: int) -> TaxRate | None:
    query = (
        select(TaxRate)
        .options(joinedload(TaxRate.tax_category), joinedload(TaxRate.jurisdiction))
        .where(TaxRate.id == rate_id)
    )
    result = await db.execute(query)
    return result.unique().scalar_one_or_none()


async def create_rate(db: AsyncSession, data: TaxRateCreate) -> TaxRate:
    jurisdiction = await get_jurisdiction_by_code(db, data.jurisdiction_code)
    if not jurisdiction:
        raise ValueError(f"Jurisdiction not found: {data.jurisdiction_code}")

    category_result = await db.execute(
        select(TaxCategory).where(TaxCategory.code == data.tax_category_code)
    )
    category = category_result.scalar_one_or_none()
    if not category:
        raise ValueError(f"Tax category not found: {data.tax_category_code}")

    rate = TaxRate(
        jurisdiction_id=jurisdiction.id,
        tax_category_id=category.id,
        rate_type=data.rate_type,
        rate_value=data.rate_value,
        currency_code=data.currency_code,
        tiers=data.tiers,
        tier_type=data.tier_type,
        enacted_date=data.enacted_date,
        effective_start=data.effective_start,
        effective_end=data.effective_end,
        applicability_start=data.applicability_start,
        announcement_date=data.announcement_date,
        calculation_order=data.calculation_order,
        base_includes=data.base_includes,
        legal_reference=data.legal_reference,
        legal_uri=data.legal_uri,
        source_url=data.source_url,
        authority_name=data.authority_name,
        status=data.status,
        created_by=data.created_by,
    )
    db.add(rate)
    await db.flush()

    await log_change(
        db,
        entity_type="tax_rate",
        entity_id=rate.id,
        action="create",
        changed_by=data.created_by,
        change_source="api",
        new_values={
            "jurisdiction_code": data.jurisdiction_code,
            "tax_category_code": data.tax_category_code,
            "rate_type": data.rate_type,
            "rate_value": float(data.rate_value) if data.rate_value else None,
            "status": data.status,
        },
    )

    return rate


async def create_rates_bulk(db: AsyncSession, rates: list[TaxRateCreate]) -> list[TaxRate]:
    results = []
    for rate_data in rates:
        r = await create_rate(db, rate_data)
        results.append(r)
    return results


async def update_rate_status(
    db: AsyncSession,
    rate_id: int,
    new_status: str,
    reviewed_by: str | None = None,
    review_notes: str | None = None,
) -> TaxRate | None:
    rate = await get_rate_by_id(db, rate_id)
    if not rate:
        return None

    old_status = rate.status
    rate.status = new_status
    if reviewed_by:
        rate.reviewed_by = reviewed_by
        rate.reviewed_at = datetime.now(UTC)
    if review_notes:
        rate.review_notes = review_notes

    await db.flush()

    await log_change(
        db,
        entity_type="tax_rate",
        entity_id=rate.id,
        action="status_change",
        changed_by=reviewed_by or "system",
        change_source="api",
        old_values={"status": old_status},
        new_values={"status": new_status},
        change_reason=review_notes,
    )

    return rate
