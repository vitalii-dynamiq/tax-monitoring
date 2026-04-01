"""
Seed comprehensive country data for TaxLens.

Adds all countries relevant to OTA accommodation tax compliance:
Booking.com, Expedia, Hotels.com, Airbnb, and similar platforms.

Uses ISO 3166-1 alpha-2 codes, IANA timezones, ISO 4217 currencies.
Idempotent — safe to run multiple times.

Usage:
    python -m scripts.seed_countries
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.jurisdiction import Jurisdiction
from app.models.monitoring_schedule import MonitoringSchedule

# ──────────────────────────────────────────────────────────────────────
# Comprehensive country list for OTA accommodation tax platforms
# ──────────────────────────────────────────────────────────────────────

COUNTRIES = [
    # ─── Europe ──────────────────────────────────────────────────
    # Western Europe
    ("AD", "Andorra", "Europe/Andorra", "EUR"),
    ("BE", "Belgium", "Europe/Brussels", "EUR"),
    ("CH", "Switzerland", "Europe/Zurich", "CHF"),
    ("DK", "Denmark", "Europe/Copenhagen", "DKK"),
    ("FI", "Finland", "Europe/Helsinki", "EUR"),
    ("IE", "Ireland", "Europe/Dublin", "EUR"),
    ("IS", "Iceland", "Atlantic/Reykjavik", "ISK"),
    ("LI", "Liechtenstein", "Europe/Vaduz", "CHF"),
    ("LU", "Luxembourg", "Europe/Luxembourg", "EUR"),
    ("MC", "Monaco", "Europe/Monaco", "EUR"),
    ("MT", "Malta", "Europe/Malta", "EUR"),
    ("NO", "Norway", "Europe/Oslo", "NOK"),
    ("SE", "Sweden", "Europe/Stockholm", "SEK"),
    # Eastern Europe
    ("AL", "Albania", "Europe/Tirane", "ALL"),
    ("BA", "Bosnia and Herzegovina", "Europe/Sarajevo", "BAM"),
    ("BG", "Bulgaria", "Europe/Sofia", "BGN"),
    ("BY", "Belarus", "Europe/Minsk", "BYN"),
    ("EE", "Estonia", "Europe/Tallinn", "EUR"),
    ("GE", "Georgia", "Asia/Tbilisi", "GEL"),
    ("HR", "Croatia", "Europe/Zagreb", "EUR"),
    ("LT", "Lithuania", "Europe/Vilnius", "EUR"),
    ("LV", "Latvia", "Europe/Riga", "EUR"),
    ("MD", "Moldova", "Europe/Chisinau", "MDL"),
    ("ME", "Montenegro", "Europe/Podgorica", "EUR"),
    ("MK", "North Macedonia", "Europe/Skopje", "MKD"),
    ("PL", "Poland", "Europe/Warsaw", "PLN"),
    ("RO", "Romania", "Europe/Bucharest", "RON"),
    ("RS", "Serbia", "Europe/Belgrade", "RSD"),
    ("SI", "Slovenia", "Europe/Ljubljana", "EUR"),
    ("SK", "Slovakia", "Europe/Bratislava", "EUR"),
    ("UA", "Ukraine", "Europe/Kyiv", "UAH"),
    # Southern Europe / Mediterranean
    ("CY", "Cyprus", "Asia/Nicosia", "EUR"),
    ("TR", "Turkey", "Europe/Istanbul", "TRY"),
    # ─── Asia-Pacific ────────────────────────────────────────────
    ("CN", "China", "Asia/Shanghai", "CNY"),
    ("HK", "Hong Kong", "Asia/Hong_Kong", "HKD"),
    ("IN", "India", "Asia/Kolkata", "INR"),
    ("KH", "Cambodia", "Asia/Phnom_Penh", "KHR"),
    ("KR", "South Korea", "Asia/Seoul", "KRW"),
    ("LA", "Laos", "Asia/Vientiane", "LAK"),
    ("LK", "Sri Lanka", "Asia/Colombo", "LKR"),
    ("MM", "Myanmar", "Asia/Yangon", "MMK"),
    ("MO", "Macau", "Asia/Macau", "MOP"),
    ("MY", "Malaysia", "Asia/Kuala_Lumpur", "MYR"),
    ("NP", "Nepal", "Asia/Kathmandu", "NPR"),
    ("PH", "Philippines", "Asia/Manila", "PHP"),
    ("PK", "Pakistan", "Asia/Karachi", "PKR"),
    ("TW", "Taiwan", "Asia/Taipei", "TWD"),
    ("VN", "Vietnam", "Asia/Ho_Chi_Minh", "VND"),
    ("BD", "Bangladesh", "Asia/Dhaka", "BDT"),
    # Oceania
    ("NZ", "New Zealand", "Pacific/Auckland", "NZD"),
    ("FJ", "Fiji", "Pacific/Fiji", "FJD"),
    ("PG", "Papua New Guinea", "Pacific/Port_Moresby", "PGK"),
    # ─── Middle East & North Africa ──────────────────────────────
    ("BH", "Bahrain", "Asia/Bahrain", "BHD"),
    ("EG", "Egypt", "Africa/Cairo", "EGP"),
    ("IL", "Israel", "Asia/Jerusalem", "ILS"),
    ("JO", "Jordan", "Asia/Amman", "JOD"),
    ("KW", "Kuwait", "Asia/Kuwait", "KWD"),
    ("LB", "Lebanon", "Asia/Beirut", "LBP"),
    ("MA", "Morocco", "Africa/Casablanca", "MAD"),
    ("OM", "Oman", "Asia/Muscat", "OMR"),
    ("QA", "Qatar", "Asia/Qatar", "QAR"),
    ("SA", "Saudi Arabia", "Asia/Riyadh", "SAR"),
    ("TN", "Tunisia", "Africa/Tunis", "TND"),
    # ─── Americas ────────────────────────────────────────────────
    ("AR", "Argentina", "America/Buenos_Aires", "ARS"),
    ("BB", "Barbados", "America/Barbados", "BBD"),
    ("BM", "Bermuda", "Atlantic/Bermuda", "BMD"),
    ("BO", "Bolivia", "America/La_Paz", "BOB"),
    ("BR", "Brazil", "America/Sao_Paulo", "BRL"),
    ("BS", "Bahamas", "America/Nassau", "BSD"),
    ("CA", "Canada", "America/Toronto", "CAD"),
    ("CL", "Chile", "America/Santiago", "CLP"),
    ("CO", "Colombia", "America/Bogota", "COP"),
    ("CR", "Costa Rica", "America/Costa_Rica", "CRC"),
    ("CU", "Cuba", "America/Havana", "CUP"),
    ("DO", "Dominican Republic", "America/Santo_Domingo", "DOP"),
    ("EC", "Ecuador", "America/Guayaquil", "USD"),
    ("JM", "Jamaica", "America/Jamaica", "JMD"),
    ("KY", "Cayman Islands", "America/Cayman", "KYD"),
    ("PA", "Panama", "America/Panama", "PAB"),
    ("PE", "Peru", "America/Lima", "PEN"),
    ("PR", "Puerto Rico", "America/Puerto_Rico", "USD"),
    ("PY", "Paraguay", "America/Asuncion", "PYG"),
    ("TT", "Trinidad and Tobago", "America/Port_of_Spain", "TTD"),
    ("UY", "Uruguay", "America/Montevideo", "UYU"),
    ("VG", "British Virgin Islands", "America/Virgin", "USD"),
    # ─── Africa ──────────────────────────────────────────────────
    ("ET", "Ethiopia", "Africa/Addis_Ababa", "ETB"),
    ("GH", "Ghana", "Africa/Accra", "GHS"),
    ("KE", "Kenya", "Africa/Nairobi", "KES"),
    ("MU", "Mauritius", "Indian/Mauritius", "MUR"),
    ("NG", "Nigeria", "Africa/Lagos", "NGN"),
    ("RW", "Rwanda", "Africa/Kigali", "RWF"),
    ("SC", "Seychelles", "Indian/Mahe", "SCR"),
    ("TZ", "Tanzania", "Africa/Dar_es_Salaam", "TZS"),
    ("ZA", "South Africa", "Africa/Johannesburg", "ZAR"),
    ("ZW", "Zimbabwe", "Africa/Harare", "ZWL"),
]


async def seed_countries(db: AsyncSession) -> int:
    """Seed all OTA-relevant countries. Returns count of newly created."""
    created = 0
    for code, name, timezone, currency in COUNTRIES:
        result = await db.execute(
            select(Jurisdiction).where(Jurisdiction.code == code)
        )
        if result.scalar_one_or_none():
            continue

        j = Jurisdiction(
            code=code,
            name=name,
            jurisdiction_type="country",
            path=code,
            country_code=code,
            timezone=timezone,
            currency_code=currency,
            status="active",
            created_by="system",
        )
        db.add(j)
        created += 1

    if created > 0:
        await db.flush()

        # Create monitoring schedules for new countries
        new_countries = await db.execute(
            select(Jurisdiction).where(
                Jurisdiction.jurisdiction_type == "country",
                Jurisdiction.code.in_([c[0] for c in COUNTRIES]),
            )
        )
        for country in new_countries.scalars().all():
            existing_schedule = await db.execute(
                select(MonitoringSchedule).where(
                    MonitoringSchedule.jurisdiction_id == country.id
                )
            )
            if not existing_schedule.scalar_one_or_none():
                schedule = MonitoringSchedule(
                    jurisdiction_id=country.id,
                    enabled=False,
                    cadence="weekly",
                )
                db.add(schedule)

        await db.flush()

    return created


async def main():
    async with async_session_factory() as db:
        print("Seeding OTA countries...")
        created = await seed_countries(db)
        await db.commit()
        print(f"  {created} new countries added ({len(COUNTRIES)} total in list)")

        # Count total
        result = await db.execute(
            select(Jurisdiction).where(Jurisdiction.jurisdiction_type == "country")
        )
        total = len(list(result.scalars().all()))
        print(f"  Total countries in database: {total}")


if __name__ == "__main__":
    asyncio.run(main())
