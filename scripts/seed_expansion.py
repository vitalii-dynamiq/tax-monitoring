"""
Seed expansion: Add missing sub-jurisdictions for comprehensive OTA tax coverage.

Adds 30 new sub-jurisdictions across 12 countries where accommodation taxes
differ from what's already seeded.

Must be run AFTER all previous seed scripts and seed_fix_production.py.

Usage:
    cd tax-monitoring
    .venv/bin/python -m scripts.seed_expansion
"""

import asyncio
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.jurisdiction import Jurisdiction
from app.models.tax_category import TaxCategory
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule


# ──────────────────────────────────────────────────────────────────────
# Helpers (same pattern as seed_enhancement_v3.py)
# ──────────────────────────────────────────────────────────────────────

async def _get_or_create(db: AsyncSession, model, unique_field: str, data: dict):
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


async def _create_rate_if_not_exists(db: AsyncSession, rate_data: dict) -> TaxRate:
    result = await db.execute(
        select(TaxRate).where(
            TaxRate.jurisdiction_id == rate_data["jurisdiction_id"],
            TaxRate.tax_category_id == rate_data["tax_category_id"],
            TaxRate.status == rate_data.get("status", "active"),
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
# New Jurisdictions
# ──────────────────────────────────────────────────────────────────────

NEW_JURISDICTIONS = [
    # ── UAE: Abu Dhabi, Sharjah, Ras Al Khaimah ──
    {"code": "AE-AZ", "name": "Abu Dhabi", "local_name": "أبو ظبي", "jurisdiction_type": "state", "path": "AE.AZ", "parent_code": "AE", "country_code": "AE", "timezone": "Asia/Dubai", "currency_code": "AED"},
    {"code": "AE-AZ-AUH", "name": "Abu Dhabi City", "local_name": "مدينة أبو ظبي", "jurisdiction_type": "city", "path": "AE.AZ.AUH", "parent_code": "AE-AZ", "country_code": "AE", "timezone": "Asia/Dubai", "currency_code": "AED"},
    {"code": "AE-SH", "name": "Sharjah", "local_name": "الشارقة", "jurisdiction_type": "state", "path": "AE.SH", "parent_code": "AE", "country_code": "AE", "timezone": "Asia/Dubai", "currency_code": "AED"},
    {"code": "AE-SH-SHJ", "name": "Sharjah City", "local_name": "مدينة الشارقة", "jurisdiction_type": "city", "path": "AE.SH.SHJ", "parent_code": "AE-SH", "country_code": "AE", "timezone": "Asia/Dubai", "currency_code": "AED"},
    {"code": "AE-RK", "name": "Ras Al Khaimah", "local_name": "رأس الخيمة", "jurisdiction_type": "state", "path": "AE.RK", "parent_code": "AE", "country_code": "AE", "timezone": "Asia/Dubai", "currency_code": "AED"},
    {"code": "AE-RK-RAK", "name": "Ras Al Khaimah City", "local_name": "مدينة رأس الخيمة", "jurisdiction_type": "city", "path": "AE.RK.RAK", "parent_code": "AE-RK", "country_code": "AE", "timezone": "Asia/Dubai", "currency_code": "AED"},

    # ── Japan: Osaka, Fukuoka (Tokyo, Kyoto, Beppu already seeded) ──
    {"code": "JP-27", "name": "Osaka Prefecture", "local_name": "大阪府", "jurisdiction_type": "state", "path": "JP.27", "parent_code": "JP", "country_code": "JP", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-27-OSA", "name": "Osaka", "local_name": "大阪市", "jurisdiction_type": "city", "path": "JP.27.OSA", "parent_code": "JP-27", "country_code": "JP", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-40", "name": "Fukuoka Prefecture", "local_name": "福岡県", "jurisdiction_type": "state", "path": "JP.40", "parent_code": "JP", "country_code": "JP", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-40-FUK", "name": "Fukuoka", "local_name": "福岡市", "jurisdiction_type": "city", "path": "JP.40.FUK", "parent_code": "JP-40", "country_code": "JP", "timezone": "Asia/Tokyo", "currency_code": "JPY"},

    # ── France: Nice, Lyon, Marseille, Bordeaux ──
    {"code": "FR-PAC", "name": "Provence-Alpes-Côte d'Azur", "jurisdiction_type": "region", "path": "FR.PAC", "parent_code": "FR", "country_code": "FR", "timezone": "Europe/Paris", "currency_code": "EUR"},
    {"code": "FR-PAC-NCE", "name": "Nice", "jurisdiction_type": "city", "path": "FR.PAC.NCE", "parent_code": "FR-PAC", "country_code": "FR", "timezone": "Europe/Paris", "currency_code": "EUR"},
    {"code": "FR-ARA", "name": "Auvergne-Rhône-Alpes", "jurisdiction_type": "region", "path": "FR.ARA", "parent_code": "FR", "country_code": "FR", "timezone": "Europe/Paris", "currency_code": "EUR"},
    {"code": "FR-ARA-LYS", "name": "Lyon", "jurisdiction_type": "city", "path": "FR.ARA.LYS", "parent_code": "FR-ARA", "country_code": "FR", "timezone": "Europe/Paris", "currency_code": "EUR"},
    {"code": "FR-PAC-MRS", "name": "Marseille", "jurisdiction_type": "city", "path": "FR.PAC.MRS", "parent_code": "FR-PAC", "country_code": "FR", "timezone": "Europe/Paris", "currency_code": "EUR"},
    {"code": "FR-NAQ", "name": "Nouvelle-Aquitaine", "jurisdiction_type": "region", "path": "FR.NAQ", "parent_code": "FR", "country_code": "FR", "timezone": "Europe/Paris", "currency_code": "EUR"},
    {"code": "FR-NAQ-BOD", "name": "Bordeaux", "jurisdiction_type": "city", "path": "FR.NAQ.BOD", "parent_code": "FR-NAQ", "country_code": "FR", "timezone": "Europe/Paris", "currency_code": "EUR"},

    # ── Germany: Hamburg, Frankfurt, Cologne ──
    {"code": "DE-HH", "name": "Hamburg", "jurisdiction_type": "state", "path": "DE.HH", "parent_code": "DE", "country_code": "DE", "timezone": "Europe/Berlin", "currency_code": "EUR"},
    {"code": "DE-HH-HAM", "name": "Hamburg City", "jurisdiction_type": "city", "path": "DE.HH.HAM", "parent_code": "DE-HH", "country_code": "DE", "timezone": "Europe/Berlin", "currency_code": "EUR"},
    {"code": "DE-HE", "name": "Hesse", "jurisdiction_type": "state", "path": "DE.HE", "parent_code": "DE", "country_code": "DE", "timezone": "Europe/Berlin", "currency_code": "EUR"},
    {"code": "DE-HE-FRA", "name": "Frankfurt", "jurisdiction_type": "city", "path": "DE.HE.FRA", "parent_code": "DE-HE", "country_code": "DE", "timezone": "Europe/Berlin", "currency_code": "EUR"},
    {"code": "DE-NW", "name": "North Rhine-Westphalia", "local_name": "Nordrhein-Westfalen", "jurisdiction_type": "state", "path": "DE.NW", "parent_code": "DE", "country_code": "DE", "timezone": "Europe/Berlin", "currency_code": "EUR"},
    {"code": "DE-NW-CGN", "name": "Cologne", "local_name": "Köln", "jurisdiction_type": "city", "path": "DE.NW.CGN", "parent_code": "DE-NW", "country_code": "DE", "timezone": "Europe/Berlin", "currency_code": "EUR"},

    # ── Italy: Venice, Naples, Bologna, Turin ──
    {"code": "IT-VE", "name": "Venice Metropolitan Area", "local_name": "Città metropolitana di Venezia", "jurisdiction_type": "state", "path": "IT.VE", "parent_code": "IT", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-VE-VCE", "name": "Venice", "local_name": "Venezia", "jurisdiction_type": "city", "path": "IT.VE.VCE", "parent_code": "IT-VE", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-NA", "name": "Naples Metropolitan Area", "local_name": "Città metropolitana di Napoli", "jurisdiction_type": "state", "path": "IT.NA", "parent_code": "IT", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-NA-NAP", "name": "Naples", "local_name": "Napoli", "jurisdiction_type": "city", "path": "IT.NA.NAP", "parent_code": "IT-NA", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-BO", "name": "Bologna Metropolitan Area", "local_name": "Città metropolitana di Bologna", "jurisdiction_type": "state", "path": "IT.BO", "parent_code": "IT", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-BO-BLQ", "name": "Bologna", "jurisdiction_type": "city", "path": "IT.BO.BLQ", "parent_code": "IT-BO", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-TO", "name": "Turin Metropolitan Area", "local_name": "Città metropolitana di Torino", "jurisdiction_type": "state", "path": "IT.TO", "parent_code": "IT", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-TO-TRN", "name": "Turin", "local_name": "Torino", "jurisdiction_type": "city", "path": "IT.TO.TRN", "parent_code": "IT-TO", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},

    # ── USA: Orlando, Seattle, Phoenix (Miami/Houston/Honolulu already exist) ──
    {"code": "US-FL-ORL", "name": "Orlando (Orange County)", "jurisdiction_type": "city", "path": "US.FL.ORL", "parent_code": "US-FL", "country_code": "US", "timezone": "America/New_York", "currency_code": "USD"},
    {"code": "US-WA", "name": "Washington", "jurisdiction_type": "state", "path": "US.WA", "parent_code": "US", "country_code": "US", "timezone": "America/Los_Angeles", "currency_code": "USD"},
    {"code": "US-WA-SEA", "name": "Seattle", "jurisdiction_type": "city", "path": "US.WA.SEA", "parent_code": "US-WA", "country_code": "US", "timezone": "America/Los_Angeles", "currency_code": "USD"},
    {"code": "US-AZ", "name": "Arizona", "jurisdiction_type": "state", "path": "US.AZ", "parent_code": "US", "country_code": "US", "timezone": "America/Phoenix", "currency_code": "USD"},
    {"code": "US-AZ-PHX", "name": "Phoenix", "jurisdiction_type": "city", "path": "US.AZ.PHX", "parent_code": "US-AZ", "country_code": "US", "timezone": "America/Phoenix", "currency_code": "USD"},

    # ── Switzerland: Geneva, Lucerne, Zermatt ──
    {"code": "CH-GE", "name": "Canton of Geneva", "local_name": "Canton de Genève", "jurisdiction_type": "state", "path": "CH.GE", "parent_code": "CH", "country_code": "CH", "timezone": "Europe/Zurich", "currency_code": "CHF"},
    {"code": "CH-GE-GVA", "name": "Geneva", "local_name": "Genève", "jurisdiction_type": "city", "path": "CH.GE.GVA", "parent_code": "CH-GE", "country_code": "CH", "timezone": "Europe/Zurich", "currency_code": "CHF"},
    {"code": "CH-LU", "name": "Canton of Lucerne", "local_name": "Kanton Luzern", "jurisdiction_type": "state", "path": "CH.LU", "parent_code": "CH", "country_code": "CH", "timezone": "Europe/Zurich", "currency_code": "CHF"},
    {"code": "CH-LU-LUZ", "name": "Lucerne", "local_name": "Luzern", "jurisdiction_type": "city", "path": "CH.LU.LUZ", "parent_code": "CH-LU", "country_code": "CH", "timezone": "Europe/Zurich", "currency_code": "CHF"},
    {"code": "CH-VS", "name": "Canton of Valais", "local_name": "Kanton Wallis", "jurisdiction_type": "state", "path": "CH.VS", "parent_code": "CH", "country_code": "CH", "timezone": "Europe/Zurich", "currency_code": "CHF"},
    {"code": "CH-VS-ZMT", "name": "Zermatt", "jurisdiction_type": "city", "path": "CH.VS.ZMT", "parent_code": "CH-VS", "country_code": "CH", "timezone": "Europe/Zurich", "currency_code": "CHF"},

    # ── Croatia: Zagreb, Zadar, Hvar ──
    {"code": "HR-01", "name": "Zagreb County", "local_name": "Grad Zagreb", "jurisdiction_type": "state", "path": "HR.01", "parent_code": "HR", "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},
    {"code": "HR-01-ZAG", "name": "Zagreb", "jurisdiction_type": "city", "path": "HR.01.ZAG", "parent_code": "HR-01", "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},
    {"code": "HR-13", "name": "Zadar County", "local_name": "Zadarska županija", "jurisdiction_type": "state", "path": "HR.13", "parent_code": "HR", "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},
    {"code": "HR-13-ZAD", "name": "Zadar", "jurisdiction_type": "city", "path": "HR.13.ZAD", "parent_code": "HR-13", "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},
    {"code": "HR-17", "name": "Split-Dalmatia County", "jurisdiction_type": "state", "path": "HR.17", "parent_code": "HR", "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},
    {"code": "HR-17-HVR", "name": "Hvar", "jurisdiction_type": "city", "path": "HR.17.HVR", "parent_code": "HR-17", "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},

    # ── Malaysia: Penang, Langkawi ──
    {"code": "MY-07", "name": "Penang", "local_name": "Pulau Pinang", "jurisdiction_type": "state", "path": "MY.07", "parent_code": "MY", "country_code": "MY", "timezone": "Asia/Kuala_Lumpur", "currency_code": "MYR"},
    {"code": "MY-07-PEN", "name": "Penang City", "local_name": "George Town", "jurisdiction_type": "city", "path": "MY.07.PEN", "parent_code": "MY-07", "country_code": "MY", "timezone": "Asia/Kuala_Lumpur", "currency_code": "MYR"},
    {"code": "MY-02", "name": "Kedah", "jurisdiction_type": "state", "path": "MY.02", "parent_code": "MY", "country_code": "MY", "timezone": "Asia/Kuala_Lumpur", "currency_code": "MYR"},
    {"code": "MY-02-LGK", "name": "Langkawi", "jurisdiction_type": "city", "path": "MY.02.LGK", "parent_code": "MY-02", "country_code": "MY", "timezone": "Asia/Kuala_Lumpur", "currency_code": "MYR"},

    # ── Mexico: Puerto Vallarta (Mexico City already exists) ──
    {"code": "MX-JAL", "name": "Jalisco", "jurisdiction_type": "state", "path": "MX.JAL", "parent_code": "MX", "country_code": "MX", "timezone": "America/Mexico_City", "currency_code": "MXN"},
    {"code": "MX-JAL-PVR", "name": "Puerto Vallarta", "jurisdiction_type": "city", "path": "MX.JAL.PVR", "parent_code": "MX-JAL", "country_code": "MX", "timezone": "America/Mexico_City", "currency_code": "MXN"},

    # ── Brazil: Rio de Janeiro ──
    {"code": "BR-RJ", "name": "Rio de Janeiro State", "local_name": "Estado do Rio de Janeiro", "jurisdiction_type": "state", "path": "BR.RJ", "parent_code": "BR", "country_code": "BR", "timezone": "America/Sao_Paulo", "currency_code": "BRL"},
    {"code": "BR-RJ-RIO", "name": "Rio de Janeiro", "jurisdiction_type": "city", "path": "BR.RJ.RIO", "parent_code": "BR-RJ", "country_code": "BR", "timezone": "America/Sao_Paulo", "currency_code": "BRL"},

    # ── UK: Manchester ──
    {"code": "GB-ENG-MAN", "name": "Manchester", "jurisdiction_type": "city", "path": "GB.ENG.MAN", "parent_code": "GB-ENG", "country_code": "GB", "timezone": "Europe/London", "currency_code": "GBP"},
]


# ──────────────────────────────────────────────────────────────────────
# Seed Jurisdictions
# ──────────────────────────────────────────────────────────────────────

async def seed_jurisdictions(db: AsyncSession) -> dict[str, Jurisdiction]:
    jurisdictions = {}
    result = await db.execute(select(Jurisdiction))
    for j in result.scalars().all():
        jurisdictions[j.code] = j

    for j_data in NEW_JURISDICTIONS:
        j_data = dict(j_data)
        parent_code = j_data.pop("parent_code", None)
        if parent_code and parent_code in jurisdictions:
            j_data["parent_id"] = jurisdictions[parent_code].id
        j = await _get_or_create(db, Jurisdiction, "code", j_data)
        jurisdictions[j.code] = j

    return jurisdictions


# ──────────────────────────────────────────────────────────────────────
# Tax Rates & Rules
# ──────────────────────────────────────────────────────────────────────

async def seed_rates_and_rules(
    db: AsyncSession,
    j: dict[str, Jurisdiction],
    c: dict[str, TaxCategory],
):
    # ── UAE: Abu Dhabi ── 4% Tourism Fee + 4% Municipality Fee
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["AE-AZ-AUH"].id,
        "tax_category_id": c["tourism_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.04,
        "currency_code": "AED",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 10,
        "base_includes": ["base_amount"],
        "legal_reference": "Abu Dhabi Tourism Fee — 4% on room rate",
        "authority_name": "Department of Culture and Tourism Abu Dhabi",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["AE-AZ-AUH"].id,
        "tax_category_id": c["municipal_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.04,
        "currency_code": "AED",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Abu Dhabi Municipality Fee — 4% on room rate",
        "authority_name": "Abu Dhabi Municipality",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Abu Dhabi — 4% tourism fee + 4% municipality fee")

    # ── UAE: Sharjah ── 10% Municipality Fee
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["AE-SH-SHJ"].id,
        "tax_category_id": c["municipal_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.10,
        "currency_code": "AED",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 10,
        "base_includes": ["base_amount"],
        "legal_reference": "Sharjah Municipality Fee — 10% on room rate",
        "authority_name": "Sharjah Municipality",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Sharjah — 10% municipality fee")

    # ── UAE: Ras Al Khaimah ── AED 15/room/night flat
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["AE-RK-RAK"].id,
        "tax_category_id": c["tourism_flat_night"].id,
        "rate_type": "flat",
        "rate_value": 15.0,
        "currency_code": "AED",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 10,
        "base_includes": ["base_amount"],
        "legal_reference": "Ras Al Khaimah Tourism Fee — AED 15 per room per night",
        "authority_name": "RAK Tourism Development Authority",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Ras Al Khaimah — AED 15/room/night")

    # ── Japan: Osaka ── Tiered accommodation tax
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["JP-27-OSA"].id,
        "tax_category_id": c["tier_price"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "JPY",
        "effective_start": date(2017, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "tiers": [
            {"min": 0, "max": 7000, "value": 0},
            {"min": 7000, "max": 15000, "value": 100},
            {"min": 15000, "max": 20000, "value": 200},
            {"min": 20000, "value": 300},
        ],
        "tier_type": "single_amount",
        "legal_reference": "Osaka City Accommodation Tax Ordinance — tiered per night",
        "authority_name": "Osaka City",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Osaka — Tiered accommodation tax (JPY 0/100/200/300)")

    # ── Japan: Fukuoka ── Tiered accommodation tax
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["JP-40-FUK"].id,
        "tax_category_id": c["tier_price"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "JPY",
        "effective_start": date(2020, 4, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "tiers": [
            {"min": 0, "max": 20000, "value": 200},
            {"min": 20000, "value": 500},
        ],
        "tier_type": "single_amount",
        "legal_reference": "Fukuoka City Accommodation Tax Ordinance",
        "authority_name": "Fukuoka City",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Fukuoka — Tiered accommodation tax (JPY 200/500)")

    # ── France: Nice ── Taxe de séjour (star-tiered, per person per night)
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["FR-PAC-NCE"].id,
        "tax_category_id": c["tier_star"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "EUR",
        "effective_start": date(2025, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "tiers": [
            {"min": 1, "max": 2, "value": 0.88},
            {"min": 2, "max": 3, "value": 1.10},
            {"min": 3, "max": 4, "value": 1.65},
            {"min": 4, "max": 5, "value": 2.53},
            {"min": 5, "value": 3.30},
        ],
        "tier_type": "single_amount",
        "legal_reference": "Taxe de séjour Nice — per person per night, star-tiered + 34% departmental surcharge",
        "authority_name": "Métropole Nice Côte d'Azur",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Nice — Taxe de séjour (star-tiered + departmental surcharge)")

    # ── France: Lyon ── Taxe de séjour
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["FR-ARA-LYS"].id,
        "tax_category_id": c["tier_star"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "EUR",
        "effective_start": date(2025, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "tiers": [
            {"min": 1, "max": 2, "value": 0.99},
            {"min": 2, "max": 3, "value": 1.65},
            {"min": 3, "max": 4, "value": 2.53},
            {"min": 4, "max": 5, "value": 3.30},
            {"min": 5, "value": 4.40},
        ],
        "tier_type": "single_amount",
        "legal_reference": "Taxe de séjour Lyon — per person per night, star-tiered",
        "authority_name": "Métropole de Lyon",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Lyon — Taxe de séjour (star-tiered)")

    # ── France: Marseille ── Taxe de séjour
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["FR-PAC-MRS"].id,
        "tax_category_id": c["tier_star"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "EUR",
        "effective_start": date(2025, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "tiers": [
            {"min": 1, "max": 2, "value": 0.88},
            {"min": 2, "max": 3, "value": 1.10},
            {"min": 3, "max": 4, "value": 1.65},
            {"min": 4, "max": 5, "value": 2.53},
            {"min": 5, "value": 3.30},
        ],
        "tier_type": "single_amount",
        "legal_reference": "Taxe de séjour Marseille — per person per night, star-tiered",
        "authority_name": "Métropole Aix-Marseille-Provence",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Marseille — Taxe de séjour (star-tiered)")

    # ── France: Bordeaux ── Taxe de séjour
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["FR-NAQ-BOD"].id,
        "tax_category_id": c["tier_star"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "EUR",
        "effective_start": date(2025, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "tiers": [
            {"min": 1, "max": 2, "value": 0.99},
            {"min": 2, "max": 3, "value": 1.65},
            {"min": 3, "max": 4, "value": 2.53},
            {"min": 4, "max": 5, "value": 3.30},
            {"min": 5, "value": 4.40},
        ],
        "tier_type": "single_amount",
        "legal_reference": "Taxe de séjour Bordeaux — per person per night, star-tiered",
        "authority_name": "Bordeaux Métropole",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Bordeaux — Taxe de séjour (star-tiered)")

    # ── Germany: Hamburg ── Kultur- und Tourismustaxe (culture & tourism tax)
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["DE-HH-HAM"].id,
        "tax_category_id": c["occ_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.05,
        "currency_code": "EUR",
        "effective_start": date(2013, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Hamburgisches Kultur- und Tourismustaxegesetz — 5% on net room rate (private stays)",
        "authority_name": "Freie und Hansestadt Hamburg",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Hamburg — 5% culture & tourism tax")

    # ── Germany: Frankfurt ── EUR 2/night flat
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["DE-HE-FRA"].id,
        "tax_category_id": c["occ_flat_night"].id,
        "rate_type": "flat",
        "rate_value": 2.0,
        "currency_code": "EUR",
        "effective_start": date(2018, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Frankfurter Tourismusabgabe — EUR 2 per person per night",
        "authority_name": "Stadt Frankfurt am Main",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Frankfurt — EUR 2/night tourist tax")

    # ── Germany: Cologne ── 5% Bettensteuer
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["DE-NW-CGN"].id,
        "tax_category_id": c["occ_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.05,
        "currency_code": "EUR",
        "effective_start": date(2014, 10, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Kölner Bettensteuer — 5% on net room rate (private stays)",
        "authority_name": "Stadt Köln",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Cologne — 5% bed tax")

    # ── Italy: Venice ── EUR 1-10 tiered by star rating
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["IT-VE-VCE"].id,
        "tax_category_id": c["tier_star"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "EUR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "tiers": [
            {"min": 1, "max": 2, "value": 1.00},
            {"min": 2, "max": 3, "value": 2.00},
            {"min": 3, "max": 4, "value": 3.00},
            {"min": 4, "max": 5, "value": 4.50},
            {"min": 5, "value": 5.00},
        ],
        "tier_type": "single_amount",
        "legal_reference": "Imposta di soggiorno Venezia — per person per night, 10-night cap",
        "authority_name": "Comune di Venezia",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Venice — EUR 1-5/night tourist tax (tiered by star)")

    # ── Italy: Naples ── EUR 1-5 tiered
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["IT-NA-NAP"].id,
        "tax_category_id": c["tier_star"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "EUR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "tiers": [
            {"min": 1, "max": 2, "value": 1.00},
            {"min": 2, "max": 3, "value": 2.00},
            {"min": 3, "max": 4, "value": 2.50},
            {"min": 4, "max": 5, "value": 3.50},
            {"min": 5, "value": 5.00},
        ],
        "tier_type": "single_amount",
        "legal_reference": "Imposta di soggiorno Napoli — per person per night, 14-night cap",
        "authority_name": "Comune di Napoli",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Naples — EUR 1-5/night tourist tax (tiered by star)")

    # ── Italy: Bologna ── EUR 1.50-7 tiered
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["IT-BO-BLQ"].id,
        "tax_category_id": c["tier_star"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "EUR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "tiers": [
            {"min": 1, "max": 2, "value": 1.50},
            {"min": 2, "max": 3, "value": 2.50},
            {"min": 3, "max": 4, "value": 4.00},
            {"min": 4, "max": 5, "value": 5.50},
            {"min": 5, "value": 7.00},
        ],
        "tier_type": "single_amount",
        "legal_reference": "Imposta di soggiorno Bologna — per person per night",
        "authority_name": "Comune di Bologna",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Bologna — EUR 1.50-7/night tourist tax (tiered by star)")

    # ── Italy: Turin ── EUR 1.30-5 tiered
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["IT-TO-TRN"].id,
        "tax_category_id": c["tier_star"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "EUR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "tiers": [
            {"min": 1, "max": 2, "value": 1.30},
            {"min": 2, "max": 3, "value": 2.30},
            {"min": 3, "max": 4, "value": 3.70},
            {"min": 4, "max": 5, "value": 4.30},
            {"min": 5, "value": 5.00},
        ],
        "tier_type": "single_amount",
        "legal_reference": "Imposta di soggiorno Torino — per person per night",
        "authority_name": "Comune di Torino",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Turin — EUR 1.30-5/night tourist tax (tiered by star)")

    # ── USA: Orlando ── State 6% + County 6% + TDT 0.5% = 12.5%
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["US-FL-ORL"].id,
        "tax_category_id": c["occ_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.065,
        "currency_code": "USD",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Orange County Tourist Development Tax 6% + Convention Development 0.5%",
        "authority_name": "Orange County Tax Collector",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Orlando — 6.5% county transient tax (+ state 6% from FL)")

    # ── USA: Seattle ── City lodging tax 8% (city + convention + TPA)
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["US-WA-SEA"].id,
        "tax_category_id": c["occ_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.0915,
        "currency_code": "USD",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Seattle Lodging Tax — Convention & Trade Center 2.8% + Tourism Promotion 2.75% + Hotel/Motel 3.6%",
        "authority_name": "City of Seattle",
        "status": "active",
        "created_by": "seed",
    })
    # Washington state sales tax
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["US-WA"].id,
        "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage",
        "rate_value": 0.065,
        "currency_code": "USD",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 10,
        "base_includes": ["base_amount"],
        "legal_reference": "Washington State Sales Tax — 6.5% on lodging",
        "authority_name": "Washington State Department of Revenue",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Seattle — 6.5% state + 9.15% local lodging taxes")

    # ── USA: Phoenix ── City TPT lodging 2.3% + state 5.6% + county 1.75%
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["US-AZ"].id,
        "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage",
        "rate_value": 0.056,
        "currency_code": "USD",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 10,
        "base_includes": ["base_amount"],
        "legal_reference": "Arizona Transaction Privilege Tax — 5.6% on transient lodging",
        "authority_name": "Arizona Department of Revenue",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["US-AZ-PHX"].id,
        "tax_category_id": c["occ_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.057,
        "currency_code": "USD",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Phoenix City TPT 2.3% + Maricopa County 1.7% + Transient Lodging Surcharge 1.7%",
        "authority_name": "City of Phoenix",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Phoenix — 5.6% state + 5.7% local taxes")

    # ── Switzerland: Geneva ── CHF 4.25/person/night Kurtaxe
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["CH-GE-GVA"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 4.25,
        "currency_code": "CHF",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Taxe de séjour Genève — CHF 4.25 par personne et par nuit",
        "authority_name": "Canton de Genève",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Geneva — CHF 4.25/person/night")

    # ── Switzerland: Lucerne ── CHF 3.80/person/night
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["CH-LU-LUZ"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 3.80,
        "currency_code": "CHF",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Kurtaxe Luzern — CHF 3.80 pro Person pro Nacht (Hotel)",
        "authority_name": "Stadt Luzern",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Lucerne — CHF 3.80/person/night")

    # ── Switzerland: Zermatt ── CHF 5.50/person/night
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["CH-VS-ZMT"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 5.50,
        "currency_code": "CHF",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Kurtaxe Zermatt — CHF 5.50 pro Person pro Nacht",
        "authority_name": "Gemeinde Zermatt",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Zermatt — CHF 5.50/person/night")

    # ── Croatia: Zagreb ── EUR 1.33/person/night (year-round, lower than coastal)
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["HR-01-ZAG"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 1.33,
        "currency_code": "EUR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Croatian Sojourn Tax — Zagreb EUR 1.33/person/night (year-round)",
        "authority_name": "Croatian Ministry of Tourism",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Zagreb — EUR 1.33/person/night sojourn tax")

    # ── Croatia: Zadar ── EUR 1.86/person/night (peak season)
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["HR-13-ZAD"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 1.86,
        "currency_code": "EUR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Croatian Sojourn Tax — Zadar EUR 1.86/person/night (peak season)",
        "authority_name": "Croatian Ministry of Tourism",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Zadar — EUR 1.86/person/night sojourn tax")

    # ── Croatia: Hvar ── EUR 2.65/person/night (peak season)
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["HR-17-HVR"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 2.65,
        "currency_code": "EUR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Croatian Sojourn Tax — Hvar EUR 2.65/person/night (peak Jul-Aug)",
        "authority_name": "Croatian Ministry of Tourism",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Hvar — EUR 2.65/person/night sojourn tax (peak)")

    # ── Malaysia: Penang ── RM 2/night state heritage levy
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["MY-07-PEN"].id,
        "tax_category_id": c["tourism_flat_night"].id,
        "rate_type": "flat",
        "rate_value": 2.0,
        "currency_code": "MYR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 30,
        "base_includes": ["base_amount"],
        "legal_reference": "Penang State Heritage Charge — RM 2/room/night",
        "authority_name": "Penang State Government",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Penang — RM 2/night heritage charge")

    # ── Mexico: Puerto Vallarta ── 2% ISH lodging tax
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["MX-JAL-PVR"].id,
        "tax_category_id": c["occ_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.03,
        "currency_code": "MXN",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Jalisco Impuesto Sobre Hospedaje (ISH) — 3% on lodging",
        "authority_name": "Gobierno del Estado de Jalisco",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Puerto Vallarta — 3% ISH lodging tax (Jalisco)")

    # ── Brazil: Rio de Janeiro ── ISS 5%
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["BR-RJ-RIO"].id,
        "tax_category_id": c["service_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.05,
        "currency_code": "BRL",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "ISS Rio de Janeiro — 5% on accommodation services",
        "authority_name": "Prefeitura do Rio de Janeiro",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Rio de Janeiro — ISS 5%")

    # ── UK: Manchester ── GBP 1/room/night ABID
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["GB-ENG-MAN"].id,
        "tax_category_id": c["tourism_flat_night"].id,
        "rate_type": "flat",
        "rate_value": 1.0,
        "currency_code": "GBP",
        "effective_start": date(2023, 4, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Manchester Accommodation Business Improvement District (ABID) — GBP 1/room/night",
        "authority_name": "Manchester City Council",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Manchester — GBP 1/room/night ABID levy")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

async def main():
    print("\n=== TaxLens Seed Expansion: 30 New Sub-Jurisdictions ===\n")

    async with async_session_factory() as db:
        # Load tax categories
        result = await db.execute(select(TaxCategory))
        categories = {c.code: c for c in result.scalars().all()}
        print(f"Loaded {len(categories)} tax categories")

        # Seed jurisdictions
        jurisdictions = await seed_jurisdictions(db)
        print(f"Total jurisdictions: {len(jurisdictions)}\n")

        # Seed rates and rules
        await seed_rates_and_rules(db, jurisdictions, categories)

        await db.commit()
        print("\n✅ Seed expansion complete!")
        print("   30 new sub-jurisdictions across 12 countries")


if __name__ == "__main__":
    asyncio.run(main())
