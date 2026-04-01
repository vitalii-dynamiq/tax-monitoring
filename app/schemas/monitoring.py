from datetime import datetime

from pydantic import BaseModel, Field


class MonitoredSourceCreate(BaseModel):
    jurisdiction_code: str | None = None
    url: str = Field(..., description="Government domain to monitor (e.g. 'nyc.gov', 'tax.ny.gov')")
    source_type: str = Field(..., examples=["government_website", "tax_authority", "legal_gazette"])
    language: str = "en"
    check_frequency_days: int = Field(default=7, ge=1)
    metadata: dict = Field(default_factory=dict)


class MonitoredSourceResponse(BaseModel):
    id: int
    jurisdiction_code: str | None = None
    url: str
    source_type: str
    language: str
    check_frequency_days: int
    last_checked_at: datetime | None
    last_content_hash: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DetectedChangeCreate(BaseModel):
    source_id: int | None = None
    jurisdiction_code: str | None = None
    change_type: str = Field(..., examples=["rate_change", "new_tax", "exemption_change", "repeal"])
    extracted_data: dict
    confidence: float = Field(..., ge=0, le=1)
    source_quote: str | None = None
    source_snapshot_url: str | None = None


class DetectedChangeResponse(BaseModel):
    id: int
    source_id: int | None
    jurisdiction_id: int | None
    jurisdiction_code: str | None = None
    change_type: str
    detected_at: datetime
    extracted_data: dict
    confidence: float
    source_quote: str | None
    review_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_notes: str | None
    applied_rate_id: int | None
    applied_rule_id: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DetectedChangeReview(BaseModel):
    review_status: str = Field(..., examples=["approved", "rejected", "needs_review"])
    reviewed_by: str = "system"
    review_notes: str | None = None


# ─── Monitoring Jobs ────────────────────────────────────────────────


class MonitoringJobResponse(BaseModel):
    id: int
    jurisdiction_id: int
    jurisdiction_code: str | None = None
    job_type: str = "monitoring"
    status: str
    trigger_type: str
    triggered_by: str
    started_at: datetime | None
    completed_at: datetime | None
    result_summary: dict | None
    changes_detected: int
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── Monitoring Schedules ───────────────────────────────────────────


class MonitoringScheduleResponse(BaseModel):
    id: int
    jurisdiction_id: int
    jurisdiction_code: str | None = None
    enabled: bool
    cadence: str
    cron_expression: str | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MonitoringScheduleUpdate(BaseModel):
    enabled: bool | None = None
    cadence: str | None = Field(None, examples=["daily", "weekly", "monthly", "custom"])
    cron_expression: str | None = None
