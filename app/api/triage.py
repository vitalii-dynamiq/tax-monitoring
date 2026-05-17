from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.config import settings as app_settings
from app.db.session import get_db
from app.models.monitoring_job import MonitoringJob
from app.schemas.monitoring import MonitoringJobResponse
from app.schemas.triage import TriageRunRequest
from app.services.monitoring_job_service import create_job
from app.services.triage_job_service import run_triage_job_with_limits

router = APIRouter(prefix="/v1/triage", tags=["Triage"])


def _job_to_response(job) -> MonitoringJobResponse:
    resp = MonitoringJobResponse.model_validate(job)
    if job.jurisdiction:
        resp.jurisdiction_code = job.jurisdiction.code
    if job.estimated_cost_usd is not None:
        resp.estimated_cost_usd = str(job.estimated_cost_usd)
    return resp


@router.post("/run", response_model=MonitoringJobResponse, status_code=202)
async def trigger_triage_run(
    data: TriageRunRequest,
    background_tasks: BackgroundTasks,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch the AI triage agent over the pending-approval queue.

    Returns the new MonitoringJob (job_type='triage'). Track progress in
    /app/agent-monitoring/runs/{id}.
    """
    if not app_settings.anthropic_api_key:
        raise HTTPException(
            503,
            "Triage is not available: ANTHROPIC_API_KEY is not configured. "
            "Contact your administrator.",
        )

    # Only one triage run at a time.
    busy = await db.execute(
        select(MonitoringJob.id).where(
            MonitoringJob.job_type == "triage",
            MonitoringJob.status.in_(("pending", "running")),
        )
    )
    if busy.first() is not None:
        raise HTTPException(409, "A triage job is already running. Wait for it to finish.")

    # Create the job. jurisdiction_id is NULL — triage spans the queue.
    # Stash the triage options in result_summary so the runner can read them.
    job = await create_job(
        db,
        jurisdiction_id=None,  # type: ignore[arg-type]
        trigger_type="manual",
        triggered_by="api",
        job_type="triage",
    )
    job.result_summary = {
        "triage_options": {
            "jurisdiction_code": data.jurisdiction_code,
            "max_items": data.max_items,
        }
    }
    await db.commit()

    background_tasks.add_task(run_triage_job_with_limits, job.id)
    return _job_to_response(job)
