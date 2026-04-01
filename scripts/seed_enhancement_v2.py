"""
Seed data v2: 15 tricky global tax rules for TaxLens.

Adds challenging edge cases from smaller/unusual jurisdictions that
demonstrate capabilities other platforms can't match:
  - Age-graduated reductions (Croatia)
  - Per-stay entry taxes (NZ, Cancún)
  - Zero-decimal currency rounding (Iceland ISK, Japan JPY)
  - Anti-compounding rules (Malaysia)
  - Nationality-based exemptions (Bhutan)
  - Future-dated scheduled rates (Edinburgh)
  - Municipal fragmentation (3 Italian cities, 2 Croatian cities)
  - Platform-specific surcharges (Denver)
  - Seasonal + duration compound reductions (Palma)

Must be run AFTER seed_data.py and seed_enhancement.py.

Usage:
    cd tax-monitoring
    .venv/bin/python -m scripts.seed_enhancement_v2
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
# Helpers (same patterns as seed_enhancement.py)
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


async def _lookup(db: AsyncSession, model, field: str, value):
    result = await db.execute(select(model).where(getattr(model, field) == value))
    return result.scalar_one_or_none()


# ──────────────────────────────────────────────────────────────────────
# New Jurisdictions
# ──────────────────────────────────────────────────────────────────────

NEW_JURISDICTIONS = [
    # ── Croatia ──
    {"code": "HR", "name": "Croatia", "jurisdiction_type": "country", "path": "HR", "parent_code": None, "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},
    {"code": "HR-19", "name": "Dubrovnik-Neretva County", "jurisdiction_type": "state", "path": "HR.19", "parent_code": "HR", "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},
    {"code": "HR-19-DBV", "name": "Dubrovnik", "local_name": "Grad Dubrovnik", "jurisdiction_type": "city", "path": "HR.19.DBV", "parent_code": "HR-19", "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},
    {"code": "HR-21", "name": "Split-Dalmatia County", "jurisdiction_type": "state", "path": "HR.21", "parent_code": "HR", "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},
    {"code": "HR-21-SPU", "name": "Split", "local_name": "Grad Split", "jurisdiction_type": "city", "path": "HR.21.SPU", "parent_code": "HR-21", "country_code": "HR", "timezone": "Europe/Zagreb", "currency_code": "EUR"},

    # ── Switzerland ──
    {"code": "CH", "name": "Switzerland", "local_name": "Schweiz / Suisse / Svizzera", "jurisdiction_type": "country", "path": "CH", "parent_code": None, "country_code": "CH", "timezone": "Europe/Zurich", "currency_code": "CHF"},
    {"code": "CH-BE", "name": "Canton of Bern", "local_name": "Kanton Bern", "jurisdiction_type": "state", "path": "CH.BE", "parent_code": "CH", "country_code": "CH", "timezone": "Europe/Zurich", "currency_code": "CHF"},
    {"code": "CH-BE-INT", "name": "Interlaken", "jurisdiction_type": "city", "path": "CH.BE.INT", "parent_code": "CH-BE", "country_code": "CH", "timezone": "Europe/Zurich", "currency_code": "CHF"},

    # ── Belgium ──
    {"code": "BE", "name": "Belgium", "local_name": "België / Belgique", "jurisdiction_type": "country", "path": "BE", "parent_code": None, "country_code": "BE", "timezone": "Europe/Brussels", "currency_code": "EUR"},
    {"code": "BE-BRU", "name": "Brussels-Capital Region", "local_name": "Région de Bruxelles-Capitale", "jurisdiction_type": "state", "path": "BE.BRU", "parent_code": "BE", "country_code": "BE", "timezone": "Europe/Brussels", "currency_code": "EUR"},
    {"code": "BE-BRU-BXL", "name": "Brussels", "local_name": "Bruxelles / Brussel", "jurisdiction_type": "city", "path": "BE.BRU.BXL", "parent_code": "BE-BRU", "country_code": "BE", "timezone": "Europe/Brussels", "currency_code": "EUR"},

    # ── Iceland ──
    {"code": "IS", "name": "Iceland", "local_name": "Ísland", "jurisdiction_type": "country", "path": "IS", "parent_code": None, "country_code": "IS", "timezone": "Atlantic/Reykjavik", "currency_code": "ISK"},
    {"code": "IS-1", "name": "Capital Region", "local_name": "Höfuðborgarsvæðið", "jurisdiction_type": "state", "path": "IS.1", "parent_code": "IS", "country_code": "IS", "timezone": "Atlantic/Reykjavik", "currency_code": "ISK"},
    {"code": "IS-1-REY", "name": "Reykjavik", "local_name": "Reykjavík", "jurisdiction_type": "city", "path": "IS.1.REY", "parent_code": "IS-1", "country_code": "IS", "timezone": "Atlantic/Reykjavik", "currency_code": "ISK"},

    # ── Italy — Florence ──
    {"code": "IT-FI", "name": "Florence Metropolitan Area", "local_name": "Città Metropolitana di Firenze", "jurisdiction_type": "state", "path": "IT.FI", "parent_code": "IT", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-FI-FLR", "name": "Florence", "local_name": "Firenze", "jurisdiction_type": "city", "path": "IT.FI.FLR", "parent_code": "IT-FI", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},

    # ── Italy — Milan ──
    {"code": "IT-MI", "name": "Milan Metropolitan Area", "local_name": "Città Metropolitana di Milano", "jurisdiction_type": "state", "path": "IT.MI", "parent_code": "IT", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},
    {"code": "IT-MI-MIL", "name": "Milan", "local_name": "Milano", "jurisdiction_type": "city", "path": "IT.MI.MIL", "parent_code": "IT-MI", "country_code": "IT", "timezone": "Europe/Rome", "currency_code": "EUR"},

    # ── Scotland — Edinburgh ──
    {"code": "GB-SCT", "name": "Scotland", "jurisdiction_type": "state", "path": "GB.SCT", "parent_code": "GB", "country_code": "GB", "timezone": "Europe/London", "currency_code": "GBP"},
    {"code": "GB-SCT-EDI", "name": "Edinburgh", "jurisdiction_type": "city", "path": "GB.SCT.EDI", "parent_code": "GB-SCT", "country_code": "GB", "timezone": "Europe/London", "currency_code": "GBP"},

    # ── Japan — Beppu ──
    {"code": "JP-44", "name": "Oita Prefecture", "local_name": "大分県", "jurisdiction_type": "state", "path": "JP.44", "parent_code": "JP", "country_code": "JP", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-44-BPU", "name": "Beppu", "local_name": "別府市", "jurisdiction_type": "city", "path": "JP.44.BPU", "parent_code": "JP-44", "country_code": "JP", "timezone": "Asia/Tokyo", "currency_code": "JPY"},

    # ── Mexico — Cancún ──
    {"code": "MX-ROO", "name": "Quintana Roo", "jurisdiction_type": "state", "path": "MX.ROO", "parent_code": "MX", "country_code": "MX", "timezone": "America/Cancun", "currency_code": "MXN"},
    {"code": "MX-ROO-CUN", "name": "Cancún", "jurisdiction_type": "city", "path": "MX.ROO.CUN", "parent_code": "MX-ROO", "country_code": "MX", "timezone": "America/Cancun", "currency_code": "MXN"},

    # ── Malaysia ──
    {"code": "MY", "name": "Malaysia", "jurisdiction_type": "country", "path": "MY", "parent_code": None, "country_code": "MY", "timezone": "Asia/Kuala_Lumpur", "currency_code": "MYR"},
    {"code": "MY-14", "name": "KL Federal Territory", "local_name": "Wilayah Persekutuan Kuala Lumpur", "jurisdiction_type": "state", "path": "MY.14", "parent_code": "MY", "country_code": "MY", "timezone": "Asia/Kuala_Lumpur", "currency_code": "MYR"},
    {"code": "MY-14-KUL", "name": "Kuala Lumpur", "jurisdiction_type": "city", "path": "MY.14.KUL", "parent_code": "MY-14", "country_code": "MY", "timezone": "Asia/Kuala_Lumpur", "currency_code": "MYR"},

    # ── Spain — Palma de Mallorca (under existing ES-IB) ──
    {"code": "ES-IB-PMI", "name": "Palma de Mallorca", "local_name": "Palma", "jurisdiction_type": "city", "path": "ES.IB.PMI", "parent_code": "ES-IB", "country_code": "ES", "timezone": "Europe/Madrid", "currency_code": "EUR"},

    # ── New Zealand ──
    {"code": "NZ", "name": "New Zealand", "local_name": "Aotearoa", "jurisdiction_type": "country", "path": "NZ", "parent_code": None, "country_code": "NZ", "timezone": "Pacific/Auckland", "currency_code": "NZD"},

    # ── USA — Denver ──
    {"code": "US-CO", "name": "Colorado", "jurisdiction_type": "state", "path": "US.CO", "parent_code": "US", "country_code": "US", "timezone": "America/Denver", "currency_code": "USD"},
    {"code": "US-CO-DEN", "name": "Denver", "jurisdiction_type": "city", "path": "US.CO.DEN", "parent_code": "US-CO", "country_code": "US", "timezone": "America/Denver", "currency_code": "USD"},

    # ── Bhutan ──
    {"code": "BT", "name": "Bhutan", "local_name": "འབྲུག་ཡུལ", "jurisdiction_type": "country", "path": "BT", "parent_code": None, "country_code": "BT", "timezone": "Asia/Thimphu", "currency_code": "USD"},
]


async def seed_jurisdictions(db: AsyncSession) -> dict[str, Jurisdiction]:
    """Seed new jurisdictions, resolving parent references."""
    jurisdictions = {}

    # Pre-load existing
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
# Tax Rates & Rules — 15 tricky scenarios
# ──────────────────────────────────────────────────────────────────────

async def seed_all_rates_and_rules(
    db: AsyncSession,
    j: dict[str, Jurisdiction],
    c: dict[str, TaxCategory],
):
    """Seed all 15 tricky tax rate/rule combinations."""

    # ── 1. Dubrovnik, Croatia — Age-graduated tourist tax ──
    dbv_rate = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["HR-19-DBV"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 1.86,
        "currency_code": "EUR",
        "effective_start": date(2025, 4, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Zakon o boravišnoj pristojbi, NN 152/2008 — Dubrovnik A-category municipality, 4-5 star",
        "source_url": "https://narodne-novine.nn.hr/clanci/sluzbeni/2008_12_152_4145.html",
        "authority_name": "Croatian Ministry of Tourism",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": dbv_rate.id,
        "jurisdiction_id": j["HR-19-DBV"].id,
        "rule_type": "exemption",
        "priority": 100,
        "name": "Children Under 12 Exemption",
        "description": "Children under 12 are fully exempt from tourist tax in Croatia",
        "conditions": {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 12}]},
        "action": {},
        "effective_start": date(2025, 1, 1),
        "legal_reference": "Zakon o boravišnoj pristojbi, čl. 4, st. 2",
        "authority_name": "Croatian Ministry of Tourism",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": dbv_rate.id,
        "jurisdiction_id": j["HR-19-DBV"].id,
        "rule_type": "reduction",
        "priority": 90,
        "name": "Youth 50% Reduction (Ages 12-17)",
        "description": "Guests aged 12-17 pay 50% of the standard tourist tax rate",
        "conditions": {"operator": "AND", "rules": [{"field": "guest_age", "op": "between", "value": [12, 17]}]},
        "action": {"reduction_percent": 0.5},
        "effective_start": date(2025, 1, 1),
        "legal_reference": "Zakon o boravišnoj pristojbi, čl. 4, st. 3",
        "authority_name": "Croatian Ministry of Tourism",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Dubrovnik — age-graduated tourist tax + child exemption + youth reduction")

    # ── 2. Interlaken, Switzerland — Municipal Kurtaxe ──
    int_rate = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["CH-BE-INT"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 4.20,
        "currency_code": "CHF",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Tourismusgesetz Kanton Bern, BSG 935.21 — Interlaken Kurtaxe (Gästetaxe)",
        "source_url": "https://www.belex.sites.be.ch/app/de/texts_of_law/935.21",
        "authority_name": "Gemeinde Interlaken",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": int_rate.id,
        "jurisdiction_id": j["CH-BE-INT"].id,
        "rule_type": "exemption",
        "priority": 100,
        "name": "Children Under 6 Exemption",
        "description": "Children under 6 are exempt from Kurtaxe in Interlaken",
        "conditions": {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 6}]},
        "action": {},
        "effective_start": date(2024, 1, 1),
        "legal_reference": "Tourismusgesetz Kanton Bern, Art. 14 Abs. 2",
        "authority_name": "Gemeinde Interlaken",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Interlaken — CHF 4.20 Kurtaxe + child exemption")

    # ── 3. Brussels, Belgium — Per-room flat fee ──
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["BE-BRU-BXL"].id,
        "tax_category_id": c["occ_flat_night"].id,
        "rate_type": "flat",
        "rate_value": 4.24,
        "currency_code": "EUR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Brussels City Tax — per occupied room per night (not per person)",
        "source_url": "https://fiscalite.brussels/taxe-regionale-hebergements-touristiques",
        "authority_name": "Brussels-Capital Region",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Brussels — €4.24/room/night (per-room, NOT per-person)")

    # ── 4. Reykjavik, Iceland — ISK zero-decimal + 28-night cap ──
    rey_rate = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["IS-1-REY"].id,
        "tax_category_id": c["occ_flat_night"].id,
        "rate_type": "flat",
        "rate_value": 600,
        "currency_code": "ISK",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Lög um gistináttaskatt, No. 87/2011 — ISK 600 per room per night",
        "source_url": "https://www.althingi.is/lagas/nuna/2011087.html",
        "authority_name": "Ríkisskattstjóri (Directorate of Internal Revenue)",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": rey_rate.id,
        "jurisdiction_id": j["IS-1-REY"].id,
        "rule_type": "cap",
        "priority": 50,
        "name": "28-Night Lodging Tax Cap",
        "description": "Lodging tax is capped at 28 consecutive nights per stay",
        "conditions": {},
        "action": {"max_nights": 28},
        "effective_start": date(2024, 1, 1),
        "legal_reference": "Lög um gistináttaskatt, 4. gr.",
        "authority_name": "Ríkisskattstjóri",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Reykjavik — ISK 600/night + 28-night cap (zero-decimal currency)")

    # ── 5. Florence, Italy — Star-tiered + 7-night cap ──
    flr_rate = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["IT-FI-FLR"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "EUR",
        "tiers": [
            {"min": 1, "max": 2, "value": 2.00},
            {"min": 2, "max": 3, "value": 3.00},
            {"min": 3, "max": 4, "value": 4.50},
            {"min": 4, "max": 5, "value": 5.50},
            {"min": 5, "value": 8.00},
        ],
        "tier_type": "single_amount",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Delibera Consiglio Comunale di Firenze n. 2023/C/00076",
        "source_url": "https://www.comune.fi.it/pagina/imposta-di-soggiorno",
        "authority_name": "Comune di Firenze",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": flr_rate.id,
        "jurisdiction_id": j["IT-FI-FLR"].id,
        "rule_type": "cap",
        "priority": 50,
        "name": "Florence 7-Night City Tax Cap",
        "description": "Imposta di soggiorno capped at 7 consecutive nights (vs Rome 10, Milan 14)",
        "conditions": {},
        "action": {"max_nights": 7},
        "effective_start": date(2024, 1, 1),
        "legal_reference": "Delibera Consiglio Comunale di Firenze n. 2023/C/00076, Art. 5",
        "authority_name": "Comune di Firenze",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Florence — star-tiered €2-€8/person/night + 7-night cap")

    # ── 6. Edinburgh, Scotland — Transient Visitor Levy (scheduled 2026) ──
    edi_rate = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["GB-SCT-EDI"].id,
        "tax_category_id": c["tourism_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.05,
        "currency_code": "GBP",
        "effective_start": date(2026, 7, 24),
        "enacted_date": date(2024, 10, 2),
        "announcement_date": date(2024, 3, 15),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Visitor Levy (Scotland) Act 2024, asp 14 — 5% of accommodation charge",
        "legal_uri": "https://www.legislation.gov.uk/asp/2024/14",
        "source_url": "https://www.edinburgh.gov.uk/visitorlevy",
        "authority_name": "City of Edinburgh Council",
        "status": "scheduled",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": edi_rate.id,
        "jurisdiction_id": j["GB-SCT-EDI"].id,
        "rule_type": "exemption",
        "priority": 100,
        "name": "Long-Stay Exemption (28+ nights)",
        "description": "Stays of 28+ consecutive nights are exempt from the visitor levy",
        "conditions": {"operator": "AND", "rules": [{"field": "stay_length_days", "op": ">=", "value": 28}]},
        "action": {},
        "effective_start": date(2026, 7, 24),
        "legal_reference": "Visitor Levy (Scotland) Act 2024, Section 7(2)",
        "authority_name": "City of Edinburgh Council",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Edinburgh — 5% visitor levy (scheduled Jul 2026) + 28-night exemption")

    # ── 7. Beppu, Japan — Onsen bathing tax ──
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["JP-44-BPU"].id,
        "tax_category_id": c["onsen_tier_price"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "JPY",
        "tiers": [
            {"min": 0, "max": 16000, "value": 250},
            {"min": 16000, "max": 50000, "value": 500},
            {"min": 50000, "value": 750},
        ],
        "tier_type": "single_amount",
        "effective_start": date(2025, 4, 1),
        "calculation_order": 200,
        "base_includes": ["base_amount"],
        "legal_reference": "別府市入湯税条例 (Beppu City Bathing Tax Ordinance), revised 2025",
        "source_url": "https://www.city.beppu.oita.jp/",
        "authority_name": "Beppu City Government",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Beppu — onsen tax ¥250/500/750 tiered by room price (JPY 0-decimal)")

    # ── 8. Cancún, Mexico — Environmental fee (per_stay!) + state lodging tax ──
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["MX-ROO"].id,
        "tax_category_id": c["occ_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.03,
        "currency_code": "MXN",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 50,
        "base_includes": ["base_amount"],
        "legal_reference": "Ley del Impuesto al Hospedaje del Estado de Quintana Roo — 3% state lodging tax",
        "authority_name": "Estado de Quintana Roo",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["MX-ROO-CUN"].id,
        "tax_category_id": c["entry_flat_person_stay"].id,
        "rate_type": "flat",
        "rate_value": 224,
        "currency_code": "MXN",
        "effective_start": date(2025, 1, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Cancún Municipal Environmental Fee — MXN 224 per person per stay (one-time)",
        "source_url": "https://www.cancun.gob.mx/",
        "authority_name": "Municipio de Benito Juárez (Cancún)",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Cancún — 3% state lodging + MXN 224/person one-time entry fee (per_stay!)")

    # ── 9. Kuala Lumpur, Malaysia — Anti-compounding ──
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["MY"].id,
        "tax_category_id": c["tourism_flat_night"].id,
        "rate_type": "flat",
        "rate_value": 10,
        "currency_code": "MYR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Tourism Tax Act 2017 (Act 791) — MYR 10 per room per night",
        "legal_uri": "https://www.federalgazette.agc.gov.my/outputaktap/aktaBI_20170911_Act791-BI.pdf",
        "authority_name": "Royal Malaysian Customs Department",
        "status": "active",
        "created_by": "seed",
    })
    # SST: 8% but base_includes ONLY base_amount (NOT tourism tax) = anti-compounding
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["MY"].id,
        "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage",
        "rate_value": 0.08,
        "currency_code": "MYR",
        "effective_start": date(2024, 3, 1),
        "calculation_order": 200,
        "base_includes": ["base_amount"],  # Explicitly NOT including tourism_flat_night!
        "legal_reference": "Service Tax Act 2018 — 8% SST (service tax NOT applied on tourism tax amount)",
        "authority_name": "Royal Malaysian Customs Department",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Kuala Lumpur — MYR 10 tourism tax + 8% SST (anti-compounding: SST NOT on TTx)")

    # ── 10. Palma de Mallorca — Ecotax with seasonal reduction ──
    pmi_rate = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["ES-IB-PMI"].id,
        "tax_category_id": c["eco_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 4.00,
        "currency_code": "EUR",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Ley 2/2016, de 30 de marzo — Impuesto sobre Estancias Turísticas (IET), €4/person/night peak",
        "source_url": "https://www.caib.es/sites/impostestades/es/normativa/",
        "authority_name": "Govern de les Illes Balears",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": pmi_rate.id,
        "jurisdiction_id": j["ES-IB-PMI"].id,
        "rule_type": "reduction",
        "priority": 80,
        "name": "Off-Season 75% Discount (Nov-Mar)",
        "description": "75% reduction on ecotax during winter months (November through March)",
        "conditions": {"operator": "OR", "rules": [
            {"field": "stay_month", "op": ">=", "value": 11},
            {"field": "stay_month", "op": "<=", "value": 3},
        ]},
        "action": {"reduction_percent": 0.75},
        "effective_start": date(2024, 1, 1),
        "legal_reference": "Ley 2/2016, Art. 18 — temporada baja",
        "authority_name": "Govern de les Illes Balears",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": pmi_rate.id,
        "jurisdiction_id": j["ES-IB-PMI"].id,
        "rule_type": "reduction",
        "priority": 70,
        "name": "Long-Stay 50% Discount (9+ nights)",
        "description": "50% reduction on ecotax for stays exceeding 8 nights",
        "conditions": {"operator": "AND", "rules": [{"field": "stay_length_days", "op": ">", "value": 8}]},
        "action": {"reduction_percent": 0.5},
        "effective_start": date(2024, 1, 1),
        "legal_reference": "Ley 2/2016, Art. 19 — estancias de larga duración",
        "authority_name": "Govern de les Illes Balears",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Palma — €4 ecotax + 75% off-season (Nov-Mar) + 50% long-stay (9+ nights)")

    # ── 11. Milan, Italy — Wide star spread + 14-night cap ──
    mil_rate = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["IT-MI-MIL"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "tiered",
        "rate_value": None,
        "currency_code": "EUR",
        "tiers": [
            {"min": 1, "max": 2, "value": 2.00},
            {"min": 2, "max": 3, "value": 3.00},
            {"min": 3, "max": 4, "value": 4.00},
            {"min": 4, "max": 5, "value": 5.00},
            {"min": 5, "value": 10.00},
        ],
        "tier_type": "single_amount",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Regolamento Imposta di Soggiorno del Comune di Milano — €2-€10/person/night by star",
        "source_url": "https://www.comune.milano.it/servizi/imposta-di-soggiorno",
        "authority_name": "Comune di Milano",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": mil_rate.id,
        "jurisdiction_id": j["IT-MI-MIL"].id,
        "rule_type": "cap",
        "priority": 50,
        "name": "Milan 14-Night City Tax Cap",
        "description": "Imposta di soggiorno capped at 14 consecutive nights",
        "conditions": {},
        "action": {"max_nights": 14},
        "effective_start": date(2024, 1, 1),
        "legal_reference": "Regolamento Imposta di Soggiorno, Art. 4",
        "authority_name": "Comune di Milano",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Milan — star-tiered €2-€10 (5x spread!) + 14-night cap")

    # ── 12. New Zealand — One-time IVL entry tax (per_stay!) ──
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["NZ"].id,
        "tax_category_id": c["entry_flat_person_stay"].id,
        "rate_type": "flat",
        "rate_value": 100,
        "currency_code": "NZD",
        "effective_start": date(2024, 10, 1),
        "calculation_order": 50,
        "base_includes": ["base_amount"],
        "legal_reference": "International Visitor Conservation and Tourism Levy (IVL) — NZD 100 per person, one-time",
        "legal_uri": "https://www.legislation.govt.nz/regulation/public/2010/0241/latest/DLM3142843.html",
        "source_url": "https://www.immigration.govt.nz/new-zealand-visas/preparing-a-visa-application/your-journey-to-new-zealand/before-you-travel-to-new-zealand/paying-the-international-visitor-levy",
        "authority_name": "Immigration New Zealand",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ New Zealand — NZD 100 one-time IVL per person (per_stay, not per_night!)")

    # ── 13. Denver, Colorado — Lodging tax + platform surcharge ──
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["US-CO"].id,
        "tax_category_id": c["occ_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.04,
        "currency_code": "USD",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 10,
        "base_includes": ["base_amount"],
        "legal_reference": "Colorado Lodging Tax — 4% state-level, CRS §39-26-102(16)",
        "authority_name": "Colorado Department of Revenue",
        "status": "active",
        "created_by": "seed",
    })
    den_rate = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["US-CO-DEN"].id,
        "tax_category_id": c["occ_pct"].id,
        "rate_type": "percentage",
        "rate_value": 0.1075,
        "currency_code": "USD",
        "effective_start": date(2024, 1, 1),
        "calculation_order": 20,
        "base_includes": ["base_amount"],
        "legal_reference": "Denver Lodging Tax — 10.75% city-level, DRMC §53-251",
        "source_url": "https://www.denvergov.org/Government/Agencies-Departments-Offices/Agencies-Departments-Offices-Directory/Department-of-Finance/Our-Divisions/Treasury/Tax-Audit/Tax-Guide/Lodgers-Tax",
        "authority_name": "City and County of Denver",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": den_rate.id,
        "jurisdiction_id": j["US-CO-DEN"].id,
        "rule_type": "surcharge",
        "priority": 50,
        "name": "STR Platform Surcharge (+2%)",
        "description": "Additional 2% surcharge for short-term rentals booked through online platforms",
        "conditions": {"operator": "AND", "rules": [
            {"field": "property_type", "op": "==", "value": "short_term_rental"},
            {"field": "is_marketplace", "op": "==", "value": True},
        ]},
        "action": {"rate_value": 0.02},
        "effective_start": date(2024, 7, 1),
        "legal_reference": "Colorado HB 23-1164 — Short-term Rental Platform Tax",
        "authority_name": "City and County of Denver",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Denver — 4% state + 10.75% city + 2% STR platform surcharge")

    # ── 14. Split, Croatia — Different rate from Dubrovnik ──
    spu_rate = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["HR-21-SPU"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 1.33,
        "currency_code": "EUR",
        "effective_start": date(2025, 4, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Zakon o boravišnoj pristojbi, NN 152/2008 — Split B-category municipality, 3-4 star",
        "authority_name": "Croatian Ministry of Tourism",
        "status": "active",
        "created_by": "seed",
    })
    # Same national exemption rules apply
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": spu_rate.id,
        "jurisdiction_id": j["HR-21-SPU"].id,
        "rule_type": "exemption",
        "priority": 100,
        "name": "Children Under 12 Exemption",
        "description": "Children under 12 are fully exempt (national Croatian law)",
        "conditions": {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 12}]},
        "action": {},
        "effective_start": date(2025, 1, 1),
        "legal_reference": "Zakon o boravišnoj pristojbi, čl. 4, st. 2",
        "authority_name": "Croatian Ministry of Tourism",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": spu_rate.id,
        "jurisdiction_id": j["HR-21-SPU"].id,
        "rule_type": "reduction",
        "priority": 90,
        "name": "Youth 50% Reduction (Ages 12-17)",
        "description": "Guests aged 12-17 pay 50% (national Croatian law)",
        "conditions": {"operator": "AND", "rules": [{"field": "guest_age", "op": "between", "value": [12, 17]}]},
        "action": {"reduction_percent": 0.5},
        "effective_start": date(2025, 1, 1),
        "legal_reference": "Zakon o boravišnoj pristojbi, čl. 4, st. 3",
        "authority_name": "Croatian Ministry of Tourism",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Split — €1.33/person/night (vs Dubrovnik €1.86) + same age rules")

    # ── 15. Bhutan — $100/day SDF + nationality exemption ──
    bt_rate = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["BT"].id,
        "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat",
        "rate_value": 100,
        "currency_code": "USD",
        "effective_start": date(2023, 9, 1),
        "calculation_order": 100,
        "base_includes": ["base_amount"],
        "legal_reference": "Tourism Levy Act of Bhutan 2022, Section 4 — USD 100/person/day Sustainable Development Fee",
        "source_url": "https://www.tourism.gov.bt/",
        "authority_name": "Tourism Council of Bhutan",
        "status": "active",
        "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "tax_rate_id": bt_rate.id,
        "jurisdiction_id": j["BT"].id,
        "rule_type": "exemption",
        "priority": 100,
        "name": "SAARC Neighbor Exemption",
        "description": "Citizens of India, Bangladesh, and Maldives are exempt from the SDF",
        "conditions": {"operator": "AND", "rules": [
            {"field": "guest_nationality", "op": "in", "value": ["IN", "BD", "MV"]}
        ]},
        "action": {},
        "effective_start": date(2023, 9, 1),
        "legal_reference": "Tourism Levy Act of Bhutan 2022, Section 5(a) — SAARC regional exemption",
        "authority_name": "Tourism Council of Bhutan",
        "status": "active",
        "created_by": "seed",
    })
    print("  ✓ Bhutan — $100/person/night SDF + SAARC nationality exemption")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

async def main():
    print("\n🌍 TaxLens Seed Enhancement v2 — 15 Tricky Global Tax Rules\n")

    async with async_session_factory() as db:
        # Load categories
        result = await db.execute(select(TaxCategory))
        categories = {c.code: c for c in result.scalars().all()}
        print(f"  Loaded {len(categories)} tax categories")

        # Check for new categories we need
        for needed in ["entry_flat_person_stay", "entry_flat_stay", "onsen_tier_price"]:
            if needed not in categories:
                print(f"  ⚠ Missing category '{needed}' — run seed_data.py first to add it")
                return

        # Seed jurisdictions
        print("\n📍 Seeding jurisdictions...")
        jurisdictions = await seed_jurisdictions(db)
        print(f"  Total: {len(jurisdictions)} jurisdictions")

        # Seed rates & rules
        print("\n💰 Seeding tax rates & rules...\n")
        await seed_all_rates_and_rules(db, jurisdictions, categories)

        await db.commit()

    print("\n✅ Done! Added 15 tricky tax rules from 7 new countries.\n")
    print("   Key features tested:")
    print("   • Age-graduated reductions (Croatia)")
    print("   • Per-stay entry taxes (NZ, Cancún)")
    print("   • Zero-decimal currencies (ISK, JPY)")
    print("   • Anti-compounding (Malaysia)")
    print("   • Nationality exemptions (Bhutan)")
    print("   • Future-dated scheduled rates (Edinburgh)")
    print("   • Platform surcharges (Denver)")
    print("   • Municipal fragmentation (3 Italian cities)")
    print("   • Seasonal + duration reductions (Palma)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
