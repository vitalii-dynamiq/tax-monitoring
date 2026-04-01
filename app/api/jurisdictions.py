from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import require_admin
from app.db.session import get_db
from app.schemas.jurisdiction import (
    JurisdictionBulkCreate,
    JurisdictionCreate,
    JurisdictionResponse,
    JurisdictionUpdate,
)
from app.services.jurisdiction_service import (
    create_jurisdiction,
    create_jurisdictions_bulk,
    get_all_jurisdictions,
    get_jurisdiction_ancestors,
    get_jurisdiction_by_code,
    get_jurisdiction_children,
    resolve_jurisdiction,
)

router = APIRouter(prefix="/v1/jurisdictions", tags=["Jurisdictions"])


def _jurisdiction_to_response(j) -> dict:
    """Serialize Jurisdiction model to response dict, handling metadata_ -> metadata mapping."""
    return {
        "id": j.id,
        "code": j.code,
        "name": j.name,
        "local_name": j.local_name,
        "jurisdiction_type": j.jurisdiction_type,
        "path": j.path,
        "parent_id": j.parent_id,
        "country_code": j.country_code,
        "subdivision_code": j.subdivision_code,
        "timezone": j.timezone,
        "currency_code": j.currency_code,
        "status": j.status,
        "created_by": j.created_by,
        "created_at": j.created_at,
        "updated_at": j.updated_at,
    }


@router.get("", response_model=list[JurisdictionResponse])
async def list_jurisdictions(
    country_code: str | None = None,
    jurisdiction_type: str | None = None,
    status: str | None = None,
    parent_code: str | None = None,
    q: str | None = Query(None, description="Search by name"),
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    results = await get_all_jurisdictions(
        db,
        country_code=country_code,
        jurisdiction_type=jurisdiction_type,
        status=status,
        parent_code=parent_code,
        search=q,
        limit=limit,
        offset=offset,
    )
    return [_jurisdiction_to_response(j) for j in results]


@router.get("/resolve", response_model=list[JurisdictionResponse])
async def resolve_jurisdiction_endpoint(
    query: str = Query(..., min_length=1, description="City name, jurisdiction code, or ISO subdivision code"),
    country: str | None = Query(None, description="Filter by ISO country code (e.g., US, ES, JP)"),
    type: str | None = Query(None, description="Filter by jurisdiction type (country, state, city, etc.)"),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    """Resolve a location name or code to matching jurisdictions.

    Use this endpoint to map OTA location names to TaxLens jurisdiction codes.
    Returns the best matches sorted by relevance.

    Examples:
    - `/resolve?query=Barcelona&country=ES` → ES-CT-BCN
    - `/resolve?query=new+york&country=US` → US-NY, US-NY-NYC
    - `/resolve?query=dubai` → AE-DU
    - `/resolve?query=US-NY` → exact code match
    """
    results = await resolve_jurisdiction(
        db, query=query, country_code=country, jurisdiction_type=type, limit=limit,
    )
    return [_jurisdiction_to_response(j) for j in results]


@router.get("/{code}", response_model=JurisdictionResponse)
async def get_jurisdiction(code: str, db: AsyncSession = Depends(get_db)):
    j = await get_jurisdiction_by_code(db, code)
    if not j:
        raise HTTPException(404, f"Jurisdiction not found: {code}")
    return _jurisdiction_to_response(j)


@router.get("/{code}/children", response_model=list[JurisdictionResponse])
async def get_children(code: str, db: AsyncSession = Depends(get_db)):
    children = await get_jurisdiction_children(db, code)
    return [_jurisdiction_to_response(c) for c in children]


@router.get("/{code}/ancestors", response_model=list[JurisdictionResponse])
async def get_ancestors(code: str, db: AsyncSession = Depends(get_db)):
    ancestors = await get_jurisdiction_ancestors(db, code)
    return [_jurisdiction_to_response(a) for a in ancestors]


@router.post("", response_model=JurisdictionResponse, status_code=201)
async def create_new_jurisdiction(
    data: JurisdictionCreate,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await get_jurisdiction_by_code(db, data.code)
    if existing:
        raise HTTPException(409, f"Jurisdiction already exists: {data.code}")
    j = await create_jurisdiction(db, data)
    return _jurisdiction_to_response(j)


@router.post("/bulk", response_model=list[JurisdictionResponse], status_code=201)
async def create_jurisdictions_bulk_endpoint(
    data: JurisdictionBulkCreate,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    parent = await get_jurisdiction_by_code(db, data.parent_code)
    if not parent:
        raise HTTPException(404, f"Parent jurisdiction not found: {data.parent_code}")
    results = await create_jurisdictions_bulk(db, data.parent_code, data.children)
    return [_jurisdiction_to_response(j) for j in results]


@router.put("/{code}", response_model=JurisdictionResponse)
async def update_jurisdiction(
    code: str,
    data: JurisdictionUpdate,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    j = await get_jurisdiction_by_code(db, code)
    if not j:
        raise HTTPException(404, f"Jurisdiction not found: {code}")

    if data.name is not None:
        j.name = data.name
    if data.local_name is not None:
        j.local_name = data.local_name
    if data.timezone is not None:
        j.timezone = data.timezone
    if data.status is not None:
        j.status = data.status
    if data.metadata is not None:
        j.metadata_ = data.metadata

    await db.flush()
    return _jurisdiction_to_response(j)
