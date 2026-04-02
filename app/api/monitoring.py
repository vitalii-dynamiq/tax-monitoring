from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_admin
from app.db.session import get_db
from app.schemas.monitoring import (
    DetectedChangeCreate,
    DetectedChangeResponse,
    DetectedChangeReview,
    MonitoredSourceCreate,
    MonitoredSourceResponse,
    MonitoringJobResponse,
    MonitoringScheduleResponse,
    MonitoringScheduleUpdate,
)
from app.services.jurisdiction_service import get_jurisdiction_by_code
from app.config import settings as app_settings
from app.services.discovery_job_service import run_discovery_job
from app.services.monitoring_job_service import (
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
async def get_source(source_id: int, _user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    source = await get_source_by_id(db, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return _source_to_response(source)


@router.post("/sources", response_model=MonitoredSourceResponse, status_code=201)
async def create_new_source(data: MonitoredSourceCreate, _admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
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
async def get_change(change_id: int, _user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    change = await get_change_by_id(db, change_id)
    if not change:
        raise HTTPException(404, "Change not found")
    return _change_to_response(change)


@router.post("/changes", response_model=DetectedChangeResponse, status_code=201)
async def create_new_change(data: DetectedChangeCreate, _admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
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

    if await has_running_job(db, jurisdiction.id):
        raise HTTPException(409, "A monitoring job is already running for this jurisdiction")

    job = await create_job(
        db,
        jurisdiction_id=jurisdiction.id,
        trigger_type="manual",
        triggered_by="api",
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
async def get_monitoring_job(job_id: int, _user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_to_response(job)


# ─── Monitoring Schedules ───────────────────────────────────────────


def _schedule_to_response(schedule) -> MonitoringScheduleResponse:
    resp = MonitoringScheduleResponse.model_validate(schedule)
    if schedule.jurisdiction:
        resp.jurisdiction_code = schedule.jurisdiction.code
    return resp


@router.get("/schedules", response_model=list[MonitoringScheduleResponse])
async def list_monitoring_schedules(
    enabled: bool | None = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    schedules = await list_schedules(db, enabled=enabled, limit=limit, offset=offset)
    return [_schedule_to_response(s) for s in schedules]


@router.get("/schedules/{jurisdiction_code}", response_model=MonitoringScheduleResponse)
async def get_monitoring_schedule(
    jurisdiction_code: str, _user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    schedule = await get_schedule(db, jurisdiction_code)
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
    )
    return _schedule_to_response(schedule)


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
        raise HTTPException(400, f"{country_code} is not a country. Discovery only works on countries.")

    if await has_running_job(db, jurisdiction.id):
        raise HTTPException(409, "A job is already running for this jurisdiction")

    job = await create_job(
        db,
        jurisdiction_id=jurisdiction.id,
        trigger_type="manual",
        triggered_by="api",
    )
    job.job_type = "discovery"
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
