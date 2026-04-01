"""
Reverse geocoding service — resolves lat/long to jurisdiction code.

Uses Nominatim (free, OpenStreetMap) by default.
Set OPENCAGE_API_KEY for production (2,500 free/day, $50/mo for 10K/day).

Includes in-memory cache to minimize external API calls.
"""

import logging
from functools import lru_cache

import httpx

from app.config import settings

logger = logging.getLogger("taxlens.geocode")

# Simple in-memory cache: (rounded lat, rounded lng) → geocode result
_cache: dict[tuple[float, float], dict] = {}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
OPENCAGE_URL = "https://api.opencagedata.com/geocode/v1/json"


def _round_coords(lat: float, lng: float) -> tuple[float, float]:
    """Round to 2 decimal places (~1.1 km precision) for cache key."""
    return round(lat, 2), round(lng, 2)


async def reverse_geocode(lat: float, lng: float) -> dict:
    """Reverse geocode lat/lng to location components.

    Returns:
        {
            "city": "Barcelona",
            "state": "Catalonia",
            "country": "Spain",
            "country_code": "ES",
            "subdivision_code": "ES-CT",  # ISO 3166-2 if available
        }
    """
    cache_key = _round_coords(lat, lng)
    if cache_key in _cache:
        return _cache[cache_key]

    opencage_key = getattr(settings, "opencage_api_key", "")
    if opencage_key:
        result = await _geocode_opencage(lat, lng, opencage_key)
    else:
        result = await _geocode_nominatim(lat, lng)

    _cache[cache_key] = result
    return result


async def _geocode_nominatim(lat: float, lng: float) -> dict:
    """Free reverse geocoding via OpenStreetMap Nominatim."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(NOMINATIM_URL, params={
                "lat": lat, "lon": lng, "format": "json",
                "addressdetails": 1, "accept-language": "en",
            }, headers={"User-Agent": "TaxLens/1.0 (tax-compliance-platform)"})
            resp.raise_for_status()
            data = resp.json()

        address = data.get("address", {})
        return {
            "city": address.get("city") or address.get("town") or address.get("village")
                    or address.get("municipality") or address.get("county"),
            "state": address.get("state") or address.get("province") or address.get("region"),
            "country": address.get("country"),
            "country_code": (address.get("country_code") or "").upper(),
            "subdivision_code": None,  # Nominatim doesn't return ISO 3166-2
        }
    except Exception as e:
        logger.warning("Nominatim geocode failed for %s,%s: %s", lat, lng, e)
        return {"city": None, "state": None, "country": None, "country_code": None, "subdivision_code": None}


async def _geocode_opencage(lat: float, lng: float, api_key: str) -> dict:
    """Paid reverse geocoding via OpenCage (returns ISO codes)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(OPENCAGE_URL, params={
                "q": f"{lat},{lng}", "key": api_key,
                "no_annotations": 1, "language": "en",
            })
            resp.raise_for_status()
            data = resp.json()

        if not data.get("results"):
            return {"city": None, "state": None, "country": None, "country_code": None, "subdivision_code": None}

        components = data["results"][0].get("components", {})
        iso = components.get("ISO_3166-2", {})

        return {
            "city": components.get("city") or components.get("town") or components.get("village"),
            "state": components.get("state") or components.get("province") or components.get("region"),
            "country": components.get("country"),
            "country_code": (components.get("country_code") or "").upper(),
            "subdivision_code": iso if isinstance(iso, str) else None,
        }
    except Exception as e:
        logger.warning("OpenCage geocode failed for %s,%s: %s — falling back to Nominatim", lat, lng, e)
        return await _geocode_nominatim(lat, lng)


async def resolve_lat_lng_to_jurisdiction_code(
    db, lat: float, lng: float
) -> str | None:
    """Full pipeline: lat/lng → reverse geocode → resolve to jurisdiction code.

    Fallback chain:
    1. Try exact city name match
    2. Try state/region name match
    3. Fall back to country code (always works)
    """
    from app.services.jurisdiction_service import resolve_jurisdiction

    geo = await reverse_geocode(lat, lng)
    country_code = geo.get("country_code")

    if not country_code:
        return None

    # Try city first (most specific)
    city = geo.get("city")
    if city:
        results = await resolve_jurisdiction(db, query=city, country_code=country_code, jurisdiction_type="city", limit=1)
        if results:
            return results[0].code

    # Try state/region
    state = geo.get("state")
    if state:
        results = await resolve_jurisdiction(db, query=state, country_code=country_code, limit=1)
        if results:
            return results[0].code

    # Try subdivision code (ISO 3166-2)
    subdiv = geo.get("subdivision_code")
    if subdiv:
        results = await resolve_jurisdiction(db, query=subdiv, country_code=country_code, limit=1)
        if results:
            return results[0].code

    # Fall back to country (always exists)
    results = await resolve_jurisdiction(db, query=country_code, limit=1)
    if results:
        return results[0].code

    return country_code  # Last resort: return the raw country code
