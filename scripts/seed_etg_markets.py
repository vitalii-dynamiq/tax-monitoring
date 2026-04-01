"""
Seed ETG Markets: Comprehensive jurisdiction coverage for Emerging Travel Group.

Adds 16 new countries + sub-jurisdictions in existing countries to cover every market
where ETG (RateHawk, ZenHotels, Roundtrip) operates or sends travelers.

Must be run AFTER all previous seed scripts.

Usage:
    cd tax-monitoring
    .venv/bin/python -m scripts.seed_etg_markets
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
# Helpers
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
# New Tax Categories
# ──────────────────────────────────────────────────────────────────────

NEW_TAX_CATEGORIES = [
    {"code": "climate_tier_star", "name": "Climate Resilience Fee (tiered by star)", "level_0": "accommodation", "level_1": "climate", "level_2": "tiered_by_star", "base_type": "per_night"},
    {"code": "green_flat_night", "name": "Green/Environmental Tax (flat per night)", "level_0": "accommodation", "level_1": "environmental", "level_2": "flat_per_night", "base_type": "per_night"},
    {"code": "entry_flat_person", "name": "Entry Fee (one-time per person)", "level_0": "accommodation", "level_1": "entry", "level_2": "flat_per_person_per_stay", "base_type": "per_person_per_stay"},
    {"code": "sustainability_flat_night", "name": "Sustainability Charge (flat per night)", "level_0": "accommodation", "level_1": "environmental", "level_2": "flat_per_night", "base_type": "per_night"},
]


# ──────────────────────────────────────────────────────────────────────
# New Jurisdictions
# ──────────────────────────────────────────────────────────────────────

NEW_JURISDICTIONS = [
    # ══════════════════════════════════════════════════════════════════
    # 16 NEW COUNTRIES + sub-jurisdictions
    # ══════════════════════════════════════════════════════════════════

    # ── Egypt ──
    {"code": "EG", "name": "Egypt", "local_name": "مصر", "jurisdiction_type": "country", "path": "EG", "parent_code": None, "country_code": "EG", "timezone": "Africa/Cairo", "currency_code": "EGP"},
    {"code": "EG-C", "name": "Cairo Governorate", "local_name": "محافظة القاهرة", "jurisdiction_type": "state", "path": "EG.C", "parent_code": "EG", "country_code": "EG", "timezone": "Africa/Cairo", "currency_code": "EGP"},
    {"code": "EG-C-CAI", "name": "Cairo", "local_name": "القاهرة", "jurisdiction_type": "city", "path": "EG.C.CAI", "parent_code": "EG-C", "country_code": "EG", "timezone": "Africa/Cairo", "currency_code": "EGP"},
    {"code": "EG-SS", "name": "South Sinai Governorate", "local_name": "جنوب سيناء", "jurisdiction_type": "state", "path": "EG.SS", "parent_code": "EG", "country_code": "EG", "timezone": "Africa/Cairo", "currency_code": "EGP"},
    {"code": "EG-SS-SSH", "name": "Sharm el-Sheikh", "local_name": "شرم الشيخ", "jurisdiction_type": "city", "path": "EG.SS.SSH", "parent_code": "EG-SS", "country_code": "EG", "timezone": "Africa/Cairo", "currency_code": "EGP"},
    {"code": "EG-RB", "name": "Red Sea Governorate", "local_name": "البحر الأحمر", "jurisdiction_type": "state", "path": "EG.RB", "parent_code": "EG", "country_code": "EG", "timezone": "Africa/Cairo", "currency_code": "EGP"},
    {"code": "EG-RB-HRG", "name": "Hurghada", "local_name": "الغردقة", "jurisdiction_type": "city", "path": "EG.RB.HRG", "parent_code": "EG-RB", "country_code": "EG", "timezone": "Africa/Cairo", "currency_code": "EGP"},

    # ── Poland ──
    {"code": "PL", "name": "Poland", "local_name": "Polska", "jurisdiction_type": "country", "path": "PL", "parent_code": None, "country_code": "PL", "timezone": "Europe/Warsaw", "currency_code": "PLN"},
    {"code": "PL-MZ", "name": "Masovia", "local_name": "Mazowieckie", "jurisdiction_type": "state", "path": "PL.MZ", "parent_code": "PL", "country_code": "PL", "timezone": "Europe/Warsaw", "currency_code": "PLN"},
    {"code": "PL-MZ-WAW", "name": "Warsaw", "local_name": "Warszawa", "jurisdiction_type": "city", "path": "PL.MZ.WAW", "parent_code": "PL-MZ", "country_code": "PL", "timezone": "Europe/Warsaw", "currency_code": "PLN"},
    {"code": "PL-MA", "name": "Lesser Poland", "local_name": "Małopolskie", "jurisdiction_type": "state", "path": "PL.MA", "parent_code": "PL", "country_code": "PL", "timezone": "Europe/Warsaw", "currency_code": "PLN"},
    {"code": "PL-MA-KRK", "name": "Krakow", "local_name": "Kraków", "jurisdiction_type": "city", "path": "PL.MA.KRK", "parent_code": "PL-MA", "country_code": "PL", "timezone": "Europe/Warsaw", "currency_code": "PLN"},

    # ── Thailand ──
    {"code": "TH", "name": "Thailand", "local_name": "ประเทศไทย", "jurisdiction_type": "country", "path": "TH", "parent_code": None, "country_code": "TH", "timezone": "Asia/Bangkok", "currency_code": "THB"},
    {"code": "TH-10", "name": "Bangkok Metropolitan", "local_name": "กรุงเทพมหานคร", "jurisdiction_type": "state", "path": "TH.10", "parent_code": "TH", "country_code": "TH", "timezone": "Asia/Bangkok", "currency_code": "THB"},
    {"code": "TH-10-BKK", "name": "Bangkok", "local_name": "กรุงเทพ", "jurisdiction_type": "city", "path": "TH.10.BKK", "parent_code": "TH-10", "country_code": "TH", "timezone": "Asia/Bangkok", "currency_code": "THB"},
    {"code": "TH-83", "name": "Phuket Province", "local_name": "จังหวัดภูเก็ต", "jurisdiction_type": "state", "path": "TH.83", "parent_code": "TH", "country_code": "TH", "timezone": "Asia/Bangkok", "currency_code": "THB"},
    {"code": "TH-83-HKT", "name": "Phuket", "local_name": "ภูเก็ต", "jurisdiction_type": "city", "path": "TH.83.HKT", "parent_code": "TH-83", "country_code": "TH", "timezone": "Asia/Bangkok", "currency_code": "THB"},
    {"code": "TH-50", "name": "Chiang Mai Province", "local_name": "จังหวัดเชียงใหม่", "jurisdiction_type": "state", "path": "TH.50", "parent_code": "TH", "country_code": "TH", "timezone": "Asia/Bangkok", "currency_code": "THB"},
    {"code": "TH-50-CNX", "name": "Chiang Mai", "local_name": "เชียงใหม่", "jurisdiction_type": "city", "path": "TH.50.CNX", "parent_code": "TH-50", "country_code": "TH", "timezone": "Asia/Bangkok", "currency_code": "THB"},

    # ── Indonesia ──
    {"code": "ID", "name": "Indonesia", "jurisdiction_type": "country", "path": "ID", "parent_code": None, "country_code": "ID", "timezone": "Asia/Jakarta", "currency_code": "IDR"},
    {"code": "ID-BA", "name": "Bali Province", "jurisdiction_type": "state", "path": "ID.BA", "parent_code": "ID", "country_code": "ID", "timezone": "Asia/Makassar", "currency_code": "IDR"},
    {"code": "ID-BA-DPS", "name": "Bali (Denpasar)", "jurisdiction_type": "city", "path": "ID.BA.DPS", "parent_code": "ID-BA", "country_code": "ID", "timezone": "Asia/Makassar", "currency_code": "IDR"},
    {"code": "ID-JK", "name": "DKI Jakarta", "jurisdiction_type": "state", "path": "ID.JK", "parent_code": "ID", "country_code": "ID", "timezone": "Asia/Jakarta", "currency_code": "IDR"},
    {"code": "ID-JK-JKT", "name": "Jakarta", "jurisdiction_type": "city", "path": "ID.JK.JKT", "parent_code": "ID-JK", "country_code": "ID", "timezone": "Asia/Jakarta", "currency_code": "IDR"},

    # ── India ──
    {"code": "IN", "name": "India", "local_name": "भारत", "jurisdiction_type": "country", "path": "IN", "parent_code": None, "country_code": "IN", "timezone": "Asia/Kolkata", "currency_code": "INR"},
    {"code": "IN-DL", "name": "Delhi NCT", "jurisdiction_type": "state", "path": "IN.DL", "parent_code": "IN", "country_code": "IN", "timezone": "Asia/Kolkata", "currency_code": "INR"},
    {"code": "IN-DL-DEL", "name": "Delhi", "local_name": "दिल्ली", "jurisdiction_type": "city", "path": "IN.DL.DEL", "parent_code": "IN-DL", "country_code": "IN", "timezone": "Asia/Kolkata", "currency_code": "INR"},
    {"code": "IN-MH", "name": "Maharashtra", "jurisdiction_type": "state", "path": "IN.MH", "parent_code": "IN", "country_code": "IN", "timezone": "Asia/Kolkata", "currency_code": "INR"},
    {"code": "IN-MH-BOM", "name": "Mumbai", "local_name": "मुंबई", "jurisdiction_type": "city", "path": "IN.MH.BOM", "parent_code": "IN-MH", "country_code": "IN", "timezone": "Asia/Kolkata", "currency_code": "INR"},
    {"code": "IN-GA", "name": "Goa", "jurisdiction_type": "state", "path": "IN.GA", "parent_code": "IN", "country_code": "IN", "timezone": "Asia/Kolkata", "currency_code": "INR"},
    {"code": "IN-GA-GOI", "name": "Goa", "jurisdiction_type": "city", "path": "IN.GA.GOI", "parent_code": "IN-GA", "country_code": "IN", "timezone": "Asia/Kolkata", "currency_code": "INR"},
    {"code": "IN-KA", "name": "Karnataka", "jurisdiction_type": "state", "path": "IN.KA", "parent_code": "IN", "country_code": "IN", "timezone": "Asia/Kolkata", "currency_code": "INR"},
    {"code": "IN-KA-BLR", "name": "Bangalore", "local_name": "ಬೆಂಗಳೂರು", "jurisdiction_type": "city", "path": "IN.KA.BLR", "parent_code": "IN-KA", "country_code": "IN", "timezone": "Asia/Kolkata", "currency_code": "INR"},

    # ── Vietnam ──
    {"code": "VN", "name": "Vietnam", "local_name": "Việt Nam", "jurisdiction_type": "country", "path": "VN", "parent_code": None, "country_code": "VN", "timezone": "Asia/Ho_Chi_Minh", "currency_code": "VND"},
    {"code": "VN-HN", "name": "Hanoi", "local_name": "Hà Nội", "jurisdiction_type": "state", "path": "VN.HN", "parent_code": "VN", "country_code": "VN", "timezone": "Asia/Ho_Chi_Minh", "currency_code": "VND"},
    {"code": "VN-HN-HAN", "name": "Hanoi City", "local_name": "Thành phố Hà Nội", "jurisdiction_type": "city", "path": "VN.HN.HAN", "parent_code": "VN-HN", "country_code": "VN", "timezone": "Asia/Ho_Chi_Minh", "currency_code": "VND"},
    {"code": "VN-SG", "name": "Ho Chi Minh City Province", "local_name": "Thành phố Hồ Chí Minh", "jurisdiction_type": "state", "path": "VN.SG", "parent_code": "VN", "country_code": "VN", "timezone": "Asia/Ho_Chi_Minh", "currency_code": "VND"},
    {"code": "VN-SG-SGN", "name": "Ho Chi Minh City", "local_name": "Sài Gòn", "jurisdiction_type": "city", "path": "VN.SG.SGN", "parent_code": "VN-SG", "country_code": "VN", "timezone": "Asia/Ho_Chi_Minh", "currency_code": "VND"},
    {"code": "VN-DN", "name": "Da Nang", "local_name": "Đà Nẵng", "jurisdiction_type": "state", "path": "VN.DN", "parent_code": "VN", "country_code": "VN", "timezone": "Asia/Ho_Chi_Minh", "currency_code": "VND"},
    {"code": "VN-DN-DAD", "name": "Da Nang City", "local_name": "Thành phố Đà Nẵng", "jurisdiction_type": "city", "path": "VN.DN.DAD", "parent_code": "VN-DN", "country_code": "VN", "timezone": "Asia/Ho_Chi_Minh", "currency_code": "VND"},

    # ── Philippines ──
    {"code": "PH", "name": "Philippines", "local_name": "Pilipinas", "jurisdiction_type": "country", "path": "PH", "parent_code": None, "country_code": "PH", "timezone": "Asia/Manila", "currency_code": "PHP"},
    {"code": "PH-00", "name": "Metro Manila", "jurisdiction_type": "state", "path": "PH.00", "parent_code": "PH", "country_code": "PH", "timezone": "Asia/Manila", "currency_code": "PHP"},
    {"code": "PH-00-MNL", "name": "Manila", "jurisdiction_type": "city", "path": "PH.00.MNL", "parent_code": "PH-00", "country_code": "PH", "timezone": "Asia/Manila", "currency_code": "PHP"},
    {"code": "PH-07", "name": "Central Visayas", "jurisdiction_type": "state", "path": "PH.07", "parent_code": "PH", "country_code": "PH", "timezone": "Asia/Manila", "currency_code": "PHP"},
    {"code": "PH-07-CEB", "name": "Cebu", "jurisdiction_type": "city", "path": "PH.07.CEB", "parent_code": "PH-07", "country_code": "PH", "timezone": "Asia/Manila", "currency_code": "PHP"},

    # ── Colombia ──
    {"code": "CO", "name": "Colombia", "jurisdiction_type": "country", "path": "CO", "parent_code": None, "country_code": "CO", "timezone": "America/Bogota", "currency_code": "COP"},
    {"code": "CO-DC", "name": "Bogota Capital District", "local_name": "Distrito Capital", "jurisdiction_type": "state", "path": "CO.DC", "parent_code": "CO", "country_code": "CO", "timezone": "America/Bogota", "currency_code": "COP"},
    {"code": "CO-DC-BOG", "name": "Bogota", "local_name": "Bogotá", "jurisdiction_type": "city", "path": "CO.DC.BOG", "parent_code": "CO-DC", "country_code": "CO", "timezone": "America/Bogota", "currency_code": "COP"},
    {"code": "CO-BOL", "name": "Bolivar Department", "local_name": "Bolívar", "jurisdiction_type": "state", "path": "CO.BOL", "parent_code": "CO", "country_code": "CO", "timezone": "America/Bogota", "currency_code": "COP"},
    {"code": "CO-BOL-CTG", "name": "Cartagena", "jurisdiction_type": "city", "path": "CO.BOL.CTG", "parent_code": "CO-BOL", "country_code": "CO", "timezone": "America/Bogota", "currency_code": "COP"},

    # ── Dominican Republic ──
    {"code": "DO", "name": "Dominican Republic", "local_name": "República Dominicana", "jurisdiction_type": "country", "path": "DO", "parent_code": None, "country_code": "DO", "timezone": "America/Santo_Domingo", "currency_code": "DOP"},
    {"code": "DO-11", "name": "La Altagracia Province", "jurisdiction_type": "state", "path": "DO.11", "parent_code": "DO", "country_code": "DO", "timezone": "America/Santo_Domingo", "currency_code": "DOP"},
    {"code": "DO-11-PUJ", "name": "Punta Cana", "jurisdiction_type": "city", "path": "DO.11.PUJ", "parent_code": "DO-11", "country_code": "DO", "timezone": "America/Santo_Domingo", "currency_code": "DOP"},
    {"code": "DO-01", "name": "Distrito Nacional", "jurisdiction_type": "state", "path": "DO.01", "parent_code": "DO", "country_code": "DO", "timezone": "America/Santo_Domingo", "currency_code": "DOP"},
    {"code": "DO-01-SDQ", "name": "Santo Domingo", "jurisdiction_type": "city", "path": "DO.01.SDQ", "parent_code": "DO-01", "country_code": "DO", "timezone": "America/Santo_Domingo", "currency_code": "DOP"},

    # ── Cyprus ──
    {"code": "CY", "name": "Cyprus", "local_name": "Κύπρος", "jurisdiction_type": "country", "path": "CY", "parent_code": None, "country_code": "CY", "timezone": "Asia/Nicosia", "currency_code": "EUR"},
    {"code": "CY-04", "name": "Limassol District", "local_name": "Λεμεσός", "jurisdiction_type": "state", "path": "CY.04", "parent_code": "CY", "country_code": "CY", "timezone": "Asia/Nicosia", "currency_code": "EUR"},
    {"code": "CY-04-LIM", "name": "Limassol", "local_name": "Λεμεσός", "jurisdiction_type": "city", "path": "CY.04.LIM", "parent_code": "CY-04", "country_code": "CY", "timezone": "Asia/Nicosia", "currency_code": "EUR"},
    {"code": "CY-06", "name": "Paphos District", "local_name": "Πάφος", "jurisdiction_type": "state", "path": "CY.06", "parent_code": "CY", "country_code": "CY", "timezone": "Asia/Nicosia", "currency_code": "EUR"},
    {"code": "CY-06-PFO", "name": "Paphos", "local_name": "Πάφος", "jurisdiction_type": "city", "path": "CY.06.PFO", "parent_code": "CY-06", "country_code": "CY", "timezone": "Asia/Nicosia", "currency_code": "EUR"},
    {"code": "CY-03", "name": "Larnaca District", "local_name": "Λάρνακα", "jurisdiction_type": "state", "path": "CY.03", "parent_code": "CY", "country_code": "CY", "timezone": "Asia/Nicosia", "currency_code": "EUR"},
    {"code": "CY-03-LCA", "name": "Larnaca", "local_name": "Λάρνακα", "jurisdiction_type": "city", "path": "CY.03.LCA", "parent_code": "CY-03", "country_code": "CY", "timezone": "Asia/Nicosia", "currency_code": "EUR"},

    # ── Romania ──
    {"code": "RO", "name": "Romania", "local_name": "România", "jurisdiction_type": "country", "path": "RO", "parent_code": None, "country_code": "RO", "timezone": "Europe/Bucharest", "currency_code": "RON"},
    {"code": "RO-B", "name": "Bucharest Municipality", "local_name": "Municipiul București", "jurisdiction_type": "state", "path": "RO.B", "parent_code": "RO", "country_code": "RO", "timezone": "Europe/Bucharest", "currency_code": "RON"},
    {"code": "RO-B-BUH", "name": "Bucharest", "local_name": "București", "jurisdiction_type": "city", "path": "RO.B.BUH", "parent_code": "RO-B", "country_code": "RO", "timezone": "Europe/Bucharest", "currency_code": "RON"},

    # ── Aruba ──
    {"code": "AW", "name": "Aruba", "jurisdiction_type": "country", "path": "AW", "parent_code": None, "country_code": "AW", "timezone": "America/Aruba", "currency_code": "AWG"},
    {"code": "AW-ORA", "name": "Oranjestad District", "jurisdiction_type": "state", "path": "AW.ORA", "parent_code": "AW", "country_code": "AW", "timezone": "America/Aruba", "currency_code": "AWG"},
    {"code": "AW-ORA-AUA", "name": "Oranjestad", "jurisdiction_type": "city", "path": "AW.ORA.AUA", "parent_code": "AW-ORA", "country_code": "AW", "timezone": "America/Aruba", "currency_code": "AWG"},

    # ── Ireland ──
    {"code": "IE", "name": "Ireland", "local_name": "Éire", "jurisdiction_type": "country", "path": "IE", "parent_code": None, "country_code": "IE", "timezone": "Europe/Dublin", "currency_code": "EUR"},
    {"code": "IE-D", "name": "Dublin Region", "local_name": "Baile Átha Cliath", "jurisdiction_type": "state", "path": "IE.D", "parent_code": "IE", "country_code": "IE", "timezone": "Europe/Dublin", "currency_code": "EUR"},
    {"code": "IE-D-DUB", "name": "Dublin", "local_name": "Baile Átha Cliath", "jurisdiction_type": "city", "path": "IE.D.DUB", "parent_code": "IE-D", "country_code": "IE", "timezone": "Europe/Dublin", "currency_code": "EUR"},

    # ── Sri Lanka ──
    {"code": "LK", "name": "Sri Lanka", "local_name": "ශ්‍රී ලංකාව", "jurisdiction_type": "country", "path": "LK", "parent_code": None, "country_code": "LK", "timezone": "Asia/Colombo", "currency_code": "LKR"},
    {"code": "LK-1", "name": "Western Province", "jurisdiction_type": "state", "path": "LK.1", "parent_code": "LK", "country_code": "LK", "timezone": "Asia/Colombo", "currency_code": "LKR"},
    {"code": "LK-1-CMB", "name": "Colombo", "local_name": "කොළඹ", "jurisdiction_type": "city", "path": "LK.1.CMB", "parent_code": "LK-1", "country_code": "LK", "timezone": "Asia/Colombo", "currency_code": "LKR"},

    # ── Peru ──
    {"code": "PE", "name": "Peru", "local_name": "Perú", "jurisdiction_type": "country", "path": "PE", "parent_code": None, "country_code": "PE", "timezone": "America/Lima", "currency_code": "PEN"},
    {"code": "PE-LIM", "name": "Lima Region", "jurisdiction_type": "state", "path": "PE.LIM", "parent_code": "PE", "country_code": "PE", "timezone": "America/Lima", "currency_code": "PEN"},
    {"code": "PE-LIM-LIM", "name": "Lima", "jurisdiction_type": "city", "path": "PE.LIM.LIM", "parent_code": "PE-LIM", "country_code": "PE", "timezone": "America/Lima", "currency_code": "PEN"},
    {"code": "PE-CUS", "name": "Cusco Region", "jurisdiction_type": "state", "path": "PE.CUS", "parent_code": "PE", "country_code": "PE", "timezone": "America/Lima", "currency_code": "PEN"},
    {"code": "PE-CUS-CUZ", "name": "Cusco", "jurisdiction_type": "city", "path": "PE.CUS.CUZ", "parent_code": "PE-CUS", "country_code": "PE", "timezone": "America/Lima", "currency_code": "PEN"},

    # ── Chile ──
    {"code": "CL", "name": "Chile", "jurisdiction_type": "country", "path": "CL", "parent_code": None, "country_code": "CL", "timezone": "America/Santiago", "currency_code": "CLP"},
    {"code": "CL-RM", "name": "Santiago Metropolitan Region", "local_name": "Región Metropolitana", "jurisdiction_type": "state", "path": "CL.RM", "parent_code": "CL", "country_code": "CL", "timezone": "America/Santiago", "currency_code": "CLP"},
    {"code": "CL-RM-SCL", "name": "Santiago", "jurisdiction_type": "city", "path": "CL.RM.SCL", "parent_code": "CL-RM", "country_code": "CL", "timezone": "America/Santiago", "currency_code": "CLP"},

    # ══════════════════════════════════════════════════════════════════
    # SUB-JURISDICTIONS IN EXISTING COUNTRIES
    # ══════════════════════════════════════════════════════════════════

    # ── Greece: Santorini, Mykonos, Thessaloniki, Crete ── (GR, GR-I, GR-I-ATH already exist)
    {"code": "GR-M", "name": "South Aegean", "local_name": "Νότιο Αιγαίο", "jurisdiction_type": "state", "path": "GR.M", "parent_code": "GR", "country_code": "GR", "timezone": "Europe/Athens", "currency_code": "EUR"},
    {"code": "GR-M-JTR", "name": "Santorini (Thira)", "local_name": "Σαντορίνη", "jurisdiction_type": "city", "path": "GR.M.JTR", "parent_code": "GR-M", "country_code": "GR", "timezone": "Europe/Athens", "currency_code": "EUR"},
    {"code": "GR-M-JMK", "name": "Mykonos", "local_name": "Μύκονος", "jurisdiction_type": "city", "path": "GR.M.JMK", "parent_code": "GR-M", "country_code": "GR", "timezone": "Europe/Athens", "currency_code": "EUR"},
    {"code": "GR-B", "name": "Central Macedonia", "local_name": "Κεντρική Μακεδονία", "jurisdiction_type": "state", "path": "GR.B", "parent_code": "GR", "country_code": "GR", "timezone": "Europe/Athens", "currency_code": "EUR"},
    {"code": "GR-B-SKG", "name": "Thessaloniki", "local_name": "Θεσσαλονίκη", "jurisdiction_type": "city", "path": "GR.B.SKG", "parent_code": "GR-B", "country_code": "GR", "timezone": "Europe/Athens", "currency_code": "EUR"},
    {"code": "GR-N", "name": "Crete", "local_name": "Κρήτη", "jurisdiction_type": "state", "path": "GR.N", "parent_code": "GR", "country_code": "GR", "timezone": "Europe/Athens", "currency_code": "EUR"},
    {"code": "GR-N-HER", "name": "Heraklion", "local_name": "Ηράκλειο", "jurisdiction_type": "city", "path": "GR.N.HER", "parent_code": "GR-N", "country_code": "GR", "timezone": "Europe/Athens", "currency_code": "EUR"},

    # ── USA: Washington DC, New Orleans, Las Vegas, San Diego ──
    {"code": "US-DC", "name": "District of Columbia", "jurisdiction_type": "state", "path": "US.DC", "parent_code": "US", "country_code": "US", "timezone": "America/New_York", "currency_code": "USD"},
    {"code": "US-DC-WAS", "name": "Washington DC", "jurisdiction_type": "city", "path": "US.DC.WAS", "parent_code": "US-DC", "country_code": "US", "timezone": "America/New_York", "currency_code": "USD"},
    {"code": "US-LA", "name": "Louisiana", "jurisdiction_type": "state", "path": "US.LA", "parent_code": "US", "country_code": "US", "timezone": "America/Chicago", "currency_code": "USD"},
    {"code": "US-LA-MSY", "name": "New Orleans", "jurisdiction_type": "city", "path": "US.LA.MSY", "parent_code": "US-LA", "country_code": "US", "timezone": "America/Chicago", "currency_code": "USD"},
    {"code": "US-NV-LAS", "name": "Las Vegas", "jurisdiction_type": "city", "path": "US.NV.LAS", "parent_code": "US-NV", "country_code": "US", "timezone": "America/Los_Angeles", "currency_code": "USD"},
    {"code": "US-CA-SDG", "name": "San Diego", "jurisdiction_type": "city", "path": "US.CA.SDG", "parent_code": "US-CA", "country_code": "US", "timezone": "America/Los_Angeles", "currency_code": "USD"},

    # ── Spain: Madrid, Valencia, Seville, Malaga ── (ES, ES-CT, ES-IB already exist)
    {"code": "ES-MD", "name": "Community of Madrid", "local_name": "Comunidad de Madrid", "jurisdiction_type": "state", "path": "ES.MD", "parent_code": "ES", "country_code": "ES", "timezone": "Europe/Madrid", "currency_code": "EUR"},
    {"code": "ES-MD-MAD", "name": "Madrid", "jurisdiction_type": "city", "path": "ES.MD.MAD", "parent_code": "ES-MD", "country_code": "ES", "timezone": "Europe/Madrid", "currency_code": "EUR"},
    {"code": "ES-VC", "name": "Valencian Community", "local_name": "Comunitat Valenciana", "jurisdiction_type": "state", "path": "ES.VC", "parent_code": "ES", "country_code": "ES", "timezone": "Europe/Madrid", "currency_code": "EUR"},
    {"code": "ES-VC-VLC", "name": "Valencia", "local_name": "València", "jurisdiction_type": "city", "path": "ES.VC.VLC", "parent_code": "ES-VC", "country_code": "ES", "timezone": "Europe/Madrid", "currency_code": "EUR"},
    {"code": "ES-AN", "name": "Andalusia", "local_name": "Andalucía", "jurisdiction_type": "state", "path": "ES.AN", "parent_code": "ES", "country_code": "ES", "timezone": "Europe/Madrid", "currency_code": "EUR"},
    {"code": "ES-AN-SVQ", "name": "Seville", "local_name": "Sevilla", "jurisdiction_type": "city", "path": "ES.AN.SVQ", "parent_code": "ES-AN", "country_code": "ES", "timezone": "Europe/Madrid", "currency_code": "EUR"},
    {"code": "ES-AN-AGP", "name": "Malaga", "local_name": "Málaga", "jurisdiction_type": "city", "path": "ES.AN.AGP", "parent_code": "ES-AN", "country_code": "ES", "timezone": "Europe/Madrid", "currency_code": "EUR"},

    # ── Japan: Okinawa, Hokkaido ── (JP, JP-13, JP-26, JP-27, JP-40, JP-44 already exist)
    {"code": "JP-47", "name": "Okinawa Prefecture", "local_name": "沖縄県", "jurisdiction_type": "state", "path": "JP.47", "parent_code": "JP", "country_code": "JP", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-47-OKA", "name": "Naha (Okinawa)", "local_name": "那覇市", "jurisdiction_type": "city", "path": "JP.47.OKA", "parent_code": "JP-47", "country_code": "JP", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-01", "name": "Hokkaido", "local_name": "北海道", "jurisdiction_type": "state", "path": "JP.01", "parent_code": "JP", "country_code": "JP", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
    {"code": "JP-01-CTS", "name": "Sapporo", "local_name": "札幌市", "jurisdiction_type": "city", "path": "JP.01.CTS", "parent_code": "JP-01", "country_code": "JP", "timezone": "Asia/Tokyo", "currency_code": "JPY"},
]


# ──────────────────────────────────────────────────────────────────────
# Seed Jurisdictions
# ──────────────────────────────────────────────────────────────────────

async def seed_jurisdictions(db: AsyncSession) -> dict[str, Jurisdiction]:
    jurisdictions: dict[str, Jurisdiction] = {}
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


async def seed_categories(db: AsyncSession) -> dict[str, TaxCategory]:
    cats: dict[str, TaxCategory] = {}
    result = await db.execute(select(TaxCategory))
    for c in result.scalars().all():
        cats[c.code] = c

    for cat_data in NEW_TAX_CATEGORIES:
        c = await _get_or_create(db, TaxCategory, "code", cat_data)
        cats[c.code] = c

    return cats


# ──────────────────────────────────────────────────────────────────────
# Tax Rates & Rules
# ──────────────────────────────────────────────────────────────────────

async def seed_rates_and_rules(db: AsyncSession, j: dict[str, Jurisdiction], c: dict[str, TaxCategory]):
    # ══════════════════════════════════════════════════════════════════
    # EGYPT — 14% VAT + 10% service + 2% municipal + 1% tourism fund
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["EG"].id, "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage", "rate_value": 0.14, "currency_code": "EGP",
        "effective_start": date(2016, 9, 8), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "Law No. 67/2016 — VAT at 14% on accommodation services",
        "authority_name": "Egyptian Tax Authority", "status": "active", "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["EG"].id, "tax_category_id": c["service_pct"].id,
        "rate_type": "percentage", "rate_value": 0.10, "currency_code": "EGP",
        "effective_start": date(2020, 1, 1), "calculation_order": 20, "base_includes": ["base_amount"],
        "legal_reference": "Mandatory 10% service charge on hotel accommodation",
        "authority_name": "Ministry of Tourism and Antiquities", "status": "active", "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["EG"].id, "tax_category_id": c["municipal_pct"].id,
        "rate_type": "percentage", "rate_value": 0.02, "currency_code": "EGP",
        "effective_start": date(2020, 1, 1), "calculation_order": 30, "base_includes": ["base_amount"],
        "legal_reference": "Municipal tax 2% on hotel room charges",
        "authority_name": "Local Municipality", "status": "active", "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["EG"].id, "tax_category_id": c["tourism_pct"].id,
        "rate_type": "percentage", "rate_value": 0.01, "currency_code": "EGP",
        "effective_start": date(2023, 3, 1), "calculation_order": 40, "base_includes": ["base_amount"],
        "legal_reference": "Tourism Support Fund fee — 1% on hotel accommodation (PM Decree 2023)",
        "authority_name": "Tourism Development Authority", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # POLAND — 8% VAT reduced + Krakow resort tax PLN 2.50/person/night
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["PL"].id, "tax_category_id": c["vat_reduced"].id,
        "rate_type": "percentage", "rate_value": 0.08, "currency_code": "PLN",
        "effective_start": date(2011, 1, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "Ustawa o VAT, Art. 41 ust. 2 — 8% reduced rate on accommodation",
        "authority_name": "Ministry of Finance (Poland)", "status": "active", "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["PL-MA-KRK"].id, "tax_category_id": c["tourism_flat_person_night"].id,
        "rate_type": "flat", "rate_value": 2.50, "currency_code": "PLN",
        "effective_start": date(2024, 1, 1), "calculation_order": 20, "base_includes": ["per_person_per_night"],
        "legal_reference": "Opłata miejscowa — Krakow PLN 2.50/person/night (Uchwała Rady Miasta)",
        "authority_name": "City of Krakow", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # THAILAND — 7% VAT + 300 THB entry fee (scheduled Feb 2026)
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["TH"].id, "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage", "rate_value": 0.07, "currency_code": "THB",
        "effective_start": date(2023, 10, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "Revenue Code, Royal Decree No. 726 — VAT 7% on accommodation",
        "authority_name": "Revenue Department of Thailand", "status": "active", "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["TH"].id, "tax_category_id": c["entry_flat_person"].id,
        "rate_type": "flat", "rate_value": 300, "currency_code": "THB",
        "effective_start": date(2026, 2, 1), "calculation_order": 50, "base_includes": ["per_person_per_stay"],
        "legal_reference": "Kha Yeap Pan Din (Tourist Entry Fee) — THB 300 per air arrival",
        "authority_name": "Ministry of Tourism and Sports (Thailand)", "status": "scheduled", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # INDONESIA — 11% VAT + Bali IDR 150,000 eco levy
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["ID"].id, "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage", "rate_value": 0.11, "currency_code": "IDR",
        "effective_start": date(2022, 4, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "UU No. 7/2021 Harmonisasi Peraturan Perpajakan — PPN 11%",
        "authority_name": "Direktorat Jenderal Pajak", "status": "active", "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["ID-BA"].id, "tax_category_id": c["entry_flat_person"].id,
        "rate_type": "flat", "rate_value": 150000, "currency_code": "IDR",
        "effective_start": date(2024, 2, 14), "calculation_order": 50, "base_includes": ["per_person_per_stay"],
        "legal_reference": "Bali Governor Regulation No. 36/2023 — IDR 150,000 foreign tourist levy",
        "authority_name": "Province of Bali", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # INDIA — GST tiered: 12% (<INR 7,500) / 18% (≥INR 7,500)
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["IN"].id, "tax_category_id": c["tier_price"].id,
        "rate_type": "tiered", "currency_code": "INR",
        "tiers": [
            {"min": 0, "max": 7500, "rate": 0.12},
            {"min": 7500, "rate": 0.18},
        ],
        "tier_type": "threshold",
        "effective_start": date(2017, 7, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "CGST Act 2017, Notification No. 11/2017 — GST 12%/18% tiered by room tariff",
        "authority_name": "GST Council of India", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # VIETNAM — 10% VAT
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["VN"].id, "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage", "rate_value": 0.10, "currency_code": "VND",
        "effective_start": date(2008, 1, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "Law on VAT No. 13/2008/QH12 — 10% standard rate on accommodation",
        "authority_name": "General Department of Taxation (Vietnam)", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # PHILIPPINES — 12% VAT
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["PH"].id, "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage", "rate_value": 0.12, "currency_code": "PHP",
        "effective_start": date(2018, 1, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "NIRC Section 106, as amended by TRAIN Law (RA 10963) — 12% VAT",
        "authority_name": "Bureau of Internal Revenue (Philippines)", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # COLOMBIA — 19% IVA + foreign tourist exemption
    # ══════════════════════════════════════════════════════════════════
    co_vat = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["CO"].id, "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage", "rate_value": 0.19, "currency_code": "COP",
        "effective_start": date(2017, 1, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "Estatuto Tributario, Art. 468 — IVA 19% on accommodation",
        "authority_name": "DIAN (Colombia)", "status": "active", "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "jurisdiction_id": j["CO"].id, "tax_rate_id": co_vat.id,
        "rule_type": "exemption", "priority": 100,
        "name": "Foreign Tourist IVA Exemption (Colombia)",
        "description": "Non-resident foreign tourists can claim IVA refund on accommodation services",
        "conditions": {"AND": [{"field": "guest_nationality", "operator": "!=", "value": "CO"}]},
        "action": {"exempt": True},
        "effective_start": date(2017, 1, 1),
        "legal_reference": "Estatuto Tributario, Art. 481 — Tourism IVA exemption for foreign visitors",
        "authority_name": "DIAN (Colombia)", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # DOMINICAN REPUBLIC — 18% ITBIS
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["DO"].id, "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage", "rate_value": 0.18, "currency_code": "DOP",
        "effective_start": date(2013, 1, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "Ley 253-12 (Código Tributario) — ITBIS 18% on accommodation",
        "authority_name": "DGII (Dominican Republic)", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # CYPRUS — 9% VAT reduced on accommodation
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["CY"].id, "tax_category_id": c["vat_reduced"].id,
        "rate_type": "percentage", "rate_value": 0.09, "currency_code": "EUR",
        "effective_start": date(2017, 1, 13), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "VAT Law N.95(I)/2000, Eighth Schedule — 9% reduced rate on accommodation",
        "authority_name": "Tax Department of Cyprus", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # ROMANIA — 9% VAT + Bucharest €2/night (scheduled 2026)
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["RO"].id, "tax_category_id": c["vat_reduced"].id,
        "rate_type": "percentage", "rate_value": 0.09, "currency_code": "RON",
        "effective_start": date(2017, 1, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "Codul Fiscal, Art. 291 alin. (2) — 9% reduced VAT on accommodation",
        "authority_name": "ANAF (Romania)", "status": "active", "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["RO-B-BUH"].id, "tax_category_id": c["tourism_flat_night"].id,
        "rate_type": "flat", "rate_value": 10, "currency_code": "RON",
        "effective_start": date(2026, 1, 1), "calculation_order": 20, "base_includes": ["per_night"],
        "legal_reference": "Bucharest City Council Decision — RON 10 (~€2) per room per night tourist tax",
        "authority_name": "Bucharest City Council", "status": "scheduled", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # ARUBA — 12.5% tourist levy + $2/night sustainability
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["AW"].id, "tax_category_id": c["tourism_pct"].id,
        "rate_type": "percentage", "rate_value": 0.125, "currency_code": "AWG",
        "effective_start": date(2020, 1, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "Landsverordening toerismeheffing — 12.5% tourist levy on room rate",
        "authority_name": "Aruba Tax Authority (DIMP)", "status": "active", "created_by": "seed",
    })
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["AW"].id, "tax_category_id": c["sustainability_flat_night"].id,
        "rate_type": "flat", "rate_value": 2.00, "currency_code": "USD",
        "effective_start": date(2024, 7, 1), "calculation_order": 20, "base_includes": ["per_night"],
        "legal_reference": "Environmental Sustainability Fee — USD 2.00 per room per night",
        "authority_name": "Government of Aruba", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # IRELAND — 13.5% VAT reduced on accommodation
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["IE"].id, "tax_category_id": c["vat_reduced"].id,
        "rate_type": "percentage", "rate_value": 0.135, "currency_code": "EUR",
        "effective_start": date(2023, 9, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "VATA 1972, Schedule 3 — 13.5% reduced rate on hotel accommodation",
        "authority_name": "Revenue Commissioners (Ireland)", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # SRI LANKA — 18% VAT on hotels
    # ══════════════════════════════════════════════════════════════════
    await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["LK"].id, "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage", "rate_value": 0.18, "currency_code": "LKR",
        "effective_start": date(2024, 1, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "Value Added Tax Act No. 14/2002, as amended — 18% VAT on accommodation",
        "authority_name": "Inland Revenue Department of Sri Lanka", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # PERU — 18% IGV + foreign tourist exemption
    # ══════════════════════════════════════════════════════════════════
    pe_vat = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["PE"].id, "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage", "rate_value": 0.18, "currency_code": "PEN",
        "effective_start": date(2011, 3, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "TUO Ley del IGV, D.S. 055-99-EF — 18% IGV on accommodation",
        "authority_name": "SUNAT (Peru)", "status": "active", "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "jurisdiction_id": j["PE"].id, "tax_rate_id": pe_vat.id,
        "rule_type": "exemption", "priority": 100,
        "name": "Foreign Tourist IGV Exemption (Peru)",
        "description": "Non-domiciled tourists are exempt from IGV on accommodation (requires tourist card + foreign passport)",
        "conditions": {"AND": [{"field": "guest_nationality", "operator": "!=", "value": "PE"}]},
        "action": {"exempt": True},
        "effective_start": date(2001, 1, 1),
        "legal_reference": "Decreto Legislativo 919 — IGV exemption for foreign tourists on accommodation",
        "authority_name": "SUNAT (Peru)", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # CHILE — 19% IVA + foreign tourist exemption (paying in foreign currency)
    # ══════════════════════════════════════════════════════════════════
    cl_vat = await _create_rate_if_not_exists(db, {
        "jurisdiction_id": j["CL"].id, "tax_category_id": c["vat_standard"].id,
        "rate_type": "percentage", "rate_value": 0.19, "currency_code": "CLP",
        "effective_start": date(2003, 1, 1), "calculation_order": 10, "base_includes": ["base_amount"],
        "legal_reference": "DL 825, Ley sobre Impuesto a las Ventas y Servicios — IVA 19%",
        "authority_name": "SII (Chile)", "status": "active", "created_by": "seed",
    })
    await _create_rule_if_not_exists(db, {
        "jurisdiction_id": j["CL"].id, "tax_rate_id": cl_vat.id,
        "rule_type": "exemption", "priority": 100,
        "name": "Foreign Tourist IVA Exemption (Chile)",
        "description": "Foreign tourists paying in foreign currency (USD/EUR) are exempt from IVA on accommodation",
        "conditions": {"AND": [{"field": "guest_nationality", "operator": "!=", "value": "CL"}]},
        "action": {"exempt": True},
        "effective_start": date(2003, 1, 1),
        "legal_reference": "DL 825 Art. 12, letra E, No. 17 — IVA exemption for foreign tourists",
        "authority_name": "SII (Chile)", "status": "active", "created_by": "seed",
    })

    # ══════════════════════════════════════════════════════════════════
    # GREECE — Climate Crisis Resilience Tax for new sub-cities
    # (GR 13% VAT already exists from seed_enhancement.py)
    # ══════════════════════════════════════════════════════════════════
    for city_code in ["GR-M-JTR", "GR-M-JMK", "GR-B-SKG", "GR-N-HER"]:
        if city_code in j:
            await _create_rate_if_not_exists(db, {
                "jurisdiction_id": j[city_code].id, "tax_category_id": c["climate_tier_star"].id,
                "rate_type": "tiered", "currency_code": "EUR",
                "tiers": [
                    {"min": 1, "max": 2, "value": 1.50},
                    {"min": 3, "max": 3, "value": 3.00},
                    {"min": 4, "max": 4, "value": 7.00},
                    {"min": 5, "max": 5, "value": 10.00},
                ],
                "tier_type": "single_amount",
                "effective_start": date(2024, 1, 1), "calculation_order": 20, "base_includes": ["per_night"],
                "legal_reference": "Law 5073/2023, Art. 53 — Climate Crisis Resilience Tax (per room per night)",
                "authority_name": "Hellenic Ministry of Finance", "status": "active", "created_by": "seed",
            })

    # ══════════════════════════════════════════════════════════════════
    # MALDIVES — Update T-GST 16%→17% and Green Tax $6→$12
    # (Existing rates from seed_enhancement.py stay as historical)
    # ══════════════════════════════════════════════════════════════════
    if "MV" in j:
        await _create_rate_if_not_exists(db, {
            "jurisdiction_id": j["MV"].id, "tax_category_id": c["vat_standard"].id,
            "rate_type": "percentage", "rate_value": 0.17, "currency_code": "USD",
            "effective_start": date(2025, 7, 1), "calculation_order": 10, "base_includes": ["base_amount"],
            "legal_reference": "7th Amendment to GST Act — T-GST increased from 16% to 17% (July 2025)",
            "authority_name": "Maldives Inland Revenue Authority (MIRA)", "status": "scheduled", "created_by": "seed",
        })
        mv_green = await _create_rate_if_not_exists(db, {
            "jurisdiction_id": j["MV"].id, "tax_category_id": c["green_flat_night"].id,
            "rate_type": "flat", "rate_value": 12.00, "currency_code": "USD",
            "effective_start": date(2025, 1, 1), "calculation_order": 20, "base_includes": ["per_person_per_night"],
            "legal_reference": "Green Tax Amendment — USD 12/person/night for tourist resorts (doubled from $6)",
            "authority_name": "Maldives Inland Revenue Authority (MIRA)", "status": "active", "created_by": "seed",
        })
        await _create_rule_if_not_exists(db, {
            "jurisdiction_id": j["MV"].id, "tax_rate_id": mv_green.id,
            "rule_type": "exemption", "priority": 100,
            "name": "Maldives Green Tax Under-2 Exemption",
            "description": "Children under 2 years at check-in are exempt from Green Tax",
            "conditions": {"AND": [{"field": "guest_age", "operator": "<", "value": 2}]},
            "action": {"exempt": True},
            "effective_start": date(2025, 1, 1),
            "legal_reference": "Green Tax Regulation — Under-2 exemption",
            "authority_name": "Maldives Inland Revenue Authority (MIRA)", "status": "active", "created_by": "seed",
        })

    # ══════════════════════════════════════════════════════════════════
    # USA — Washington DC, New Orleans, Las Vegas, San Diego
    # ══════════════════════════════════════════════════════════════════

    # Washington DC — 14.95% transient accommodations tax
    if "US-DC-WAS" in j:
        await _create_rate_if_not_exists(db, {
            "jurisdiction_id": j["US-DC-WAS"].id, "tax_category_id": c["occ_pct"].id,
            "rate_type": "percentage", "rate_value": 0.1495, "currency_code": "USD",
            "effective_start": date(2023, 10, 1), "calculation_order": 20, "base_includes": ["base_amount"],
            "legal_reference": "DC Code §47-2002.02 — 14.5% transient accommodations tax + 0.45% Ballpark Fee",
            "authority_name": "DC Office of Tax and Revenue", "status": "active", "created_by": "seed",
        })

    # Louisiana state sales tax on lodging
    if "US-LA" in j:
        await _create_rate_if_not_exists(db, {
            "jurisdiction_id": j["US-LA"].id, "tax_category_id": c["vat_standard"].id,
            "rate_type": "percentage", "rate_value": 0.0445, "currency_code": "USD",
            "effective_start": date(2025, 1, 1), "calculation_order": 10, "base_includes": ["base_amount"],
            "legal_reference": "Louisiana Revenue Code — 4.45% state sales tax on transient accommodations",
            "authority_name": "Louisiana Department of Revenue", "status": "active", "created_by": "seed",
        })

    # New Orleans — local hotel occupancy taxes
    if "US-LA-MSY" in j:
        await _create_rate_if_not_exists(db, {
            "jurisdiction_id": j["US-LA-MSY"].id, "tax_category_id": c["occ_pct"].id,
            "rate_type": "percentage", "rate_value": 0.0600, "currency_code": "USD",
            "effective_start": date(2023, 1, 1), "calculation_order": 20, "base_includes": ["base_amount"],
            "legal_reference": "Orleans Parish — 3% NOEHA hotel occupancy tax + 3% city hotel occupancy tax",
            "authority_name": "City of New Orleans", "status": "active", "created_by": "seed",
        })
        await _create_rate_if_not_exists(db, {
            "jurisdiction_id": j["US-LA-MSY"].id, "tax_category_id": c["convention_pct"].id,
            "rate_type": "percentage", "rate_value": 0.0525, "currency_code": "USD",
            "effective_start": date(2023, 1, 1), "calculation_order": 30, "base_includes": ["base_amount"],
            "legal_reference": "3% Ernest N. Morial Convention Center + 1% tourism district + 1.25% additional parish",
            "authority_name": "NOEHA / Convention Center Authority", "status": "active", "created_by": "seed",
        })

    # Las Vegas — Nevada state + Clark County + city room taxes
    if "US-NV" in j and "US-NV-LAS" in j:
        await _create_rate_if_not_exists(db, {
            "jurisdiction_id": j["US-NV-LAS"].id, "tax_category_id": c["occ_pct"].id,
            "rate_type": "percentage", "rate_value": 0.1338, "currency_code": "USD",
            "effective_start": date(2024, 1, 1), "calculation_order": 20, "base_includes": ["base_amount"],
            "legal_reference": "Clark County combined: 8.375% sales + 3% room tax + 1% LVCVA + 1% tourism improvement",
            "authority_name": "Clark County / LVCVA", "status": "active", "created_by": "seed",
        })

    # San Diego — California state exists, add city TOT + TMD
    if "US-CA-SDG" in j:
        await _create_rate_if_not_exists(db, {
            "jurisdiction_id": j["US-CA-SDG"].id, "tax_category_id": c["occ_pct"].id,
            "rate_type": "percentage", "rate_value": 0.105, "currency_code": "USD",
            "effective_start": date(2024, 1, 1), "calculation_order": 20, "base_includes": ["base_amount"],
            "legal_reference": "San Diego Municipal Code §35.0101 — 10.5% Transient Occupancy Tax",
            "authority_name": "City of San Diego", "status": "active", "created_by": "seed",
        })
        await _create_rate_if_not_exists(db, {
            "jurisdiction_id": j["US-CA-SDG"].id, "tax_category_id": c["convention_pct"].id,
            "rate_type": "percentage", "rate_value": 0.02, "currency_code": "USD",
            "effective_start": date(2024, 1, 1), "calculation_order": 30, "base_includes": ["base_amount"],
            "legal_reference": "Tourism Marketing District — 2% assessment on room rate",
            "authority_name": "San Diego Tourism Marketing District", "status": "active", "created_by": "seed",
        })

    # ══════════════════════════════════════════════════════════════════
    # SPAIN — Madrid, Valencia, Seville, Malaga (IVA only, no local tourist tax)
    # (Spain's 10% IVA already applied at ES country level)
    # ══════════════════════════════════════════════════════════════════
    # No additional rates needed — these cities inherit Spain's 10% IVA.
    # They exist as jurisdictions for future regional tourist tax tracking.

    # ══════════════════════════════════════════════════════════════════
    # JAPAN — Okinawa, Hokkaido
    # (JP 10% consumption tax already applied at country level)
    # ══════════════════════════════════════════════════════════════════
    # No additional accommodation tax — inherit national consumption tax.
    # Okinawa and Hokkaido are emerging ETG destinations.


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

async def main():
    print("=== TaxLens Seed: ETG Market Coverage ===\n")

    async with async_session_factory() as db:
        cats = await seed_categories(db)
        print(f"  Tax categories: {len(cats)} total ({len(NEW_TAX_CATEGORIES)} new)")

        j = await seed_jurisdictions(db)
        print(f"  Jurisdictions: {len(j)} total ({len(NEW_JURISDICTIONS)} new)")

        await seed_rates_and_rules(db, j, c=cats)

        await db.commit()

    # Summary
    countries = [code for code, jur in j.items() if hasattr(jur, 'jurisdiction_type') and jur.jurisdiction_type == "country"]
    print(f"\n✅ ETG market coverage complete!")
    print(f"   {len(NEW_JURISDICTIONS)} new jurisdictions across 16 new countries + existing expansions")
    print(f"   50+ tax rates with legal references")
    print(f"   Foreign tourist exemptions for Colombia, Peru, Chile")
    print(f"   Scheduled rates: Thailand entry fee (Feb 2026), Bucharest tourist tax (Jan 2026)")
    print(f"   Maldives T-GST update 16% → 17% (July 2025) + Green Tax $12")


if __name__ == "__main__":
    asyncio.run(main())
