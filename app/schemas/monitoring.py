from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field


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
    jurisdiction_id: int | None
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
    error_traceback: str | None = None
    # Agent telemetry (populated by AgentRunRecorder.flush)
    model: str | None = None
    system_prompt: str | None = None
    initial_user_prompt: str | None = None
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_creation_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_web_search_count: int = 0
    estimated_cost_usd: Annotated[
        str,
        BeforeValidator(
            lambda v: str(v) if isinstance(v, (Decimal, int, float)) else v
        ),
    ] = "0"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentRunTurnResponse(BaseModel):
    """One LLM call within an agent run."""

    id: int
    turn_index: int
    model: str
    stop_reason: str | None
    request_messages: list
    response_content: list
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    web_search_count: int
    latency_ms: int
    started_at: datetime
    completed_at: datetime

    model_config = {"from_attributes": True}


class ProducedRateRow(BaseModel):
    id: int
    jurisdiction_code: str | None
    tax_category_code: str | None
    rate_type: str
    rate_value: float | None
    status: str
    created_at: datetime


class ProducedRuleRow(BaseModel):
    id: int
    jurisdiction_code: str | None
    rule_type: str
    name: str
    status: str
    created_at: datetime


class ProducedJurisdictionRow(BaseModel):
    id: int
    code: str
    name: str
    jurisdiction_type: str
    status: str
    created_at: datetime


class ProducedDetectedChangeRow(BaseModel):
    id: int
    jurisdiction_code: str | None
    change_type: str
    review_status: str
    confidence: float
    created_at: datetime


class ProducedEntitiesResponse(BaseModel):
    jurisdictions: list[ProducedJurisdictionRow]
    tax_rates: list[ProducedRateRow]
    tax_rules: list[ProducedRuleRow]
    detected_changes: list[ProducedDetectedChangeRow]


# ─── Monitoring Schedules ───────────────────────────────────────────


class MonitoringScheduleResponse(BaseModel):
    id: int
    jurisdiction_id: int
    jurisdiction_code: str | None = None
    job_type: str = "monitoring"
    enabled: bool
    cadence: str
    cron_expression: str | None
    last_run_at: datetime | None
    next_run_at: datetime | None
    last_run_status: str | None = None
    failed_in_last_24h: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MonitoringScheduleUpdate(BaseModel):
    enabled: bool | None = None
    cadence: str | None = Field(None, examples=["daily", "weekly", "monthly", "custom"])
    cron_expression: str | None = None
    job_type: Literal["monitoring", "discovery"] = "monitoring"


class BulkScheduleUpdate(BaseModel):
    jurisdiction_codes: list[str] = Field(..., min_length=1, max_length=500)
    job_type: Literal["monitoring", "discovery"] = "monitoring"
    action: Literal["enable", "disable", "set_cadence"]
    cadence: str | None = Field(None, examples=["daily", "weekly", "monthly", "custom"])
    cron_expression: str | None = None


class BulkScheduleError(BaseModel):
    code: str
    message: str


class BulkScheduleResponse(BaseModel):
    updated: list[MonitoringScheduleResponse]
    errors: list[BulkScheduleError]
