"""
Seed data for TaxLens.

Populates tax_categories (L0-L2 taxonomy), property_classifications,
jurisdictions (US, EU, Asia-Pacific), and verified tax rates/rules
for key cities as validation scenarios.

Tax rates are sourced from official tax authority publications
and verified against multiple references.

Usage:
    cd tax-monitoring
    .venv/bin/python -m scripts.seed_data
"""

import asyncio
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.jurisdiction import Jurisdiction
from app.models.property_classification import PropertyClassification
from app.models.tax_category import TaxCategory
from app.models.monitored_source import MonitoredSource
from app.models.monitoring_schedule import MonitoringSchedule
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule

# ──────────────────────────────────────────────────────────────────────
# Tax Categories (L0-L2 taxonomy from RFC Section 8)
# ──────────────────────────────────────────────────────────────────────

TAX_CATEGORIES = [
    # Occupancy taxes — percentage of room rate
    {"code": "occ_pct", "name": "Occupancy Tax (% of room)", "level_0": "accommodation", "level_1": "occupancy", "level_2": "percentage", "base_type": "room_rate"},
    {"code": "occ_flat_night", "name": "Occupancy Tax (flat per night)", "level_0": "accommodation", "level_1": "occupancy", "level_2": "flat_per_night", "base_type": "per_night"},
    {"code": "occ_flat_person_night", "name": "Occupancy Tax (flat per person per night)", "level_0": "accommodation", "level_1": "occupancy", "level_2": "flat_per_person_per_night", "base_type": "per_person_per_night"},

    # Tourism / city / visitor taxes
    {"code": "tourism_pct", "name": "Tourism Tax (%)", "level_0": "accommodation", "level_1": "tourism", "level_2": "percentage", "base_type": "room_rate"},
    {"code": "tourism_flat_night", "name": "Tourism Tax (flat per night)", "level_0": "accommodation", "level_1": "tourism", "level_2": "flat_per_night", "base_type": "per_night"},
    {"code": "tourism_flat_person_night", "name": "Tourism Tax (flat per person per night)", "level_0": "accommodation", "level_1": "tourism", "level_2": "flat_per_person_per_night", "base_type": "per_person_per_night"},

    # VAT / Sales tax
    {"code": "vat_standard", "name": "VAT / Sales Tax (standard)", "level_0": "consumption", "level_1": "vat", "level_2": "percentage", "base_type": "room_rate"},
    {"code": "vat_reduced", "name": "VAT / Sales Tax (reduced rate)", "level_0": "consumption", "level_1": "vat", "level_2": "percentage", "base_type": "room_rate"},

    # Tiered rates
    {"code": "tier_price", "name": "Tiered by Price", "level_0": "accommodation", "level_1": "occupancy", "level_2": "tiered_by_price", "base_type": "room_rate"},
    {"code": "tier_star", "name": "Tiered by Star Rating", "level_0": "accommodation", "level_1": "tourism", "level_2": "tiered_by_star", "base_type": "room_rate"},

    # Convention / special district
    {"code": "convention_pct", "name": "Convention Center Tax (%)", "level_0": "accommodation", "level_1": "special_district", "level_2": "percentage", "base_type": "room_rate"},
    {"code": "convention_flat", "name": "Convention Center Tax (flat)", "level_0": "accommodation", "level_1": "special_district", "level_2": "flat_per_night", "base_type": "per_night"},

    # Infrastructure / improvement surcharge
    {"code": "infrastructure_pct", "name": "Infrastructure Surcharge (%)", "level_0": "accommodation", "level_1": "infrastructure", "level_2": "percentage", "base_type": "room_rate"},
    {"code": "infrastructure_flat", "name": "Infrastructure Surcharge (flat)", "level_0": "accommodation", "level_1": "infrastructure", "level_2": "flat_per_night", "base_type": "per_night"},

    # Environmental / eco tax
    {"code": "eco_pct", "name": "Environmental Tax (%)", "level_0": "accommodation", "level_1": "environmental", "level_2": "percentage", "base_type": "room_rate"},
    {"code": "eco_flat_person_night", "name": "Environmental Tax (per person per night)", "level_0": "accommodation", "level_1": "environmental", "level_2": "flat_per_person_per_night", "base_type": "per_person_per_night"},

    # Municipal / local surcharge
    {"code": "municipal_pct", "name": "Municipal Surcharge (%)", "level_0": "accommodation", "level_1": "municipal", "level_2": "percentage", "base_type": "room_rate"},
    {"code": "municipal_flat", "name": "Municipal Surcharge (flat per night)", "level_0": "accommodation", "level_1": "municipal", "level_2": "flat_per_night", "base_type": "per_night"},

    # Entry / one-time taxes (per stay, NOT per night)
    {"code": "entry_flat_person_stay", "name": "Entry Tax (per person per stay)", "level_0": "accommodation", "level_1": "entry", "level_2": "flat_per_person_per_stay", "base_type": "per_person_per_stay"},
    {"code": "entry_flat_stay", "name": "Entry Tax (per stay)", "level_0": "accommodation", "level_1": "entry", "level_2": "flat_per_stay", "base_type": "per_stay"},

    # Bathing / onsen tax
    {"code": "onsen_tier_price", "name": "Bathing/Onsen Tax (tiered by price)", "level_0": "accommodation", "level_1": "bathing", "level_2": "tiered_by_price", "base_type": "room_rate"},

    # Service tax (consumption-based)
    {"code": "service_pct", "name": "Service Tax (%)", "level_0": "consumption", "level_1": "service", "level_2": "percentage", "base_type": "room_rate"},

    # Tourism contribution (flat per night)
    {"code": "contribution_flat_night", "name": "Tourism Contribution (flat per night)", "level_0": "accommodation", "level_1": "contribution", "level_2": "flat_per_night", "base_type": "per_night"},
]

# ──────────────────────────────────────────────────────────────────────
# Property Classifications
# ──────────────────────────────────────────────────────────────────────

