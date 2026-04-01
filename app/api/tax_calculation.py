from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.tax_calculation import (
    BatchCalculationRequest,
    BatchCalculationResponse,
    TaxCalculationRequest,
    TaxCalculationResponse,
)
from app.services.tax_calculation_service import calculate_tax, calculate_tax_batch

router = APIRouter(prefix="/v1/tax", tags=["Tax Calculation"])


@router.post("/calculate", response_model=TaxCalculationResponse)
async def calculate_endpoint(
    request: TaxCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Calculate accommodation tax for a booking.

    Provide EITHER `jurisdiction_code` OR `lat`+`lng` (coordinates).
    If coordinates are provided, the jurisdiction is auto-resolved via
    reverse geocoding with fallback chain: city → state → country.
    """
    # Auto-resolve jurisdiction from lat/lng if no code provided
    if not request.jurisdiction_code:
        if request.lat is not None and request.lng is not None:
            from app.services.geocode_service import resolve_lat_lng_to_jurisdiction_code
            resolved = await resolve_lat_lng_to_jurisdiction_code(db, request.lat, request.lng)
            if not resolved:
                raise HTTPException(400, "Could not resolve coordinates to a jurisdiction")
            request.jurisdiction_code = resolved
        else:
            raise HTTPException(400, "Provide either jurisdiction_code or lat+lng coordinates")

    try:
        return await calculate_tax(db, request)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/calculate/batch", response_model=BatchCalculationResponse)
async def calculate_batch_endpoint(
    request: BatchCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    return await calculate_tax_batch(db, request)
