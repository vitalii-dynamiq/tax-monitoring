from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class TaxCalculationRequest(BaseModel):
    jurisdiction_code: str | None = Field(None, examples=["US-NY-NYC"])
    lat: float | None = Field(None, ge=-90, le=90, description="Latitude — used to auto-resolve jurisdiction if jurisdiction_code not provided")
    lng: float | None = Field(None, ge=-180, le=180, description="Longitude — used to auto-resolve jurisdiction if jurisdiction_code not provided")
    stay_date: date
    checkout_date: date | None = None
    nightly_rate: Decimal = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3, examples=["USD"])
    property_type: str = Field(default="hotel")
    star_rating: int | None = Field(None, ge=1, le=5)
    guest_type: str = "standard"
    guest_age: int | None = None
    guest_nationality: str | None = None
    nights: int = Field(..., ge=1)
    number_of_guests: int = Field(default=1, ge=1)
    is_marketplace: bool = False
    platform_type: str = "direct"
    is_bundled: bool = False


class TaxComponent(BaseModel):
    name: str
    category_code: str
    jurisdiction_code: str
    jurisdiction_level: str
    rate: float | None
    rate_type: str
    taxable_amount: Decimal | None
    tax_amount: Decimal
    legal_reference: str | None
    authority: str | None


class RuleTraceEntry(BaseModel):
    rule_id: int
    name: str
    rule_type: str
    result: str  # applied, skipped, exempted


class TaxBreakdown(BaseModel):
    components: list[TaxComponent]
    total_tax: Decimal
    effective_rate: Decimal
    currency: str


class CollectionInfo(BaseModel):
    who_collects: str = "property"  # property, platform, both, guest
    taxable_base: str = "room_rate"  # room_rate, total_consideration, net_rate
    platform_must_collect: bool = False
    notes: list[str] = []


class TaxCalculationResponse(BaseModel):
    calculation_id: str
    jurisdiction: dict
    input: dict
    tax_breakdown: TaxBreakdown
    total_with_tax: Decimal
    rules_applied: list[RuleTraceEntry]
    collection_info: CollectionInfo | None = None
    calculated_at: datetime
    data_version: str | None = None


class BatchCalculationRequest(BaseModel):
    calculations: list[TaxCalculationRequest]


class BatchCalculationResult(BaseModel):
    id: str | None = None
    total_tax: Decimal
    effective_rate: Decimal
    components: list[TaxComponent]
    error: str | None = None


class BatchCalculationResponse(BaseModel):
    results: list[BatchCalculationResult]
