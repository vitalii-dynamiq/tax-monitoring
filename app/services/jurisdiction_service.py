from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jurisdiction import Jurisdiction
from app.schemas.jurisdiction import JurisdictionCreate


async def resolve_jurisdiction(
    db: AsyncSession,
    query: str,
    country_code: str | None = None,
    jurisdiction_type: str | None = None,
    limit: int = 10,
) -> list[Jurisdiction]:
    """Resolve a location name/code to matching jurisdictions.

    Searches by:
    1. Exact code match (highest priority)
    2. Code prefix match (e.g., "US-NY" matches "US-NY-NYC")
    3. Name match (case-insensitive)
    4. Subdivision code match (ISO 3166-2)

    Returns results sorted by relevance: exact > prefix > partial.
    """
    escaped = query.replace("%", r"\%").replace("_", r"\_")
    upper_query = query.upper().strip()

    conditions = [
        Jurisdiction.code == upper_query,
        Jurisdiction.code.ilike(f"{escaped}%", escape="\\"),
        Jurisdiction.name.ilike(f"%{escaped}%", escape="\\"),
        Jurisdiction.subdivision_code == upper_query,
    ]

    stmt = select(Jurisdiction).where(or_(*conditions))

    if country_code:
        stmt = stmt.where(Jurisdiction.country_code == country_code.upper())
    if jurisdiction_type:
        stmt = stmt.where(Jurisdiction.jurisdiction_type == jurisdiction_type)

    stmt = stmt.order_by(
        # Exact code match first, then by path length (most specific first)
        (Jurisdiction.code == upper_query).desc(),
        Jurisdiction.path.desc(),
    ).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_all_jurisdictions(
    db: AsyncSession,
    country_code: str | None = None,
    jurisdiction_type: str | None = None,
    status: str | None = None,
    parent_code: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Jurisdiction]:
    query = select(Jurisdiction)

    if country_code:
        query = query.where(Jurisdiction.country_code == country_code)
    if jurisdiction_type:
        query = query.where(Jurisdiction.jurisdiction_type == jurisdiction_type)
    if status:
        query = query.where(Jurisdiction.status == status)
    if parent_code:
        parent = await get_jurisdiction_by_code(db, parent_code)
        if parent:
            query = query.where(Jurisdiction.parent_id == parent.id)
    if search:
        escaped = search.replace("%", r"\%").replace("_", r"\_")
        query = query.where(Jurisdiction.name.ilike(f"%{escaped}%", escape="\\"))

    query = query.order_by(Jurisdiction.path).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_jurisdiction_by_code(db: AsyncSession, code: str) -> Jurisdiction | None:
    result = await db.execute(select(Jurisdiction).where(Jurisdiction.code == code))
    return result.scalar_one_or_none()


async def get_jurisdiction_children(db: AsyncSession, code: str) -> list[Jurisdiction]:
    parent = await get_jurisdiction_by_code(db, code)
    if not parent:
        return []
    result = await db.execute(
        select(Jurisdiction)
        .where(Jurisdiction.parent_id == parent.id)
        .order_by(Jurisdiction.name)
    )
    return list(result.scalars().all())


async def get_jurisdiction_ancestors(db: AsyncSession, code: str) -> list[Jurisdiction]:
    """Get all ancestors of a jurisdiction using ltree path traversal."""
    jurisdiction = await get_jurisdiction_by_code(db, code)
    if not jurisdiction:
        return []

    # Walk up the parent chain
    ancestors = []
    current = jurisdiction
    while current.parent_id:
        result = await db.execute(
            select(Jurisdiction).where(Jurisdiction.id == current.parent_id)
        )
        parent = result.scalar_one_or_none()
        if parent:
            ancestors.insert(0, parent)
            current = parent
        else:
            break
    return ancestors


async def get_jurisdiction_with_ancestors(db: AsyncSession, code: str) -> list[Jurisdiction]:
    """Get a jurisdiction and all its ancestors (for tax calculation)."""
    ancestors = await get_jurisdiction_ancestors(db, code)
    jurisdiction = await get_jurisdiction_by_code(db, code)
    if jurisdiction:
        ancestors.append(jurisdiction)
    return ancestors


def _build_path(parent: Jurisdiction | None, code: str) -> str:
    """Build ltree path from parent path and jurisdiction code."""
    # Use the last segment of the code as the path segment
    segments = code.replace("-", ".").split(".")
    path_segment = segments[-1] if segments else code

    if parent:
        return f"{parent.path}.{path_segment}"
    return path_segment


async def create_jurisdiction(
    db: AsyncSession, data: JurisdictionCreate
) -> Jurisdiction:
    parent = None
    if data.parent_code:
        parent = await get_jurisdiction_by_code(db, data.parent_code)

    path = _build_path(parent, data.code)

    jurisdiction = Jurisdiction(
        code=data.code,
        name=data.name,
        local_name=data.local_name,
        jurisdiction_type=data.jurisdiction_type,
        path=path,
        parent_id=parent.id if parent else None,
        country_code=data.country_code,
        subdivision_code=data.subdivision_code,
        timezone=data.timezone,
        currency_code=data.currency_code,
        status=data.status,
        metadata_=data.metadata,
    )
    db.add(jurisdiction)
    await db.flush()
    return jurisdiction


async def create_jurisdictions_bulk(
    db: AsyncSession, parent_code: str, children: list[JurisdictionCreate]
) -> list[Jurisdiction]:
    results = []
    for child in children:
        child.parent_code = parent_code
        j = await create_jurisdiction(db, child)
        results.append(j)
    return results
