from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.core.rule_engine import BOOKING_CONTEXT_FIELDS

if TYPE_CHECKING:
    from app.models.jurisdiction import Jurisdiction
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

## Your Capabilities
You have access to web search. Use it to find current, authoritative tax information.

## Your Task
For a given jurisdiction, research ALL current accommodation/tourism tax regulations by:
1. Searching the provided monitored source URLs (government sites, tax authority pages)
2. Searching for additional official sources for this jurisdiction's accommodation taxes
3. Comparing what you find against the currently known tax data in our database
4. Reporting ALL findings using the report_tax_findings tool

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


def build_user_prompt(
    jurisdiction: Jurisdiction,
    current_rates: list[TaxRate],
    current_rules: list[TaxRule],
    monitored_domains: list[str],
) -> str:
    """Build the user prompt with jurisdiction context and priority domains.

    The agent uses web_search to find tax information, prioritizing the given domains.
    """
    sections = []

    # Jurisdiction info
    sections.append(
        f"## Jurisdiction to Research\n"
        f"- Code: {jurisdiction.code}\n"
        f"- Name: {jurisdiction.name}\n"
        f"- Type: {jurisdiction.jurisdiction_type}\n"
        f"- Country: {jurisdiction.country_code}\n"
        f"- Currency: {jurisdiction.currency_code}\n"
        f"- Path: {jurisdiction.path}"
    )
    if jurisdiction.local_name:
        sections[-1] += f"\n- Local Name: {jurisdiction.local_name}"

    # Priority government domains to search
    if monitored_domains:
        domain_list = "\n".join(f"  - {d}" for d in monitored_domains)
        sections.append(
            f"## Priority Government Domains ({len(monitored_domains)})\n"
            f"Prioritize searching these official domains for tax information:\n{domain_list}"
        )
    else:
        sections.append(
            "## Sources\n"
            "No specific domains configured. Use web search to find "
            "official government and tax authority pages for this jurisdiction."
        )

    # Current rates grouped by status
    active_rates = [r for r in current_rates if r.status == "active"]
    draft_rates = [r for r in current_rates if r.status in ("draft", "scheduled", "approved")]

    if active_rates or draft_rates:
        rate_sections = []
        if active_rates:
            rate_lines = [_format_rate(r) for r in active_rates]
            rate_sections.append(
                f"### ACTIVE Rates ({len(active_rates)}) — currently enforced:\n"
                + "\n".join(rate_lines)
            )
        if draft_rates:
            rate_lines = [_format_rate(r) for r in draft_rates]
            rate_sections.append(
                f"### DRAFT Rates ({len(draft_rates)}) — already detected, pending review (do NOT re-report):\n"
                + "\n".join(rate_lines)
            )
        sections.append(
            f"## Known Tax Rates ({len(active_rates)} active, {len(draft_rates)} draft)\n"
            "Compare your findings against ACTIVE rates. Do NOT re-detect DRAFT rates.\n\n"
            + "\n\n".join(rate_sections)
        )
    else:
        sections.append("## Known Tax Rates\nNone recorded in our database.")

    # Current rules grouped by status
    active_rules = [r for r in current_rules if r.status == "active"]
    draft_rules = [r for r in current_rules if r.status in ("draft", "scheduled", "approved")]

    if active_rules or draft_rules:
        rule_sections = []
        if active_rules:
            rule_lines = [_format_rule(r) for r in active_rules]
            rule_sections.append(
                f"### ACTIVE Rules ({len(active_rules)}) — currently enforced:\n"
                + "\n".join(rule_lines)
            )
        if draft_rules:
            rule_lines = [_format_rule(r) for r in draft_rules]
            rule_sections.append(
                f"### DRAFT Rules ({len(draft_rules)}) — already detected, pending review (do NOT re-report):\n"
                + "\n".join(rule_lines)
            )
        sections.append(
            f"## Known Tax Rules & Exemptions ({len(active_rules)} active, {len(draft_rules)} draft)\n"
            "Compare against ACTIVE rules. Do NOT re-detect DRAFT rules.\n\n"
            + "\n\n".join(rule_sections)
        )
    else:
        sections.append("## Known Tax Rules\nNone recorded in our database.")

    sections.append(
        "## Instructions\n"
        "1. Search each priority source URL listed above\n"
        "2. Search for additional official sources about accommodation/hotel/tourism taxes "
        f"in {jurisdiction.name} ({jurisdiction.country_code})\n"
        "3. Compare all findings against our currently known rates and rules\n"
        "4. Call the report_tax_findings tool with your complete findings"
    )

    return "\n\n".join(sections)
