from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_admin
from app.config import settings as app_settings
from app.db.session import get_db
from app.schemas.monitoring import (
    AgentRunTurnResponse,
    BulkScheduleResponse,
    BulkScheduleUpdate,
    DetectedChangeCreate,
    DetectedChangeResponse,
    DetectedChangeReview,
    MonitoredSourceCreate,
    MonitoredSourceResponse,
    MonitoringJobResponse,
    MonitoringScheduleResponse,
    MonitoringScheduleUpdate,
    ProducedDetectedChangeRow,
    ProducedEntitiesResponse,
    ProducedJurisdictionRow,
    ProducedRateRow,
    ProducedRuleRow,
)
from app.services.discovery_job_service import run_discovery_job
from app.services.jurisdiction_service import get_jurisdiction_by_code
from app.services.monitoring_job_service import (
    bulk_update_schedules,
    create_job,
    get_job,
    get_schedule,
    has_running_job,
    list_jobs,
    list_schedules,
    run_monitoring_job_with_limits,
    upsert_schedule,
    validate_cron_expression,
)
from app.services.monitoring_service import (
    create_change,
    create_source,
    get_all_changes,
    get_all_sources,
    get_change_by_id,
    get_source_by_id,
    review_change,
)

router = APIRouter(prefix="/v1/monitoring", tags=["Monitoring"])


# ─── Monitored Sources ───────────────────────────────────────────────

def _source_to_response(source) -> MonitoredSourceResponse:
    resp = MonitoredSourceResponse.model_validate(source)
    if source.jurisdiction:
        resp.jurisdiction_code = source.jurisdiction.code
    return resp


