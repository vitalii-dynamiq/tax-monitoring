from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.rule_engine import BOOKING_CONTEXT_FIELDS

if TYPE_CHECKING:
    from app.models.jurisdiction import Jurisdiction
    from app.models.monitored_source import MonitoredSource
    from app.models.tax_rate import TaxRate
    from app.models.tax_rule import TaxRule


_BOOKING_CONTEXT_FIELDS_LIST = ", ".join(sorted(BOOKING_CONTEXT_FIELDS))


SYSTEM_PROMPT = f"""\
You are a tax regulation research agent specializing in accommodation and tourism taxes.

## Platform Purpose (READ THIS FIRST)
This platform calculates per-booking accommodation tax for a specific stay
(jurisdiction + dates + nights + nightly rate + guest attributes). We do NOT
track operator compliance, business registration, filing procedures, or other
administrative rules. Only report regulations that would change the TAX
CALCULATION for a given booking.

## Scope: One Run = One Country
Each run covers ONE COUNTRY and ALL of its sub-jurisdictions (states, provinces,
cities, districts, special zones) at once. The user prompt lists every known
jurisdiction in the country plus the rates and rules we currently have on file.

Your job is to research the country and report the COMPLETE current picture of
accommodation taxes across the country tree, tagging each finding with the
specific jurisdiction it applies to.

## Your Capabilities
You have access to web search. Use it to find current, authoritative tax information.

## Your Task
For the given country and its sub-jurisdictions, research ALL current
accommodation/tourism tax regulations by:
1. Searching the provided monitored source URLs (government sites, tax authority pages)
2. Searching for additional official sources at country, state/province, and city level
3. Comparing what you find against the currently known tax data in our database
4. Reporting ALL findings using the report_tax_findings tool, tagging every rate
   and rule with the EXACT `jurisdiction_code` from the user prompt that it
   applies to (the country, a state, or a city)

## Research Process
- Search each monitored source URL to find current tax rates and rules
- Search for "[jurisdiction name] accommodation tax", "[jurisdiction name] hotel tax", \
"[jurisdiction name] tourist tax" to find official sources
- Look for: tax rates (percentage, flat, tiered), exemptions, thresholds, effective dates
- Cross-reference multiple sources for accuracy

## CRITICAL: Only Report Concrete, Enacted Regulations
- ONLY report tax rates and rules that are CURRENTLY IN EFFECT or have been \
OFFICIALLY ENACTED with a specific effective date.
- Do NOT report rumors, proposals, potential changes, draft legislation, \
or speculative information. We need actionable data, not alerts.
- Every rate with change_type "new" or "changed" MUST include:
  - A concrete rate_value (for percentage or flat rates) or tiers (for tiered rates)
  - An effective_start date
  - A source_quote from an authoritative source
- Every rule with change_type "new" or "changed" MUST include:
  - Specific conditions and actions (not vague descriptions)
  - An effective_start date
- If you cannot find the exact rate value from an authoritative source, \
do NOT report it as "new" or "changed". Mark it as "unchanged" instead.

## Valid Rule Condition Fields (HARD CONSTRAINT)
When reporting a rule, `conditions` MUST reference ONLY these fields (exact names):
  {_BOOKING_CONTEXT_FIELDS_LIST}
If a rule requires a field NOT in this list — for example operator turnover,
registration status, business/establishment type, hotel zone, stay in hours,
bedroom/room count, booking channel beyond `platform_type`, payment method,
residency beyond `guest_nationality`, etc. — DO NOT REPORT IT. Our rule engine
silently ignores unknown fields, so the rule would never fire.

Canonical value shapes:
- `property_type` ∈ {{hotel, motel, str, bnb, hostel, resort, apartment_hotel, \
vacation_rental, campground, boutique}}
- `star_rating` is an integer 1-5
- `guest_type` is free-text but commonly: standard, business, resident, diplomatic, student
- `guest_age` is an integer
- `stay_length_days` is an integer (same as `nights`)

## Valid Rule Action Shapes
The `action` dict MUST use ONE of these shapes (anything else is ignored by the engine):
- Exemption:   {{"type": "exempt"}}  or just {{}}
- Reduction:   {{"reduction_pct": N}}       (N 0-100, percentage off the tax)
- Surcharge:   {{"surcharge_rate": N}}      (extra percentage on top)
- Cap nights:  {{"cap_nights": N}}          (tax only first N nights)
- Cap amount:  {{"cap_amount": M}}          (max total tax for the stay)
- Cap per night:  {{"cap_per_night": M}}
- Override:    {{"override_rate": M}}       (replace base rate with M)
- Min amount:  {{"min_amount": M}}          (floor)
Do not invent new action keys. Do not use strings like "type": "reduce" or \
"type": "apply_tourism_tax" — those won't do anything.

## Do NOT Report Administrative Rules (HARD REJECTION)
REJECT and do not include in your findings ANY rule that is informational,
procedural, or about operator compliance:
- Registration, licensing, permit obligations (for operators, PMS, OTAs)
- Filing deadlines, reporting frequencies, remit procedures
- Record-keeping, invoicing, e-invoicing mandates
- Audit, inspection, gazette-publication rules
- Who-collects-what between property/marketplace/operator
- Tax thresholds that gate OPERATOR VAT registration (vs. gating booking tax)
A valid rule gates the tax for a SPECIFIC BOOKING. Examples of valid rules:
guest under 12 exempt; stays >= 30 days reduced by 50%; cap at 10 nights; \
5-star hotels pay higher rate; business travelers exempt. These all use allow-\
listed fields and change the calculation output.

## Change Detection: Removals and Deprecations
- If a rate in our database marked "active" has been REPEALED, REPLACED, REDUCED, \
or otherwise MODIFIED, mark it as CHANGED or REMOVED. This is critical — we must \
not keep stale rates active.
- Rates marked as "draft" in our database are already detected changes pending \
human review. Do NOT re-report them as new findings.
- Pay special attention to effective_end dates that may have passed (expired rates).

## Reporting Guidelines
- For each tax rate or rule found, indicate if it is NEW, CHANGED, UNCHANGED, or REMOVED \
compared to our current database data
- Always include a direct source_quote from the source material
- Set confidence based on source authority: government sites (0.8-1.0), \
reputable news (0.5-0.7), unofficial sources (0.2-0.4)
- If you cannot find information about a known rate/rule, mark it as "unchanged" \
with lower confidence and explain in the notes
- For rate values, use DECIMAL numbers: 5.5 means 5.5%, not 0.055
- For dates, use ISO format: YYYY-MM-DD
- Do NOT invent tax rates. Only report what is supported by authoritative sources.

## When Done
After completing your research, call the report_tax_findings tool with ALL findings. \
Do not end your turn without calling this tool.
"""


