from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detected_change import DetectedChange
from app.models.jurisdiction import Jurisdiction
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule
from app.services.audit_service import log_change
from app.services.prompts.output_schema import AIExtractedRate, AIExtractedRule, AIMonitoringResult

logger = logging.getLogger(__name__)


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    return date.fromisoformat(s)


def _convert_rate_value(extracted: AIExtractedRate) -> float | None:
    """Convert AI rate value to database format.

    The AI prompt tells Claude to return percentage values as human-readable numbers
    (e.g. 5.875 means 5.875%). The database stores percentages as decimals (0.05875).
    Flat rates are stored as-is (e.g. 2.50 means $2.50).
    """
    if extracted.rate_value is None:
        return None
    if extracted.rate_type == "percentage":
        return extracted.rate_value / 100.0  # 5.875 → 0.05875
    return extracted.rate_value  # flat rates stored as-is


async def _create_draft_rate(
    db: AsyncSession,
    jurisdiction: Jurisdiction,
    extracted: AIExtractedRate,
    current_rate: TaxRate | None,
    job_id: int,
) -> TaxRate | None:
    """Create an ai_draft TaxRate from AI-extracted data."""
    from sqlalchemy import select

    from app.models.tax_category import TaxCategory

    category = None
    if extracted.tax_category_code:
        result = await db.execute(
            select(TaxCategory).where(TaxCategory.code == extracted.tax_category_code)
        )
        category = result.scalar_one_or_none()

    if not category:
        logger.warning(
            "Tax category '%s' not found for jurisdiction %s, skipping rate",
            extracted.tax_category_code,
            jurisdiction.code,
        )
        return None

    version = 1
    supersedes_id = None
    if current_rate and extracted.change_type == "changed":
        version = current_rate.version + 1
        supersedes_id = current_rate.id

    # Convert percentage values from AI format (5.875) to DB format (0.05875)
    db_rate_value = _convert_rate_value(extracted)

    rate = TaxRate(
        jurisdiction_id=jurisdiction.id,
        tax_category_id=category.id,
        rate_type=extracted.rate_type,
        rate_value=db_rate_value,
        currency_code=extracted.currency_code,
        tiers=extracted.tiers,
        tier_type=extracted.tier_type,
        enacted_date=_parse_date(extracted.enacted_date),
        effective_start=_parse_date(extracted.effective_start) or date.today(),
        effective_end=_parse_date(extracted.effective_end),
        legal_reference=extracted.legal_reference,
        legal_uri=extracted.legal_uri,
        source_url=extracted.source_url,
        authority_name=extracted.authority_name,
        version=version,
        supersedes_id=supersedes_id,
        status="draft",
        created_by="ai_monitoring",
    )
    db.add(rate)
    await db.flush()

    await log_change(
        db,
        entity_type="tax_rate",
        entity_id=rate.id,
        action="create",
        changed_by="ai_monitoring",
        change_source="ai_monitoring",
        new_values={
            "rate_type": extracted.rate_type,
            "rate_value": db_rate_value,
            "ai_raw_value": extracted.rate_value,
            "tax_category_code": extracted.tax_category_code,
            "change_type": extracted.change_type,
            "confidence": extracted.confidence,
        },
        old_values={
            "rate_value": float(current_rate.rate_value) if current_rate and current_rate.rate_value else None,
            "rate_type": current_rate.rate_type if current_rate else None,
        } if current_rate else None,
        change_reason=f"AI monitoring job #{job_id} detected {extracted.change_type} rate",
    )

    return rate