PROPERTY_CLASSIFICATIONS = [
    {"code": "hotel", "name": "Hotel", "description": "Full-service hotel with front desk"},
    {"code": "motel", "name": "Motel", "description": "Motor hotel, typically roadside"},
    {"code": "str", "name": "Short-Term Rental", "description": "Entire home or apartment rented short-term (e.g., Airbnb, VRBO)"},
    {"code": "bnb", "name": "Bed & Breakfast", "description": "Owner-occupied, breakfast included"},
    {"code": "hostel", "name": "Hostel", "description": "Budget shared accommodation"},
    {"code": "resort", "name": "Resort", "description": "Full-service resort with amenities"},
    {"code": "apartment_hotel", "name": "Apartment Hotel", "description": "Serviced apartments with hotel amenities"},
    {"code": "vacation_rental", "name": "Vacation Rental", "description": "Seasonal or vacation property rental"},
    {"code": "campground", "name": "Campground / RV Park", "description": "Outdoor camping or RV accommodation"},
    {"code": "boutique", "name": "Boutique Hotel", "description": "Small, stylish independent hotel"},
]

# ──────────────────────────────────────────────────────────────────────
# Jurisdictions
# ──────────────────────────────────────────────────────────────────────

JURISDICTIONS = [
    # ── United States ──
    {"code": "US", "name": "United States", "jurisdiction_type": "country", "path": "US", "parent_code": None, "country_code": "US", "subdivision_code": None, "timezone": None, "currency_code": "USD"},
    {"code": "US-NY", "name": "New York", "jurisdiction_type": "state", "path": "US.NY", "parent_code": "US", "country_code": "US", "subdivision_code": "US-NY", "timezone": "America/New_York", "currency_code": "USD"},
    {"code": "US-NY-NYC", "name": "New York City", "jurisdiction_type": "city", "path": "US.NY.NYC", "parent_code": "US-NY", "country_code": "US", "subdivision_code": "US-NY", "timezone": "America/New_York", "currency_code": "USD"},
    {"code": "US-IL", "name": "Illinois", "jurisdiction_type": "state", "path": "US.IL", "parent_code": "US", "country_code": "US", "subdivision_code": "US-IL", "timezone": "America/Chicago", "currency_code": "USD"},
    {"code": "US-IL-CHI", "name": "Chicago", "jurisdiction_type": "city", "path": "US.IL.CHI", "parent_code": "US-IL", "country_code": "US", "subdivision_code": "US-IL", "timezone": "America/Chicago", "currency_code": "USD"},
    {"code": "US-CA", "name": "California", "jurisdiction_type": "state", "path": "US.CA", "parent_code": "US", "country_code": "US", "subdivision_code": "US-CA", "timezone": "America/Los_Angeles", "currency_code": "USD"},
    {"code": "US-CA-LAX", "name": "Los Angeles", "jurisdiction_type": "city", "path": "US.CA.LAX", "parent_code": "US-CA", "country_code": "US", "subdivision_code": "US-CA", "timezone": "America/Los_Angeles", "currency_code": "USD"},
    {"code": "US-CA-SFO", "name": "San Francisco", "jurisdiction_type": "city", "path": "US.CA.SFO", "parent_code": "US-CA", "country_code": "US", "subdivision_code": "US-CA", "timezone": "America/Los_Angeles", "currency_code": "USD"},
    {"code": "US-TX", "name": "Texas", "jurisdiction_type": "state", "path": "US.TX", "parent_code": "US", "country_code": "US", "subdivision_code": "US-TX", "timezone": "America/Chicago", "currency_code": "USD"},
    {"code": "US-TX-HOU", "name": "Houston", "jurisdiction_type": "city", "path": "US.TX.HOU", "parent_code": "US-TX", "country_code": "US", "subdivision_code": "US-TX", "timezone": "America/Chicago", "currency_code": "USD"},
    {"code": "US-FL", "name": "Florida", "jurisdiction_type": "state", "path": "US.FL", "parent_code": "US", "country_code": "US", "subdivision_code": "US-FL", "timezone": "America/New_York", "currency_code": "USD"},
    {"code": "US-FL-MIA", "name": "Miami-Dade County", "jurisdiction_type": "city", "path": "US.FL.MIA", "parent_code": "US-FL", "country_code": "US", "subdivision_code": "US-FL", "timezone": "America/New_York", "currency_code": "USD"},
    {"code": "US-VA", "name": "Virginia", "jurisdiction_type": "state", "path": "US.VA", "parent_code": "US", "country_code": "US", "subdivision_code": "US-VA", "timezone": "America/New_York", "currency_code": "USD"},
    {"code": "US-VA-VBH", "name": "Virginia Beach", "jurisdiction_type": "city", "path": "US.VA.VBH", "parent_code": "US-VA", "country_code": "US", "subdivision_code": "US-VA", "timezone": "America/New_York", "currency_code": "USD"},
    {"code": "US-HI", "name": "Hawaii", "jurisdiction_type": "state", "path": "US.HI", "parent_code": "US", "country_code": "US", "subdivision_code": "US-HI", "timezone": "Pacific/Honolulu", "currency_code": "USD"},
    {"code": "US-HI-HNL", "name": "Honolulu", "jurisdiction_type": "city", "path": "US.HI.HNL", "parent_code": "US-HI", "country_code": "US", "subdivision_code": "US-HI", "timezone": "Pacific/Honolulu", "currency_code": "USD"},

    # ── Europe ──
    {"code": "NL", "name": "Netherlands", "jurisdiction_type": "country", "path": "NL", "parent_code": None, "country_code": "NL", "subdivision_code": None, "timezone": "Europe/Amsterdam", "currency_code": "EUR"},
    {"code": "NL-NH", "name": "North Holland", "jurisdiction_type": "state", "path": "NL.NH", "parent_code": "NL", "country_code": "NL", "subdivision_code": "NL-NH", "timezone": "Europe/Amsterdam", "currency_code": "EUR"},
    {"code": "NL-NH-AMS", "name": "Amsterdam", "jurisdiction_type": "city", "path": "NL.NH.AMS", "parent_code": "NL-NH", "country_code": "NL", "subdivision_code": "NL-NH", "timezone": "Europe/Amsterdam", "currency_code": "EUR"},

    {"code": "FR", "name": "France", "jurisdiction_type": "country", "path": "FR", "parent_code": None, "country_code": "FR", "subdivision_code": None, "timezone": "Europe/Paris", "currency_code": "EUR"},
    {"code": "FR-IDF", "name": "Ile-de-France", "jurisdiction_type": "state", "path": "FR.IDF", "parent_code": "FR", "country_code": "FR", "subdivision_code": "FR-IDF", "timezone": "Europe/Paris", "currency_code": "EUR"},
    {"code": "FR-IDF-PAR", "name": "Paris", "jurisdiction_type": "city", "path": "FR.IDF.PAR", "parent_code": "FR-IDF", "country_code": "FR", "subdivision_code": "FR-IDF", "timezone": "Europe/Paris", "currency_code": "EUR"},

    {"code": "IT", "name": "Italy", "jurisdiction_type": "country", "path": "IT", "parent_code": None, "country_code": "IT", "subdivision_code": None, "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-RM", "name": "Lazio", "jurisdiction_type": "state", "path": "IT.RM", "parent_code": "IT", "country_code": "IT", "subdivision_code": "IT-RM", "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-RM-ROM", "name": "Rome", "jurisdiction_type": "city", "path": "IT.RM.ROM", "parent_code": "IT-RM", "country_code": "IT", "subdivision_code": "IT-RM", "timezone": "Europe/Rome", "currency_code": "EUR"},

    {"code": "ES", "name": "Spain", "jurisdiction_type": "country", "path": "ES", "parent_code": None, "country_code": "ES", "subdivision_code": None, "timezone": "Europe/Madrid", "currency_code": "EUR"},
    {"code": "ES-IB", "name": "Balearic Islands", "jurisdiction_type": "state", "path": "ES.IB", "parent_code": "ES", "country_code": "ES", "subdivision_code": "ES-IB", "timezone": "Europe/Madrid", "currency_code": "EUR"},

    {"code": "DE", "name": "Germany", "jurisdiction_type": "country", "path": "DE", "parent_code": None, "country_code": "DE", "subdivision_code": None, "timezone": "Europe/Berlin", "currency_code": "EUR"},
    {"code": "DE-BE", "name": "Berlin (State)", "jurisdiction_type": "state", "path": "DE.BE", "parent_code": "DE", "country_code": "DE", "subdivision_code": "DE-BE", "timezone": "Europe/Berlin", "currency_code": "EUR"},
    {"code": "DE-BE-BER", "name": "Berlin", "jurisdiction_type": "city", "path": "DE.BE.BER", "parent_code": "DE-BE", "country_code": "DE", "subdivision_code": "DE-BE", "timezone": "Europe/Berlin", "currency_code": "EUR"},

    # ── Asia-Pacific ──
    {"code": "JP", "name": "Japan", "jurisdiction_type": "country", "path": "JP", "parent_code": None, "country_code": "JP", "subdivision_code": None, "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-13", "name": "Tokyo Prefecture", "jurisdiction_type": "state", "path": "JP.13", "parent_code": "JP", "country_code": "JP", "subdivision_code": "JP-13", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-13-TYO", "name": "Tokyo", "jurisdiction_type": "city", "path": "JP.13.TYO", "parent_code": "JP-13", "country_code": "JP", "subdivision_code": "JP-13", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-26", "name": "Kyoto Prefecture", "jurisdiction_type": "state", "path": "JP.26", "parent_code": "JP", "country_code": "JP", "subdivision_code": "JP-26", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-26-KYO", "name": "Kyoto", "jurisdiction_type": "city", "path": "JP.26.KYO", "parent_code": "JP-26", "country_code": "JP", "subdivision_code": "JP-26", "timezone": "Asia/Tokyo", "currency_code": "JPY"},

    {"code": "AE", "name": "United Arab Emirates", "jurisdiction_type": "country", "path": "AE", "parent_code": None, "country_code": "AE", "subdivision_code": None, "timezone": "Asia/Dubai", "currency_code": "AED"},
    {"code": "AE-DU", "name": "Dubai", "jurisdiction_type": "state", "path": "AE.DU", "parent_code": "AE", "country_code": "AE", "subdivision_code": "AE-DU", "timezone": "Asia/Dubai", "currency_code": "AED"},

    {"code": "ID", "name": "Indonesia", "jurisdiction_type": "country", "path": "ID", "parent_code": None, "country_code": "ID", "subdivision_code": None, "timezone": "Asia/Makassar", "currency_code": "IDR"},
    {"code": "ID-BA", "name": "Bali", "jurisdiction_type": "state", "path": "ID.BA", "parent_code": "ID", "country_code": "ID", "subdivision_code": "ID-BA", "timezone": "Asia/Makassar", "currency_code": "IDR"},

    {"code": "TH", "name": "Thailand", "jurisdiction_type": "country", "path": "TH", "parent_code": None, "country_code": "TH", "subdivision_code": None, "timezone": "Asia/Bangkok", "currency_code": "THB"},
    {"code": "TH-10", "name": "Bangkok Province", "jurisdiction_type": "state", "path": "TH.10", "parent_code": "TH", "country_code": "TH", "subdivision_code": "TH-10", "timezone": "Asia/Bangkok", "currency_code": "THB"},
    {"code": "TH-10-BKK", "name": "Bangkok", "jurisdiction_type": "city", "path": "TH.10.BKK", "parent_code": "TH-10", "country_code": "TH", "subdivision_code": "TH-10", "timezone": "Asia/Bangkok", "currency_code": "THB"},
]


async def _get_or_create(db: AsyncSession, model, unique_field: str, data: dict):
    """Get existing record or create new one."""
    result = await db.execute(
        select(model).where(getattr(model, unique_field) == data[unique_field])
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    obj = model(**data)
    db.add(obj)
    await db.flush()
    return obj


async def seed_tax_categories(db: AsyncSession) -> dict[str, TaxCategory]:
    categories = {}
    for cat_data in TAX_CATEGORIES:
        cat = await _get_or_create(db, TaxCategory, "code", cat_data)
        categories[cat.code] = cat
    return categories


async def seed_property_classifications(db: AsyncSession) -> dict[str, PropertyClassification]:
    classifications = {}
    for cls_data in PROPERTY_CLASSIFICATIONS:
        cls = await _get_or_create(db, PropertyClassification, "code", cls_data)
        classifications[cls.code] = cls
    return classifications


async def seed_jurisdictions(db: AsyncSession) -> dict[str, Jurisdiction]:
    jurisdictions = {}
    for j_data in JURISDICTIONS:
        j_data = dict(j_data)  # copy to avoid mutating original
        parent_code = j_data.pop("parent_code", None)
        if parent_code and parent_code in jurisdictions:
            j_data["parent_id"] = jurisdictions[parent_code].id
        j = await _get_or_create(db, Jurisdiction, "code", j_data)
        jurisdictions[j.code] = j
    return jurisdictions


async def _create_rate_if_not_exists(db: AsyncSession, rate_data: dict) -> TaxRate:
    """Create a rate only if one doesn't already exist for the same jurisdiction+category+status."""
    result = await db.execute(
        select(TaxRate).where(
            TaxRate.jurisdiction_id == rate_data["jurisdiction_id"],
            TaxRate.tax_category_id == rate_data["tax_category_id"],
            TaxRate.status == "active",
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    rate = TaxRate(**rate_data)
    db.add(rate)
    await db.flush()
    return rate


async def _create_rule_if_not_exists(db: AsyncSession, rule_data: dict) -> TaxRule:
    """Create a rule only if one doesn't already exist with the same name+rate."""
    result = await db.execute(
        select(TaxRule).where(
            TaxRule.tax_rate_id == rule_data.get("tax_rate_id"),
            TaxRule.name == rule_data["name"],
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    rule = TaxRule(**rule_data)
    db.add(rule)
    await db.flush()
    return rule


# ──────────────────────────────────────────────────────────────────────
# NYC Tax Rates
# Source: NYC Dept of Finance, NY Tax Law §1105(e), NYC Admin Code §11-2502
#
# Total NYC hotel tax stack (2024-2025):
#   NY State Sales Tax:           4.000%
#   NYC Local Sales Tax:          4.500%
#   NYC Hotel Room Occupancy Tax: 5.875%
#   Unit Fee:                    $2.00/room/night (rooms ≥$100)
#                                $1.50/room/night (rooms <$100)
# Combined rate:                 14.375% + unit fee
# ──────────────────────────────────────────────────────────────────────

async def seed_nyc_rates(db, jurisdictions, categories) -> list[TaxRate]:
    rates = []
    effective = date(2024, 1, 1)

    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["US-NY"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.04,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "NY Tax Law §1105(e) — state sales tax on hotel room occupancy",
            "legal_uri": "https://www.nysenate.gov/legislation/laws/TAX/1105",
            "source_url": "https://www.tax.ny.gov/bus/st/stidx.htm",
            "authority_name": "New York State Department of Taxation and Finance",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-NY-NYC"].id,
            "tax_category_id": categories["municipal_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.045,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "NYC Administrative Code §11-2502 — city sales tax on hotel occupancy",
            "source_url": "https://www.nyc.gov/site/finance/taxes/business-hotel-room-occupancy-tax.page",
            "authority_name": "NYC Department of Finance",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-NY-NYC"].id,
            "tax_category_id": categories["occ_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.05875,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 30,
            "base_includes": ["base_amount"],
            "legal_reference": "NYC Administrative Code §11-2502 — hotel room occupancy tax",
            "source_url": "https://www.nyc.gov/site/finance/taxes/business-hotel-room-occupancy-tax.page",
            "authority_name": "NYC Department of Finance",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-NY-NYC"].id,
            "tax_category_id": categories["occ_flat_night"].id,
            "rate_type": "flat",
            "rate_value": 2.00,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 40,
            "base_includes": ["base_amount"],
            "legal_reference": "NYC Admin Code §11-2502 — unit fee ($2.00/room/night for rooms ≥$100/night)",
            "source_url": "https://www.nyc.gov/site/finance/taxes/business-hotel-room-occupancy-tax.page",
            "authority_name": "NYC Department of Finance",
            "status": "active",
            "created_by": "seed",
        },
    ]

    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_nyc_rules(db, rates, jurisdictions) -> list[TaxRule]:
    rules = []
    effective = date(2024, 1, 1)

    # Find the NYC occupancy tax rate by category code match
    nyc_occ_rate = None
    for r in rates:
        cat_result = await db.execute(
            select(TaxCategory).where(TaxCategory.id == r.tax_category_id)
        )
        cat = cat_result.scalar_one_or_none()
        if cat and cat.code == "occ_pct" and r.jurisdiction_id == jurisdictions["US-NY-NYC"].id:
            nyc_occ_rate = r
            break

    if not nyc_occ_rate:
        print("  WARNING: NYC occupancy rate not found, skipping rules")
        return rules

    # Permanent resident exemption — stays >= 180 consecutive days
    rules.append(await _create_rule_if_not_exists(db, {
        "tax_rate_id": nyc_occ_rate.id,
        "jurisdiction_id": jurisdictions["US-NY-NYC"].id,
        "rule_type": "exemption",
        "priority": 100,
        "name": "Permanent Resident Exemption (180+ days)",
        "description": "NYC hotel occupancy tax exempt for stays of 180 or more consecutive days. "
                       "Guest is considered a permanent resident per NYC Administrative Code.",
        "conditions": {
            "operator": "AND",
            "rules": [{"field": "stay_length_days", "op": ">=", "value": 180}],
        },
        "action": {},
        "effective_start": effective,
        "legal_reference": "NYC Administrative Code §11-2502(a) — permanent resident exemption",
        "authority_name": "NYC Department of Finance",
        "status": "active",
        "created_by": "seed",
    }))

    # Unit fee — only applies to rooms $100+/night
    nyc_flat_rate = None
    for r in rates:
        cat_result = await db.execute(
            select(TaxCategory).where(TaxCategory.id == r.tax_category_id)
        )
        cat = cat_result.scalar_one_or_none()
        if cat and cat.code == "occ_flat_night" and r.jurisdiction_id == jurisdictions["US-NY-NYC"].id:
            nyc_flat_rate = r
            break

    if nyc_flat_rate:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": nyc_flat_rate.id,
            "jurisdiction_id": jurisdictions["US-NY-NYC"].id,
            "rule_type": "exemption",
            "priority": 90,
            "name": "Unit Fee Exemption (rooms under $100/night)",
            "description": "The $2.00 unit fee only applies to rooms costing $100 or more per night. "
                           "Rooms under $100/night are exempt from this fee.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "nightly_rate", "op": "<", "value": 100}],
            },
            "action": {},
            "effective_start": effective,
            "legal_reference": "NYC Admin Code §11-2502 — unit fee applicability threshold",
            "authority_name": "NYC Department of Finance",
            "status": "active",
            "created_by": "seed",
        }))

    return rules


# ──────────────────────────────────────────────────────────────────────
# Chicago Tax Rates
# Source: City of Chicago Dept of Finance, IL DOR
#
# Chicago hotel tax stack (2024):
#   IL State Hotel Operators' Occupation Tax: 6.00%
#   Chicago Hotel Accommodation Tax:          4.50%
#   Chicago Convention Center Surcharge:      varies (simplified to 1%)
#   McPier Metropolitan Pier and Exposition:  2.50% (on hotel rooms within Chicago)
# ──────────────────────────────────────────────────────────────────────

async def seed_chicago_rates(db, jurisdictions, categories) -> list[TaxRate]:
    rates = []
    effective = date(2024, 1, 1)

    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["US-IL"].id,
            "tax_category_id": categories["occ_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.06,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Illinois Hotel Operators' Occupation Tax Act (35 ILCS 145/)",
            "source_url": "https://tax.illinois.gov/research/taxrates/st-hotel.html",
            "authority_name": "Illinois Department of Revenue",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-IL-CHI"].id,
            "tax_category_id": categories["occ_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.045,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Chicago Municipal Code 3-24 — Hotel Accommodation Tax",
            "source_url": "https://www.chicago.gov/city/en/depts/fin/supp_info/revenue/tax_list/hotel_accommodationtax.html",
            "authority_name": "City of Chicago Department of Finance",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-IL-CHI"].id,
            "tax_category_id": categories["convention_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.025,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 30,
            "base_includes": ["base_amount"],
            "legal_reference": "Metropolitan Pier and Exposition Authority Act — McPier tax on Chicago hotel rooms",
            "authority_name": "Metropolitan Pier and Exposition Authority",
            "status": "active",
            "created_by": "seed",
        },
    ]

    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


# ──────────────────────────────────────────────────────────────────────
# Amsterdam Tax Rates
# Source: Gemeente Amsterdam, Belastingdienst
#
# Amsterdam (2025):
#   Netherlands VAT on accommodation: 9% (reduced rate, BTW laag tarief)
#   Amsterdam tourist tax: 12.5% of room rate (was 7% until 2024)
# ──────────────────────────────────────────────────────────────────────

async def seed_amsterdam_rates(db, jurisdictions, categories) -> list[TaxRate]:
    rates = []

    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["NL"].id,
            "tax_category_id": categories["vat_reduced"].id,
            "rate_type": "percentage",
            "rate_value": 0.09,
            "currency_code": "EUR",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Wet op de omzetbelasting 1968 — BTW laag tarief (9%) for accommodation",
            "source_url": "https://www.belastingdienst.nl/wps/wcm/connect/nl/btw/content/btw-tarief-702",
            "authority_name": "Belastingdienst",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["NL-NH-AMS"].id,
            "tax_category_id": categories["tourism_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.125,
            "currency_code": "EUR",
            "effective_start": date(2025, 1, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Verordening toeristenbelasting 2025 — Amsterdam tourist tax increased to 12.5%",
            "source_url": "https://www.amsterdam.nl/en/municipal-taxes/tourist-tax/",
            "authority_name": "Gemeente Amsterdam",
            "status": "active",
            "created_by": "seed",
        },
    ]

    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


# ──────────────────────────────────────────────────────────────────────
# Tokyo Tax Rates
# Source: National Tax Agency, Tokyo Metropolitan Government
#
# Tokyo (2024-2025):
#   Japan Consumption Tax: 10%
#   Tokyo Accommodation Tax (tiered by nightly rate):
#     Under ¥10,000:     exempt
#     ¥10,000 - ¥14,999: ¥100/night
#     ¥15,000+:          ¥200/night
# ──────────────────────────────────────────────────────────────────────

async def seed_tokyo_rates(db, jurisdictions, categories) -> list[TaxRate]:
    rates = []
    effective = date(2024, 1, 1)

    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["JP"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.10,
            "currency_code": "JPY",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Consumption Tax Act (消費税法) — 10% standard rate",
            "authority_name": "National Tax Agency (国税庁)",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["JP-13-TYO"].id,
            "tax_category_id": categories["tier_price"].id,
            "rate_type": "tiered",
            "rate_value": None,
            "currency_code": "JPY",
            "tiers": [
                {"min": 0, "max": 10000, "value": 0},
                {"min": 10000, "max": 15000, "value": 100},
                {"min": 15000, "value": 200},
            ],
            "tier_type": "single_amount",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Tokyo Metropolitan Hotel Tax Ordinance (東京都宿泊税条例)",
            "source_url": "https://www.tax.metro.tokyo.lg.jp/english/hotel_tax.html",
            "authority_name": "Tokyo Metropolitan Government (東京都)",
            "status": "active",
            "created_by": "seed",
        },
    ]

    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


# ──────────────────────────────────────────────────────────────────────
# Paris Tax Rates
# Source: Service-Public.fr, Mairie de Paris
#
# Paris (2024):
#   France VAT on accommodation: 10% (taux intermédiaire)
#   Paris taxe de séjour: tiered by star rating
#     Palace:    €15.00/person/night
#     5-star:    €5.00/person/night
#     4-star:    €3.75/person/night
#     3-star:    €2.88/person/night
#     2-star:    €1.88/person/night
#     1-star:    €1.13/person/night
#     Unranked:  €1.00/person/night
#   + 10% departmental surtax on top of taxe de séjour
# ──────────────────────────────────────────────────────────────────────

async def seed_paris_rates(db, jurisdictions, categories) -> list[TaxRate]:
    rates = []

    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["FR"].id,
            "tax_category_id": categories["vat_reduced"].id,
            "rate_type": "percentage",
            "rate_value": 0.10,
            "currency_code": "EUR",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Code général des impôts, Article 279 — TVA taux intermédiaire 10% for accommodation",
            "authority_name": "Direction générale des Finances publiques",
            "status": "active",
            "created_by": "seed",
        },
        # Simplified: using 4-star rate as the default flat rate for demo
        # Production: this would be a tiered rule by star_rating
        {
            "jurisdiction_id": jurisdictions["FR-IDF-PAR"].id,
            "tax_category_id": categories["tourism_flat_person_night"].id,
            "rate_type": "tiered",
            "rate_value": None,
            "currency_code": "EUR",
            "tiers": [
                {"min": 0, "max": 2, "value": 1.00},   # unranked/1-star
                {"min": 2, "max": 3, "value": 1.88},    # 2-star
                {"min": 3, "max": 4, "value": 2.88},    # 3-star
                {"min": 4, "max": 5, "value": 3.75},    # 4-star
                {"min": 5, "value": 5.00},               # 5-star
            ],
            "tier_type": "single_amount",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Code du tourisme, Article L422-3 — Taxe de séjour (tiered by star rating)",
            "source_url": "https://www.service-public.fr/professionnels-entreprises/vosdroits/F31635",
            "authority_name": "Mairie de Paris",
            "status": "active",
            "created_by": "seed",
        },
    ]

    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


# ──────────────────────────────────────────────────────────────────────
# Dubai Tax Rates
# Source: UAE Federal Tax Authority
#
# Dubai (2024):
#   UAE VAT: 5%
#   Tourism Dirham Fee: AED 7-20/room/night (varies by star rating)
#   Municipality Fee: 7% of room rate
#   Service Charge: 10% (typically included in rate, not a tax)
# ──────────────────────────────────────────────────────────────────────

async def seed_dubai_rates(db, jurisdictions, categories) -> list[TaxRate]:
    rates = []
    effective = date(2024, 1, 1)

    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["AE"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.05,
            "currency_code": "AED",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "UAE Federal Decree-Law No. 8 of 2017 — VAT at 5%",
            "authority_name": "UAE Federal Tax Authority",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["AE-DU"].id,
            "tax_category_id": categories["municipal_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.07,
            "currency_code": "AED",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Dubai Municipality Fee — 7% of room rate",
            "authority_name": "Dubai Municipality",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["AE-DU"].id,
            "tax_category_id": categories["tourism_flat_night"].id,
            "rate_type": "tiered",
            "rate_value": None,
            "currency_code": "AED",
            "tiers": [
                {"min": 0, "max": 2, "value": 7},   # 1-star
                {"min": 2, "max": 3, "value": 10},   # 2-star
                {"min": 3, "max": 4, "value": 10},   # 3-star
                {"min": 4, "max": 5, "value": 15},   # 4-star
                {"min": 5, "value": 20},              # 5-star
            ],
            "tier_type": "single_amount",
            "effective_start": effective,
            "calculation_order": 30,
            "base_includes": ["base_amount"],
            "legal_reference": "DTCM Tourism Dirham — per room per night fee by hotel classification",
            "source_url": "https://www.dubaitourism.gov.ae/en/tourism-dirham",
            "authority_name": "Dubai Department of Tourism and Commerce Marketing",
            "status": "active",
            "created_by": "seed",
        },
    ]

    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


# ──────────────────────────────────────────────────────────────────────
# Rome Tax Rates
# Source: Comune di Roma
#
# Rome (2024):
#   Italy VAT on accommodation: 10% (aliquota ridotta)
#   Rome Contributo di Soggiorno (city tax): per person per night
#     1-star: €4.00    2-star: €5.00    3-star: €6.00
#     4-star: €7.50    5-star: €10.00
#   Max 10 consecutive nights
# ──────────────────────────────────────────────────────────────────────

async def seed_rome_rates(db, jurisdictions, categories) -> list[TaxRate]:
    rates = []
    effective = date(2024, 1, 1)

    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["IT"].id,
            "tax_category_id": categories["vat_reduced"].id,
            "rate_type": "percentage",
            "rate_value": 0.10,
            "currency_code": "EUR",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "DPR 633/1972, Table A, Part III — IVA aliquota ridotta 10% for accommodation",
            "authority_name": "Agenzia delle Entrate",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["IT-RM-ROM"].id,
            "tax_category_id": categories["tourism_flat_person_night"].id,
            "rate_type": "tiered",
            "rate_value": None,
            "currency_code": "EUR",
            "tiers": [
                {"min": 0, "max": 2, "value": 4.00},   # 1-star
                {"min": 2, "max": 3, "value": 5.00},    # 2-star
                {"min": 3, "max": 4, "value": 6.00},    # 3-star
                {"min": 4, "max": 5, "value": 7.50},    # 4-star
                {"min": 5, "value": 10.00},              # 5-star
            ],
            "tier_type": "single_amount",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Deliberazione dell'Assemblea Capitolina n. 36/2023 — Contributo di Soggiorno",
            "source_url": "https://www.comune.roma.it/web/it/informazione-di-servizio.page?contentId=IDS879556",
            "authority_name": "Comune di Roma",
            "status": "active",
            "created_by": "seed",
        },
    ]

    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_rome_rules(db, rates, jurisdictions) -> list[TaxRule]:
    """Rome: city tax capped at 10 consecutive nights."""
    rules = []

    rome_tourism_rate = None
    for r in rates:
        cat_result = await db.execute(
            select(TaxCategory).where(TaxCategory.id == r.tax_category_id)
        )
        cat = cat_result.scalar_one_or_none()
        if cat and cat.code == "tourism_flat_person_night" and r.jurisdiction_id == jurisdictions["IT-RM-ROM"].id:
            rome_tourism_rate = r
            break

    if rome_tourism_rate:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": rome_tourism_rate.id,
            "jurisdiction_id": jurisdictions["IT-RM-ROM"].id,
            "rule_type": "cap",
            "priority": 50,
            "name": "Rome City Tax 10-Night Cap",
            "description": "Rome's Contributo di Soggiorno is charged for a maximum of 10 consecutive nights. "
                           "Nights beyond 10 are exempt from the city tax.",
            "conditions": {},
            "action": {"max_nights": 10},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "Deliberazione dell'Assemblea Capitolina n. 36/2023 — cap at 10 nights",
            "authority_name": "Comune di Roma",
            "status": "active",
            "created_by": "seed",
        }))

    return rules