def _format_rate(rate: TaxRate) -> str:
    parts = [f"  - Category: {rate.tax_category.code if rate.tax_category else 'unknown'}"]
    parts.append(f"({rate.tax_category.name if rate.tax_category else 'N/A'})")
    parts.append(f"| Type: {rate.rate_type}")
    if rate.rate_value is not None:
        if rate.rate_type == "percentage":
            parts.append(f"| Value: {float(rate.rate_value) * 100:.2f}%")
        else:
            parts.append(f"| Value: {rate.rate_value} {rate.currency_code or ''}")
    parts.append(f"| Effective: {rate.effective_start}")
    if rate.effective_end:
        parts.append(f"to {rate.effective_end}")
    if rate.legal_reference:
        parts.append(f"| Ref: {rate.legal_reference}")
    if rate.authority_name:
        parts.append(f"| Authority: {rate.authority_name}")
    if rate.source_url:
        parts.append(f"| Source: {rate.source_url}")
    return " ".join(parts)


def _format_rule(rule: TaxRule) -> str:
    parts = [f"  - Name: {rule.name}"]
    parts.append(f"| Type: {rule.rule_type}")
    parts.append(f"| Effective: {rule.effective_start}")
    if rule.effective_end:
        parts.append(f"to {rule.effective_end}")
    # Show the structured conditions + action (truncated) so the agent sees what
    # well-formed rules look like and mirrors them when proposing new ones.
    if rule.conditions:
        parts.append(f"| Conditions: {json.dumps(rule.conditions)[:300]}")
    if rule.action:
        parts.append(f"| Action: {json.dumps(rule.action)[:200]}")
    if rule.description:
        parts.append(f"| Description: {rule.description[:200]}")
    if rule.legal_reference:
        parts.append(f"| Ref: {rule.legal_reference}")
    return " ".join(parts)


def _format_rate_for_jur(rate: TaxRate, code_by_id: dict[int, str]) -> str:
    """Same as _format_rate but prefixes with the jurisdiction code for clarity."""
    code = code_by_id.get(rate.jurisdiction_id, "?")
    return f"  [{code}]" + _format_rate(rate)[3:]  # drop the "  -" prefix and replace


def _format_rule_for_jur(rule: TaxRule, code_by_id: dict[int, str]) -> str:
    code = code_by_id.get(rule.jurisdiction_id, "?")
    return f"  [{code}]" + _format_rule(rule)[3:]


