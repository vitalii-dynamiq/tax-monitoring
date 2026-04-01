from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class JurisdictionType(StrEnum):
    country = "country"
    state = "state"
    province = "province"
    region = "region"
    city = "city"
    district = "district"
    special_zone = "special_zone"


class JurisdictionStatus(StrEnum):
    active = "active"
    inactive = "inactive"
    pending = "pending"


class JurisdictionCreate(BaseModel):
    code: str = Field(..., examples=["US-NY-NYC"])
    name: str = Field(..., examples=["New York City"])
    local_name: str | None = None
    jurisdiction_type: JurisdictionType = Field(..., examples=["city"])
    parent_code: str | None = Field(None, description="Code of parent jurisdiction")
    country_code: str = Field(..., min_length=2, max_length=2, examples=["US"])
    subdivision_code: str | None = None
    timezone: str | None = None
    currency_code: str = Field(..., min_length=3, max_length=3, examples=["USD"])
    status: JurisdictionStatus = JurisdictionStatus.active
    metadata: dict = Field(default_factory=dict)


class JurisdictionUpdate(BaseModel):
    name: str | None = None
    local_name: str | None = None
    timezone: str | None = None
    status: JurisdictionStatus | None = None
    metadata: dict | None = None


class JurisdictionResponse(BaseModel):
    id: int
    code: str
    name: str
    local_name: str | None = None
    jurisdiction_type: str
    path: str
    parent_id: int | None = None
    country_code: str
    subdivision_code: str | None = None
    timezone: str | None = None
    currency_code: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class JurisdictionBulkCreate(BaseModel):
    parent_code: str
    children: list[JurisdictionCreate]