# ──────────────────────────────────────────────────────────────────────
# Berlin Tax Rates
# Source: Senatsverwaltung für Finanzen Berlin
#
# Berlin (2024):
#   Germany VAT on accommodation: 7% (reduced rate, ermäßigter Satz)
#   Berlin City Tax (Übernachtungsteuer): 5% of net room rate
#     Exemption: business travel (with employer confirmation)
# ──────────────────────────────────────────────────────────────────────

async def seed_berlin_rates(db, jurisdictions, categories) -> list[TaxRate]:
    rates = []
    effective = date(2024, 1, 1)

    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["DE"].id,
            "tax_category_id": categories["vat_reduced"].id,
            "rate_type": "percentage",
            "rate_value": 0.07,
            "currency_code": "EUR",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "UStG §12 Abs. 2 Nr. 11 — ermäßigter Steuersatz 7% for short-term accommodation",
            "authority_name": "Bundesministerium der Finanzen",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["DE-BE-BER"].id,
            "tax_category_id": categories["tourism_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.05,
            "currency_code": "EUR",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Übernachtungsteuergesetz (ÜnStG) Berlin — City Tax 5% of net room rate",
            "source_url": "https://www.berlin.de/sen/finanzen/steuern/informationen-fuer-steuerzahler-/city-tax/",
            "authority_name": "Senatsverwaltung für Finanzen Berlin",
            "status": "active",
            "created_by": "seed",
        },
    ]

    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_berlin_rules(db, rates, jurisdictions) -> list[TaxRule]:
    """Berlin: business travel exempt from city tax."""
    rules = []

    berlin_city_tax = None
    for r in rates:
        cat_result = await db.execute(
            select(TaxCategory).where(TaxCategory.id == r.tax_category_id)
        )
        cat = cat_result.scalar_one_or_none()
        if cat and cat.code == "tourism_pct" and r.jurisdiction_id == jurisdictions["DE-BE-BER"].id:
            berlin_city_tax = r
            break

    if berlin_city_tax:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": berlin_city_tax.id,
            "jurisdiction_id": jurisdictions["DE-BE-BER"].id,
            "rule_type": "exemption",
            "priority": 100,
            "name": "Berlin City Tax Business Travel Exemption",
            "description": "Business travelers are exempt from Berlin's Übernachtungsteuer. "
                           "Guest must provide employer confirmation.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "guest_type", "op": "==", "value": "business"}],
            },
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "ÜnStG Berlin §1 Abs. 1 — exemption for compulsory professional stays",
            "authority_name": "Senatsverwaltung für Finanzen Berlin",
            "status": "active",
            "created_by": "seed",
        }))

    return rules


