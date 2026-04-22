"""
Prompt and output schema for the AI district-discovery agent.

Complements `tax_monitoring.py` (which researches taxes for ONE jurisdiction) with
the inverse shape: given a parent jurisdiction (city or state), find ALL
special-purpose tax districts/zones within it that impose accommodation taxes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from app.services.prompts.output_schema import AIExtractedRate, AIExtractedRule

if TYPE_CHECKING:
    from app.models.jurisdiction import Jurisdiction
    from app.models.tax_rate import TaxRate


SYSTEM_PROMPT = """\
You are a municipal tax researcher specializing in special-purpose tax districts that \
impose additional accommodation taxes beyond the standard city/state rates.

## Your Task
Given a PARENT jurisdiction (city or state) and its currently-known city-wide taxes, \
find EVERY SPECIAL-PURPOSE DISTRICT, ZONE, or IMPROVEMENT AREA within that parent \
that has an additional accommodation tax, fee, or assessment. Examples of what you're \
looking for:

- Tourism Marketing Districts (TMDs) — e.g., San Diego TMD (2% assessment on hotels)
- Tourism Improvement Districts (TIDs) — e.g., San Francisco TID, LA TMD
- Business Improvement Districts (BIDs) — e.g., Times Square Alliance, Hudson Yards
- Auditorium Districts (Idaho-specific) — e.g., Greater Boise Auditorium District (5%)
- Venue/Sports District taxes — e.g., Arlington TX Cowboys/Rangers venue tax
- Convention Center Facility/Financing Districts — e.g., SJCC, Santa Clara CCFD
- Parking/Infrastructure Improvement Zones
- Hudson Yards Infrastructure Corp, etc.
- Resort/Destination Marketing taxes scoped to specific geographic areas

## Critical Rules

1. **Do NOT report the city/state-wide base tax** (TOT, sales tax, occupancy tax) — \
those are already in our database and will be listed below for your reference.

2. **ONLY report districts with STATUTORY, CURRENTLY-IN-FORCE additional taxes.** \
If a BID/marketing org collects voluntary contributions or markets itself as a \
"district" without an actual government-levied tax, do NOT include it.

3. **Each district must have a SPECIFIC GEOGRAPHIC SCOPE.** A district that covers \
the entire city is just the city tax — not a district. We want sub-city zones.