@router.get("/sources", response_model=list[MonitoredSourceResponse])
async def list_sources(
    jurisdiction_code: str | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    sources = await get_all_sources(
        db, jurisdiction_code=jurisdiction_code,
        status=status, limit=limit, offset=offset,
    )
    return [_source_to_response(s) for s in sources]


@router.get("/sources/{source_id}", response_model=MonitoredSourceResponse)
async def get_source(
    source_id: int, _user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    source = await get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return _source_to_response(source)


@router.post("/sources", response_model=MonitoredSourceResponse, status_code=201)
async def create_new_source(
    data: MonitoredSourceCreate, _admin=Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    try:
        source = await create_source(db, data)
        return _source_to_response(source)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ─── Detected Changes ────────────────────────────────────────────────

def _change_to_response(change) -> DetectedChangeResponse:
    resp = DetectedChangeResponse.model_validate(change)
    if change.jurisdiction:
        resp.jurisdiction_code = change.jurisdiction.code
    return resp


@router.get("/changes", response_model=list[DetectedChangeResponse])
async def list_changes(
    jurisdiction_code: str | None = None,
    review_status: str | None = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    changes = await get_all_changes(
        db, jurisdiction_code=jurisdiction_code,
        review_status=review_status, limit=limit, offset=offset,
    )
    return [_change_to_response(c) for c in changes]


@router.get("/changes/{change_id}", response_model=DetectedChangeResponse)
async def get_change(
    change_id: int, _user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    change = await get_change_by_id(db, change_id)
    if not change:
        raise HTTPException(404, "Change not found")
    return _change_to_response(change)


@router.post("/changes", response_model=DetectedChangeResponse, status_code=201)
async def create_new_change(
    data: DetectedChangeCreate, _admin=Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    change = await create_change(db, data)
    return _change_to_response(change)


@router.post("/changes/{change_id}/review", response_model=DetectedChangeResponse)
async def review_detected_change(
    change_id: int,
    review: DetectedChangeReview,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    change = await review_change(
        db, change_id, review.review_status, review.reviewed_by, review.review_notes
    )
    if not change:
        raise HTTPException(404, "Change not found")
    return _change_to_response(change)


# ─── Monitoring Jobs ────────────────────────────────────────────────


def _job_to_response(job) -> MonitoringJobResponse:
    resp = MonitoringJobResponse.model_validate(job)
    if job.jurisdiction:
        resp.jurisdiction_code = job.jurisdiction.code
    # Serialize Decimal cost as a clean string for the UI
    if job.estimated_cost_usd is not None:
        resp.estimated_cost_usd = str(job.estimated_cost_usd)
    return resp


@router.post(
    "/jobs/{jurisdiction_code}/run",
    response_model=MonitoringJobResponse,
    status_code=202,
)
async def trigger_monitoring_run(
    jurisdiction_code: str,
    background_tasks: BackgroundTasks,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a manual monitoring run for a jurisdiction."""
    if not app_settings.anthropic_api_key:
        raise HTTPException(
            503,
            "Tax monitoring is not available: ANTHROPIC_API_KEY is not configured. "
            "Contact your administrator.",
        )

    jurisdiction = await get_jurisdiction_by_code(db, jurisdiction_code)
    if not jurisdiction:
        raise HTTPException(404, f"Jurisdiction not found: {jurisdiction_code}")
    if jurisdiction.jurisdiction_type != "country":
        raise HTTPException(
            400,
            f"{jurisdiction_code} is not a country. "
            f"Monitoring only works on countries — runs cover the country and all "
            f"its sub-jurisdictions in a single agentic loop.",
        )

    if await has_running_job(db, jurisdiction.id, job_type="monitoring"):
        raise HTTPException(409, "A monitoring job is already running for this jurisdiction")

    job = await create_job(
        db,
        jurisdiction_id=jurisdiction.id,
        trigger_type="manual",
        triggered_by="api",
        job_type="monitoring",
    )
    # Commit before dispatching background task so the job row is visible
    # to the background task's separate DB session
    await db.commit()

    background_tasks.add_task(run_monitoring_job_with_limits, job.id)
    return _job_to_response(job)


@router.get("/jobs", response_model=list[MonitoringJobResponse])
async def list_monitoring_jobs(
    jurisdiction_code: str | None = None,
    job_type: str | None = None,
    status: str | None = None,
    trigger_type: str | None = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    jobs = await list_jobs(
        db,
        jurisdiction_code=jurisdiction_code,
        job_type=job_type,
        status=status,
        trigger_type=trigger_type,
        limit=limit,
        offset=offset,
    )
    return [_job_to_response(j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=MonitoringJobResponse)
async def get_monitoring_job(
    job_id: int, _user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_to_response(job)


@router.get("/jobs/{job_id}/turns", response_model=list[AgentRunTurnResponse])
async def get_monitoring_job_turns(
    job_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return the full agent conversation transcript for a job.

    Admin-only: prompts and request payloads may contain internal context.
    """
    from sqlalchemy import select

    from app.models.agent_run_turn import AgentRunTurn

    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    result = await db.execute(
        select(AgentRunTurn)
        .where(AgentRunTurn.monitoring_job_id == job_id)
        .order_by(AgentRunTurn.turn_index)
    )
    return [AgentRunTurnResponse.model_validate(t) for t in result.scalars().all()]


@router.get("/jobs/{job_id}/produced", response_model=ProducedEntitiesResponse)
async def get_monitoring_job_produced(
    job_id: int,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Return entities produced by this job: jurisdictions, rates, rules, detected_changes."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.detected_change import DetectedChange
    from app.models.jurisdiction import Jurisdiction
    from app.models.tax_rate import TaxRate
    from app.models.tax_rule import TaxRule

    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    juris_result = await db.execute(
        select(Jurisdiction)
        .where(Jurisdiction.monitoring_job_id == job_id)
        .order_by(Jurisdiction.created_at)
    )
    jurisdictions = [
        ProducedJurisdictionRow(
            id=j.id,
            code=j.code,
            name=j.name,
            jurisdiction_type=j.jurisdiction_type,
            status=j.status,
            created_at=j.created_at,
        )
        for j in juris_result.scalars().all()
    ]

    rates_result = await db.execute(
        select(TaxRate)
        .options(selectinload(TaxRate.jurisdiction), selectinload(TaxRate.tax_category))
        .where(TaxRate.monitoring_job_id == job_id)
        .order_by(TaxRate.created_at)
    )
    tax_rates = [
        ProducedRateRow(
            id=r.id,
            jurisdiction_code=r.jurisdiction.code if r.jurisdiction else None,
            tax_category_code=r.tax_category.code if r.tax_category else None,
            rate_type=r.rate_type,
            rate_value=float(r.rate_value) if r.rate_value is not None else None,
            status=r.status,
            created_at=r.created_at,
        )
        for r in rates_result.scalars().all()
    ]

    rules_result = await db.execute(
        select(TaxRule)
        .options(selectinload(TaxRule.jurisdiction))
        .where(TaxRule.monitoring_job_id == job_id)
        .order_by(TaxRule.created_at)
    )
    tax_rules = [
        ProducedRuleRow(
            id=r.id,
            jurisdiction_code=r.jurisdiction.code if r.jurisdiction else None,
            rule_type=r.rule_type,
            name=r.name,
            status=r.status,
            created_at=r.created_at,
        )
        for r in rules_result.scalars().all()
    ]

    changes_result = await db.execute(
        select(DetectedChange)
        .options(selectinload(DetectedChange.jurisdiction))
        .where(DetectedChange.monitoring_job_id == job_id)
        .order_by(DetectedChange.created_at)
    )
    detected_changes = [
        ProducedDetectedChangeRow(
            id=c.id,
            jurisdiction_code=c.jurisdiction.code if c.jurisdiction else None,
            change_type=c.change_type,
            review_status=c.review_status,
            confidence=float(c.confidence),
            created_at=c.created_at,
        )
        for c in changes_result.scalars().all()
    ]

    return ProducedEntitiesResponse(
        jurisdictions=jurisdictions,
        tax_rates=tax_rates,
        tax_rules=tax_rules,
        detected_changes=detected_changes,
    )


# ─── Monitoring Schedules ───────────────────────────────────────────


def _schedule_to_response(schedule) -> MonitoringScheduleResponse:
    resp = MonitoringScheduleResponse.model_validate(schedule)
    if schedule.jurisdiction:
        resp.jurisdiction_code = schedule.jurisdiction.code
    return resp


@router.get("/schedules", response_model=list[MonitoringScheduleResponse])
async def list_monitoring_schedules(
    enabled: bool | None = None,
    job_type: str | None = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedules = await list_schedules(
        db, enabled=enabled, job_type=job_type, limit=limit, offset=offset
    )
    return [_schedule_to_response(s) for s in schedules]


@router.get("/schedules/{jurisdiction_code}", response_model=MonitoringScheduleResponse)
async def get_monitoring_schedule(
    jurisdiction_code: str,
    job_type: str = "monitoring",
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    schedule = await get_schedule(db, jurisdiction_code, job_type=job_type)
    if not schedule:
        raise HTTPException(404, "Schedule not found for this jurisdiction")
    return _schedule_to_response(schedule)


@router.put("/schedules/{jurisdiction_code}", response_model=MonitoringScheduleResponse)
async def update_monitoring_schedule(
    jurisdiction_code: str,
    data: MonitoringScheduleUpdate,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a monitoring schedule for a jurisdiction."""
    jurisdiction = await get_jurisdiction_by_code(db, jurisdiction_code)
    if not jurisdiction:
        raise HTTPException(404, f"Jurisdiction not found: {jurisdiction_code}")

    if data.job_type in ("discovery", "monitoring") and jurisdiction.jurisdiction_type != "country":
        raise HTTPException(
            400,
            f"{jurisdiction_code} is not a country. "
            f"{data.job_type.capitalize()} only works on countries.",
        )

    if data.cadence == "custom" and not data.cron_expression:
        raise HTTPException(400, "cron_expression required when cadence is 'custom'")

    if data.cron_expression and not validate_cron_expression(data.cron_expression):
        raise HTTPException(400, f"Invalid cron expression: '{data.cron_expression}'")

    schedule = await upsert_schedule(
        db,
        jurisdiction_id=jurisdiction.id,
        enabled=data.enabled,
        cadence=data.cadence,
        cron_expression=data.cron_expression,
        job_type=data.job_type,
    )
    return _schedule_to_response(schedule)


@router.post("/schedules/bulk", response_model=BulkScheduleResponse)
async def bulk_update_monitoring_schedules(
    data: BulkScheduleUpdate,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Bulk enable/disable or change cadence on schedules for the given jurisdictions.

    Per-row failures don't abort the batch; check the returned `errors` list.
    """
    try:
        updated, errors = await bulk_update_schedules(
            db,
            jurisdiction_codes=data.jurisdiction_codes,
            job_type=data.job_type,
            action=data.action,
            cadence=data.cadence,
            cron_expression=data.cron_expression,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    await db.commit()
    return BulkScheduleResponse(
        updated=[_schedule_to_response(s) for s in updated],
        errors=errors,  # pydantic coerces dicts to BulkScheduleError
    )


# ─── Discovery Jobs ─────────────────────────────────────────────────


@router.post(
    "/discovery/{country_code}/run",
    response_model=MonitoringJobResponse,
    status_code=202,
)
async def trigger_discovery_run(
    country_code: str,
    background_tasks: BackgroundTasks,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Trigger a sub-jurisdiction discovery run for a country."""
    if not app_settings.anthropic_api_key:
        raise HTTPException(
            503,
            "Discovery is not available: ANTHROPIC_API_KEY is not configured.",
        )

    jurisdiction = await get_jurisdiction_by_code(db, country_code)
    if not jurisdiction:
        raise HTTPException(404, f"Jurisdiction not found: {country_code}")
    if jurisdiction.jurisdiction_type != "country":
        raise HTTPException(
            400, f"{country_code} is not a country. Discovery only works on countries.",
        )

    if await has_running_job(db, jurisdiction.id, job_type="discovery"):
        raise HTTPException(409, "A discovery job is already running for this jurisdiction")

    job = await create_job(
        db,
        jurisdiction_id=jurisdiction.id,
        trigger_type="manual",
        triggered_by="api",
        job_type="discovery",
    )
    await db.commit()

    background_tasks.add_task(run_discovery_job, job.id)
    return _job_to_response(job)


@router.get("/discovery/jobs", response_model=list[MonitoringJobResponse])
async def list_discovery_jobs(
    country_code: str | None = None,
    status: str | None = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List discovery jobs."""
    jobs = await list_jobs(
        db,
        jurisdiction_code=country_code,
        job_type="discovery",
        status=status,
        limit=limit,
        offset=offset,
    )
    return [_job_to_response(j) for j in jobs]
