from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def log_change(
    db: AsyncSession,
    entity_type: str,
    entity_id: int,
    action: str,
    changed_by: str,
    change_source: str,
    old_values: dict | None = None,
    new_values: dict | None = None,
    change_reason: str | None = None,
    source_reference: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changed_by=changed_by,
        change_source=change_source,
        old_values=old_values,
        new_values=new_values,
        change_reason=change_reason,
        source_reference=source_reference,
    )
    db.add(entry)
    await db.flush()
    return entry


async def get_audit_log(
    db: AsyncSession,
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLog]:
    query = select(AuditLog)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
    if entity_id:
        query = query.where(AuditLog.entity_id == entity_id)
    query = query.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())