# ──────────────────────────────────────────────────────────────────────
# Balearic Islands (Mallorca, Ibiza, Menorca)
# Source: Govern de les Illes Balears
#
# ITS - Impost de Turisme Sostenible (Sustainable Tourism Tax):
#   May-Oct (high season): €1-4/person/night by category
#   Nov-Apr (low season): 50% of high season rate
#   Stays > 8 nights: 50% discount from night 9 onward
# ──────────────────────────────────────────────────────────────────────

async def seed_balearic_rates(db, jurisdictions, categories) -> list[TaxRate]:
    rates = []

    rate_defs = [
        # Spain VAT on accommodation (IVA) — 10%
        {
            "jurisdiction_id": jurisdictions["ES"].id,
            "tax_category_id": categories["vat_reduced"].id,
            "rate_type": "percentage",
            "rate_value": 0.10,
            "currency_code": "EUR",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Ley 37/1992 del IVA, Art. 91 — tipo reducido 10% for accommodation",
            "authority_name": "Agencia Tributaria",
            "status": "active",
            "created_by": "seed",
        },
        # Balearic ITS — simplified as flat per person per night (4-star high season rate)
        {
            "jurisdiction_id": jurisdictions["ES-IB"].id,
            "tax_category_id": categories["eco_flat_person_night"].id,
            "rate_type": "flat",
            "rate_value": 4.00,
            "currency_code": "EUR",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Llei 2/2016 de l'Impost sobre Estades Turístiques — ITS Balearic sustainable tourism tax",
            "source_url": "https://www.caib.es/sites/impostturistic/",
            "authority_name": "Govern de les Illes Balears",
            "status": "active",
            "created_by": "seed",
        },
    ]

    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


