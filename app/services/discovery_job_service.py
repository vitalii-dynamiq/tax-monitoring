from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import settings
from app.db.session import async_session_factory
from app.models.jurisdiction import Jurisdiction
from app.models.monitoring_schedule import MonitoringSchedule
from app.models.tax_category import TaxCategory
from app.models.tax_rate import TaxRate
from app.services.audit_service import log_change
from app.services.monitoring_job_service import _job_semaphore, get_job

logger = logging.getLogger(__name__)


async def run_discovery_job(job_id: int) -> None:
    """Run a discovery job with concurrency and timeout limits."""
    async with _job_semaphore:
        try:
            await asyncio.wait_for(
                _run_discovery_job_inner(job_id),
                timeout=settings.monitoring_job_timeout_seconds,
            )
        except TimeoutError:
            logger.error("Discovery job %d timed out after %ds", job_id, settings.monitoring_job_timeout_seconds)
            try:
                async with async_session_factory() as db:
                    job = await get_job(db, job_id)
                    if job and job.status in ("pending", "running"):
                        job.status = "failed"
                        job.completed_at = datetime.now(UTC)
                        job.error_message = f"Job timed out after {settings.monitoring_job_timeout_seconds} seconds"
                        await db.commit()
            except Exception:
                logger.error("Failed to update timed-out discovery job %d", job_id, exc_info=True)


