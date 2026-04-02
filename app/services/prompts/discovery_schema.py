from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class AIDiscoveredJurisdiction(BaseModel):
    """A sub-jurisdiction discovered by the AI agent."""

    suggested_code: str = Field(
        description=(
            "ISO-style code for this jurisdiction. Format: "
            "COUNTRY-STATE for states (e.g. AE-AJ for Ajman), "
            "COUNTRY-STATE-CITY for cities (e.g. AE-DU-DXB for Dubai city). "
            "Use 2-3 letter abbreviations."
        )
    )
    name: str = Field(description="Official English name of the jurisdiction")
    local_name: str | None = Field(None, description="Name in the local language")
    jurisdiction_type: Literal["state", "province", "region", "city", "district", "special_zone"] = Field(
        description="The administrative level of this jurisdiction"
    )
    parent_code: str = Field(
        description="Code of the parent jurisdiction in our hierarchy (country code or state code)"
    )
    timezone: str | None = Field(None, description="IANA timezone (e.g. 'Asia/Dubai')")
    currency_code: str = Field(description="ISO 4217 currency code (e.g. 'AED')")
    has_own_tax_rules: bool = Field(
        description=(
            "True if this jurisdiction levies its OWN accommodation/tourism taxes "
            "(not just inheriting from parent). Only include jurisdictions where this is True."
        )
    )
    tax_summary: str = Field(
        description=(
            "Brief description of what accommodation taxes this jurisdiction levies. "
            "e.g. 'Tourism Dirham fee of AED 7-20/night based on hotel star rating'"
        )
    )
    initial_rates: list[dict] = Field(
        default_factory=list,
        description=(
            "Initial tax rates found for this jurisdiction. Each dict should have: "
            "{rate_type: 'percentage'|'flat'|'tiered', rate_value: number, "
            "tax_category: str (e.g. 'tourism_flat_night', 'occ_pct'), "
            "currency_code: str (for flat rates), description: str}. "
            "Example: {rate_type: 'flat', rate_value: 15, tax_category: 'tourism_flat_night', "
            "currency_code: 'AED', description: 'Tourism Dirham fee per room per night'}"
        ),
    )
    source_url: str | None = Field(None, description="URL of the authoritative source")
    source_quote: str = Field(
        max_length=2000,
        description="Direct quote from the source confirming this jurisdiction has accommodation taxes",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")

    @model_validator(mode="after")
    def validate_has_own_taxes(self) -> AIDiscoveredJurisdiction:
        """Only include jurisdictions that actually have their own tax rules."""
        if not self.has_own_tax_rules:
            raise ValueError(
                f"Jurisdiction {self.name} does not have its own tax rules. "
                "Only report jurisdictions that levy their own accommodation taxes."
            )
        return self


class AIDiscoveryResult(BaseModel):
    """Complete discovery result for a country's sub-jurisdictions."""

    country_code: str = Field(description="The 2-letter ISO country code that was analyzed")
    summary: str = Field(
        description=(
            "Summary of the discovery: how many levels of government levy accommodation taxes, "
            "how many sub-jurisdictions were found, key observations about the tax structure"
        )
    )
    jurisdictions: list[AIDiscoveredJurisdiction] = Field(
        default_factory=list,
        description="ALL sub-jurisdictions that levy their own accommodation/tourism taxes",
    )
    hierarchy_depth: int = Field(
        description="Deepest nesting level found (1=states only, 2=states+cities, 3=states+cities+districts)"
    )
    sources_checked: list[str] = Field(
        default_factory=list, description="URLs that were searched"
    )
    overall_confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in completeness of the discovery"
    )
    notes: str | None = Field(
        None, description="Caveats, limitations, or notes about the discovery"
    )
