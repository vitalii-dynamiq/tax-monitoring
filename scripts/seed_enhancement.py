"""
Seed data enhancement for TaxLens.

Adds additional jurisdictions, tax rates, rules, monitoring sources,
detected changes, and audit log entries ON TOP of the base seed_data.py.

Must be run AFTER seed_data.py has already seeded the initial data.

Tax rates are sourced from official tax authority publications
and verified against multiple references.

Usage:
    cd tax-monitoring
    .venv/bin/python -m scripts.seed_enhancement
"""

import asyncio
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.audit_log import AuditLog
from app.models.detected_change import DetectedChange
from app.models.jurisdiction import Jurisdiction
from app.models.monitored_source import MonitoredSource
from app.models.tax_category import TaxCategory
from app.models.tax_rate import TaxRate
from app.models.tax_rule import TaxRule


# ──────────────────────────────────────────────────────────────────────
# Helpers (same patterns as seed_data.py)
# ──────────────────────────────────────────────────────────────────────

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


async def _create_source_if_not_exists(db: AsyncSession, source_data: dict) -> MonitoredSource:
    """Create a monitored source only if one doesn't already exist with the same URL."""
    result = await db.execute(
        select(MonitoredSource).where(MonitoredSource.url == source_data["url"])
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    source = MonitoredSource(**source_data)
    db.add(source)
    await db.flush()
    return source


async def _create_change_if_not_exists(db: AsyncSession, change_data: dict) -> DetectedChange:
    """Create a detected change only if a similar one doesn't exist."""
    result = await db.execute(
        select(DetectedChange).where(
            DetectedChange.jurisdiction_id == change_data.get("jurisdiction_id"),
            DetectedChange.change_type == change_data["change_type"],
            DetectedChange.source_quote == change_data.get("source_quote"),
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    change = DetectedChange(**change_data)
    db.add(change)
    await db.flush()
    return change


async def _lookup_jurisdiction(db: AsyncSession, code: str) -> Jurisdiction | None:
    result = await db.execute(select(Jurisdiction).where(Jurisdiction.code == code))
    return result.scalar_one_or_none()


async def _lookup_category(db: AsyncSession, code: str) -> TaxCategory | None:
    result = await db.execute(select(TaxCategory).where(TaxCategory.code == code))
    return result.scalar_one_or_none()


async def _find_rate(db: AsyncSession, jurisdiction_id: int, category_code: str) -> TaxRate | None:
    """Find an active rate by jurisdiction and category code."""
    cat = await db.execute(select(TaxCategory).where(TaxCategory.code == category_code))
    cat_obj = cat.scalar_one_or_none()
    if not cat_obj:
        return None
    result = await db.execute(
        select(TaxRate).where(
            TaxRate.jurisdiction_id == jurisdiction_id,
            TaxRate.tax_category_id == cat_obj.id,
            TaxRate.status == "active",
        )
    )
    return result.scalar_one_or_none()


# ──────────────────────────────────────────────────────────────────────
# 1. NEW JURISDICTIONS
# ──────────────────────────────────────────────────────────────────────

NEW_JURISDICTIONS = [
    # ── United Kingdom ──
    {"code": "GB", "name": "United Kingdom", "jurisdiction_type": "country", "path": "GB", "parent_code": None, "country_code": "GB", "subdivision_code": None, "timezone": "Europe/London", "currency_code": "GBP"},
    {"code": "GB-ENG", "name": "England", "jurisdiction_type": "state", "path": "GB.ENG", "parent_code": "GB", "country_code": "GB", "subdivision_code": "GB-ENG", "timezone": "Europe/London", "currency_code": "GBP"},
    {"code": "GB-ENG-LDN", "name": "London", "jurisdiction_type": "city", "path": "GB.ENG.LDN", "parent_code": "GB-ENG", "country_code": "GB", "subdivision_code": "GB-ENG", "timezone": "Europe/London", "currency_code": "GBP"},

    # ── Portugal ──
    {"code": "PT", "name": "Portugal", "jurisdiction_type": "country", "path": "PT", "parent_code": None, "country_code": "PT", "subdivision_code": None, "timezone": "Europe/Lisbon", "currency_code": "EUR"},
    {"code": "PT-11", "name": "Lisbon District", "jurisdiction_type": "state", "path": "PT.11", "parent_code": "PT", "country_code": "PT", "subdivision_code": "PT-11", "timezone": "Europe/Lisbon", "currency_code": "EUR"},
    {"code": "PT-11-LIS", "name": "Lisbon", "jurisdiction_type": "city", "path": "PT.11.LIS", "parent_code": "PT-11", "country_code": "PT", "subdivision_code": "PT-11", "timezone": "Europe/Lisbon", "currency_code": "EUR"},

    # ── Austria ──
    {"code": "AT", "name": "Austria", "jurisdiction_type": "country", "path": "AT", "parent_code": None, "country_code": "AT", "subdivision_code": None, "timezone": "Europe/Vienna", "currency_code": "EUR"},
    {"code": "AT-9", "name": "Vienna (State)", "jurisdiction_type": "state", "path": "AT.9", "parent_code": "AT", "country_code": "AT", "subdivision_code": "AT-9", "timezone": "Europe/Vienna", "currency_code": "EUR"},
    {"code": "AT-9-VIE", "name": "Vienna", "jurisdiction_type": "city", "path": "AT.9.VIE", "parent_code": "AT-9", "country_code": "AT", "subdivision_code": "AT-9", "timezone": "Europe/Vienna", "currency_code": "EUR"},

    # ── Czech Republic ──
    {"code": "CZ", "name": "Czech Republic", "jurisdiction_type": "country", "path": "CZ", "parent_code": None, "country_code": "CZ", "subdivision_code": None, "timezone": "Europe/Prague", "currency_code": "CZK"},
    {"code": "CZ-PHA", "name": "Prague Region", "jurisdiction_type": "state", "path": "CZ.PHA", "parent_code": "CZ", "country_code": "CZ", "subdivision_code": "CZ-PHA", "timezone": "Europe/Prague", "currency_code": "CZK"},
    {"code": "CZ-PHA-PRG", "name": "Prague", "jurisdiction_type": "city", "path": "CZ.PHA.PRG", "parent_code": "CZ-PHA", "country_code": "CZ", "subdivision_code": "CZ-PHA", "timezone": "Europe/Prague", "currency_code": "CZK"},

    # ── Hungary ──
    {"code": "HU", "name": "Hungary", "jurisdiction_type": "country", "path": "HU", "parent_code": None, "country_code": "HU", "subdivision_code": None, "timezone": "Europe/Budapest", "currency_code": "HUF"},
    {"code": "HU-BU", "name": "Budapest Region", "jurisdiction_type": "state", "path": "HU.BU", "parent_code": "HU", "country_code": "HU", "subdivision_code": "HU-BU", "timezone": "Europe/Budapest", "currency_code": "HUF"},
    {"code": "HU-BU-BUD", "name": "Budapest", "jurisdiction_type": "city", "path": "HU.BU.BUD", "parent_code": "HU-BU", "country_code": "HU", "subdivision_code": "HU-BU", "timezone": "Europe/Budapest", "currency_code": "HUF"},

    # ── Singapore (city-state) ──
    {"code": "SG", "name": "Singapore", "jurisdiction_type": "country", "path": "SG", "parent_code": None, "country_code": "SG", "subdivision_code": None, "timezone": "Asia/Singapore", "currency_code": "SGD"},

    # ── Australia ──
    {"code": "AU", "name": "Australia", "jurisdiction_type": "country", "path": "AU", "parent_code": None, "country_code": "AU", "subdivision_code": None, "timezone": "Australia/Sydney", "currency_code": "AUD"},
    {"code": "AU-NSW", "name": "New South Wales", "jurisdiction_type": "state", "path": "AU.NSW", "parent_code": "AU", "country_code": "AU", "subdivision_code": "AU-NSW", "timezone": "Australia/Sydney", "currency_code": "AUD"},
    {"code": "AU-NSW-SYD", "name": "Sydney", "jurisdiction_type": "city", "path": "AU.NSW.SYD", "parent_code": "AU-NSW", "country_code": "AU", "subdivision_code": "AU-NSW", "timezone": "Australia/Sydney", "currency_code": "AUD"},

    # ── Greece ──
    {"code": "GR", "name": "Greece", "jurisdiction_type": "country", "path": "GR", "parent_code": None, "country_code": "GR", "subdivision_code": None, "timezone": "Europe/Athens", "currency_code": "EUR"},
    {"code": "GR-I", "name": "Attica", "jurisdiction_type": "state", "path": "GR.I", "parent_code": "GR", "country_code": "GR", "subdivision_code": "GR-I", "timezone": "Europe/Athens", "currency_code": "EUR"},
    {"code": "GR-I-ATH", "name": "Athens", "jurisdiction_type": "city", "path": "GR.I.ATH", "parent_code": "GR-I", "country_code": "GR", "subdivision_code": "GR-I", "timezone": "Europe/Athens", "currency_code": "EUR"},

    # ── Maldives ──
    {"code": "MV", "name": "Maldives", "jurisdiction_type": "country", "path": "MV", "parent_code": None, "country_code": "MV", "subdivision_code": None, "timezone": "Indian/Maldives", "currency_code": "USD"},

    # ── Mexico ──
    {"code": "MX", "name": "Mexico", "jurisdiction_type": "country", "path": "MX", "parent_code": None, "country_code": "MX", "subdivision_code": None, "timezone": "America/Mexico_City", "currency_code": "MXN"},
    {"code": "MX-CMX", "name": "Mexico City (State)", "jurisdiction_type": "state", "path": "MX.CMX", "parent_code": "MX", "country_code": "MX", "subdivision_code": "MX-CMX", "timezone": "America/Mexico_City", "currency_code": "MXN"},
    {"code": "MX-CMX-MEX", "name": "Mexico City", "jurisdiction_type": "city", "path": "MX.CMX.MEX", "parent_code": "MX-CMX", "country_code": "MX", "subdivision_code": "MX-CMX", "timezone": "America/Mexico_City", "currency_code": "MXN"},

    # ── Spain — Catalonia / Barcelona ──
    {"code": "ES-CT", "name": "Catalonia", "jurisdiction_type": "state", "path": "ES.CT", "parent_code": "ES", "country_code": "ES", "subdivision_code": "ES-CT", "timezone": "Europe/Madrid", "currency_code": "EUR"},
    {"code": "ES-CT-BCN", "name": "Barcelona", "jurisdiction_type": "city", "path": "ES.CT.BCN", "parent_code": "ES-CT", "country_code": "ES", "subdivision_code": "ES-CT", "timezone": "Europe/Madrid", "currency_code": "EUR"},
]


async def seed_new_jurisdictions(db: AsyncSession) -> dict[str, Jurisdiction]:
    """Seed new jurisdictions, resolving parent references."""
    jurisdictions = {}

    # Pre-load existing jurisdictions so parent lookups work
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
# 2. TAX RATES — new jurisdictions + existing jurisdictions without rates
# ──────────────────────────────────────────────────────────────────────

async def seed_uk_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """UK: 20% VAT standard rate, no specific city hotel tax."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["GB"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.20,
            "currency_code": "GBP",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Value Added Tax Act 1994, Schedule 9 — standard rate 20% on hotel accommodation",
            "legal_uri": "https://www.legislation.gov.uk/ukpga/1994/23/schedule/9",
            "source_url": "https://www.gov.uk/guidance/vat-on-hotel-accommodation",
            "authority_name": "HM Revenue & Customs",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_portugal_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Portugal: 6% VAT reduced on accommodation. Lisbon: EUR 2/person/night tourist tax."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["PT"].id,
            "tax_category_id": categories["vat_reduced"].id,
            "rate_type": "percentage",
            "rate_value": 0.06,
            "currency_code": "EUR",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Codigo do IVA, Art. 18 — taxa reduzida 6% for accommodation services",
            "authority_name": "Autoridade Tributaria e Aduaneira",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["PT-11-LIS"].id,
            "tax_category_id": categories["tourism_flat_person_night"].id,
            "rate_type": "flat",
            "rate_value": 2.00,
            "currency_code": "EUR",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Regulamento Municipal da Taxa Turistica de Lisboa — EUR 2/person/night, max 7 nights",
            "source_url": "https://www.visitlisboa.com/en/p/tourist-tax",
            "authority_name": "Camara Municipal de Lisboa",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_austria_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Austria: 10% VAT reduced on accommodation. Vienna: 3.2% Ortstaxe."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["AT"].id,
            "tax_category_id": categories["vat_reduced"].id,
            "rate_type": "percentage",
            "rate_value": 0.10,
            "currency_code": "EUR",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "UStG 1994 §10 Abs. 2 Z 4 — ermassigte Steuer 10% for accommodation",
            "authority_name": "Bundesministerium fur Finanzen",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["AT-9-VIE"].id,
            "tax_category_id": categories["tourism_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.032,
            "currency_code": "EUR",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Wiener Tourismusforderungsgesetz — Ortstaxe 3.2% of net accommodation charge",
            "source_url": "https://www.wien.gv.at/amtshelfer/finanzielles/rechnungswesen/abgaben/ortstaxe.html",
            "authority_name": "Magistrat der Stadt Wien",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_czech_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Czech Republic: 12% VAT reduced on accommodation. Prague: CZK 50/person/night."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["CZ"].id,
            "tax_category_id": categories["vat_reduced"].id,
            "rate_type": "percentage",
            "rate_value": 0.12,
            "currency_code": "CZK",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Zakon o DPH 235/2004 Sb. — snizena sazba 12% for accommodation (consolidated 2024)",
            "authority_name": "Financni sprava Ceske republiky",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["CZ-PHA-PRG"].id,
            "tax_category_id": categories["occ_flat_person_night"].id,
            "rate_type": "flat",
            "rate_value": 50.00,
            "currency_code": "CZK",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Obecne zavazna vyhlaska c. 27/2003 Sb. hl. m. Prahy — poplatek za ubytovani CZK 50/person/night",
            "source_url": "https://www.praha.eu/jnp/en/business/taxes_and_fees/index.html",
            "authority_name": "Magistrat hlavniho mesta Prahy",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_hungary_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Hungary: 5% VAT reduced on accommodation. Budapest: 4% tourist tax on room rate."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["HU"].id,
            "tax_category_id": categories["vat_reduced"].id,
            "rate_type": "percentage",
            "rate_value": 0.05,
            "currency_code": "HUF",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "2007. evi CXXVII. torveny az AFArol — kedvezmenyes 5% for accommodation services",
            "authority_name": "Nemzeti Ado- es Vamhivatal",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["HU-BU-BUD"].id,
            "tax_category_id": categories["tourism_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.04,
            "currency_code": "HUF",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "1990. evi C. torveny a helyi adokrol 31.§ — idegenforgalmi ado 4% of room rate",
            "source_url": "https://www.budapest.hu/Lapok/idegenforgalmi-ado.aspx",
            "authority_name": "Budapest Fovaros Onkormanyzata",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_singapore_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Singapore: 9% GST (increased from 8% on 1 Jan 2024)."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["SG"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.09,
            "currency_code": "SGD",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Goods and Services Tax Act 1993 — GST 9% (effective 1 Jan 2024)",
            "source_url": "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)",
            "authority_name": "Inland Revenue Authority of Singapore",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_australia_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Australia: 10% GST (no specific hotel/tourism tax)."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["AU"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.10,
            "currency_code": "AUD",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "A New Tax System (Goods and Services Tax) Act 1999 — GST 10%",
            "source_url": "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes",
            "authority_name": "Australian Taxation Office",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_greece_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Greece: 13% VAT reduced. Athens: tiered overnight stay tax by star rating (EUR 0.50-4.00)."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["GR"].id,
            "tax_category_id": categories["vat_reduced"].id,
            "rate_type": "percentage",
            "rate_value": 0.13,
            "currency_code": "EUR",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "N. 2859/2000, Art. 21 — FPA meioumenos suntelestis 13% for accommodation",
            "authority_name": "Anexartiti Archi Dimosion Esodon (AADE)",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["GR-I-ATH"].id,
            "tax_category_id": categories["tier_star"].id,
            "rate_type": "tiered",
            "rate_value": None,
            "currency_code": "EUR",
            "tiers": [
                {"min": 0, "max": 2, "value": 0.50},   # 1-star
                {"min": 2, "max": 3, "value": 1.50},    # 2-star
                {"min": 3, "max": 4, "value": 3.00},    # 3-star
                {"min": 4, "max": 5, "value": 3.50},    # 4-star
                {"min": 5, "value": 4.00},               # 5-star
            ],
            "tier_type": "single_amount",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "N. 4389/2016, Art. 53 — telos diamonis (overnight stay tax) by star rating",
            "source_url": "https://www.aade.gr/",
            "authority_name": "AADE / Ministry of Tourism",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_maldives_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Maldives: 16% T-GST on tourism services + $6/night green tax."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["MV"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.16,
            "currency_code": "USD",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Goods and Services Tax Act 10/2011, Amendment 2023 — T-GST 16% on tourism goods and services",
            "source_url": "https://www.mira.gov.mv/TaxLegislation.aspx",
            "authority_name": "Maldives Inland Revenue Authority (MIRA)",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["MV"].id,
            "tax_category_id": categories["eco_flat_person_night"].id,
            "rate_type": "flat",
            "rate_value": 6.00,
            "currency_code": "USD",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Green Tax Act 78/2015 — USD 6/night per room for tourist resorts and hotels",
            "source_url": "https://www.mira.gov.mv/TaxLegislation.aspx",
            "authority_name": "Maldives Inland Revenue Authority (MIRA)",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_mexico_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Mexico: 16% IVA. Mexico City: 3% ISH (Impuesto sobre Hospedaje)."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["MX"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.16,
            "currency_code": "MXN",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Ley del Impuesto al Valor Agregado, Art. 1 — IVA tasa general 16%",
            "authority_name": "Servicio de Administracion Tributaria (SAT)",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["MX-CMX-MEX"].id,
            "tax_category_id": categories["occ_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.03,
            "currency_code": "MXN",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Codigo Fiscal de la Ciudad de Mexico, Art. 274 — ISH 3% on accommodation charges",
            "authority_name": "Secretaria de Administracion y Finanzas de la CDMX",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_barcelona_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Catalonia ITS + Barcelona municipal surcharge. 4-star hotel example: EUR 1.70 + EUR 3.25 = EUR 4.95/person/night."""
    rates = []
    rate_defs = [
        # Catalonia IEET (Impost sobre les Estades en Establiments Turistics)
        {
            "jurisdiction_id": jurisdictions["ES-CT"].id,
            "tax_category_id": categories["tourism_flat_person_night"].id,
            "rate_type": "tiered",
            "rate_value": None,
            "currency_code": "EUR",
            "tiers": [
                {"min": 0, "max": 2, "value": 0.65},    # 1-star/apartment
                {"min": 2, "max": 3, "value": 0.90},     # 2-star
                {"min": 3, "max": 4, "value": 1.30},     # 3-star
                {"min": 4, "max": 5, "value": 1.70},     # 4-star
                {"min": 5, "value": 2.25},                # 5-star
            ],
            "tier_type": "single_amount",
            "effective_start": date(2024, 4, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Llei 5/2017 IEET — Impost sobre les Estades en Establiments Turistics de Catalunya",
            "source_url": "https://web.gencat.cat/en/temes/turisme/impost-estades-establiments-turistics/",
            "authority_name": "Generalitat de Catalunya",
            "status": "active",
            "created_by": "seed",
        },
        # Barcelona municipal surcharge (recarrec municipal)
        {
            "jurisdiction_id": jurisdictions["ES-CT-BCN"].id,
            "tax_category_id": categories["municipal_flat"].id,
            "rate_type": "flat",
            "rate_value": 3.25,
            "currency_code": "EUR",
            "effective_start": date(2024, 4, 1),
            "calculation_order": 25,
            "base_includes": ["base_amount"],
            "legal_reference": "Ordenanca fiscal Barcelona — recarrec municipal sobre l'IEET, EUR 3.25/person/night (2024)",
            "source_url": "https://ajuntament.barcelona.cat/hisenda/en/tourist-tax",
            "authority_name": "Ajuntament de Barcelona",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


# ──────────────────────────────────────────────────────────────────────
# 2b. TAX RATES for existing jurisdictions WITHOUT rates
# ──────────────────────────────────────────────────────────────────────

async def seed_los_angeles_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Los Angeles: 14% TOT + 1.5% TMD. No CA state hotel tax."""
    rates = []
    effective = date(2024, 1, 1)
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["US-CA-LAX"].id,
            "tax_category_id": categories["occ_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.14,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Los Angeles Municipal Code Sec 21.7.3 — Transient Occupancy Tax (TOT) 14%",
            "source_url": "https://finance.lacity.gov/transient-occupancy-tax",
            "authority_name": "City of Los Angeles Office of Finance",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-CA-LAX"].id,
            "tax_category_id": categories["infrastructure_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.015,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "LA Tourism Marketing District (TMD) — 1.5% assessment on room rate",
            "authority_name": "Los Angeles Tourism Marketing District",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_san_francisco_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """San Francisco: 14% Hotel Room Tax + 1-1.5% TID."""
    rates = []
    effective = date(2024, 1, 1)
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["US-CA-SFO"].id,
            "tax_category_id": categories["occ_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.14,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "SF Business and Tax Regulations Code Article 7 — Hotel Room Tax 14%",
            "source_url": "https://sftreasurer.org/registration-for-hotel-tax",
            "authority_name": "City and County of San Francisco Treasurer",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-CA-SFO"].id,
            "tax_category_id": categories["infrastructure_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.0125,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "SF Tourism Improvement District assessment — 1-1.5% (avg 1.25%)",
            "authority_name": "San Francisco Travel Association / TID",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_miami_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Miami-Dade: FL 6% sales + 6% tourist dev + 2% convention + 1% pro sports = ~13% total (excl. surtax)."""
    rates = []
    effective = date(2024, 1, 1)
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["US-FL"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.06,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "FL Statute 212.03 — state sales tax 6% on transient rental",
            "source_url": "https://floridarevenue.com/taxes/taxesfees/pages/transient_rental.aspx",
            "authority_name": "Florida Department of Revenue",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-FL-MIA"].id,
            "tax_category_id": categories["tourism_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.06,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "FL Statute 125.0104 — Miami-Dade Tourist Development Tax 6%",
            "authority_name": "Miami-Dade County Tax Collector",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-FL-MIA"].id,
            "tax_category_id": categories["convention_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.03,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 30,
            "base_includes": ["base_amount"],
            "legal_reference": "FL Statute 212.0305 — Miami-Dade Convention Development Tax (2% + 1% pro sports)",
            "authority_name": "Miami-Dade County Tax Collector",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_houston_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Houston: TX 6% + Houston 7% + Harris County 2% = 15% total hotel occupancy tax."""
    rates = []
    effective = date(2024, 1, 1)
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["US-TX"].id,
            "tax_category_id": categories["occ_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.06,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "TX Tax Code Chapter 156 — State Hotel Occupancy Tax 6%",
            "source_url": "https://comptroller.texas.gov/taxes/hotel/",
            "authority_name": "Texas Comptroller of Public Accounts",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-TX-HOU"].id,
            "tax_category_id": categories["occ_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.07,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Houston Code of Ordinances Ch. 44 — Municipal Hotel Occupancy Tax 7%",
            "authority_name": "City of Houston Controller's Office",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-TX-HOU"].id,
            "tax_category_id": categories["municipal_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.02,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 30,
            "base_includes": ["base_amount"],
            "legal_reference": "TX Tax Code Chapter 352 — Harris County Hotel Occupancy Tax 2%",
            "authority_name": "Harris County",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_honolulu_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Honolulu: HI GET 4.712% + TAT 10.25% + Oahu surcharge 3%."""
    rates = []
    effective = date(2024, 1, 1)
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["US-HI"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.04712,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "HRS §237 — General Excise Tax 4% + 0.712% Oahu county surcharge",
            "source_url": "https://tax.hawaii.gov/geninfo/get/",
            "authority_name": "Hawaii Department of Taxation",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-HI"].id,
            "tax_category_id": categories["occ_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.1025,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "HRS §237D — Transient Accommodations Tax (TAT) 10.25%",
            "source_url": "https://tax.hawaii.gov/geninfo/tat/",
            "authority_name": "Hawaii Department of Taxation",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["US-HI-HNL"].id,
            "tax_category_id": categories["municipal_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.03,
            "currency_code": "USD",
            "effective_start": effective,
            "calculation_order": 30,
            "base_includes": ["base_amount"],
            "legal_reference": "HRS §237D — Oahu TAT Surcharge 3% (county-level)",
            "authority_name": "City and County of Honolulu",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_bangkok_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Bangkok: Thailand VAT 7%, no specific hotel tax beyond VAT."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["TH"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.07,
            "currency_code": "THB",
            "effective_start": date(2024, 1, 1),
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "Revenue Code, Section 80 — VAT 7% (reduced from 10% standard rate by Royal Decree)",
            "source_url": "https://www.rd.go.th/english/6045.html",
            "authority_name": "Thailand Revenue Department",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_bali_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Bali: Indonesia VAT 11% + provincial accommodation tax 10%."""
    rates = []
    effective = date(2024, 1, 1)
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["ID"].id,
            "tax_category_id": categories["vat_standard"].id,
            "rate_type": "percentage",
            "rate_value": 0.11,
            "currency_code": "IDR",
            "effective_start": effective,
            "calculation_order": 10,
            "base_includes": ["base_amount"],
            "legal_reference": "UU No. 7 Tahun 2021 (Harmonisasi Peraturan Perpajakan) — PPN 11%",
            "authority_name": "Direktorat Jenderal Pajak",
            "status": "active",
            "created_by": "seed",
        },
        {
            "jurisdiction_id": jurisdictions["ID-BA"].id,
            "tax_category_id": categories["occ_pct"].id,
            "rate_type": "percentage",
            "rate_value": 0.10,
            "currency_code": "IDR",
            "effective_start": effective,
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "UU No. 1 Tahun 2022 HKPD — Pajak Hotel / Accommodation Tax 10% (Bali provincial)",
            "authority_name": "Pemerintah Provinsi Bali",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


async def seed_kyoto_rates(db: AsyncSession, jurisdictions: dict, categories: dict) -> list[TaxRate]:
    """Kyoto: accommodation tax tiered by room price (different from Tokyo tiers)."""
    rates = []
    rate_defs = [
        {
            "jurisdiction_id": jurisdictions["JP-26-KYO"].id,
            "tax_category_id": categories["tier_price"].id,
            "rate_type": "tiered",
            "rate_value": None,
            "currency_code": "JPY",
            "tiers": [
                {"min": 0, "max": 20000, "value": 200},
                {"min": 20000, "max": 50000, "value": 500},
                {"min": 50000, "value": 1000},
            ],
            "tier_type": "single_amount",
            "effective_start": date(2018, 10, 1),
            "calculation_order": 20,
            "base_includes": ["base_amount"],
            "legal_reference": "Kyoto City Accommodation Tax Ordinance (京都市宿泊税条例) — tiered by nightly rate",
            "source_url": "https://www.city.kyoto.lg.jp/gyozai/page/0000236942.html",
            "authority_name": "Kyoto City Government (京都市)",
            "status": "active",
            "created_by": "seed",
        },
    ]
    for rd in rate_defs:
        rates.append(await _create_rate_if_not_exists(db, rd))
    return rates


# ──────────────────────────────────────────────────────────────────────
# 3. TAX RULES — exemptions, caps, and conditions
# ──────────────────────────────────────────────────────────────────────

async def seed_enhancement_rules(db: AsyncSession, jurisdictions: dict) -> list[TaxRule]:
    """Seed all additional rules for both new and existing jurisdictions."""
    rules = []

    # --- Chicago long-stay exemption (30+ days) ---
    chi_occ = await _find_rate(db, jurisdictions["US-IL-CHI"].id, "occ_pct")
    if chi_occ:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": chi_occ.id,
            "jurisdiction_id": jurisdictions["US-IL-CHI"].id,
            "rule_type": "exemption",
            "priority": 100,
            "name": "Chicago Long-Stay Exemption (30+ days)",
            "description": "Stays of 30 or more consecutive days are exempt from Chicago's "
                           "Hotel Accommodation Tax per IL Hotel Operators' Occupation Tax Act.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "stay_length_days", "op": ">=", "value": 30}],
            },
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "IL Hotel Operators' Occupation Tax Act (35 ILCS 145/) — 30-day exemption",
            "authority_name": "Illinois Department of Revenue",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Amsterdam short-stay rental surcharge ---
    ams_tourism = await _find_rate(db, jurisdictions["NL-NH-AMS"].id, "tourism_pct")
    if ams_tourism:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": ams_tourism.id,
            "jurisdiction_id": jurisdictions["NL-NH-AMS"].id,
            "rule_type": "surcharge",
            "priority": 50,
            "name": "Amsterdam STR Surcharge (+3%)",
            "description": "Short-term rental properties in Amsterdam pay an additional 3% on top of "
                           "the standard tourist tax (total ~15.5% for STR vs 12.5% for hotels).",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "property_type", "op": "in", "value": ["str", "vacation_rental"]}],
            },
            "action": {"additional_rate": 0.03},
            "effective_start": date(2025, 1, 1),
            "legal_reference": "Verordening toeristenbelasting 2025 — additional levy on private vacation rental",
            "authority_name": "Gemeente Amsterdam",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Paris minors exemption ---
    par_tourism = await _find_rate(db, jurisdictions["FR-IDF-PAR"].id, "tourism_flat_person_night")
    if par_tourism:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": par_tourism.id,
            "jurisdiction_id": jurisdictions["FR-IDF-PAR"].id,
            "rule_type": "exemption",
            "priority": 100,
            "name": "Paris Minors Exemption (under 18)",
            "description": "Children under 18 years of age are exempt from the taxe de sejour "
                           "per Code du tourisme Art. R2333-50.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "guest_age", "op": "<", "value": 18}],
            },
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "Code du tourisme, Art. R2333-50 — exemption for minors under 18",
            "authority_name": "Mairie de Paris",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Balearic low season reduction ---
    bal_eco = await _find_rate(db, jurisdictions["ES-IB"].id, "eco_flat_person_night")
    if bal_eco:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": bal_eco.id,
            "jurisdiction_id": jurisdictions["ES-IB"].id,
            "rule_type": "reduction",
            "priority": 80,
            "name": "Balearic Low Season 50% Reduction (Nov-Apr)",
            "description": "The Balearic ITS rate is reduced by 50% during the low season "
                           "(November through April) per Llei 2/2016.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "stay_month", "op": "in", "value": [11, 12, 1, 2, 3, 4]}],
            },
            "action": {"rate_multiplier": 0.5},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "Llei 2/2016 de l'Impost sobre Estades Turistiques — 50% low season reduction",
            "authority_name": "Govern de les Illes Balears",
            "status": "active",
            "created_by": "seed",
        }))

        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": bal_eco.id,
            "jurisdiction_id": jurisdictions["ES-IB"].id,
            "rule_type": "reduction",
            "priority": 70,
            "name": "Balearic 9-Night Stay Discount (50% from night 9)",
            "description": "Stays longer than 8 nights receive a 50% discount on the ITS "
                           "from night 9 onward.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "night_number", "op": ">=", "value": 9}],
            },
            "action": {"rate_multiplier": 0.5},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "Llei 2/2016 — 50% reduction from night 9 onward",
            "authority_name": "Govern de les Illes Balears",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Los Angeles long-stay exemption ---
    lax_occ = await _find_rate(db, jurisdictions["US-CA-LAX"].id, "occ_pct")
    if lax_occ:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": lax_occ.id,
            "jurisdiction_id": jurisdictions["US-CA-LAX"].id,
            "rule_type": "exemption",
            "priority": 100,
            "name": "LA Long-Stay Exemption (31+ days)",
            "description": "Stays of 31 or more consecutive days are exempt from LA's "
                           "Transient Occupancy Tax per LAMC 21.7.3.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "stay_length_days", "op": ">=", "value": 31}],
            },
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "Los Angeles Municipal Code Sec 21.7.3 — 31-day exemption",
            "authority_name": "City of Los Angeles Office of Finance",
            "status": "active",
            "created_by": "seed",
        }))

    # --- San Francisco non-profit exemption ---
    sfo_occ = await _find_rate(db, jurisdictions["US-CA-SFO"].id, "occ_pct")
    if sfo_occ:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": sfo_occ.id,
            "jurisdiction_id": jurisdictions["US-CA-SFO"].id,
            "rule_type": "exemption",
            "priority": 90,
            "name": "SF Non-Profit Organization Exemption",
            "description": "Qualifying non-profit organizations are exempt from SF Hotel Room Tax "
                           "per SF Business and Tax Regulations Code Article 7.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "guest_type", "op": "==", "value": "non_profit"}],
            },
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "SF Business and Tax Regulations Code Article 7 — non-profit exemption",
            "authority_name": "City and County of San Francisco",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Miami: no business travel exemption (Florida does NOT exempt) ---
    mia_tourism = await _find_rate(db, jurisdictions["US-FL-MIA"].id, "tourism_pct")
    if mia_tourism:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": mia_tourism.id,
            "jurisdiction_id": jurisdictions["US-FL-MIA"].id,
            "rule_type": "note",
            "priority": 0,
            "name": "Miami No Business Travel Exemption",
            "description": "Florida does NOT exempt business travel from transient rental taxes. "
                           "All short-term stays under 6 months are subject to full tax regardless of purpose.",
            "conditions": {},
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "FL Statute 212.03 — no business exemption for transient rentals",
            "authority_name": "Florida Department of Revenue",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Honolulu long-stay exemption (180+ days) ---
    hi_tat = await _find_rate(db, jurisdictions["US-HI"].id, "occ_pct")
    if hi_tat:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": hi_tat.id,
            "jurisdiction_id": jurisdictions["US-HI-HNL"].id,
            "rule_type": "exemption",
            "priority": 100,
            "name": "Hawaii TAT Long-Stay Exemption (180+ days)",
            "description": "Stays of 180 or more consecutive days are exempt from Hawaii's "
                           "Transient Accommodations Tax per HRS 237D.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "stay_length_days", "op": ">=", "value": 180}],
            },
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "HRS §237D — 180-day exemption for long-term residents",
            "authority_name": "Hawaii Department of Taxation",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Lisbon 7-night cap ---
    lis_tourism = await _find_rate(db, jurisdictions["PT-11-LIS"].id, "tourism_flat_person_night")
    if lis_tourism:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": lis_tourism.id,
            "jurisdiction_id": jurisdictions["PT-11-LIS"].id,
            "rule_type": "cap",
            "priority": 50,
            "name": "Lisbon Tourist Tax 7-Night Cap",
            "description": "Lisbon's tourist tax is charged for a maximum of 7 consecutive nights per stay.",
            "conditions": {},
            "action": {"max_nights": 7},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "Regulamento Municipal da Taxa Turistica de Lisboa — cap at 7 nights",
            "authority_name": "Camara Municipal de Lisboa",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Vienna minors exemption (under 15) ---
    vie_tourism = await _find_rate(db, jurisdictions["AT-9-VIE"].id, "tourism_pct")
    if vie_tourism:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": vie_tourism.id,
            "jurisdiction_id": jurisdictions["AT-9-VIE"].id,
            "rule_type": "exemption",
            "priority": 100,
            "name": "Vienna Minors Exemption (under 15)",
            "description": "Children under 15 years of age are exempt from Vienna's Ortstaxe.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "guest_age", "op": "<", "value": 15}],
            },
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "Wiener Tourismusforderungsgesetz — exemption for children under 15",
            "authority_name": "Magistrat der Stadt Wien",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Prague business travel exemption ---
    prg_occ = await _find_rate(db, jurisdictions["CZ-PHA-PRG"].id, "occ_flat_person_night")
    if prg_occ:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": prg_occ.id,
            "jurisdiction_id": jurisdictions["CZ-PHA-PRG"].id,
            "rule_type": "exemption",
            "priority": 100,
            "name": "Prague Business Travel Exemption",
            "description": "Business travelers with employer confirmation are exempt from "
                           "Prague's local accommodation charge.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "guest_type", "op": "==", "value": "business"}],
            },
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "Zakon c. 565/1990 Sb. o mistnich poplatcich — business travel exemption",
            "authority_name": "Magistrat hlavniho mesta Prahy",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Budapest minors exemption (under 18) ---
    bud_tourism = await _find_rate(db, jurisdictions["HU-BU-BUD"].id, "tourism_pct")
    if bud_tourism:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": bud_tourism.id,
            "jurisdiction_id": jurisdictions["HU-BU-BUD"].id,
            "rule_type": "exemption",
            "priority": 100,
            "name": "Budapest Minors Exemption (under 18)",
            "description": "Children under 18 years of age are exempt from Budapest's tourist tax "
                           "(idegenforgalmi ado).",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "guest_age", "op": "<", "value": 18}],
            },
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "1990. evi C. torveny a helyi adokrol 31.§ — exemption for minors under 18",
            "authority_name": "Budapest Fovaros Onkormanyzata",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Greece camping reduction (50%) ---
    ath_star = await _find_rate(db, jurisdictions["GR-I-ATH"].id, "tier_star")
    if ath_star:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": ath_star.id,
            "jurisdiction_id": jurisdictions["GR"].id,
            "rule_type": "reduction",
            "priority": 80,
            "name": "Greece Camping/RV 50% Reduction",
            "description": "Camping sites and RV parks receive a 50% reduction on the overnight stay tax.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "property_type", "op": "in", "value": ["campground"]}],
            },
            "action": {"rate_multiplier": 0.5},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "N. 4389/2016, Art. 53 — 50% reduction for camping establishments",
            "authority_name": "AADE / Ministry of Tourism",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Maldives green tax transit exemption ---
    mv_green = await _find_rate(db, jurisdictions["MV"].id, "eco_flat_person_night")
    if mv_green:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": mv_green.id,
            "jurisdiction_id": jurisdictions["MV"].id,
            "rule_type": "exemption",
            "priority": 100,
            "name": "Maldives Green Tax Transit Exemption (<24 hours)",
            "description": "Transit stays of less than 24 hours are exempt from the green tax.",
            "conditions": {
                "operator": "AND",
                "rules": [{"field": "stay_hours", "op": "<", "value": 24}],
            },
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "Green Tax Act 78/2015 — transit exemption for stays under 24 hours",
            "authority_name": "Maldives Inland Revenue Authority (MIRA)",
            "status": "active",
            "created_by": "seed",
        }))

    # --- Singapore: no specific long-stay hotel exemption under GST ---
    sg_gst = await _find_rate(db, jurisdictions["SG"].id, "vat_standard")
    if sg_gst:
        rules.append(await _create_rule_if_not_exists(db, {
            "tax_rate_id": sg_gst.id,
            "jurisdiction_id": jurisdictions["SG"].id,
            "rule_type": "note",
            "priority": 0,
            "name": "Singapore No Long-Stay Hotel GST Exemption",
            "description": "Singapore GST applies to all hotel accommodation regardless of duration. "
                           "There is no specific long-stay exemption for hotels under GST.",
            "conditions": {},
            "action": {},
            "effective_start": date(2024, 1, 1),
            "legal_reference": "Goods and Services Tax Act 1993 — no accommodation duration exemption",
            "authority_name": "Inland Revenue Authority of Singapore",
            "status": "active",
            "created_by": "seed",
        }))

    return rules


# ──────────────────────────────────────────────────────────────────────
# 4. MONITORING SOURCES
# ──────────────────────────────────────────────────────────────────────

async def seed_monitored_sources(db: AsyncSession, jurisdictions: dict) -> list[MonitoredSource]:
    """Seed ~15 monitored sources for major jurisdictions."""
    sources = []

    source_defs = [
        {
            "jurisdiction_code": "US-NY-NYC",
            "url": "https://www.nyc.gov/site/finance/taxes/business-hotel-room-occupancy-tax.page",
            "source_type": "government_website",
            "language": "en",
            "check_frequency_days": 7,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 10, 14, 30, 0),
            "last_content_hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "NL-NH-AMS",
            "url": "https://www.amsterdam.nl/en/municipal-taxes/tourist-tax/",
            "source_type": "tax_authority",
            "language": "en",
            "check_frequency_days": 7,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 9, 10, 0, 0),
            "last_content_hash": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "JP-13-TYO",
            "url": "https://www.tax.metro.tokyo.lg.jp/english/hotel_tax.html",
            "source_type": "government_website",
            "language": "en",
            "check_frequency_days": 14,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 5, 3, 0, 0),
            "last_content_hash": "c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "FR-IDF-PAR",
            "url": "https://www.service-public.fr/professionnels-entreprises/vosdroits/F31635",
            "source_type": "government_website",
            "language": "fr",
            "check_frequency_days": 14,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 8, 9, 15, 0),
            "last_content_hash": "d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "AE-DU",
            "url": "https://www.dubaitourism.gov.ae/en/tourism-dirham",
            "source_type": "regulatory_body",
            "language": "en",
            "check_frequency_days": 14,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 7, 8, 45, 0),
            "last_content_hash": "e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "IT-RM-ROM",
            "url": "https://www.comune.roma.it/web/it/informazione-di-servizio.page",
            "source_type": "government_website",
            "language": "it",
            "check_frequency_days": 14,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 6, 11, 30, 0),
            "last_content_hash": "f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "DE-BE-BER",
            "url": "https://www.berlin.de/sen/finanzen/steuern/informationen-fuer-steuerzahler-/city-tax/",
            "source_type": "government_website",
            "language": "de",
            "check_frequency_days": 14,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 4, 7, 0, 0),
            "last_content_hash": "a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "GB",
            "url": "https://www.gov.uk/guidance/vat-on-hotel-accommodation",
            "source_type": "tax_authority",
            "language": "en",
            "check_frequency_days": 30,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 1, 12, 0, 0),
            "last_content_hash": "b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "PT-11-LIS",
            "url": "https://www.visitlisboa.com/en/p/tourist-tax",
            "source_type": "government_website",
            "language": "en",
            "check_frequency_days": 14,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 3, 16, 0, 0),
            "last_content_hash": "c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "ES-CT-BCN",
            "url": "https://web.gencat.cat/en/temes/turisme/impost-estades-establiments-turistics/",
            "source_type": "tax_authority",
            "language": "en",
            "check_frequency_days": 14,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 2, 10, 30, 0),
            "last_content_hash": "d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "SG",
            "url": "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)",
            "source_type": "tax_authority",
            "language": "en",
            "check_frequency_days": 30,
            "status": "active",
            "last_checked_at": datetime(2026, 2, 28, 5, 0, 0),
            "last_content_hash": "e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "AU",
            "url": "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes",
            "source_type": "tax_authority",
            "language": "en",
            "check_frequency_days": 30,
            "status": "active",
            "last_checked_at": datetime(2026, 2, 25, 2, 0, 0),
            "last_content_hash": "f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "MV",
            "url": "https://www.mira.gov.mv/TaxLegislation.aspx",
            "source_type": "tax_authority",
            "language": "en",
            "check_frequency_days": 30,
            "status": "active",
            "last_checked_at": datetime(2026, 2, 20, 9, 0, 0),
            "last_content_hash": "a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "CZ-PHA-PRG",
            "url": "https://www.praha.eu/jnp/en/business/taxes_and_fees/index.html",
            "source_type": "government_website",
            "language": "en",
            "check_frequency_days": 14,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 11, 8, 0, 0),
            "last_content_hash": "b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9",
            "created_by": "system",
        },
        {
            "jurisdiction_code": "ES-IB",
            "url": "https://www.caib.es/sites/impostturistic/",
            "source_type": "legal_gazette",
            "language": "es",
            "check_frequency_days": 14,
            "status": "active",
            "last_checked_at": datetime(2026, 3, 10, 6, 30, 0),
            "last_content_hash": "c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0",
            "created_by": "system",
        },
    ]

    for sd in source_defs:
        sd = dict(sd)
        jcode = sd.pop("jurisdiction_code")
        j = jurisdictions.get(jcode)
        if j:
            sd["jurisdiction_id"] = j.id
            sources.append(await _create_source_if_not_exists(db, sd))
        else:
            print(f"  WARNING: Jurisdiction {jcode} not found, skipping source {sd['url']}")

    return sources


# ──────────────────────────────────────────────────────────────────────
# 5. DETECTED CHANGES
# ──────────────────────────────────────────────────────────────────────

async def seed_detected_changes(db: AsyncSession, jurisdictions: dict, sources: list[MonitoredSource]) -> list[DetectedChange]:
    """Seed ~12 realistic detected changes."""
    changes = []

    # Build source lookup by jurisdiction_id
    source_by_jid: dict[int, MonitoredSource] = {}
    for s in sources:
        if s.jurisdiction_id:
            source_by_jid[s.jurisdiction_id] = s

    def _get_source_id(jcode: str) -> int | None:
        j = jurisdictions.get(jcode)
        if j and j.id in source_by_jid:
            return source_by_jid[j.id].id
        return None

    change_defs = [
        # 1. Amsterdam tourist tax increase 7% -> 12.5% (2025)
        {
            "jurisdiction_code": "NL-NH-AMS",
            "change_type": "rate_increase",
            "detected_at": datetime(2024, 10, 15, 14, 22, 0),
            "extracted_data": {
                "tax_type": "tourist_tax",
                "old_rate": 0.07,
                "new_rate": 0.125,
                "effective_date": "2025-01-01",
                "description": "Amsterdam increases tourist tax from 7% to 12.5% of room rate",
            },
            "confidence": 0.97,
            "source_quote": "Per 1 januari 2025 wordt het tarief van de toeristenbelasting in Amsterdam verhoogd van 7% naar 12,5%.",
            "review_status": "approved",
            "reviewed_by": "analyst@taxlens.io",
            "reviewed_at": datetime(2024, 10, 18, 9, 0, 0),
            "review_notes": "Confirmed via Gemeente Amsterdam official announcement.",
        },
        # 2. Singapore GST increase 8% -> 9% (Jan 2024)
        {
            "jurisdiction_code": "SG",
            "change_type": "rate_increase",
            "detected_at": datetime(2023, 11, 20, 8, 15, 0),
            "extracted_data": {
                "tax_type": "GST",
                "old_rate": 0.08,
                "new_rate": 0.09,
                "effective_date": "2024-01-01",
                "description": "Singapore GST increases from 8% to 9% as planned in Budget 2022",
            },
            "confidence": 0.95,
            "source_quote": "The GST rate will increase from 8% to 9% with effect from 1 January 2024.",
            "review_status": "approved",
            "reviewed_by": "admin@taxlens.io",
            "reviewed_at": datetime(2023, 11, 22, 10, 30, 0),
            "review_notes": "Official IRAS announcement confirmed. Second planned increase per Budget 2022.",
        },
        # 3. Bali accommodation tax proposal
        {
            "jurisdiction_code": "ID-BA",
            "change_type": "new_tax",
            "detected_at": datetime(2025, 6, 10, 11, 0, 0),
            "extracted_data": {
                "tax_type": "accommodation_tax",
                "proposed_rate": 0.10,
                "description": "Bali implements 10% provincial accommodation tax under UU HKPD",
            },
            "confidence": 0.82,
            "source_quote": "Pemerintah Provinsi Bali menetapkan pajak hotel sebesar 10% berdasarkan UU No. 1 Tahun 2022.",
            "review_status": "pending",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": None,
        },
        # 4. Barcelona tourist tax increase for 2025
        {
            "jurisdiction_code": "ES-CT-BCN",
            "change_type": "rate_increase",
            "detected_at": datetime(2024, 12, 5, 16, 30, 0),
            "extracted_data": {
                "tax_type": "municipal_surcharge",
                "old_rate_flat": 2.75,
                "new_rate_flat": 3.25,
                "effective_date": "2024-04-01",
                "description": "Barcelona municipal surcharge increases from EUR 2.75 to EUR 3.25/person/night",
            },
            "confidence": 0.91,
            "source_quote": "El recarrec municipal de Barcelona sobre l'IEET puja a 3,25 euros per persona i nit.",
            "review_status": "approved",
            "reviewed_by": "analyst@taxlens.io",
            "reviewed_at": datetime(2024, 12, 8, 11, 0, 0),
            "review_notes": "Confirmed via Ajuntament de Barcelona fiscal ordinance update.",
        },
        # 5-7 removed: speculative proposals without concrete rate values
        # 8. Prague accommodation charge increase (CZK 21 -> CZK 50)
        {
            "jurisdiction_code": "CZ-PHA-PRG",
            "change_type": "rate_increase",
            "detected_at": datetime(2023, 12, 1, 9, 0, 0),
            "extracted_data": {
                "tax_type": "accommodation_charge",
                "old_rate_flat": 21,
                "new_rate_flat": 50,
                "currency": "CZK",
                "effective_date": "2024-01-01",
                "description": "Prague increases local accommodation charge from CZK 21 to CZK 50/person/night",
            },
            "confidence": 0.94,
            "source_quote": "Poplatek za ubytovani se zvysuje z 21 Kc na 50 Kc za osobu a noc.",
            "review_status": "approved",
            "reviewed_by": "admin@taxlens.io",
            "reviewed_at": datetime(2023, 12, 5, 15, 0, 0),
            "review_notes": "Confirmed by Prague city hall vyhlaska. Significant increase effective Jan 2024.",
        },
        # 9-10 removed: speculative proposals without concrete rate values
        # 11. France departmental surtax update
        {
            "jurisdiction_code": "FR-IDF-PAR",
            "change_type": "rate_adjustment",
            "detected_at": datetime(2025, 1, 10, 11, 0, 0),
            "extracted_data": {
                "tax_type": "taxe_de_sejour_departementale",
                "old_rate": 0.10,
                "new_rate": 0.15,
                "effective_date": "2025-01-01",
                "description": "Ile-de-France departmental surtax on taxe de sejour increased from 10% to 15%",
            },
            "confidence": 0.91,
            "source_quote": "La taxe additionnelle departementale est portee a 15% du montant de la taxe de sejour.",
            "review_status": "approved",
            "reviewed_by": "analyst@taxlens.io",
            "reviewed_at": datetime(2025, 1, 14, 16, 0, 0),
            "review_notes": "Confirmed via legifrance.gouv.fr update to Code du tourisme.",
        },
        # 12. Maldives green tax rate increase proposal
        {
            "jurisdiction_code": "MV",
            "change_type": "rate_increase",
            "detected_at": datetime(2025, 7, 20, 6, 0, 0),
            "extracted_data": {
                "tax_type": "green_tax",
                "old_rate_flat": 6.00,
                "proposed_rate_flat": 8.00,
                "description": "Maldives government considering increasing green tax from USD 6 to USD 8/night",
            },
            "confidence": 0.68,
            "source_quote": "The Maldives Ministry of Tourism is reviewing a proposal to increase the green tax to $8 per night.",
            "review_status": "pending",
            "reviewed_by": None,
            "reviewed_at": None,
            "review_notes": None,
        },
    ]

    for cd in change_defs:
        cd = dict(cd)
        jcode = cd.pop("jurisdiction_code")
        j = jurisdictions.get(jcode)
        if j:
            cd["jurisdiction_id"] = j.id
            cd["source_id"] = _get_source_id(jcode)
            changes.append(await _create_change_if_not_exists(db, cd))
        else:
            print(f"  WARNING: Jurisdiction {jcode} not found, skipping detected change")

    return changes


# ──────────────────────────────────────────────────────────────────────
# 6. AUDIT LOG ENTRIES
# ──────────────────────────────────────────────────────────────────────

async def seed_audit_logs(db: AsyncSession, jurisdictions: dict) -> list[AuditLog]:
    """Seed ~30 audit log entries covering various actions."""
    logs = []

    log_defs = [
        # --- Initial seed data creation ---
        {
            "entity_type": "jurisdiction",
            "entity_id": 1,
            "action": "create",
            "old_values": None,
            "new_values": {"code": "US", "name": "United States", "jurisdiction_type": "country"},
            "changed_by": "system",
            "change_source": "seed",
            "change_reason": "Initial seed data — US country jurisdiction",
            "source_reference": None,
            "created_at": datetime(2024, 1, 15, 10, 0, 0),
        },
        {
            "entity_type": "jurisdiction",
            "entity_id": 2,
            "action": "create",
            "old_values": None,
            "new_values": {"code": "US-NY-NYC", "name": "New York City", "jurisdiction_type": "city"},
            "changed_by": "system",
            "change_source": "seed",
            "change_reason": "Initial seed data — NYC city jurisdiction",
            "source_reference": None,
            "created_at": datetime(2024, 1, 15, 10, 0, 1),
        },
        {
            "entity_type": "tax_category",
            "entity_id": 1,
            "action": "create",
            "old_values": None,
            "new_values": {"code": "occ_pct", "name": "Occupancy Tax (% of room)"},
            "changed_by": "system",
            "change_source": "seed",
            "change_reason": "Initial seed data — occupancy percentage tax category",
            "source_reference": None,
            "created_at": datetime(2024, 1, 15, 10, 0, 2),
        },
        {
            "entity_type": "tax_rate",
            "entity_id": 1,
            "action": "create",
            "old_values": None,
            "new_values": {"jurisdiction": "US-NY", "category": "vat_standard", "rate_value": 0.04, "status": "active"},
            "changed_by": "seed",
            "change_source": "seed",
            "change_reason": "Initial seed — NY State sales tax on hotel occupancy",
            "source_reference": "NY Tax Law §1105(e)",
            "created_at": datetime(2024, 1, 15, 10, 5, 0),
        },
        {
            "entity_type": "tax_rate",
            "entity_id": 2,
            "action": "create",
            "old_values": None,
            "new_values": {"jurisdiction": "US-NY-NYC", "category": "municipal_pct", "rate_value": 0.045, "status": "active"},
            "changed_by": "seed",
            "change_source": "seed",
            "change_reason": "Initial seed — NYC local sales tax on hotel occupancy",
            "source_reference": "NYC Administrative Code §11-2502",
            "created_at": datetime(2024, 1, 15, 10, 5, 1),
        },
        {
            "entity_type": "tax_rate",
            "entity_id": 3,
            "action": "create",
            "old_values": None,
            "new_values": {"jurisdiction": "US-NY-NYC", "category": "occ_pct", "rate_value": 0.05875, "status": "active"},
            "changed_by": "seed",
            "change_source": "seed",
            "change_reason": "Initial seed — NYC hotel room occupancy tax",
            "source_reference": "NYC Administrative Code §11-2502",
            "created_at": datetime(2024, 1, 15, 10, 5, 2),
        },
        # --- Rate lifecycle: AI draft -> approved -> active ---
        {
            "entity_type": "tax_rate",
            "entity_id": 5,
            "action": "status_change",
            "old_values": {"status": "draft"},
            "new_values": {"status": "approved"},
            "changed_by": "analyst@taxlens.io",
            "change_source": "manual_review",
            "change_reason": "Verified Amsterdam tourist tax 12.5% against official gazette",
            "source_reference": "Verordening toeristenbelasting 2025",
            "created_at": datetime(2024, 11, 1, 14, 30, 0),
        },
        {
            "entity_type": "tax_rate",
            "entity_id": 5,
            "action": "status_change",
            "old_values": {"status": "approved"},
            "new_values": {"status": "active"},
            "changed_by": "admin@taxlens.io",
            "change_source": "api",
            "change_reason": "Activated Amsterdam 12.5% tourist tax rate for production",
            "source_reference": None,
            "created_at": datetime(2024, 11, 5, 9, 0, 0),
        },
        {
            "entity_type": "tax_rate",
            "entity_id": 6,
            "action": "status_change",
            "old_values": {"status": "draft"},
            "new_values": {"status": "approved"},
            "changed_by": "analyst@taxlens.io",
            "change_source": "manual_review",
            "change_reason": "Verified Tokyo accommodation tax tiers against metro.tokyo.lg.jp",
            "source_reference": "Tokyo Metropolitan Hotel Tax Ordinance",
            "created_at": datetime(2024, 6, 15, 10, 30, 0),
        },
        {
            "entity_type": "tax_rate",
            "entity_id": 6,
            "action": "status_change",
            "old_values": {"status": "approved"},
            "new_values": {"status": "active"},
            "changed_by": "admin@taxlens.io",
            "change_source": "api",
            "change_reason": "Activated Tokyo accommodation tax tiers for production",
            "source_reference": None,
            "created_at": datetime(2024, 6, 16, 8, 0, 0),
        },
        # --- Rule creation and approval ---
        {
            "entity_type": "tax_rule",
            "entity_id": 1,
            "action": "create",
            "old_values": None,
            "new_values": {"name": "Permanent Resident Exemption (180+ days)", "jurisdiction": "US-NY-NYC", "rule_type": "exemption"},
            "changed_by": "seed",
            "change_source": "seed",
            "change_reason": "Initial seed — NYC permanent resident exemption rule",
            "source_reference": "NYC Administrative Code §11-2502(a)",
            "created_at": datetime(2024, 1, 15, 10, 10, 0),
        },
        {
            "entity_type": "tax_rule",
            "entity_id": 2,
            "action": "create",
            "old_values": None,
            "new_values": {"name": "Berlin City Tax Business Travel Exemption", "jurisdiction": "DE-BE-BER", "rule_type": "exemption"},
            "changed_by": "seed",
            "change_source": "seed",
            "change_reason": "Initial seed — Berlin business travel exemption",
            "source_reference": "UenStG Berlin §1 Abs. 1",
            "created_at": datetime(2024, 1, 15, 10, 10, 1),
        },
        {
            "entity_type": "tax_rule",
            "entity_id": 3,
            "action": "create",
            "old_values": None,
            "new_values": {"name": "Rome City Tax 10-Night Cap", "jurisdiction": "IT-RM-ROM", "rule_type": "cap"},
            "changed_by": "seed",
            "change_source": "seed",
            "change_reason": "Initial seed — Rome city tax night cap rule",
            "source_reference": "Deliberazione Assemblea Capitolina n. 36/2023",
            "created_at": datetime(2024, 1, 15, 10, 10, 2),
        },
        # --- Detected change review events ---
        {
            "entity_type": "detected_change",
            "entity_id": 1,
            "action": "review_approve",
            "old_values": {"review_status": "pending"},
            "new_values": {"review_status": "approved"},
            "changed_by": "analyst@taxlens.io",
            "change_source": "manual_review",
            "change_reason": "Amsterdam tourist tax increase confirmed via official gazette",
            "source_reference": "https://www.amsterdam.nl/en/municipal-taxes/tourist-tax/",
            "created_at": datetime(2024, 10, 18, 9, 0, 0),
        },
        {
            "entity_type": "detected_change",
            "entity_id": 2,
            "action": "review_approve",
            "old_values": {"review_status": "pending"},
            "new_values": {"review_status": "approved"},
            "changed_by": "admin@taxlens.io",
            "change_source": "manual_review",
            "change_reason": "Singapore GST 9% increase confirmed via IRAS official page",
            "source_reference": "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)",
            "created_at": datetime(2023, 11, 22, 10, 30, 0),
        },
        {
            "entity_type": "detected_change",
            "entity_id": 5,
            "action": "review_reject",
            "old_values": {"review_status": "pending"},
            "new_values": {"review_status": "rejected"},
            "changed_by": "analyst@taxlens.io",
            "change_source": "manual_review",
            "change_reason": "NYC hotel tax reform was only a news article, no formal legislative proposal",
            "source_reference": None,
            "created_at": datetime(2025, 3, 18, 14, 0, 0),
        },
        {
            "entity_type": "detected_change",
            "entity_id": 8,
            "action": "review_approve",
            "old_values": {"review_status": "pending"},
            "new_values": {"review_status": "approved"},
            "changed_by": "admin@taxlens.io",
            "change_source": "manual_review",
            "change_reason": "Prague CZK 50 accommodation charge confirmed via official vyhlaska",
            "source_reference": "https://www.praha.eu/jnp/en/business/taxes_and_fees/index.html",
            "created_at": datetime(2023, 12, 5, 15, 0, 0),
        },
        {
            "entity_type": "detected_change",
            "entity_id": 11,
            "action": "review_approve",
            "old_values": {"review_status": "pending"},
            "new_values": {"review_status": "approved"},
            "changed_by": "analyst@taxlens.io",
            "change_source": "manual_review",
            "change_reason": "France IDF departmental surtax increase to 15% confirmed via legifrance",
            "source_reference": "Code du tourisme Art. L422-3",
            "created_at": datetime(2025, 1, 14, 16, 0, 0),
        },
        # --- Source URL updates ---
        {
            "entity_type": "monitored_source",
            "entity_id": 1,
            "action": "update",
            "old_values": {"last_content_hash": "0000000000000000"},
            "new_values": {"last_content_hash": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"},
            "changed_by": "ai_monitor",
            "change_source": "ai_detection",
            "change_reason": "Periodic content check — NYC finance hotel tax page",
            "source_reference": "https://www.nyc.gov/site/finance/taxes/business-hotel-room-occupancy-tax.page",
            "created_at": datetime(2026, 3, 10, 14, 30, 0),
        },
        {
            "entity_type": "monitored_source",
            "entity_id": 2,
            "action": "update",
            "old_values": {"last_content_hash": "1111111111111111"},
            "new_values": {"last_content_hash": "b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7"},
            "changed_by": "ai_monitor",
            "change_source": "ai_detection",
            "change_reason": "Periodic content check — Amsterdam tourist tax page",
            "source_reference": "https://www.amsterdam.nl/en/municipal-taxes/tourist-tax/",
            "created_at": datetime(2026, 3, 9, 10, 0, 0),
        },
        # --- Enhancement seed events ---
        {
            "entity_type": "jurisdiction",
            "entity_id": 100,
            "action": "create",
            "old_values": None,
            "new_values": {"code": "GB", "name": "United Kingdom", "jurisdiction_type": "country"},
            "changed_by": "seed",
            "change_source": "bulk_import",
            "change_reason": "Seed enhancement — UK jurisdiction added",
            "source_reference": None,
            "created_at": datetime(2025, 6, 1, 12, 0, 0),
        },
        {
            "entity_type": "jurisdiction",
            "entity_id": 101,
            "action": "create",
            "old_values": None,
            "new_values": {"code": "PT", "name": "Portugal", "jurisdiction_type": "country"},
            "changed_by": "seed",
            "change_source": "bulk_import",
            "change_reason": "Seed enhancement — Portugal jurisdiction added",
            "source_reference": None,
            "created_at": datetime(2025, 6, 1, 12, 0, 1),
        },
        {
            "entity_type": "jurisdiction",
            "entity_id": 102,
            "action": "create",
            "old_values": None,
            "new_values": {"code": "SG", "name": "Singapore", "jurisdiction_type": "country"},
            "changed_by": "seed",
            "change_source": "bulk_import",
            "change_reason": "Seed enhancement — Singapore jurisdiction added",
            "source_reference": None,
            "created_at": datetime(2025, 6, 1, 12, 0, 2),
        },
        {
            "entity_type": "tax_rate",
            "entity_id": 20,
            "action": "create",
            "old_values": None,
            "new_values": {"jurisdiction": "GB", "category": "vat_standard", "rate_value": 0.20, "status": "active"},
            "changed_by": "seed",
            "change_source": "bulk_import",
            "change_reason": "Seed enhancement — UK VAT 20% on accommodation",
            "source_reference": "Value Added Tax Act 1994",
            "created_at": datetime(2025, 6, 1, 12, 5, 0),
        },
        {
            "entity_type": "tax_rate",
            "entity_id": 21,
            "action": "create",
            "old_values": None,
            "new_values": {"jurisdiction": "SG", "category": "vat_standard", "rate_value": 0.09, "status": "active"},
            "changed_by": "seed",
            "change_source": "bulk_import",
            "change_reason": "Seed enhancement — Singapore GST 9%",
            "source_reference": "Goods and Services Tax Act 1993",
            "created_at": datetime(2025, 6, 1, 12, 5, 1),
        },
        {
            "entity_type": "tax_rate",
            "entity_id": 22,
            "action": "create",
            "old_values": None,
            "new_values": {"jurisdiction": "PT-11-LIS", "category": "tourism_flat_person_night", "rate_value": 2.00, "status": "active"},
            "changed_by": "seed",
            "change_source": "bulk_import",
            "change_reason": "Seed enhancement — Lisbon tourist tax EUR 2/person/night",
            "source_reference": "Regulamento Municipal da Taxa Turistica de Lisboa",
            "created_at": datetime(2025, 6, 1, 12, 5, 2),
        },
        {
            "entity_type": "tax_rule",
            "entity_id": 10,
            "action": "create",
            "old_values": None,
            "new_values": {"name": "Lisbon Tourist Tax 7-Night Cap", "jurisdiction": "PT-11-LIS", "rule_type": "cap"},
            "changed_by": "seed",
            "change_source": "bulk_import",
            "change_reason": "Seed enhancement — Lisbon 7-night cap rule",
            "source_reference": "Regulamento Municipal da Taxa Turistica de Lisboa",
            "created_at": datetime(2025, 6, 1, 12, 10, 0),
        },
        {
            "entity_type": "tax_rule",
            "entity_id": 11,
            "action": "create",
            "old_values": None,
            "new_values": {"name": "Vienna Minors Exemption (under 15)", "jurisdiction": "AT-9-VIE", "rule_type": "exemption"},
            "changed_by": "seed",
            "change_source": "bulk_import",
            "change_reason": "Seed enhancement — Vienna under-15 exemption",
            "source_reference": "Wiener Tourismusforderungsgesetz",
            "created_at": datetime(2025, 6, 1, 12, 10, 1),
        },
        {
            "entity_type": "monitored_source",
            "entity_id": 5,
            "action": "create",
            "old_values": None,
            "new_values": {"url": "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)", "source_type": "tax_authority"},
            "changed_by": "admin@taxlens.io",
            "change_source": "api",
            "change_reason": "Added Singapore IRAS as monitored source",
            "source_reference": None,
            "created_at": datetime(2025, 7, 10, 11, 0, 0),
        },
        {
            "entity_type": "monitored_source",
            "entity_id": 6,
            "action": "url_update",
            "old_values": {"url": "https://www.comune.roma.it/web/it/tassa-soggiorno.page"},
            "new_values": {"url": "https://www.comune.roma.it/web/it/informazione-di-servizio.page"},
            "changed_by": "admin@taxlens.io",
            "change_source": "manual_review",
            "change_reason": "Rome city tax page URL updated after website restructure",
            "source_reference": None,
            "created_at": datetime(2025, 9, 22, 14, 0, 0),
        },
    ]

    for ld in log_defs:
        log = AuditLog(**ld)
        db.add(log)
        logs.append(log)

    await db.flush()
    return logs


# ──────────────────────────────────────────────────────────────────────
# Main seed runner
# ──────────────────────────────────────────────────────────────────────

async def seed_enhancement(db: AsyncSession):
    """Run all enhancement seeds."""

    # Load existing categories
    print("Loading existing tax categories...")
    result = await db.execute(select(TaxCategory))
    categories = {c.code: c for c in result.scalars().all()}
    print(f"  {len(categories)} categories loaded")

    # 1. New jurisdictions
    print("\nSeeding new jurisdictions...")
    jurisdictions = await seed_new_jurisdictions(db)
    new_count = len([j for j in NEW_JURISDICTIONS if j["code"] in jurisdictions])
    print(f"  {new_count} new jurisdiction entries processed (some may already exist)")

    # 2. Tax rates for new jurisdictions
    print("\nSeeding tax rates for new jurisdictions:")
    all_rates = []

    print("  United Kingdom...")
    all_rates.extend(await seed_uk_rates(db, jurisdictions, categories))
    print("  Portugal / Lisbon...")
    all_rates.extend(await seed_portugal_rates(db, jurisdictions, categories))
    print("  Austria / Vienna...")
    all_rates.extend(await seed_austria_rates(db, jurisdictions, categories))
    print("  Czech Republic / Prague...")
    all_rates.extend(await seed_czech_rates(db, jurisdictions, categories))
    print("  Hungary / Budapest...")
    all_rates.extend(await seed_hungary_rates(db, jurisdictions, categories))
    print("  Singapore...")
    all_rates.extend(await seed_singapore_rates(db, jurisdictions, categories))
    print("  Australia / Sydney...")
    all_rates.extend(await seed_australia_rates(db, jurisdictions, categories))
    print("  Greece / Athens...")
    all_rates.extend(await seed_greece_rates(db, jurisdictions, categories))
    print("  Maldives...")
    all_rates.extend(await seed_maldives_rates(db, jurisdictions, categories))
    print("  Mexico / Mexico City...")
    all_rates.extend(await seed_mexico_rates(db, jurisdictions, categories))
    print("  Catalonia / Barcelona...")
    all_rates.extend(await seed_barcelona_rates(db, jurisdictions, categories))

    # 2b. Tax rates for existing jurisdictions without rates
    print("\nSeeding tax rates for existing jurisdictions:")
    print("  Los Angeles...")
    all_rates.extend(await seed_los_angeles_rates(db, jurisdictions, categories))
    print("  San Francisco...")
    all_rates.extend(await seed_san_francisco_rates(db, jurisdictions, categories))
    print("  Miami-Dade...")
    all_rates.extend(await seed_miami_rates(db, jurisdictions, categories))
    print("  Houston...")
    all_rates.extend(await seed_houston_rates(db, jurisdictions, categories))
    print("  Honolulu...")
    all_rates.extend(await seed_honolulu_rates(db, jurisdictions, categories))
    print("  Bangkok...")
    all_rates.extend(await seed_bangkok_rates(db, jurisdictions, categories))
    print("  Bali...")
    all_rates.extend(await seed_bali_rates(db, jurisdictions, categories))
    print("  Kyoto...")
    all_rates.extend(await seed_kyoto_rates(db, jurisdictions, categories))

    print(f"\n  Total rates processed: {len(all_rates)}")

    # 3. Rules
    print("\nSeeding tax rules (exemptions, caps, reductions)...")
    rules = await seed_enhancement_rules(db, jurisdictions)
    print(f"  {len(rules)} rules processed")

    # 4. Monitored sources
    print("\nSeeding monitored sources...")
    sources = await seed_monitored_sources(db, jurisdictions)
    print(f"  {len(sources)} sources processed")

    # 5. Detected changes
    print("\nSeeding detected changes...")
    changes = await seed_detected_changes(db, jurisdictions, sources)
    print(f"  {len(changes)} detected changes processed")

    # 6. Audit logs
    print("\nSeeding audit log entries...")
    logs = await seed_audit_logs(db, jurisdictions)
    print(f"  {len(logs)} audit log entries created")

    # Commit everything
    await db.commit()

    print(f"\n{'=' * 60}")
    print("Seed enhancement complete!")
    print(f"  Jurisdictions: {len(jurisdictions)} total (incl. existing)")
    print(f"  Tax rates:     {len(all_rates)}")
    print(f"  Tax rules:     {len(rules)}")
    print(f"  Sources:       {len(sources)}")
    print(f"  Changes:       {len(changes)}")
    print(f"  Audit logs:    {len(logs)}")
    print(f"{'=' * 60}")


async def main():
    async with async_session_factory() as db:
        await seed_enhancement(db)


if __name__ == "__main__":
    asyncio.run(main())
