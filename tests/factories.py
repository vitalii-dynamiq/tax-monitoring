"""
Test data factories for creating real DB model instances.

All factory functions insert into the provided async session and flush
to generate IDs. Use `db` fixture from conftest.py.
"""

from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detected_change import DetectedChange
from app.models.jurisdiction import Jurisdiction
from app.models.monitored_source import MonitoredSource
from app.models.monitoring_job import MonitoringJob
from app.models.monitoring_schedule import MonitoringSchedule
from app.models.tax_category import TaxCategory
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule


async def create_jurisdiction(
    db: AsyncSession,
    *,
    code: str = "US",
    name: str = "United States",
    jurisdiction_type: str = "country",
    path: str = "US",
    country_code: str = "US",
    currency_code: str = "USD",
    parent_id: int | None = None,
    status: str = "active",
    **kwargs,
) -> Jurisdiction:
    j = Jurisdiction(
        code=code,
        name=name,
        jurisdiction_type=jurisdiction_type,
        path=path,
        country_code=country_code,
        currency_code=currency_code,
        parent_id=parent_id,
        status=status,
        **kwargs,
    )
    db.add(j)
    await db.flush()
    return j


async def create_tax_category(
    db: AsyncSession,
    *,
    code: str = "occ_pct",
    name: str = "Occupancy Tax",
    level_0: str = "accommodation",
    level_1: str = "occupancy",
    level_2: str = "percentage",
    base_type: str = "room_rate",
    **kwargs,
) -> TaxCategory:
    cat = TaxCategory(
        code=code,
        name=name,
        level_0=level_0,
        level_1=level_1,
        level_2=level_2,
        base_type=base_type,
        **kwargs,
    )
    db.add(cat)
    await db.flush()
    return cat


async def create_tax_rate(
    db: AsyncSession,
    *,
    jurisdiction_id: int,
    tax_category_id: int,
    rate_type: str = "percentage",
    rate_value: float | None = 0.05875,
    effective_start: date = date(2024, 1, 1),
    status: str = "active",
    calculation_order: int = 100,
    # SQLite stores ARRAY as JSON, so default to list
    base_includes: list[str] | None = None,
    **kwargs,
) -> TaxRate:
    rate = TaxRate(
        jurisdiction_id=jurisdiction_id,
        tax_category_id=tax_category_id,
        rate_type=rate_type,
        rate_value=rate_value,
        effective_start=effective_start,
        status=status,
        calculation_order=calculation_order,
        base_includes=base_includes or ["base_amount"],
        **kwargs,
    )
    db.add(rate)
    await db.flush()
    return rate


async def create_tax_rule(
    db: AsyncSession,
    *,
    jurisdiction_id: int,
    rule_type: str = "exemption",
    name: str = "Test Rule",
    priority: int = 100,
    conditions: dict | None = None,
    action: dict | None = None,
    effective_start: date = date(2024, 1, 1),
    status: str = "active",
    tax_rate_id: int | None = None,
    **kwargs,
) -> TaxRule:
    rule = TaxRule(
        jurisdiction_id=jurisdiction_id,
        rule_type=rule_type,
        name=name,
        priority=priority,
        conditions=conditions or {},
        action=action or {},
        effective_start=effective_start,
        status=status,
        tax_rate_id=tax_rate_id,
        **kwargs,
    )
    db.add(rule)
    await db.flush()
    return rule


async def create_monitoring_job(
    db: AsyncSession,
    *,
    jurisdiction_id: int,
    trigger_type: str = "manual",
    status: str = "pending",
    job_type: str = "monitoring",
    **kwargs,
) -> MonitoringJob:
    job = MonitoringJob(
        jurisdiction_id=jurisdiction_id,
        trigger_type=trigger_type,
        status=status,
        job_type=job_type,
        **kwargs,
    )
    db.add(job)
    await db.flush()
    return job


