from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.audit import AuditLogResponse
from app.services.audit_service import get_audit_log

router = APIRouter(prefix="/v1/audit", tags=["Audit Log"])


@router.get("", response_model=list[AuditLogResponse])
async def list_audit_entries(
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await get_audit_log(
        db,
        entity_type=entity_type,
        entity_id=entity_id,
        limit=limit,
        offset=offset,
    )
