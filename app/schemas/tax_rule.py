from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class RuleType(StrEnum):
    condition = "condition"
    exemption = "exemption"
    reduction = "reduction"
    surcharge = "surcharge"
    cap = "cap"
    override = "override"
    threshold = "threshold"


class RuleStatus(StrEnum):
    active = "active"
    draft = "draft"
    approved = "approved"
    rejected = "rejected"
    needs_review = "needs_review"
    superseded = "superseded"


class TaxRuleCreate(BaseModel):
    tax_rate_id: int | None = None
    jurisdiction_code: str
    rule_type: RuleType
    priority: int = 0
    name: str
    description: str | None = None
    conditions: dict = Field(default_factory=dict)
    action: dict = Field(default_factory=dict)
    effective_start: date
    effective_end: date | None = None
    enacted_date: date | None = None
    legal_reference: str | None = None
    legal_uri: str | None = None
    authority_name: str | None = None
    status: RuleStatus = RuleStatus.active
    created_by: str = "system"

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_end and self.effective_start > self.effective_end:
            raise ValueError("effective_start must be before effective_end")
        return self


class TaxRuleResponse(BaseModel):
    id: int
    tax_rate_id: int | None = None
    jurisdiction_id: int
    jurisdiction_code: str | None = None
    rule_type: str
    priority: int
    name: str
    description: str | None = None
    conditions: dict
    action: dict
    effective_start: date
    effective_end: date | None = None
    enacted_date: date | None = None
    legal_reference: str | None = None
    legal_uri: str | None = None
    authority_name: str | None = None
    status: str
    version: int
    supersedes_id: int | None = None
    created_by: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaxRuleBulkCreate(BaseModel):
    rules: list[TaxRuleCreate] = Field(..., max_length=100)