async def create_monitoring_schedule(
    db: AsyncSession,
    *,
    jurisdiction_id: int,
    enabled: bool = False,
    cadence: str = "weekly",
    cron_expression: str | None = None,
    next_run_at: datetime | None = None,
    **kwargs,
) -> MonitoringSchedule:
    schedule = MonitoringSchedule(
        jurisdiction_id=jurisdiction_id,
        enabled=enabled,
        cadence=cadence,
        cron_expression=cron_expression,
        next_run_at=next_run_at,
        **kwargs,
    )
    db.add(schedule)
    await db.flush()
    return schedule


async def create_monitored_source(
    db: AsyncSession,
    *,
    jurisdiction_id: int | None = None,
    url: str = "https://example.gov/tax-info",
    source_type: str = "government",
    status: str = "active",
    **kwargs,
) -> MonitoredSource:
    source = MonitoredSource(
        jurisdiction_id=jurisdiction_id,
        url=url,
        source_type=source_type,
        status=status,
        **kwargs,
    )
    db.add(source)
    await db.flush()
    return source


async def create_detected_change(
    db: AsyncSession,
    *,
    jurisdiction_id: int,
    change_type: str = "new_tax",
    extracted_data: dict | None = None,
    confidence: float = 0.85,
    review_status: str = "pending",
    **kwargs,
) -> DetectedChange:
    change = DetectedChange(
        jurisdiction_id=jurisdiction_id,
        change_type=change_type,
        extracted_data=extracted_data or {"rate_type": "percentage", "rate_value": 5.0},
        confidence=confidence,
        review_status=review_status,
        **kwargs,
    )
    db.add(change)
    await db.flush()
    return change


# ─── Composite seed helpers ─────────────────────────────────────────


async def seed_nyc_hierarchy(db: AsyncSession) -> dict:
    """Create US -> NY -> NYC jurisdiction chain with categories and sample rates/rules.

    Returns dict with keys: us, ny, nyc, occ_pct_cat, flat_cat, rate_pct, rate_flat, rule_exempt
    """
    us = await create_jurisdiction(
        db, code="US", name="United States", jurisdiction_type="country",
        path="US", country_code="US", currency_code="USD",
    )
    ny = await create_jurisdiction(
        db, code="US-NY", name="New York", jurisdiction_type="state",
        path="US.NY", country_code="US", currency_code="USD", parent_id=us.id,
    )
    nyc = await create_jurisdiction(
        db, code="US-NY-NYC", name="New York City", jurisdiction_type="city",
        path="US.NY.NYC", country_code="US", currency_code="USD", parent_id=ny.id,
    )

    occ_pct_cat = await create_tax_category(
        db, code="occ_pct", name="Hotel Occupancy Tax",
        level_0="accommodation", level_1="occupancy", level_2="percentage",
    )
    flat_cat = await create_tax_category(
        db, code="city_tax_flat", name="City Tax",
        level_0="accommodation", level_1="city_tax", level_2="per_night",
    )

    rate_pct = await create_tax_rate(
        db, jurisdiction_id=nyc.id, tax_category_id=occ_pct_cat.id,
        rate_type="percentage", rate_value=0.05875,
        effective_start=date(2024, 1, 1), status="active",
        calculation_order=100,
    )
    rate_flat = await create_tax_rate(
        db, jurisdiction_id=nyc.id, tax_category_id=flat_cat.id,
        rate_type="flat", rate_value=2.0,
        effective_start=date(2024, 1, 1), status="active",
        calculation_order=200,
    )

    rule_exempt = await create_tax_rule(
        db, jurisdiction_id=nyc.id, rule_type="exemption",
        name="Long Stay Exemption", priority=100,
        conditions={
            "operator": "AND",
            "rules": [{"field": "stay_length_days", "op": ">=", "value": 180}],
        },
        action={},
        effective_start=date(2024, 1, 1),
        tax_rate_id=rate_pct.id,
    )

    await db.commit()

    return {
        "us": us, "ny": ny, "nyc": nyc,
        "occ_pct_cat": occ_pct_cat, "flat_cat": flat_cat,
        "rate_pct": rate_pct, "rate_flat": rate_flat,
        "rule_exempt": rule_exempt,
    }