async def _create_draft_rule(
    db: AsyncSession,
    jurisdiction: Jurisdiction,
    extracted: AIExtractedRule,
    current_rule: TaxRule | None,
    job_id: int,
) -> TaxRule:
    """Create an ai_draft TaxRule from AI-extracted data."""
    version = 1
    supersedes_id = None
    if current_rule and extracted.change_type == "changed":
        version = current_rule.version + 1
        supersedes_id = current_rule.id

    rule = TaxRule(
        jurisdiction_id=jurisdiction.id,
        rule_type=extracted.rule_type,
        name=extracted.name,
        description=extracted.description,
        conditions=extracted.conditions or {},
        action=extracted.action or {},
        effective_start=_parse_date(extracted.effective_start) or date.today(),
        effective_end=_parse_date(extracted.effective_end),
        enacted_date=_parse_date(extracted.enacted_date),
        legal_reference=extracted.legal_reference,
        version=version,
        supersedes_id=supersedes_id,
        status="draft",
        created_by="ai_monitoring",
    )
    db.add(rule)
    await db.flush()

    await log_change(
        db,
        entity_type="tax_rule",
        entity_id=rule.id,
        action="create",
        changed_by="ai_monitoring",
        change_source="ai_monitoring",
        new_values={
            "rule_type": extracted.rule_type,
            "name": extracted.name,
            "change_type": extracted.change_type,
            "confidence": extracted.confidence,
        },
        old_values={
            "name": current_rule.name if current_rule else None,
            "rule_type": current_rule.rule_type if current_rule else None,
        } if current_rule else None,
        change_reason=f"AI monitoring job #{job_id} detected {extracted.change_type} rule",
    )

    return rule


def _find_matching_rate(
    extracted: AIExtractedRate, current_rates: list[TaxRate]
) -> TaxRate | None:
    """Find the current active rate that best matches the extracted rate."""
    for rate in current_rates:
        if (
            rate.tax_category
            and extracted.tax_category_code
            and rate.tax_category.code == extracted.tax_category_code
            and rate.status == "active"
        ):
            return rate
    return None


def _find_matching_rule(
    extracted: AIExtractedRule, current_rules: list[TaxRule]
) -> TaxRule | None:
    """Find the current active rule that best matches the extracted rule."""
    for rule in current_rules:
        if (
            rule.name == extracted.name
            and rule.rule_type == extracted.rule_type
            and rule.status == "active"
        ):
            return rule
    return None


