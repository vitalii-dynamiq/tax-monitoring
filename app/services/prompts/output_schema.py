from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.rule_engine import BOOKING_CONTEXT_FIELDS


def _walk_condition_fields(cond: dict | None) -> set[str]:
    """Extract every `field` name referenced in a conditions tree.

    Handles both the canonical shape {"rules": [...], "operator": ...} and the
    alternate {"AND": [...]}/{"OR": [...]} shape Claude occasionally emits.
    """
    out: set[str] = set()
    if not isinstance(cond, dict):
        return out
    fld = cond.get("field")
    if isinstance(fld, str):
        out.add(fld)
    for r in cond.get("rules") or []:
        if isinstance(r, dict):
            out |= _walk_condition_fields(r)
    for key in ("AND", "OR", "and", "or"):
        for r in cond.get(key) or []:
            if isinstance(r, dict):
                out |= _walk_condition_fields(r)
    return out


class AIExtractedRate(BaseModel):
    """A tax rate extracted by the AI monitoring agent."""

    change_type: Literal["new", "changed", "unchanged", "removed"] = Field(
        description="Whether this rate is new, changed from current, unchanged, or removed"
    )
    tax_category_code: str | None = Field(
        None,
        description=(
            "Category code matching our taxonomy. Common codes: "
            "occ_pct (occupancy tax %), occ_flat (flat occupancy), "
            "tourism_pct (tourism levy %), vat_standard (standard VAT), "
            "vat_reduced (reduced VAT), city_tax_flat (city/municipal flat tax), "
            "city_tax_pct (city/municipal %), bed_tax (bed/pillow tax), "
            "infrastructure_pct (infrastructure levy)"
        ),
    )
    rate_type: Literal["percentage", "flat", "tiered"] = Field(
        description="How the rate is calculated: percentage of room rate, flat amount per night, or tiered brackets"
    )
    rate_value: float | None = Field(
        None,
        description="Rate value as a decimal: 5.5 means 5.5% for percentage, or 2.50 means $2.50 for flat",
    )
    currency_code: str | None = Field(None, description="ISO 4217 currency code (e.g. USD, EUR) for flat rates")
    tiers: list[dict] | None = Field(
        None,
        description="For tiered rates: [{min: 0, max: 100, rate_value: 2.0}, {min: 100, max: null, rate_value: 3.0}]",
    )
    tier_type: str | None = Field(
        None,
        description="For tiered: single_amount (single bracket), marginal_rate (progressive), or threshold (step)",
    )
    base_type: str | None = Field(
        None,
        description="What the rate applies to: room_rate, per_night, per_person_per_night, per_stay, per_person_per_stay",
    )
    calculation_order: int = Field(
        default=100,
        description="Order in which this tax is calculated (lower = first). Use 100 for standard taxes, 200 for taxes on taxes",
    )
    effective_start: str = Field(description="ISO date (YYYY-MM-DD) when this rate takes effect")
    effective_end: str | None = Field(None, description="ISO date when this rate expires (null if indefinite)")
    enacted_date: str | None = Field(None, description="ISO date the law was enacted/passed")
    legal_reference: str | None = Field(None, description="Citation to the legal source (e.g. 'NYC Admin Code §11-2502')")
    legal_uri: str | None = Field(None, description="URL of the legal text")
    source_url: str | None = Field(None, description="URL where this information was found")
    authority_name: str | None = Field(None, description="Name of the tax authority (e.g. 'NYC Department of Finance')")
    source_quote: str = Field(
        max_length=2000,
        description="Direct quote from the source material supporting this rate (max 2000 chars)",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")

    @model_validator(mode="after")
    def validate_actionable_rate(self) -> AIExtractedRate:
        """Ensure new/changed rates have concrete values — no vague alerts."""
        if self.change_type in ("new", "changed"):
            if self.rate_type in ("percentage", "flat") and self.rate_value is None:
                raise ValueError(
                    f"rate_value is required for {self.change_type} {self.rate_type} rates. "
                    "Do not report rates without concrete values."
                )
            if self.rate_type == "tiered" and not self.tiers:
                raise ValueError(
                    f"tiers list is required for {self.change_type} tiered rates. "
                    "Do not report tiered rates without tier definitions."
                )
        return self


class AIExtractedRule(BaseModel):
    """A tax rule or exemption extracted by the AI monitoring agent."""

    change_type: Literal["new", "changed", "unchanged", "removed"] = Field(
        description="Whether this rule is new, changed, unchanged, or removed"
    )
    rule_type: Literal[
        "condition", "exemption", "reduction", "surcharge", "cap", "override", "threshold"
    ] = Field(description="The type of rule")
    name: str = Field(description="Short descriptive name (e.g. 'Permanent Resident Exemption')")
    description: str | None = Field(None, description="Detailed description of when and how this rule applies")
    conditions: dict | None = Field(
        None,
        description=(
            "Rule conditions as structured logic. Examples: "
            '{"field": "stay_length_days", "operator": ">=", "value": 180} or '
            '{"AND": [{"field": "guest_type", "operator": "==", "value": "resident"}, '
            '{"field": "stay_length_days", "operator": ">=", "value": 30}]}'
        ),
    )
    action: dict | None = Field(
        None,
        description=(
            "Action to apply when conditions match. Examples: "
            '{"type": "exempt"} or {"type": "reduce", "reduction_pct": 50} or '
            '{"type": "cap", "cap_amount": 5.00, "cap_nights": 21}'
        ),
    )
    effective_start: str = Field(description="ISO date (YYYY-MM-DD) when this rule takes effect")
    effective_end: str | None = Field(None, description="ISO date when this rule expires")
    enacted_date: str | None = Field(None, description="ISO date the law was enacted")
    legal_reference: str | None = Field(None, description="Citation to the legal source")
    source_url: str | None = Field(None, description="URL where this information was found")
    source_quote: str = Field(
        max_length=2000,
        description="Direct quote from the source supporting this rule (max 2000 chars)",
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")

    @model_validator(mode="after")
    def validate_condition_fields(self) -> AIExtractedRule:
        """Reject rules whose conditions reference fields the rule engine can't evaluate.

        Only enforced for new/changed rules — unchanged/removed rules may carry
        legacy field names from earlier seed batches and we don't want to fail
        the whole agent response on them.
        """
        if self.change_type not in ("new", "changed"):
            return self
        used = _walk_condition_fields(self.conditions)
        unknown = used - BOOKING_CONTEXT_FIELDS
        if unknown:
            raise ValueError(
                f"Rule '{self.name}': conditions reference unknown field(s) "
                f"{sorted(unknown)}. The rule engine only supports: "
                f"{sorted(BOOKING_CONTEXT_FIELDS)}. "
                "Either rewrite the rule to use a supported field or drop it."
            )
        return self


class AIMonitoringResult(BaseModel):
    """Complete monitoring result from the AI agent for a jurisdiction."""

    jurisdiction_code: str = Field(description="The jurisdiction code that was analyzed")
    summary: str = Field(
        description=(
            "Brief summary of findings: what changed, what's new, what was confirmed. "
            "Include the number of sources checked and overall assessment."
        )
    )
    rates: list[AIExtractedRate] = Field(
        default_factory=list, description="ALL tax rates found for this jurisdiction (new, changed, unchanged, removed)"
    )
    rules: list[AIExtractedRule] = Field(
        default_factory=list, description="ALL tax rules and exemptions found (new, changed, unchanged, removed)"
    )
    sources_checked: list[str] = Field(
        default_factory=list, description="URLs that were actually searched and analyzed"
    )
    overall_confidence: float = Field(
        ge=0.0, le=1.0,
        description="Overall confidence in the completeness and accuracy of the analysis",
    )
    notes: str | None = Field(
        None,
        description="Additional notes: limitations, sources that couldn't be accessed, caveats",
    )