# ──────────────────────────────────────────────────────────────────────
# Main seed runner
# ──────────────────────────────────────────────────────────────────────

async def seed_monitoring_sources(db: AsyncSession, jurisdictions: dict[str, Jurisdiction]):
    """Seed monitored source domains for key jurisdictions.

    We store government/authority domains (not full URLs) because the AI agent
    uses web search to find the right pages within these domains.
    """
    source_defs = [
        ("US-NY-NYC", "nyc.gov", "government_website", "en"),
        ("US-NY-NYC", "tax.ny.gov", "tax_authority", "en"),
        ("US-IL-CHI", "chicago.gov", "government_website", "en"),
        ("NL-NH-AMS", "amsterdam.nl", "government_website", "en"),
        ("JP-13-TYO", "tax.metro.tokyo.lg.jp", "government_website", "en"),
        ("FR-IDF-PAR", "paris.fr", "government_website", "fr"),
        ("AE-DU", "dubaitourism.gov.ae", "regulatory_body", "en"),
        ("IT-RM", "comune.roma.it", "government_website", "it"),
        ("DE-BE", "berlin.de", "government_website", "de"),
        ("ES-PM", "caib.es", "government_website", "en"),
    ]
    sources = []
    for code, url, source_type, language in source_defs:
        if code not in jurisdictions:
            continue
        existing = await db.execute(select(MonitoredSource).where(MonitoredSource.url == url))
        if existing.scalar_one_or_none():
            continue
        source = MonitoredSource(
            jurisdiction_id=jurisdictions[code].id,
            url=url,
            source_type=source_type,
            language=language,
            check_frequency_days=7,
            status="active",
            created_by="system",
        )
        db.add(source)
        sources.append(source)
    await db.flush()
    return sources