4. **Every rate you report MUST include:**
   - A concrete rate_value (or tiers for tiered rates)
   - An effective_start date
   - A source_quote from an authoritative source (government site, published \
     ordinance, district's own official page)
   - A source_url — prefer `.gov`, official district sites, or published ordinances

5. **Suggested district codes** should follow the pattern `<parent_code>-<suffix>` \
where suffix is a short mnemonic (e.g., `US-CA-SDG-TMD`, `US-ID-BOIAD`, \
`US-TX-ARL-VENUE`). Keep suffix under 12 chars and uppercase.

## Research Process
- Start with: "[parent name] tourism marketing district tax", "[parent name] convention \
center facility district tax", "[parent name] business improvement district hotel tax", \
"[parent name] transient occupancy tax districts", "[parent name] auditorium district"
- For each candidate, locate the enabling ordinance / authorizing statute
- Confirm the rate and the geographic scope
- Cross-check with at least one secondary source (news, academic, industry report)

## When Done
Call the report_district_findings tool with your complete findings. Include a notes \
field for anything you investigated but ultimately rejected (so the reviewer knows \
what was considered).
"""


class AIDiscoveredDistrict(BaseModel):
    """A single special-purpose tax district discovered within a parent jurisdiction."""

    name: str = Field(
        description=(
            "Official name of the district. E.g. 'San Diego Tourism Marketing District', "
            "'Greater Boise Auditorium District', 'Arlington Entertainment District'."
        )
    )
    suggested_code: str = Field(
        description=(
            "Suggested jurisdiction code, format <parent_code>-<SUFFIX>. "
            "E.g. 'US-CA-SDG-TMD', 'US-ID-BOIAD', 'US-TX-ARL-VENUE'. "
            "Uppercase, hyphens only, total length <= 30 chars."
        )
    )
    path_suffix: str = Field(
        description=(
            "Suffix for the ltree path (appended to parent path). "
            "E.g. 'TMD', 'BOIAD', 'ENTDIST'. Uppercase alphanumeric, no dots. <= 16 chars."
        )
    )
    geographic_scope: str = Field(
        description=(
            "Natural-language description of what area this district covers. "
            "E.g. 'Downtown San Diego plus Mission Bay hotel corridor, hotels with 70+ rooms only' "
            "or 'Ada County municipal boundary encompassing Boise, Garden City, Meridian, Eagle, Star, Kuna'."
        )
    )
    authority_name: str | None = Field(
        None,
        description="Name of the body that administers or levies the district's tax.",
    )
    enabling_statute: str | None = Field(
        None,
        description="Citation to the enabling statute/ordinance that created the district.",
    )
    rates: list[AIExtractedRate] = Field(
        default_factory=list,
        description="All accommodation-related tax rates levied by this district.",
    )
    rules: list[AIExtractedRule] = Field(
        default_factory=list,
        description="All rules/exemptions/thresholds/caps attached to this district's taxes.",
    )
    source_quote: str = Field(
        max_length=2000,
        description="Direct verbatim quote confirming this district's existence and tax.",
    )
    source_url: str = Field(description="Primary URL where the district/tax is documented.")
    confidence: float = Field(ge=0.0, le=1.0, description="Overall confidence 0.0-1.0.")


class AIDistrictDiscoveryResult(BaseModel):
    """Full set of districts discovered within a parent jurisdiction."""

    parent_code: str = Field(description="The parent jurisdiction code this result is for.")
    summary: str = Field(
        description="Brief summary: how many districts found, key findings, overall assessment."
    )
    districts: list[AIDiscoveredDistrict] = Field(
        default_factory=list,
        description="All districts discovered. Empty list is a valid result if no districts exist.",
    )
    sources_checked: list[str] = Field(
        default_factory=list, description="URLs actually searched and analyzed."
    )
    overall_confidence: float = Field(
        ge=0.0, le=1.0, description="Overall confidence in completeness of the discovery."
    )
    notes: str | None = Field(
        None,
        description=(
            "Context about what was investigated but rejected (e.g., "
            "'Checked Downtown Partnership but it is a BID that collects voluntary "
            "contributions, not a statutory tax').."
        ),
    )


def _format_existing_rate(rate: TaxRate) -> str:
    parts = [f"  - Category: {rate.tax_category.code if rate.tax_category else 'unknown'}"]
    parts.append(f"| Type: {rate.rate_type}")
    if rate.rate_value is not None:
        if rate.rate_type == "percentage":
            parts.append(f"| Value: {float(rate.rate_value) * 100:.2f}%")
        else:
            parts.append(f"| Value: {rate.rate_value} {rate.currency_code or ''}")
    if rate.authority_name:
        parts.append(f"| Authority: {rate.authority_name}")
    return " ".join(parts)


def build_user_prompt(
    parent: Jurisdiction | None,
    parent_code: str,
    parent_name_hint: str | None,
    parent_state_hint: str | None,
    parent_country_hint: str | None,
    existing_rates: list[TaxRate],
) -> str:
    """Assemble the user message for the district-discovery agent.

    `parent` may be None if the parent doesn't exist in our DB yet — in that case the
    hints provide the context the agent needs to identify the right jurisdiction.
    """
    sections = []

    # Identify the parent
    if parent is not None:
        parent_desc = (
            f"## Parent Jurisdiction\n"
            f"- Code: {parent.code}\n"
            f"- Name: {parent.name}\n"
            f"- Type: {parent.jurisdiction_type}\n"
            f"- Country: {parent.country_code}\n"
            f"- Path: {parent.path}"
        )
        if parent.local_name:
            parent_desc += f"\n- Local Name: {parent.local_name}"
    else:
        parent_desc = (
            f"## Parent Jurisdiction (not yet in our database)\n"
            f"- Intended code: {parent_code}\n"
            f"- Name: {parent_name_hint or '(infer from code)'}\n"
            f"- State/region: {parent_state_hint or '(infer)'}\n"
            f"- Country: {parent_country_hint or '(infer)'}"
        )
    sections.append(parent_desc)

    # Already-known base taxes (agent should NOT re-report these)
    active_rates = [r for r in existing_rates if r.status == "active"]
    if active_rates:
        rate_lines = [_format_existing_rate(r) for r in active_rates]
        sections.append(
            f"## Known City/State-wide Taxes Already in Database ({len(active_rates)})\n"
            "Do NOT re-report these — only find ADDITIONAL special-district taxes "
            "that layer on top.\n\n"
            + "\n".join(rate_lines)
        )
    else:
        sections.append(
            "## Known Taxes\n"
            "No base taxes currently recorded for this parent. Still focus on "
            "special-district taxes (not the city-wide base tax)."
        )

    sections.append(
        "## Instructions\n"
        f"1. Find every special-purpose tax district within {parent_name_hint or parent_code} "
        "that imposes an accommodation tax, fee, or assessment.\n"
        "2. For each district, report its rates/rules with concrete values and sources.\n"
        "3. Prefer sources from government / official district websites.\n"
        "4. If you investigate a candidate that turns out NOT to be a statutory tax "
        "(e.g., voluntary BID contributions), mention it in the `notes` field but do "
        "not include it in `districts`.\n"
        "5. When done, call `report_district_findings` with the full result."
    )

    return "\n\n".join(sections)
