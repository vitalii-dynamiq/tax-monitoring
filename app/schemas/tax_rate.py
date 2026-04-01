from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class RateType(StrEnum):
    percentage = "percentage"
    flat = "flat"
    tiered = "tiered"


class TierType(StrEnum):
    single_amount = "single_amount"
    threshold = "threshold"
    marginal_rate = "marginal_rate"


class RateStatus(StrEnum):
    draft = "draft"
    approved = "approved"
    scheduled = "scheduled"
    active = "active"
    superseded = "superseded"
    rejected = "rejected"
    needs_review = "needs_review"


class TaxRateCreate(BaseModel):
    jurisdiction_code: str
    tax_category_code: str
    rate_type: RateType
    rate_value: float | None = None
    currency_code: str | None = None
    tiers: list[dict] | None = None
    tier_type: TierType | None = None
    enacted_date: date | None = None
    effective_start: date
    effective_end: date | None = None
    applicability_start: date | None = None
    announcement_date: date | None = None
    calculation_order: int = 100
    base_includes: list[str] = Field(default=["base_amount"])
    legal_reference: str | None = None
    legal_uri: str | None = None
    source_url: str | None = None
    authority_name: str | None = None
    status: RateStatus = RateStatus.active
    created_by: str = "system"

    @model_validator(mode="after")
    def validate_rate_fields(self):
        if self.effective_end and self.effective_start > self.effective_end:
            raise ValueError("effective_start must be before effective_end")
        if self.rate_type == RateType.tiered:
            if not self.tiers:
                raise ValueError("tiers are required when rate_type is 'tiered'")
            if not self.tier_type:
                raise ValueError("tier_type is required when rate_type is 'tiered'")
            for i, tier in enumerate(self.tiers):
                if "min" not in tier:
                    raise ValueError(f"tier[{i}] must have a 'min' field")
                if self.tier_type == TierType.single_amount:
                    if "value" not in tier:
                        raise ValueError(
                            f"tier[{i}]: 'value' required for single_amount"
                        )
                if self.tier_type in (TierType.threshold, TierType.marginal_rate):
                    if "rate" not in tier:
                        raise ValueError(
                            f"tier[{i}]: 'rate' required for {self.tier_type}"
                        )
        elif self.rate_type in (RateType.percentage, RateType.flat):
            if self.rate_value is None:
                raise ValueError("rate_value is required for percentage and flat rate types")
        return self


class TaxRateUpdate(BaseModel):
    rate_value: float | None = None
    tiers: list[dict] | None = None
    effective_end: date | None = None
    legal_reference: str | None = None
    source_url: str | None = None
    status: RateStatus | None = None
    review_notes: str | None = None


class TaxRateResponse(BaseModel):
    id: int
    jurisdiction_id: int
    jurisdiction_code: str | None = None
    tax_category_id: int
    tax_category_code: str | None = None
    rate_type: str
    rate_value: float | None = None
    currency_code: str | None = None
    tiers: list[dict] | None = None
    tier_type: str | None = None
    enacted_date: date | None = None
    effective_start: date
    effective_end: date | None = None
    applicability_start: date | None = None
    announcement_date: date | None = None
    calculation_order: int
    base_includes: list[str]
    legal_reference: str | None = None
    legal_uri: str | None = None
    source_url: str | None = None
    authority_name: str | None = None
    version: int
    supersedes_id: int | None = None
    status: str
    collection_model: str | None = None
    taxable_amount_rule: str | None = None
    created_by: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaxRateBulkCreate(BaseModel):
    rates: list[TaxRateCreate] = Field(..., max_length=100)