def build_user_prompt(
    country: Jurisdiction,
    descendants: list[Jurisdiction],
    current_rates: list[TaxRate],
    current_rules: list[TaxRule],
    monitored_sources: list[MonitoredSource],
) -> str:
    """Build the user prompt with the FULL country tree + all current rates/rules.

    The agent uses web_search to find tax information, prioritising the given domains.
    Every reported rate/rule must be tagged with the exact jurisdiction_code from
    the tree listed in this prompt.
    """
    sections: list[str] = []
    code_by_id: dict[int, str] = {country.id: country.code}
    for d in descendants:
        code_by_id[d.id] = d.code

    # ── Country header ──
    header = (
        f"## Country to Research\n"
        f"- Code: {country.code}\n"
        f"- Name: {country.name}\n"
        f"- Currency: {country.currency_code}\n"
        f"- Timezone: {country.timezone or 'varies'}"
    )
    if country.local_name:
        header += f"\n- Local Name: {country.local_name}"
    sections.append(header)

    # ── Jurisdiction tree ──
    if descendants:
        # Group by jurisdiction_type for legibility
        by_type: dict[str, list[Jurisdiction]] = {}
        for d in descendants:
            by_type.setdefault(d.jurisdiction_type, []).append(d)
        order = ["state", "province", "region", "city", "district", "special_zone"]
        groups = []
        # Keep the original ordering when possible, append unknown types at end
        type_order = [t for t in order if t in by_type] + [
            t for t in by_type if t not in order
        ]
        for t in type_order:
            rows = sorted(by_type[t], key=lambda j: j.code)
            lines = [f"  - {j.code}  {j.name}" for j in rows]
            groups.append(f"### {t}s ({len(rows)})\n" + "\n".join(lines))
        sections.append(
            f"## Sub-Jurisdictions ({len(descendants)})\n"
            f"Tag any findings that apply ONLY to a sub-jurisdiction with its EXACT "
            f"`jurisdiction_code` from the list below. Country-wide findings use "
            f"`{country.code}`.\n\n"
            + "\n\n".join(groups)
        )
    else:
        sections.append(
            f"## Sub-Jurisdictions\n"
            f"This country has no sub-jurisdictions tracked. All findings should "
            f"use `jurisdiction_code = \"{country.code}\"`."
        )

    # ── Regulatory sources (operator-curated, per jurisdiction) ──
    if monitored_sources:
        lines = []
        for s in monitored_sources:
            j_code = code_by_id.get(s.jurisdiction_id, "?") if s.jurisdiction_id else "—"
            lines.append(
                f"  - [{s.source_type}] {s.url}  "
                f"({s.language or 'en'}, jurisdiction={j_code})"
            )
        sections.append(
            f"## Regulatory Sources ({len(monitored_sources)} curated by operators)\n"
            f"These are the URLs we already track as authoritative for tax information "
            f"in this country. Prioritize them in your research:\n"
            + "\n".join(lines)
        )
    else:
        sections.append(
            "## Regulatory Sources\n"
            "No operator-curated sources are configured for this country. Use web "
            "search to find official government and tax authority pages."
        )

    # ── Current rates ──
    active_rates = [r for r in current_rates if r.status == "active"]
    draft_rates = [r for r in current_rates if r.status in ("draft", "scheduled", "approved")]
    if active_rates or draft_rates:
        rate_sections = []
        if active_rates:
            lines = [_format_rate_for_jur(r, code_by_id) for r in active_rates]
            rate_sections.append(
                f"### ACTIVE Rates ({len(active_rates)}) — currently enforced:\n"
                + "\n".join(lines)
            )
        if draft_rates:
            lines = [_format_rate_for_jur(r, code_by_id) for r in draft_rates]
            rate_sections.append(
                f"### DRAFT Rates ({len(draft_rates)}) — already detected, pending review "
                f"(do NOT re-report):\n"
                + "\n".join(lines)
            )
        sections.append(
            f"## Known Tax Rates ({len(active_rates)} active, {len(draft_rates)} draft)\n"
            f"Compare your findings against ACTIVE rates. Do NOT re-detect DRAFT rates.\n\n"
            + "\n\n".join(rate_sections)
        )
    else:
        sections.append("## Known Tax Rates\nNone recorded in our database.")

    # ── Current rules ──
    active_rules = [r for r in current_rules if r.status == "active"]
    draft_rules = [r for r in current_rules if r.status in ("draft", "scheduled", "approved")]
    if active_rules or draft_rules:
        rule_sections = []
        if active_rules:
            lines = [_format_rule_for_jur(r, code_by_id) for r in active_rules]
            rule_sections.append(
                f"### ACTIVE Rules ({len(active_rules)}) — currently enforced:\n"
                + "\n".join(lines)
            )
        if draft_rules:
            lines = [_format_rule_for_jur(r, code_by_id) for r in draft_rules]
            rule_sections.append(
                f"### DRAFT Rules ({len(draft_rules)}) — already detected, pending review "
                f"(do NOT re-report):\n"
                + "\n".join(lines)
            )
        sections.append(
            f"## Known Tax Rules & Exemptions ({len(active_rules)} active, {len(draft_rules)} draft)\n"
            f"Compare against ACTIVE rules. Do NOT re-detect DRAFT rules.\n\n"
            + "\n\n".join(rule_sections)
        )
    else:
        sections.append("## Known Tax Rules\nNone recorded in our database.")

    sections.append(
        "## Instructions\n"
        f"1. Search priority sources for accommodation/hotel/tourism taxes in {country.name}\n"
        "2. For each sub-jurisdiction listed above, check whether it levies its OWN "
        "accommodation tax beyond what the country imposes\n"
        "3. Compare all findings against the rates and rules listed above\n"
        "4. Call the report_tax_findings tool exactly once with the COMPLETE findings, "
        "tagging every rate/rule with its EXACT `jurisdiction_code` from the lists above"
    )

    return "\n\n".join(sections)
