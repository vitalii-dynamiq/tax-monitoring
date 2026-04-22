"""Admin approval endpoints — bulk-flip draft rates/rules to active or rejected,
plus a summary endpoint that aggregates pending drafts per jurisdiction.
"""

from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.db.session import get_db
from app.models.jurisdiction import Jurisdiction
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule
from app.schemas.approval import (
    ApprovalRequest,
    BulkApprovalResponse,
    PendingSummary,
    PendingSummaryRow,
)
from app.services.audit_service import log_change

router = APIRouter(prefix="/v1/approvals", tags=["Approvals"])


@router.get("/summary", response_model=PendingSummary)
async def pending_summary(
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PendingSummary:
    """Aggregated pending-drafts count per jurisdiction. Admin-only."""
    rate_rows = (await db.execute(
        select(TaxRate.jurisdiction_id, TaxRate.created_at, TaxRate.created_by)
        .where(TaxRate.status == "draft")
    )).all()
    rule_rows = (await db.execute(
        select(TaxRule.jurisdiction_id, TaxRule.created_at, TaxRule.created_by)
        .where(TaxRule.status == "draft")
    )).all()

    per_jur: dict[int, dict] = defaultdict(
        lambda: {"rates": 0, "rules": 0, "earliest": None, "tags": set()}
    )
    for jid, created_at, created_by in rate_rows:
        bucket = per_jur[jid]
        bucket["rates"] += 1
        if bucket["earliest"] is None or created_at < bucket["earliest"]:
            bucket["earliest"] = created_at
        if created_by:
            bucket["tags"].add(created_by)
    for jid, created_at, created_by in rule_rows:
        bucket = per_jur[jid]
        bucket["rules"] += 1
        if bucket["earliest"] is None or created_at < bucket["earliest"]:
            bucket["earliest"] = created_at
        if created_by:
            bucket["tags"].add(created_by)

    if not per_jur:
        return PendingSummary(
            total_pending_rates=0, total_pending_rules=0, total_jurisdictions=0, rows=[]
        )

    jurs = (await db.execute(
        select(Jurisdiction).where(Jurisdiction.id.in_(per_jur.keys()))
    )).scalars().all()
    jurs_map = {j.id: j for j in jurs}

    rows = [
        PendingSummaryRow(
            jurisdiction_id=jid,
            jurisdiction_code=jurs_map[jid].code,
            jurisdiction_name=jurs_map[jid].name,
            jurisdiction_type=jurs_map[jid].jurisdiction_type,
            path=jurs_map[jid].path,
            pending_rates=bucket["rates"],
            pending_rules=bucket["rules"],
            earliest_created_at=bucket["earliest"],
            created_by_tags=sorted(bucket["tags"]),
        )
        for jid, bucket in per_jur.items()
        if jid in jurs_map
    ]
    rows.sort(key=lambda r: r.jurisdiction_code)

    return PendingSummary(
        total_pending_rates=sum(r.pending_rates for r in rows),
        total_pending_rules=sum(r.pending_rules for r in rows),
        total_jurisdictions=len(rows),
        rows=rows,
    )


async def _bulk_update_status(
    db: AsyncSession,
    jurisdiction_code: str,
    new_status: str,
    admin_user,
    payload: ApprovalRequest,
) -> BulkApprovalResponse:
    jur = (await db.execute(
        select(Jurisdiction).where(Jurisdiction.code == jurisdiction_code)
    )).scalar_one_or_none()
    if not jur:
        raise HTTPException(404, f"Jurisdiction not found: {jurisdiction_code}")

    reviewed_by = payload.reviewed_by or admin_user.email
    review_notes = payload.review_notes

    rate_q = select(TaxRate).where(
        TaxRate.jurisdiction_id == jur.id,
        TaxRate.status == "draft",
    )
    if payload.created_by:
        rate_q = rate_q.where(TaxRate.created_by == payload.created_by)
    rates = (await db.execute(rate_q)).scalars().all()

    rule_q = select(TaxRule).where(
        TaxRule.jurisdiction_id == jur.id,
        TaxRule.status == "draft",
    )
    if payload.created_by:
        rule_q = rule_q.where(TaxRule.created_by == payload.created_by)
    rules = (await db.execute(rule_q)).scalars().all()

    # reviewed_at columns are TIMESTAMP WITHOUT TIME ZONE — pass a naive UTC datetime
    now = datetime.now(UTC).replace(tzinfo=None)
    for r in rates:
        r.status = new_status
        r.reviewed_by = reviewed_by
        r.reviewed_at = now
        if review_notes:
            r.review_notes = review_notes
    for r in rules:
        r.status = new_status
        r.reviewed_by = reviewed_by
        r.reviewed_at = now

    await db.flush()

    for r in rates:
        await log_change(
            db,
            entity_type="tax_rate",
            entity_id=r.id,
            action="status_change",
            changed_by=reviewed_by,
            change_source="api",
            old_values={"status": "draft"},
            new_values={"status": new_status},
            change_reason=review_notes,
        )
    for r in rules:
        await log_change(
            db,
            entity_type="tax_rule",
            entity_id=r.id,
            action="status_change",
            changed_by=reviewed_by,
            change_source="api",
            old_values={"status": "draft"},
            new_values={"status": new_status},
            change_reason=review_notes,
        )

    return BulkApprovalResponse(
        jurisdiction_code=jur.code,
        new_status=new_status,
        approved_rate_ids=[r.id for r in rates],
        approved_rule_ids=[r.id for r in rules],
        reviewed_by=reviewed_by,
    )


@router.post("/jurisdiction/{jurisdiction_code}/approve", response_model=BulkApprovalResponse)
async def approve_jurisdiction_drafts(
    jurisdiction_code: str,
    payload: ApprovalRequest | None = None,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BulkApprovalResponse:
    """Flip every draft rate + rule for a jurisdiction to `active`. Admin-only."""
    return await _bulk_update_status(
        db, jurisdiction_code, "active", admin, payload or ApprovalRequest()
    )


@router.post("/jurisdiction/{jurisdiction_code}/reject", response_model=BulkApprovalResponse)
async def reject_jurisdiction_drafts(
    jurisdiction_code: str,
    payload: ApprovalRequest | None = None,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> BulkApprovalResponse:
    """Flip every draft rate + rule for a jurisdiction to `rejected`. Admin-only."""
    return await _bulk_update_status(
        db, jurisdiction_code, "rejected", admin, payload or ApprovalRequest()
    )