async def process_ai_results(
    db: AsyncSession,
    jurisdiction: Jurisdiction,
    ai_result: AIMonitoringResult,
    job_id: int,
    current_rates: list[TaxRate],
    current_rules: list[TaxRule],
) -> dict:
    """Compare AI findings with current data and create drafts for changes.

    Handles new, changed, and removed rates/rules.
    Unchanged items are skipped (no action needed).
    Returns a summary dict with counts.
    """
    rates_created = 0
    rules_created = 0
    changes_created = 0
    removals_flagged = 0

    # ─── Process rates ───────────────────────────────────────────
    logger.info(
        "[%s] Processing AI results: %d rates, %d rules",
        jurisdiction.code, len(ai_result.rates), len(ai_result.rules),
    )
    for i, extracted_rate in enumerate(ai_result.rates):
        logger.info(
            "[%s] Rate %d/%d: %s %s (category=%s, value=%s, confidence=%.2f)",
            jurisdiction.code, i + 1, len(ai_result.rates),
            extracted_rate.change_type, extracted_rate.rate_type,
            extracted_rate.tax_category_code, extracted_rate.rate_value,
            extracted_rate.confidence,
        )
        if extracted_rate.change_type in ("new", "changed"):
            # Skip rates without concrete values — these are non-actionable
            if extracted_rate.rate_type in ("percentage", "flat") and extracted_rate.rate_value is None:
                logger.warning(
                    "Skipping %s %s rate for %s: no rate_value provided",
                    extracted_rate.change_type,
                    extracted_rate.rate_type,
                    jurisdiction.code,
                )
                continue
            if extracted_rate.rate_type == "tiered" and not extracted_rate.tiers:
                logger.warning(
                    "Skipping %s tiered rate for %s: no tiers provided",
                    extracted_rate.change_type,
                    jurisdiction.code,
                )
                continue

            current_rate = _find_matching_rate(extracted_rate, current_rates)
            draft_rate = await _create_draft_rate(
                db, jurisdiction, extracted_rate, current_rate, job_id
            )
            if draft_rate:
                rates_created += 1
                change_type = (
                    "rate_change" if extracted_rate.change_type == "changed" else "new_tax"
                )
                change = DetectedChange(
                    jurisdiction_id=jurisdiction.id,
                    change_type=change_type,
                    extracted_data=extracted_rate.model_dump(),
                    confidence=extracted_rate.confidence,
                    source_quote=extracted_rate.source_quote,
                    source_snapshot_url=extracted_rate.source_url,
                    applied_rate_id=draft_rate.id,
                )
                db.add(change)
                await db.flush()
                changes_created += 1

        elif extracted_rate.change_type == "removed":
            # Flag removal for human review — don't create a new rate,
            # just record the detected change pointing to the current rate
            current_rate = _find_matching_rate(extracted_rate, current_rates)
            change = DetectedChange(
                jurisdiction_id=jurisdiction.id,
                change_type="repeal",
                extracted_data=extracted_rate.model_dump(),
                confidence=extracted_rate.confidence,
                source_quote=extracted_rate.source_quote,
                source_snapshot_url=extracted_rate.source_url,
                applied_rate_id=current_rate.id if current_rate else None,
            )
            db.add(change)
            await db.flush()
            changes_created += 1
            removals_flagged += 1

    # ─── Process rules ───────────────────────────────────────────
    for extracted_rule in ai_result.rules:
        if extracted_rule.change_type in ("new", "changed"):
            current_rule = _find_matching_rule(extracted_rule, current_rules)
            draft_rule = await _create_draft_rule(
                db, jurisdiction, extracted_rule, current_rule, job_id
            )
            rules_created += 1
            change_type = (
                "exemption_change" if extracted_rule.change_type == "changed" else "new_tax"
            )
            change = DetectedChange(
                jurisdiction_id=jurisdiction.id,
                change_type=change_type,
                extracted_data=extracted_rule.model_dump(),
                confidence=extracted_rule.confidence,
                source_quote=extracted_rule.source_quote,
                source_snapshot_url=extracted_rule.source_url,
                applied_rule_id=draft_rule.id,
            )
            db.add(change)
            await db.flush()
            changes_created += 1

        elif extracted_rule.change_type == "removed":
            current_rule = _find_matching_rule(extracted_rule, current_rules)
            change = DetectedChange(
                jurisdiction_id=jurisdiction.id,
                change_type="repeal",
                extracted_data=extracted_rule.model_dump(),
                confidence=extracted_rule.confidence,
                source_quote=extracted_rule.source_quote,
                source_snapshot_url=extracted_rule.source_url,
                applied_rule_id=current_rule.id if current_rule else None,
            )
            db.add(change)
            await db.flush()
            changes_created += 1
            removals_flagged += 1

    # Log if no changes detected
    if changes_created == 0:
        await log_change(
            db,
            entity_type="jurisdiction",
            entity_id=jurisdiction.id,
            action="monitoring_no_changes",
            changed_by="ai_monitoring",
            change_source="ai_monitoring",
            change_reason=f"Monitoring job #{job_id}: no changes detected. {ai_result.summary}",
        )

    summary = {
        "changes_detected": changes_created,
        "rates_created": rates_created,
        "rules_created": rules_created,
        "removals_flagged": removals_flagged,
        "sources_checked": len(ai_result.sources_checked),
        "overall_confidence": ai_result.overall_confidence,
        "summary": ai_result.summary,
    }

    logger.info(
        "Change detection for %s: %d changes (%d rates, %d rules, %d removals)",
        jurisdiction.code,
        changes_created,
        rates_created,
        rules_created,
        removals_flagged,
    )

    return summary