async def _run_discovery_job_inner(job_id: int) -> None:
    """Execute a jurisdiction discovery job.

    Discovers all sub-jurisdictions with accommodation taxes for a given country.
    Creates new jurisdictions with status='pending' for human review.
    """
    from app.services.discovery_agent_service import JurisdictionDiscoveryAgent

    async with async_session_factory() as db:
        try:
            job = await get_job(db, job_id)
            if not job:
                logger.error("Discovery job %d not found", job_id)
                return

            job.status = "running"
            job.started_at = datetime.now(UTC)
            await db.commit()

            # Load the country jurisdiction
            country_result = await db.execute(
                select(Jurisdiction).where(Jurisdiction.id == job.jurisdiction_id)
            )
            country = country_result.scalar_one_or_none()
            if not country:
                raise ValueError(f"Country jurisdiction ID {job.jurisdiction_id} not found")
            if country.jurisdiction_type != "country":
                raise ValueError(f"{country.code} is not a country (type={country.jurisdiction_type})")

            # Load all existing sub-jurisdictions for this country
            existing_result = await db.execute(
                select(Jurisdiction).where(
                    Jurisdiction.country_code == country.country_code,
                    Jurisdiction.id != country.id,
                )
            )
            existing_children = list(existing_result.scalars().all())
            existing_codes = {j.code for j in existing_children}
            existing_names = {j.name.lower() for j in existing_children}

            # Call discovery agent
            agent = JurisdictionDiscoveryAgent()
            result = await agent.discover_jurisdictions(country, existing_children)

            # Process discovered jurisdictions
            created_count = 0
            skipped_count = 0

            for discovered in result.jurisdictions:
                # Deduplication: skip if code or name already exists
                if discovered.suggested_code in existing_codes:
                    logger.info("Skipping %s — already exists", discovered.suggested_code)
                    skipped_count += 1
                    continue
                if discovered.name.lower() in existing_names:
                    logger.info("Skipping %s — name '%s' already exists", discovered.suggested_code, discovered.name)
                    skipped_count += 1
                    continue

                # Resolve parent
                parent_result = await db.execute(
                    select(Jurisdiction).where(Jurisdiction.code == discovered.parent_code)
                )
                parent = parent_result.scalar_one_or_none()
                if not parent:
                    logger.warning(
                        "Parent %s not found for %s, using country as parent",
                        discovered.parent_code,
                        discovered.suggested_code,
                    )
                    parent = country

                # Build path
                code_segment = discovered.suggested_code.split("-")[-1]
                path = f"{parent.path}.{code_segment}"

                # Create jurisdiction with pending status
                new_j = Jurisdiction(
                    code=discovered.suggested_code,
                    name=discovered.name,
                    local_name=discovered.local_name,
                    jurisdiction_type=discovered.jurisdiction_type,
                    path=path,
                    parent_id=parent.id,
                    country_code=country.country_code,
                    timezone=discovered.timezone,
                    currency_code=discovered.currency_code,
                    status="pending",
                    created_by="ai_discovery",
                    metadata_={
                        "tax_summary": discovered.tax_summary,
                        "discovery_confidence": discovered.confidence,
                        "discovery_source": discovered.source_url,
                        "discovery_job_id": job_id,
                    },
                )
                db.add(new_j)
                await db.flush()

                # Create a disabled monitoring schedule for the new jurisdiction
                schedule = MonitoringSchedule(
                    jurisdiction_id=new_j.id,
                    enabled=False,
                    cadence="weekly",
                )
                db.add(schedule)

                await log_change(
                    db,
                    entity_type="jurisdiction",
                    entity_id=new_j.id,
                    action="create",
                    changed_by="ai_discovery",
                    change_source="ai_discovery",
                    new_values={
                        "code": new_j.code,
                        "name": new_j.name,
                        "jurisdiction_type": new_j.jurisdiction_type,
                        "tax_summary": discovered.tax_summary,
                        "confidence": discovered.confidence,
                    },
                    change_reason=f"Discovery job #{job_id}: found sub-jurisdiction with accommodation taxes",
                    source_reference=discovered.source_url,
                )

                # Create initial tax rates from discovery data
                rates_created_for_j = 0
                for rate_data in discovered.initial_rates:
                    rate_type = rate_data.get("rate_type", "percentage")
                    rate_value = rate_data.get("rate_value")
                    category_code = rate_data.get("tax_category")

                    # Convert percentage values (AI returns 5.875, DB stores 0.05875)
                    db_rate_value = rate_value
                    if rate_type == "percentage" and rate_value is not None:
                        db_rate_value = rate_value / 100.0

                    # Resolve tax category — no silent fallback. If the agent
                    # suggested a category code we don't have, skip the rate and
                    # log loudly so the operator can add the category or correct
                    # the research. Silently coercing to `occ_pct` produced
                    # misclassified rates in earlier batches.
                    category = None
                    if category_code:
                        cat_result = await db.execute(
                            select(TaxCategory).where(TaxCategory.code == category_code)
                        )
                        category = cat_result.scalar_one_or_none()

                    if not category:
                        logger.warning(
                            "Discovery job #%s: skipping rate for %s — "
                            "unknown tax_category=%r (add to taxonomy or fix "
                            "the research).",
                            job_id, discovered.suggested_code, category_code,
                        )
                        continue

                    if category and rate_value is not None:
                        from datetime import date
                        tax_rate = TaxRate(
                            jurisdiction_id=new_j.id,
                            tax_category_id=category.id,
                            rate_type=rate_type,
                            rate_value=db_rate_value,
                            currency_code=rate_data.get("currency_code", discovered.currency_code),
                            effective_start=date.today(),
                            status="draft",
                            created_by="ai_discovery",
                            source_url=discovered.source_url,
                            authority_name=rate_data.get("description", ""),
                        )
                        db.add(tax_rate)
                        rates_created_for_j += 1

                if rates_created_for_j > 0:
                    await db.flush()
                    logger.info(
                        "Created %d initial draft rates for %s",
                        rates_created_for_j, discovered.suggested_code,
                    )

                created_count += 1
                existing_codes.add(discovered.suggested_code)
                existing_names.add(discovered.name.lower())

            # Mark job completed
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            job.changes_detected = created_count
            job.result_summary = {
                "jurisdictions_discovered": len(result.jurisdictions),
                "jurisdictions_created": created_count,
                "jurisdictions_skipped": skipped_count,
                "hierarchy_depth": result.hierarchy_depth,
                "sources_checked": len(result.sources_checked),
                "overall_confidence": result.overall_confidence,
                "summary": result.summary,
            }
            await db.commit()

            logger.info(
                "Discovery job %d completed: %d discovered, %d created, %d skipped",
                job_id, len(result.jurisdictions), created_count, skipped_count,
            )

        except Exception as e:
            logger.error("Discovery job %d failed: %s", job_id, e, exc_info=True)
            try:
                async with async_session_factory() as err_db:
                    err_job = await get_job(err_db, job_id)
                    if err_job and err_job.status in ("pending", "running"):
                        err_job.status = "failed"
                        err_job.completed_at = datetime.now(UTC)
                        err_job.error_message = str(e)[:2000]
                        err_job.error_traceback = traceback.format_exc()[:5000]
                        await err_db.commit()
            except Exception:
                logger.error("Failed to update discovery job %d after error", job_id, exc_info=True)
