from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user, require_admin
from app.db.session import get_db
from app.schemas.tax_rate import TaxRateBulkCreate, TaxRateCreate, TaxRateResponse
from app.services.jurisdiction_service import get_jurisdiction_with_ancestors
from app.services.tax_rate_service import (
    create_rate,
    create_rates_bulk,
    get_active_rates_for_jurisdiction,
    get_all_rates,
    get_rate_by_id,
    update_rate_status,
)

router = APIRouter(prefix="/v1/rates", tags=["Tax Rates"])


def _rate_to_response(rate) -> TaxRateResponse:
    resp = TaxRateResponse.model_validate(rate)
    if rate.jurisdiction:
        resp.jurisdiction_code = rate.jurisdiction.code
    if rate.tax_category:
        resp.tax_category_code = rate.tax_category.code
    return resp


@router.get("", response_model=list[TaxRateResponse])
async def list_rates(
    jurisdiction_code: str | None = None,
    category_code: str | None = None,
    status: str | None = None,
    effective_date: date | None = None,
    limit: int = Query(100, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rates = await get_all_rates(
        db,
        jurisdiction_code=jurisdiction_code,
        category_code=category_code,
        status=status,
        effective_date=effective_date,
        limit=limit,
        offset=offset,
    )
    return [_rate_to_response(r) for r in rates]


@router.get("/lookup")
async def lookup_rates(
    jurisdiction_code: str,
    effective_date: date | None = None,
    _user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all active rates for a jurisdiction on a given date."""
    lookup_date = effective_date or date.today()
    jurisdictions = await get_jurisdiction_with_ancestors(db, jurisdiction_code)
    if not jurisdictions:
        raise HTTPException(404, f"Jurisdiction not found: {jurisdiction_code}")

    jurisdiction_ids = [j.id for j in jurisdictions]
    rates = await get_active_rates_for_jurisdiction(db, jurisdiction_ids, lookup_date)

    return {
        "jurisdiction": {
            "code": jurisdictions[-1].code,
            "name": jurisdictions[-1].name,
            "path": jurisdictions[-1].path,
        },
        "date": str(lookup_date),
        "rates": [_rate_to_response(r) for r in rates],
        "combined_percentage_rate": sum(
            float(r.rate_value or 0) for r in rates if r.rate_type == "percentage"
        ),
    }


@router.get("/{rate_id}", response_model=TaxRateResponse)
async def get_rate(
    rate_id: int, _user=Depends(get_current_user), db: AsyncSession = Depends(get_db),
):
    rate = await get_rate_by_id(db, rate_id)
    if not rate:
        raise HTTPException(404, "Rate not found")
    return _rate_to_response(rate)


@router.post("", response_model=TaxRateResponse, status_code=201)
async def create_new_rate(
    data: TaxRateCreate, _admin=Depends(require_admin), db: AsyncSession = Depends(get_db),
):
    try:
        rate = await create_rate(db, data)
        rate = await get_rate_by_id(db, rate.id)
        return _rate_to_response(rate)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/bulk", response_model=list[TaxRateResponse], status_code=201)
async def create_rates_bulk_endpoint(
    data: TaxRateBulkCreate, _admin=Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    try:
        rates = await create_rates_bulk(db, data.rates)
        results = []
        for r in rates:
            rate = await get_rate_by_id(db, r.id)
            results.append(_rate_to_response(rate))
        return results
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/{rate_id}/approve", response_model=TaxRateResponse)
async def approve_rate(
    rate_id: int,
    reviewed_by: str = "system",
    review_notes: str | None = None,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rate = await update_rate_status(db, rate_id, "active", reviewed_by, review_notes)
    if not rate:
        raise HTTPException(404, "Rate not found")
    rate = await get_rate_by_id(db, rate.id)
    return _rate_to_response(rate)


@router.post("/{rate_id}/reject", response_model=TaxRateResponse)
async def reject_rate(
    rate_id: int,
    reviewed_by: str = "system",
    review_notes: str | None = None,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rate = await update_rate_status(db, rate_id, "rejected", reviewed_by, review_notes)
    if not rate:
        raise HTTPException(404, "Rate not found")
    rate = await get_rate_by_id(db, rate.id)
    return _rate_to_response(rate)