async def seed_monitoring_schedules(db: AsyncSession, jurisdictions: dict[str, Jurisdiction]):
    """Seed disabled monitoring schedules for all jurisdictions.

    Creates one MonitoringSchedule per jurisdiction, all disabled by default.
    Users can enable them in the UI.
    """
    schedules = []
    for code, j in jurisdictions.items():
        existing = await db.execute(
            select(MonitoringSchedule).where(MonitoringSchedule.jurisdiction_id == j.id)
        )
        if existing.scalar_one_or_none():
            continue
        schedule = MonitoringSchedule(
            jurisdiction_id=j.id,
            enabled=False,
            cadence="weekly",
        )
        db.add(schedule)
        schedules.append(schedule)
    await db.flush()
    return schedules


async def seed_all(db: AsyncSession):
    print("Seeding tax categories...")
    categories = await seed_tax_categories(db)
    print(f"  {len(categories)} categories")

    print("Seeding property classifications...")
    classifications = await seed_property_classifications(db)
    print(f"  {len(classifications)} classifications")

    print("Seeding jurisdictions...")
    jurisdictions = await seed_jurisdictions(db)
    print(f"  {len(jurisdictions)} jurisdictions")

    print("\nSeeding tax rates and rules:")

    print("  NYC...")
    nyc_rates = await seed_nyc_rates(db, jurisdictions, categories)
    nyc_rules = await seed_nyc_rules(db, nyc_rates, jurisdictions)
    print(f"    {len(nyc_rates)} rates, {len(nyc_rules)} rules")

    print("  Chicago...")
    chi_rates = await seed_chicago_rates(db, jurisdictions, categories)
    print(f"    {len(chi_rates)} rates")

    print("  Amsterdam...")
    ams_rates = await seed_amsterdam_rates(db, jurisdictions, categories)
    print(f"    {len(ams_rates)} rates")

    print("  Tokyo...")
    tyo_rates = await seed_tokyo_rates(db, jurisdictions, categories)
    print(f"    {len(tyo_rates)} rates")

    print("  Paris...")
    par_rates = await seed_paris_rates(db, jurisdictions, categories)
    print(f"    {len(par_rates)} rates")

    print("  Dubai...")
    dxb_rates = await seed_dubai_rates(db, jurisdictions, categories)
    print(f"    {len(dxb_rates)} rates")

    print("  Rome...")
    rom_rates = await seed_rome_rates(db, jurisdictions, categories)
    rom_rules = await seed_rome_rules(db, rom_rates, jurisdictions)
    print(f"    {len(rom_rates)} rates, {len(rom_rules)} rules")

    print("  Berlin...")
    ber_rates = await seed_berlin_rates(db, jurisdictions, categories)
    ber_rules = await seed_berlin_rules(db, ber_rates, jurisdictions)
    print(f"    {len(ber_rates)} rates, {len(ber_rules)} rules")

    print("  Balearic Islands...")
    bal_rates = await seed_balearic_rates(db, jurisdictions, categories)
    print(f"    {len(bal_rates)} rates")

    print("\nSeeding monitoring infrastructure:")

    print("  Monitored sources...")
    sources = await seed_monitoring_sources(db, jurisdictions)
    print(f"    {len(sources)} sources")

    print("  Monitoring schedules...")
    schedules = await seed_monitoring_schedules(db, jurisdictions)
    print(f"    {len(schedules)} schedules (all disabled)")

    await db.commit()

    total_rates = sum(len(r) for r in [nyc_rates, chi_rates, ams_rates, tyo_rates, par_rates, dxb_rates, rom_rates, ber_rates, bal_rates])
    total_rules = sum(len(r) for r in [nyc_rules, rom_rules, ber_rules])
    print(f"\nDone! {len(jurisdictions)} jurisdictions, {total_rates} rates, {total_rules} rules, {len(sources)} sources, {len(schedules)} schedules seeded.")


async def main():
    async with async_session_factory() as db:
        await seed_all(db)


if __name__ == "__main__":
    asyncio.run(main())
