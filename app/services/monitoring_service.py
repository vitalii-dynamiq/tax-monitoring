from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.detected_change import DetectedChange
from app.models.monitored_source import MonitoredSource
from app.schemas.monitoring import DetectedChangeCreate, MonitoredSourceCreate
from app.services.jurisdiction_service import get_jurisdiction_by_code


async def get_all_sources(
    db: AsyncSession,
    jurisdiction_code: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[MonitoredSource]:
    query = select(MonitoredSource).options(selectinload(MonitoredSource.jurisdiction))
    if jurisdiction_code:
        j = await get_jurisdiction_by_code(db, jurisdiction_code)
        if j:
            query = query.where(MonitoredSource.jurisdiction_id == j.id)
    if status:
        query = query.where(MonitoredSource.status == status)
    query = query.order_by(MonitoredSource.id).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_source_by_id(db: AsyncSession, source_id: int) -> MonitoredSource | None:
    result = await db.execute(select(MonitoredSource).options(selectinload(MonitoredSource.jurisdiction)).where(MonitoredSource.id == source_id))
    return result.scalar_one_or_none()


async def create_source(db: AsyncSession, data: MonitoredSourceCreate) -> MonitoredSource:
    jurisdiction_id = None
    if data.jurisdiction_code:
        j = await get_jurisdiction_by_code(db, data.jurisdiction_code)
        if not j:
            raise ValueError(f"Jurisdiction not found: {data.jurisdiction_code}")
        jurisdiction_id = j.id

    source = MonitoredSource(
        jurisdiction_id=jurisdiction_id,
        url=data.url,
        source_type=data.source_type,
        language=data.language,
        check_frequency_days=data.check_frequency_days,
        metadata_=data.metadata,
    )
    db.add(source)
    await db.flush()
    # Reload with relationships for serialization
    reloaded = await get_source_by_id(db, source.id)
    return reloaded or source


async def get_all_changes(
    db: AsyncSession,
    jurisdiction_code: str | None = None,
    review_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[DetectedChange]:
    query = select(DetectedChange).options(selectinload(DetectedChange.jurisdiction))
    if jurisdiction_code:
        j = await get_jurisdiction_by_code(db, jurisdiction_code)
        if j:
            query = query.where(DetectedChange.jurisdiction_id == j.id)
    if review_status:
        query = query.where(DetectedChange.review_status == review_status)
    query = query.order_by(DetectedChange.detected_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_change_by_id(db: AsyncSession, change_id: int) -> DetectedChange | None:
    result = await db.execute(select(DetectedChange).options(selectinload(DetectedChange.jurisdiction)).where(DetectedChange.id == change_id))
    return result.scalar_one_or_none()


async def create_change(db: AsyncSession, data: DetectedChangeCreate) -> DetectedChange:
    jurisdiction_id = None
    if data.jurisdiction_code:
        j = await get_jurisdiction_by_code(db, data.jurisdiction_code)
        if j:
            jurisdiction_id = j.id

    change = DetectedChange(
        source_id=data.source_id,
        jurisdiction_id=jurisdiction_id,
        change_type=data.change_type,
        extracted_data=data.extracted_data,
        confidence=data.confidence,
        source_quote=data.source_quote,
        source_snapshot_url=data.source_snapshot_url,
    )
    db.add(change)
    await db.flush()
    # Reload with relationships for serialization
    reloaded = await get_change_by_id(db, change.id)
    return reloaded or change


async def review_change(
    db: AsyncSession,
    change_id: int,
    review_status: str,
    reviewed_by: str = "system",
    review_notes: str | None = None,
) -> DetectedChange | None:
    change = await get_change_by_id(db, change_id)
    if not change:
        return None

    change.review_status = review_status
    change.reviewed_by = reviewed_by
    change.reviewed_at = datetime.now(UTC)
    if review_notes:
        change.review_notes = review_notes

    await db.flush()
    return change
