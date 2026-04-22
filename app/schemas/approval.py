from datetime import datetime

from pydantic import BaseModel, Field


class ApprovalRequest(BaseModel):
    """Body for bulk approve/reject endpoints."""
    reviewed_by: str | None = None  # falls back to authenticated admin email
    review_notes: str | None = None
    created_by: str | None = None  # optional filter: only touch drafts with matching created_by tag


class BulkApprovalResponse(BaseModel):
    jurisdiction_code: str
    new_status: str  # "active" or "rejected"
    approved_rate_ids: list[int] = Field(default_factory=list)
    approved_rule_ids: list[int] = Field(default_factory=list)
    reviewed_by: str


class PendingSummaryRow(BaseModel):
    jurisdiction_id: int
    jurisdiction_code: str
    jurisdiction_name: str
    jurisdiction_type: str
    path: str | None = None
    pending_rates: int = 0
    pending_rules: int = 0
    earliest_created_at: datetime | None = None
    created_by_tags: list[str] = Field(default_factory=list)


class PendingSummary(BaseModel):
    total_pending_rates: int
    total_pending_rules: int
    total_jurisdictions: int
    rows: list[PendingSummaryRow]
