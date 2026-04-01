"""
Comprehensive tax rate seeding for all jurisdictions.

Inserts VAT/GST, tourism taxes, occupancy taxes, and exemption rules
for all countries and sub-jurisdictions in the database.

Idempotent: skips rates that already exist for a jurisdiction+category combo.

Usage:
    python -m scripts.seed_comprehensive_rates
    python -m scripts.seed_comprehensive_rates --api-url http://localhost:8001
"""

import argparse
import asyncio
import time

import httpx

# ═══════════════════════════════════════════════════════════════════
# TAX RATE DATA
# ═══════════════════════════════════════════════════════════════════
# Format: (jurisdiction_code, category_code, rate_type, rate_value,
#          effective_start, currency_code, legal_reference, authority_name)
#
# rate_value for percentage = decimal (0.10 = 10%)
# rate_value for flat = amount in local currency
# ═══════════════════════════════════════════════════════════════════

RATES: list[tuple] = [
    # ─── EUROPE: VAT on accommodation (national) ───────────────────
    # Sources: Tax Foundation EU VAT Rates 2026, VATcalc.com
    ("AD", "vat_reduced", "percentage", 0.045, "2025-01-01", "EUR", "Andorra IGI reduced rate on accommodation", "Govern d'Andorra"),
    ("AL", "vat_reduced", "percentage", 0.06, "2025-01-01", "ALL", "Albanian VAT reduced rate on accommodation", "General Directorate of Taxation"),
    ("BA", "vat_standard", "percentage", 0.17, "2025-01-01", "BAM", "BiH VAT standard rate on accommodation", "Indirect Taxation Authority"),
    ("BE", "vat_reduced", "percentage", 0.06, "2025-01-01", "EUR", "Belgian VAT reduced rate on accommodation (increasing to 12% in 2026)", "FPS Finance"),
    ("BG", "vat_reduced", "percentage", 0.09, "2025-01-01", "BGN", "Bulgarian VAT reduced rate on accommodation", "National Revenue Agency"),
    ("BY", "vat_standard", "percentage", 0.20, "2025-01-01", "BYN", "Belarus VAT on accommodation", "Ministry of Taxes and Duties"),
    ("CH", "vat_reduced", "percentage", 0.038, "2025-01-01", "CHF", "Swiss VAT special rate on accommodation", "Federal Tax Administration"),
    ("CY", "vat_reduced", "percentage", 0.09, "2025-01-01", "EUR", "Cyprus VAT reduced rate on accommodation", "Tax Department"),
    ("DK", "vat_standard", "percentage", 0.25, "2025-01-01", "DKK", "Danish VAT on accommodation", "Danish Tax Agency (Skattestyrelsen)"),
    ("EE", "vat_reduced", "percentage", 0.13, "2025-01-01", "EUR", "Estonian VAT on accommodation (increased from 9% Jan 2025)", "Tax and Customs Board"),
    ("FI", "vat_reduced", "percentage", 0.14, "2025-01-01", "EUR", "Finnish VAT on accommodation (increased from 10% Sep 2024)", "Finnish Tax Administration"),
    ("GE", "vat_standard", "percentage", 0.18, "2025-01-01", "GEL", "Georgian VAT on accommodation", "Revenue Service"),
    ("HR", "vat_reduced", "percentage", 0.13, "2025-01-01", "EUR", "Croatian VAT reduced rate on accommodation", "Tax Administration"),
    ("IE", "vat_reduced", "percentage", 0.09, "2025-01-01", "EUR", "Irish VAT reduced rate on tourist accommodation", "Revenue Commissioners"),
    ("IS", "vat_reduced", "percentage", 0.11, "2025-01-01", "ISK", "Icelandic VAT reduced rate on accommodation", "Directorate of Internal Revenue"),
    ("LI", "vat_reduced", "percentage", 0.038, "2025-01-01", "CHF", "Liechtenstein VAT special rate on accommodation", "Tax Administration"),
    ("LT", "vat_reduced", "percentage", 0.09, "2025-01-01", "EUR", "Lithuanian VAT reduced rate on accommodation", "State Tax Inspectorate"),
    ("LU", "vat_reduced", "percentage", 0.03, "2025-01-01", "EUR", "Luxembourg VAT super-reduced rate on accommodation", "Administration des Contributions Directes"),
    ("LV", "vat_reduced", "percentage", 0.12, "2025-01-01", "EUR", "Latvian VAT reduced rate on accommodation", "State Revenue Service"),
    ("MC", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Monaco VAT on accommodation (follows France)", "Direction des Services Fiscaux"),
    ("MD", "vat_reduced", "percentage", 0.12, "2025-01-01", "MDL", "Moldovan VAT on accommodation", "State Tax Service"),
    ("ME", "vat_reduced", "percentage", 0.07, "2025-01-01", "EUR", "Montenegrin VAT reduced rate on accommodation", "Tax Administration"),
    ("MK", "vat_reduced", "percentage", 0.05, "2025-01-01", "MKD", "North Macedonia VAT reduced rate on accommodation", "Public Revenue Office"),
    ("MT", "vat_reduced", "percentage", 0.07, "2025-01-01", "EUR", "Maltese VAT reduced rate on accommodation", "Commissioner for Revenue"),
    ("NO", "vat_reduced", "percentage", 0.12, "2025-01-01", "NOK", "Norwegian VAT reduced rate on accommodation", "Skatteetaten"),
    ("PL", "vat_reduced", "percentage", 0.08, "2025-01-01", "PLN", "Polish VAT reduced rate on accommodation", "Ministry of Finance"),
    ("RO", "vat_reduced", "percentage", 0.09, "2025-01-01", "RON", "Romanian VAT reduced rate on accommodation", "ANAF"),
    ("RS", "vat_reduced", "percentage", 0.10, "2025-01-01", "RSD", "Serbian VAT reduced rate on accommodation", "Tax Administration"),
    ("SE", "vat_reduced", "percentage", 0.12, "2025-01-01", "SEK", "Swedish VAT reduced rate on accommodation", "Swedish Tax Agency"),
    ("SI", "vat_reduced", "percentage", 0.095, "2025-01-01", "EUR", "Slovenian VAT reduced rate on accommodation", "FURS"),
    ("SK", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Slovak VAT reduced rate on accommodation", "Financial Administration"),
    ("TR", "vat_reduced", "percentage", 0.10, "2025-01-01", "TRY", "Turkish VAT on accommodation (special rate)", "Revenue Administration"),
    ("UA", "vat_standard", "percentage", 0.20, "2025-01-01", "UAH", "Ukrainian VAT on accommodation", "State Tax Service"),

    # ─── AMERICAS: VAT/GST on accommodation (national) ─────────────
    ("AR", "vat_standard", "percentage", 0.21, "2025-01-01", "ARS", "Argentina IVA on accommodation", "AFIP"),
    ("BB", "vat_standard", "percentage", 0.175, "2025-01-01", "BBD", "Barbados VAT on accommodation", "Barbados Revenue Authority"),
    ("BO", "vat_standard", "percentage", 0.13, "2025-01-01", "BOB", "Bolivia IVA on accommodation", "Servicio de Impuestos Nacionales"),
    ("BR", "service_pct", "percentage", 0.065, "2025-01-01", "BRL", "Brazil ISS+PIS/COFINS on accommodation services", "Receita Federal"),
    ("BS", "vat_standard", "percentage", 0.10, "2025-01-01", "BSD", "Bahamas VAT on accommodation", "Department of Inland Revenue"),
    ("CA", "vat_standard", "percentage", 0.05, "2025-01-01", "CAD", "Canada GST on accommodation", "Canada Revenue Agency"),
    ("CL", "vat_standard", "percentage", 0.19, "2025-01-01", "CLP", "Chile IVA on accommodation", "SII"),
    ("CO", "vat_standard", "percentage", 0.19, "2025-01-01", "COP", "Colombia IVA on accommodation (exempt for foreign tourists with PIP5)", "DIAN"),
    ("CR", "vat_standard", "percentage", 0.13, "2025-01-01", "CRC", "Costa Rica IVA on accommodation", "Ministerio de Hacienda"),
    ("CU", "service_pct", "percentage", 0.10, "2025-01-01", "CUP", "Cuba accommodation service tax", "ONAT"),
    ("DO", "vat_standard", "percentage", 0.18, "2025-01-01", "DOP", "Dominican Republic ITBIS on accommodation", "DGII"),
    ("EC", "vat_standard", "percentage", 0.15, "2025-01-01", "USD", "Ecuador IVA on accommodation", "SRI"),
    ("JM", "vat_standard", "percentage", 0.15, "2025-01-01", "JMD", "Jamaica GCT on accommodation", "Tax Administration Jamaica"),
    ("PA", "vat_standard", "percentage", 0.07, "2025-01-01", "PAB", "Panama ITBMS on accommodation", "DGI"),
    ("PE", "vat_standard", "percentage", 0.18, "2025-01-01", "PEN", "Peru IGV on accommodation", "SUNAT"),
    ("PY", "vat_standard", "percentage", 0.10, "2025-01-01", "PYG", "Paraguay IVA on accommodation", "SET"),
    ("TT", "vat_standard", "percentage", 0.125, "2025-01-01", "TTD", "Trinidad and Tobago VAT on accommodation", "Board of Inland Revenue"),
    ("UY", "vat_standard", "percentage", 0.22, "2025-01-01", "UYU", "Uruguay IVA on accommodation", "DGI"),
    ("PR", "vat_standard", "percentage", 0.115, "2025-01-01", "USD", "Puerto Rico SUT on accommodation (11.5%)", "SURI"),

    # ─── ASIA-PACIFIC: VAT/GST on accommodation (national) ─────────
    ("BD", "vat_standard", "percentage", 0.15, "2025-01-01", "BDT", "Bangladesh VAT on accommodation", "NBR"),
    ("BH", "vat_standard", "percentage", 0.10, "2025-01-01", "BHD", "Bahrain VAT on accommodation", "NBR"),
    ("BM", "service_pct", "percentage", 0.0725, "2025-01-01", "BMD", "Bermuda hotel occupancy tax", "Office of the Tax Commissioner"),
    ("CN", "vat_standard", "percentage", 0.06, "2025-01-01", "CNY", "China VAT on accommodation services", "State Taxation Administration"),
    ("FJ", "vat_standard", "percentage", 0.15, "2025-01-01", "FJD", "Fiji VAT on accommodation", "FRCS"),
    ("HK", "vat_standard", "percentage", 0.00, "2025-01-01", "HKD", "Hong Kong has no VAT/GST", "Inland Revenue Department"),
    ("IN", "vat_standard", "percentage", 0.18, "2025-01-01", "INR", "India GST on accommodation (>=7500 INR/night)", "GST Council"),
    ("JO", "vat_standard", "percentage", 0.16, "2025-01-01", "JOD", "Jordan GST on accommodation", "ISTD"),
    ("KH", "vat_standard", "percentage", 0.10, "2025-01-01", "KHR", "Cambodia VAT on accommodation", "GDT"),
    ("KR", "vat_standard", "percentage", 0.10, "2025-01-01", "KRW", "South Korea VAT on accommodation", "NTS"),
    ("KW", "vat_standard", "percentage", 0.00, "2025-01-01", "KWD", "Kuwait has no VAT", "Ministry of Finance"),
    ("KY", "service_pct", "percentage", 0.00, "2025-01-01", "KYD", "Cayman Islands has no income/sales tax", "DITC"),
    ("LA", "vat_standard", "percentage", 0.10, "2025-01-01", "LAK", "Laos VAT on accommodation", "Tax Department"),
    ("LB", "vat_standard", "percentage", 0.11, "2025-01-01", "LBP", "Lebanon VAT on accommodation", "Ministry of Finance"),
    ("LK", "vat_standard", "percentage", 0.18, "2025-01-01", "LKR", "Sri Lanka VAT on accommodation", "Inland Revenue"),
    ("MM", "service_pct", "percentage", 0.05, "2025-01-01", "MMK", "Myanmar commercial tax on accommodation", "Internal Revenue Department"),
    ("MO", "vat_standard", "percentage", 0.05, "2025-01-01", "MOP", "Macau tourism tax on accommodation", "Financial Services Bureau"),
    ("MU", "vat_standard", "percentage", 0.15, "2025-01-01", "MUR", "Mauritius VAT on accommodation", "MRA"),
    ("MY", "service_pct", "percentage", 0.08, "2025-01-01", "MYR", "Malaysia SST service tax on accommodation", "Royal Malaysian Customs"),
    ("NP", "vat_standard", "percentage", 0.13, "2025-01-01", "NPR", "Nepal VAT on accommodation", "Inland Revenue Department"),
    ("NZ", "vat_standard", "percentage", 0.15, "2025-01-01", "NZD", "New Zealand GST on accommodation", "Inland Revenue"),
    ("OM", "vat_standard", "percentage", 0.05, "2025-01-01", "OMR", "Oman VAT on accommodation", "Tax Authority"),
    ("PG", "vat_standard", "percentage", 0.10, "2025-01-01", "PGK", "Papua New Guinea GST on accommodation", "IRC"),
    ("PH", "vat_standard", "percentage", 0.12, "2025-01-01", "PHP", "Philippines VAT on accommodation", "BIR"),
    ("PK", "vat_standard", "percentage", 0.18, "2025-01-01", "PKR", "Pakistan sales tax on accommodation services", "FBR"),
    ("QA", "vat_standard", "percentage", 0.00, "2025-01-01", "QAR", "Qatar has no VAT", "GTA"),
    ("SA", "vat_standard", "percentage", 0.15, "2025-01-01", "SAR", "Saudi Arabia VAT on accommodation", "ZATCA"),
    ("SC", "vat_standard", "percentage", 0.15, "2025-01-01", "SCR", "Seychelles VAT on accommodation", "SRC"),
    ("TW", "vat_standard", "percentage", 0.05, "2025-01-01", "TWD", "Taiwan VAT on accommodation", "Ministry of Finance"),
    ("VG", "service_pct", "percentage", 0.00, "2025-01-01", "USD", "BVI has no sales tax", "BVI Government"),
    ("VN", "vat_standard", "percentage", 0.10, "2025-01-01", "VND", "Vietnam VAT on accommodation", "General Department of Taxation"),
    ("ZW", "vat_standard", "percentage", 0.15, "2025-01-01", "ZWL", "Zimbabwe VAT on accommodation", "ZIMRA"),

    # ─── AFRICA: VAT on accommodation (national) ───────────────────
    ("EG", "vat_standard", "percentage", 0.14, "2025-01-01", "EGP", "Egypt VAT on accommodation", "Egyptian Tax Authority"),
    ("ET", "vat_standard", "percentage", 0.15, "2025-01-01", "ETB", "Ethiopia VAT on accommodation", "Ministry of Revenue"),
    ("GH", "vat_standard", "percentage", 0.15, "2025-01-01", "GHS", "Ghana VAT on accommodation (incl. NHIL/GETFund levies ~21.9% total)", "Ghana Revenue Authority"),
    ("KE", "vat_standard", "percentage", 0.16, "2025-01-01", "KES", "Kenya VAT on accommodation", "KRA"),
    ("MA", "vat_standard", "percentage", 0.10, "2025-01-01", "MAD", "Morocco VAT on accommodation (reduced rate)", "DGI"),
    ("NG", "vat_standard", "percentage", 0.075, "2025-01-01", "NGN", "Nigeria VAT on accommodation", "FIRS"),
    ("RW", "vat_standard", "percentage", 0.18, "2025-01-01", "RWF", "Rwanda VAT on accommodation", "RRA"),
    ("TN", "vat_standard", "percentage", 0.07, "2025-01-01", "TND", "Tunisia VAT reduced rate on accommodation", "Direction Generale des Impots"),
    ("TZ", "vat_standard", "percentage", 0.18, "2025-01-01", "TZS", "Tanzania VAT on accommodation", "TRA"),
    ("ZA", "vat_standard", "percentage", 0.15, "2025-01-01", "ZAR", "South Africa VAT on accommodation", "SARS"),

    # ─── CANADA: Provincial accommodation taxes ─────────────────────
    ("CA-ON", "vat_standard", "percentage", 0.08, "2025-01-01", "CAD", "Ontario HST provincial portion on accommodation", "Ontario Ministry of Finance"),
    ("CA-BC", "vat_standard", "percentage", 0.08, "2025-01-01", "CAD", "BC PST on short-term accommodation", "BC Ministry of Finance"),
    ("CA-BC", "municipal_pct", "percentage", 0.03, "2025-01-01", "CAD", "BC MRDT (Municipal & Regional District Tax)", "BC Ministry of Finance"),
    ("CA-QC", "vat_standard", "percentage", 0.09975, "2025-01-01", "CAD", "Quebec QST on accommodation", "Revenu Quebec"),
    ("CA-QC", "tourism_pct", "percentage", 0.035, "2025-01-01", "CAD", "Quebec Lodging Tax (QLT)", "Revenu Quebec"),
    ("CA-AB", "tourism_pct", "percentage", 0.04, "2025-01-01", "CAD", "Alberta Tourism Levy", "Alberta Treasury Board"),
    ("CA-MB", "vat_standard", "percentage", 0.07, "2025-01-01", "CAD", "Manitoba RST on accommodation", "Manitoba Finance"),
    ("CA-MB-WPG", "municipal_pct", "percentage", 0.06, "2025-01-01", "CAD", "Winnipeg accommodation tax (1% higher than provincial)", "City of Winnipeg"),
    ("CA-SK", "vat_standard", "percentage", 0.06, "2025-01-01", "CAD", "Saskatchewan PST on accommodation", "Saskatchewan Finance"),
    ("CA-NS", "vat_standard", "percentage", 0.09, "2025-01-01", "CAD", "Nova Scotia HST provincial portion (reduced Apr 2025)", "Nova Scotia Finance"),
    ("CA-NS", "tourism_pct", "percentage", 0.03, "2025-01-01", "CAD", "Nova Scotia Marketing Levy", "Tourism Nova Scotia"),
    ("CA-NB", "vat_standard", "percentage", 0.10, "2025-01-01", "CAD", "New Brunswick HST provincial portion", "Service New Brunswick"),
    ("CA-PE", "vat_standard", "percentage", 0.10, "2025-01-01", "CAD", "PEI HST provincial portion", "PEI Finance"),
    ("CA-NL", "vat_standard", "percentage", 0.10, "2025-01-01", "CAD", "Newfoundland HST provincial portion", "NL Finance"),
    ("CA-ON-TOR", "municipal_pct", "percentage", 0.06, "2025-01-01", "CAD", "Toronto Municipal Accommodation Tax (MAT)", "City of Toronto"),
    ("CA-QC-MTL", "tourism_flat_night", "flat", 3.50, "2025-01-01", "CAD", "Montreal lodging tax ($3.50/night)", "Tourisme Montreal"),
    ("CA-BC-VAN", "municipal_pct", "percentage", 0.03, "2025-01-01", "CAD", "Vancouver MRDT", "Destination Vancouver"),

    # ─── BRAZIL: Municipal ISS on accommodation ────────────────────
    ("BR-SP-SAO", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Sao Paulo ISS on accommodation", "Prefeitura de Sao Paulo"),
    ("BR-RJ-RIO", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Rio de Janeiro ISS on accommodation", "Prefeitura do Rio"),
    ("BR-MG-BHZ", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Belo Horizonte ISS on accommodation", "Prefeitura de BH"),
    ("BR-BA-SSA", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Salvador ISS on accommodation", "Prefeitura de Salvador"),
    ("BR-DF-BSB", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Brasilia ISS on accommodation", "GDF"),
    ("BR-CE-FOR", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Fortaleza ISS on accommodation", "Prefeitura de Fortaleza"),

    # ─── INDIA: GST tiered rates on accommodation ──────────────────
    ("IN", "vat_reduced", "percentage", 0.05, "2025-09-22", "INR", "India GST 5% on rooms below INR 7,500/night (no ITC)", "GST Council"),
    # State-level surcharges
    ("IN-MH", "service_pct", "percentage", 0.01, "2025-01-01", "INR", "Maharashtra tourism development surcharge", "Maharashtra Tourism"),
    ("IN-RJ", "tourism_pct", "percentage", 0.01, "2025-01-01", "INR", "Rajasthan luxury/tourism tax on hotels", "Rajasthan Finance"),
    ("IN-GA", "tourism_pct", "percentage", 0.01, "2025-01-01", "INR", "Goa tourism tax", "Goa Tourism"),
    ("IN-KA", "tourism_pct", "percentage", 0.02, "2025-01-01", "INR", "Karnataka tourism infrastructure tax", "Karnataka Tourism"),

    # ─── SWITZERLAND: Cantonal/municipal Kurtaxe ───────────────────
    ("CH-GE-GVA", "tourism_flat_person_night", "flat", 3.75, "2025-01-01", "CHF", "Geneva taxe de sejour", "Ville de Geneve"),
    ("CH-ZH-ZRH", "tourism_flat_person_night", "flat", 2.50, "2025-01-01", "CHF", "Zurich tourist tax (Kurtaxe)", "Stadt Zurich"),
    ("CH-BE-BRN", "tourism_flat_person_night", "flat", 3.30, "2025-01-01", "CHF", "Bern tourist tax", "Stadt Bern"),
    ("CH-BE-INT", "tourism_flat_person_night", "flat", 4.80, "2025-01-01", "CHF", "Interlaken tourist tax", "Gemeinde Interlaken"),
    ("CH-LU-LUZ", "tourism_flat_person_night", "flat", 3.00, "2025-01-01", "CHF", "Lucerne tourist tax", "Stadt Luzern"),
    ("CH-BS-BSL", "tourism_flat_person_night", "flat", 4.00, "2025-01-01", "CHF", "Basel tourist tax", "Kanton Basel-Stadt"),
    ("CH-VD-LSN", "tourism_flat_person_night", "flat", 3.00, "2025-01-01", "CHF", "Lausanne tourist tax", "Ville de Lausanne"),
    ("CH-VD-MTX", "tourism_flat_person_night", "flat", 4.50, "2025-01-01", "CHF", "Montreux tourist tax", "Commune de Montreux"),
    ("CH-TI-LUG", "tourism_flat_person_night", "flat", 2.50, "2025-01-01", "CHF", "Lugano tourist tax", "Citta di Lugano"),
    ("CH-GR-DVS", "tourism_flat_person_night", "flat", 6.00, "2025-01-01", "CHF", "Davos tourist tax", "Gemeinde Davos"),
    ("CH-GR-STM", "tourism_flat_person_night", "flat", 7.00, "2025-01-01", "CHF", "St. Moritz tourist tax", "Gemeinde St. Moritz"),
    ("CH-VS-ZMT", "tourism_flat_person_night", "flat", 5.50, "2025-01-01", "CHF", "Zermatt tourist tax", "Gemeinde Zermatt"),

    # ─── EUROPEAN CITY/TOURISM TAXES ───────────────────────────────
    # Belgium
    ("BE-BRU-BRU", "tourism_flat_night", "flat", 5.00, "2025-01-01", "EUR", "Brussels city tax (per room per night)", "Brussels Region"),
    ("BE-VLG-ANR", "tourism_flat_person_night", "flat", 2.97, "2025-01-01", "EUR", "Antwerp city tax", "Stad Antwerpen"),
    ("BE-VLG-BRG", "tourism_flat_person_night", "flat", 3.00, "2025-01-01", "EUR", "Bruges city tax", "Stad Brugge"),
    ("BE-VLG-GNT", "tourism_flat_person_night", "flat", 2.50, "2025-01-01", "EUR", "Ghent city tax", "Stad Gent"),

    # Croatia
    ("HR-21-SPU", "tourism_flat_person_night", "flat", 1.50, "2025-01-01", "EUR", "Split sojourn tax", "City of Split"),
    ("HR-20-DBV", "tourism_flat_person_night", "flat", 2.00, "2025-01-01", "EUR", "Dubrovnik sojourn tax", "City of Dubrovnik"),
    ("HR-01-ZAG", "tourism_flat_person_night", "flat", 1.33, "2025-01-01", "EUR", "Zagreb sojourn tax", "City of Zagreb"),
    ("HR-18-ROV", "tourism_flat_person_night", "flat", 1.50, "2025-01-01", "EUR", "Rovinj sojourn tax", "City of Rovinj"),
    ("HR-18-PUY", "tourism_flat_person_night", "flat", 1.20, "2025-01-01", "EUR", "Pula sojourn tax", "City of Pula"),
    ("HR-19-ZAD", "tourism_flat_person_night", "flat", 1.50, "2025-01-01", "EUR", "Zadar sojourn tax", "City of Zadar"),

    # Romania
    ("RO-B-BUC", "tourism_flat_night", "flat", 10.0, "2025-01-01", "RON", "Bucharest tourist tax (per room, ~2 EUR)", "Bucharest City Hall"),
    ("RO-CJ-CLJ", "tourism_flat_night", "flat", 8.0, "2025-01-01", "RON", "Cluj-Napoca tourist tax", "Cluj-Napoca City Hall"),
    ("RO-BV-BRV", "tourism_flat_night", "flat", 8.0, "2025-01-01", "RON", "Brasov tourist tax", "Brasov City Hall"),
    ("RO-SB-SBZ", "tourism_flat_night", "flat", 6.0, "2025-01-01", "RON", "Sibiu tourist tax", "Sibiu City Hall"),

    # Poland - local climate/spa fees
    ("PL-MZ-WAW", "tourism_flat_person_night", "flat", 5.00, "2025-01-01", "PLN", "Warsaw local fee (oplata miejscowa)", "City of Warsaw"),
    ("PL-MA-KRK", "tourism_flat_person_night", "flat", 5.70, "2025-01-01", "PLN", "Krakow local fee", "City of Krakow"),
    ("PL-PM-GDN", "tourism_flat_person_night", "flat", 3.20, "2025-01-01", "PLN", "Gdansk local fee", "City of Gdansk"),
    ("PL-DS-WRO", "tourism_flat_person_night", "flat", 3.20, "2025-01-01", "PLN", "Wroclaw local fee", "City of Wroclaw"),

    # Bulgaria
    ("BG-22-SOF", "tourism_flat_person_night", "flat", 2.00, "2025-01-01", "BGN", "Sofia tourist tax", "Sofia Municipality"),
    ("BG-03-VAR", "tourism_flat_person_night", "flat", 1.50, "2025-01-01", "BGN", "Varna tourist tax", "Varna Municipality"),
    ("BG-04-PDV", "tourism_flat_person_night", "flat", 1.20, "2025-01-01", "BGN", "Plovdiv tourist tax", "Plovdiv Municipality"),

    # Slovenia
    ("SI-LJ-LJU", "tourism_flat_person_night", "flat", 3.13, "2025-01-01", "EUR", "Ljubljana tourist tax + promo contribution", "City of Ljubljana"),
    ("SI-KR-BLD", "tourism_flat_person_night", "flat", 3.13, "2025-01-01", "EUR", "Bled tourist tax", "Municipality of Bled"),
    ("SI-KP-PIR", "tourism_flat_person_night", "flat", 2.50, "2025-01-01", "EUR", "Piran tourist tax", "Municipality of Piran"),

    # Slovakia
    ("SK-BL-BTS", "tourism_flat_person_night", "flat", 2.00, "2025-01-01", "EUR", "Bratislava accommodation tax", "City of Bratislava"),

    # Serbia
    ("RS-00-BEG", "tourism_flat_person_night", "flat", 160.0, "2025-01-01", "RSD", "Belgrade sojourn tax (~1.30 EUR)", "City of Belgrade"),
    ("RS-NS-NOS", "tourism_flat_person_night", "flat", 120.0, "2025-01-01", "RSD", "Novi Sad sojourn tax (~1 EUR)", "City of Novi Sad"),

    # Nordics
    ("SE-AB-STO", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "SEK", "Stockholm has no city tax (Sweden has no municipal tourism levy)", "Stockholm Municipality"),
    ("NO-03-OSL", "tourism_pct", "percentage", 0.0, "2025-01-01", "NOK", "Oslo has no tourism levy yet (planned from 2026 at up to 3%)", "Oslo Kommune"),
    ("DK-84-CPH", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "DKK", "Copenhagen has no city tourist tax", "Copenhagen Municipality"),
    ("FI-18-HEL", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Helsinki has no city tourist tax", "City of Helsinki"),
    ("IS-1-REK", "tourism_flat_night", "flat", 600.0, "2025-01-01", "ISK", "Reykjavik tourist accommodation tax (gistinattaskattur, ~$4/night)", "City of Reykjavik"),

    # Baltic
    ("EE-37-TLL", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Tallinn has no city tax", "Tallinn City"),
    ("LV-RIX", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Riga has no city tax", "Riga City Council"),
    ("LT-VL-VNO", "tourism_flat_person_night", "flat", 1.00, "2025-01-01", "EUR", "Vilnius accommodation tax", "Vilnius Municipality"),

    # Balkans / SE Europe
    ("ME-BD", "tourism_flat_person_night", "flat", 1.50, "2025-01-01", "EUR", "Budva sojourn tax", "Municipality of Budva"),
    ("ME-KO", "tourism_flat_person_night", "flat", 1.50, "2025-01-01", "EUR", "Kotor sojourn tax", "Municipality of Kotor"),
    ("ME-PG", "tourism_flat_person_night", "flat", 1.00, "2025-01-01", "EUR", "Podgorica sojourn tax", "City of Podgorica"),
    ("AL-TR-TIA", "tourism_flat_person_night", "flat", 150.0, "2025-01-01", "ALL", "Tirana accommodation tax (~1.30 EUR)", "Bashkia Tirane"),
    ("MK-SK-SKP", "tourism_flat_person_night", "flat", 50.0, "2025-01-01", "MKD", "Skopje tourist tax (~0.80 EUR)", "City of Skopje"),
    ("MK-OH", "tourism_flat_person_night", "flat", 40.0, "2025-01-01", "MKD", "Ohrid tourist tax", "Municipality of Ohrid"),
    ("BA-BIH-SJJ", "tourism_flat_person_night", "flat", 2.00, "2025-01-01", "BAM", "Sarajevo tourist tax", "Canton Sarajevo"),

    # Georgia / Ukraine
    ("GE-TB", "tourism_flat_night", "flat", 0.0, "2025-01-01", "GEL", "Tbilisi has no city tourist tax", "Tbilisi City Hall"),
    ("UA-30", "tourism_pct", "percentage", 0.01, "2025-01-01", "UAH", "Kyiv tourist tax (1% of room rate)", "Kyiv City Council"),
    ("UA-46-LWO", "tourism_pct", "percentage", 0.01, "2025-01-01", "UAH", "Lviv tourist tax (1% of room rate)", "Lviv City Council"),

    # Turkey cities
    ("TR-34-IST", "tourism_pct", "percentage", 0.02, "2025-01-01", "TRY", "Istanbul accommodation tax", "Istanbul Metropolitan Municipality"),
    ("TR-07-AYT", "tourism_pct", "percentage", 0.02, "2025-01-01", "TRY", "Antalya accommodation tax", "Antalya Metropolitan Municipality"),

    # Ireland
    ("IE-D-DUB", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Dublin has no city tourist tax", "Dublin City Council"),

    # ─── MIDDLE EAST & GULF ────────────────────────────────────────
    ("SA", "tourism_pct", "percentage", 0.05, "2025-01-01", "SAR", "Saudi Arabia White Land Tax / municipality fee on accommodation", "MOMRAH"),
    ("QA-DA", "tourism_flat_night", "flat", 0.0, "2025-01-01", "QAR", "Doha has no additional tourism levy (VAT-free)", "Qatar Tourism"),
    ("BH-13-BAH", "tourism_flat_night", "flat", 0.0, "2025-01-01", "BHD", "Manama has no additional city tax", "Bahrain Tourism"),
    ("OM-MA-MCT", "tourism_pct", "percentage", 0.04, "2025-01-01", "OMR", "Muscat tourism tax on accommodation", "Muscat Municipality"),
    ("JO-AM-AMM", "service_pct", "percentage", 0.10, "2025-01-01", "JOD", "Jordan hotel service charge", "Ministry of Tourism"),
    ("IL", "vat_standard", "percentage", 0.17, "2025-01-01", "ILS", "Israel VAT on accommodation", "Israel Tax Authority"),
    ("IL-D-ELT", "vat_standard", "percentage", 0.00, "2025-01-01", "ILS", "Eilat VAT exemption (free trade zone)", "Eilat Municipality"),

    # ─── ASIA PACIFIC: Tourism/city levies ─────────────────────────
    ("MY", "tourism_flat_night", "flat", 10.0, "2025-01-01", "MYR", "Malaysia Tourism Tax (TTx, RM10/room/night, foreign guests)", "Tourism Malaysia"),
    ("VN-SG", "service_pct", "percentage", 0.05, "2025-01-01", "VND", "Ho Chi Minh City service charge (common)", "HCMC Tax Department"),
    ("VN-HN", "service_pct", "percentage", 0.05, "2025-01-01", "VND", "Hanoi service charge (common)", "Hanoi Tax Department"),
    ("KR-49-CJU", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "KRW", "Jeju considering tourism tax (not yet enacted)", "Jeju Province"),
    ("PH-NCR-MNL", "municipal_pct", "percentage", 0.01, "2025-01-01", "PHP", "Manila local business tax on accommodation", "Manila City Hall"),
    ("KH-12", "tourism_pct", "percentage", 0.02, "2025-01-01", "KHR", "Phnom Penh accommodation tax", "Ministry of Tourism"),
    ("LK-1-CMB", "tourism_pct", "percentage", 0.01, "2025-01-01", "LKR", "Colombo tourism development levy", "SLTDA"),
    ("NP-BA-KTM", "tourism_pct", "percentage", 0.02, "2025-01-01", "NPR", "Kathmandu tourism service charge", "Nepal Tourism Board"),

    # ─── AFRICA: Tourism levies ────────────────────────────────────
    ("ZA", "tourism_pct", "percentage", 0.01, "2025-01-01", "ZAR", "South Africa tourism levy (1%)", "SA Tourism"),
    ("KE-110-NBO", "tourism_flat_night", "flat", 200.0, "2025-01-01", "KES", "Nairobi county hotel levy (~$1.50/night)", "Nairobi County"),
    ("KE-001-MBA", "tourism_flat_night", "flat", 200.0, "2025-01-01", "KES", "Mombasa county hotel levy", "Mombasa County"),
    ("TZ-25-ZNZ", "eco_flat_person_night", "flat", 5.0, "2025-01-01", "USD", "Zanzibar infrastructure tax ($5/person/night)", "Zanzibar Revenue Board"),
    ("RW-01", "eco_flat_person_night", "flat", 0.0, "2025-01-01", "RWF", "Kigali has no additional city levy", "RDB"),
    ("MA-MAR-RAK", "tourism_flat_person_night", "flat", 25.0, "2025-01-01", "MAD", "Marrakech tourist tax (~$2.50)", "Commune de Marrakech"),
    ("MA-CAS-CMN", "tourism_flat_person_night", "flat", 25.0, "2025-01-01", "MAD", "Casablanca tourist tax", "Commune de Casablanca"),
    ("MA-FES-FEZ", "tourism_flat_person_night", "flat", 20.0, "2025-01-01", "MAD", "Fez tourist tax", "Commune de Fez"),
    ("TN-11-TUN", "tourism_flat_person_night", "flat", 3.0, "2025-01-01", "TND", "Tunis tourist tax", "Commune de Tunis"),
    ("EG-C-CAI", "service_pct", "percentage", 0.12, "2025-01-01", "EGP", "Cairo service charge on hotels", "Cairo Governorate"),
    ("EG-JS-SSH", "eco_flat_person_night", "flat", 0.0, "2025-01-01", "EGP", "Sharm el-Sheikh has no additional tourist levy", "South Sinai Governorate"),
    ("NG-LA-LOS", "municipal_pct", "percentage", 0.05, "2025-01-01", "NGN", "Lagos consumption tax on accommodation", "LIRS"),

    # ─── CARIBBEAN / ISLANDS ───────────────────────────────────────
    ("BB", "tourism_pct", "percentage", 0.10, "2025-01-01", "BBD", "Barbados room rate levy (10%)", "BTMI"),
    ("BB", "service_pct", "percentage", 0.10, "2025-01-01", "BBD", "Barbados service charge (10%)", "BTMI"),
    ("BS", "tourism_pct", "percentage", 0.06, "2025-01-01", "BSD", "Bahamas hotel guest tax (6%)", "Bahamas Tourism"),
    ("JM", "tourism_pct", "percentage", 0.10, "2025-01-01", "JMD", "Jamaica accommodation tax", "Jamaica Tourist Board"),
    ("DO", "tourism_pct", "percentage", 0.10, "2025-01-01", "DOP", "Dominican Republic accommodation tip tax", "DR Tourism"),
    ("TT", "tourism_flat_night", "flat", 100.0, "2025-01-01", "TTD", "Trinidad & Tobago hotel room tax", "Ministry of Tourism"),
    ("SC", "eco_flat_person_night", "flat", 4.25, "2025-01-01", "USD", "Seychelles environmental levy ($4.25/person/night)", "Seychelles Tourism"),
    ("MU", "eco_flat_person_night", "flat", 0.0, "2025-01-01", "MUR", "Mauritius has no per-night tourist levy", "MTPA"),
    ("FJ", "eco_flat_person_night", "flat", 10.0, "2025-01-01", "FJD", "Fiji Environment & Climate Adaptation Levy (ECAL) ~$5/night", "FRCS"),
    ("MV", "eco_flat_person_night", "flat", 12.0, "2025-01-01", "USD", "Maldives Green Tax ($12/person/night resorts, doubled Jan 2025)", "MIRA"),
    ("KY", "tourism_pct", "percentage", 0.13, "2025-01-01", "KYD", "Cayman Islands accommodation tax (13%)", "DITC"),
    ("BM", "tourism_pct", "percentage", 0.0925, "2025-01-01", "BMD", "Bermuda hotel occupancy tax (9.25%)", "Bermuda Finance"),
    ("VG", "tourism_pct", "percentage", 0.10, "2025-01-01", "USD", "BVI accommodation tax (10%)", "BVI Tourism"),

    # ─── LATIN AMERICA: Accommodation levies ───────────────────────
    ("MX", "occ_pct", "percentage", 0.03, "2025-01-01", "MXN", "Mexico general lodging tax (3%, varies by state 2-5%)", "SAT"),
    ("AR-BA-BUE", "tourism_pct", "percentage", 0.03, "2025-01-01", "ARS", "Buenos Aires city tourism tax", "AGIP Buenos Aires"),
    ("CO-DC-BOG", "service_pct", "percentage", 0.0, "2025-01-01", "COP", "Bogota: foreign tourists exempt from IVA on hotels", "DIAN"),
    ("CO-BOL-CTG", "tourism_pct", "percentage", 0.025, "2025-01-01", "COP", "Cartagena tourism contribution", "Corpoturismo"),
    ("PE-LIM-LIM", "municipal_pct", "percentage", 0.0, "2025-01-01", "PEN", "Lima has no additional municipal hotel tax", "Municipalidad de Lima"),
    ("CL-RM-SCL", "tourism_pct", "percentage", 0.0, "2025-01-01", "CLP", "Santiago: foreign tourists exempt from IVA on hotels (19%)", "SII"),
    ("CR-SJ-SJO", "tourism_pct", "percentage", 0.05, "2025-01-01", "CRC", "Costa Rica tourism tax (5%)", "ICT"),
    ("PA-8-PTY", "tourism_pct", "percentage", 0.10, "2025-01-01", "PAB", "Panama hotel accommodation tax (10%)", "ATP"),
    ("EC-P-UIO", "service_pct", "percentage", 0.10, "2025-01-01", "USD", "Quito hotel service charge (10%)", "Quito Tourism"),

    # ─── OCEANIA ────────────────────────────────────────────────────
    ("NZ-OTA-ZQN", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "NZD", "Queenstown IVL considered but not enacted as per-night levy", "QLDC"),
    ("SG", "service_pct", "percentage", 0.10, "2025-01-01", "SGD", "Singapore hotel service charge (10%)", "STB"),
    ("HK", "tourism_pct", "percentage", 0.0, "2025-01-01", "HKD", "Hong Kong has no hotel tax", "Tourism Commission"),
    ("MO", "tourism_pct", "percentage", 0.05, "2025-01-01", "MOP", "Macau tourism tax (5%)", "MGTO"),

    # ─── CHINA: City-level accommodation levies ────────────────────
    ("CN-11-PEK", "municipal_pct", "percentage", 0.0, "2025-01-01", "CNY", "Beijing has no additional city tourism tax", "Beijing Municipal Tax"),
    ("CN-31-SHA", "municipal_pct", "percentage", 0.0, "2025-01-01", "CNY", "Shanghai has no additional city tourism tax", "Shanghai Municipal Tax"),
    ("CN-46-SYX", "eco_flat_person_night", "flat", 0.0, "2025-01-01", "CNY", "Sanya has no per-night eco tax", "Hainan Tourism"),
]


# ═══════════════════════════════════════════════════════════════════
# EXEMPTION RULES
# ═══════════════════════════════════════════════════════════════════
# Format: (jurisdiction_code, rule_type, name, priority, conditions, action,
#          effective_start, legal_reference)

RULES: list[tuple] = [
    # Long-stay exemptions
    ("CA-ON-TOR", "exemption", "Toronto MAT long-stay exemption", 100,
     {"operator": "AND", "rules": [{"field": "stay_length_days", "op": ">=", "value": 28}]},
     {}, "2025-01-01", "Toronto MAT Bylaw 1403-2017"),
    ("BE-BRU-BRU", "exemption", "Brussels long-stay exemption", 100,
     {"operator": "AND", "rules": [{"field": "stay_length_days", "op": ">=", "value": 90}]},
     {}, "2025-01-01", "Brussels Tax Code"),
    ("HR-20-DBV", "exemption", "Dubrovnik child exemption (under 12)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 12}]},
     {}, "2025-01-01", "Croatian Tourism Act"),
    ("SI-LJ-LJU", "exemption", "Ljubljana child exemption (under 7)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 7}]},
     {}, "2025-01-01", "Slovenian Tourism Act"),
    ("PL-MA-KRK", "exemption", "Krakow child exemption (under 7)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 7}]},
     {}, "2025-01-01", "Polish Local Tax Act"),
    ("IL-D-ELT", "exemption", "Eilat VAT exemption (free trade zone)", 200,
     {}, {}, "2025-01-01", "Eilat Free Trade Zone Act"),
    ("CO-DC-BOG", "exemption", "Colombia foreign tourist IVA exemption", 100,
     {"operator": "AND", "rules": [{"field": "guest_nationality", "op": "!=", "value": "CO"}]},
     {}, "2025-01-01", "Colombia Tax Code Art. 481"),
    ("CL-RM-SCL", "exemption", "Chile foreign tourist IVA exemption", 100,
     {"operator": "AND", "rules": [{"field": "guest_nationality", "op": "!=", "value": "CL"}]},
     {}, "2025-01-01", "Chilean IVA Exemption for Tourists"),
    ("IN", "reduction", "India GST reduced rate for budget hotels", 100,
     {"operator": "AND", "rules": [{"field": "nightly_rate", "op": "<", "value": 7500}]},
     {"reduction_percent": 0.72}, "2025-09-22", "GST Council 54th Meeting"),
    # Cap rules
    ("BB", "cap", "Barbados room rate levy cap (max 30 nights)", 100,
     {}, {"max_nights": 30}, "2025-01-01", "Barbados Tourism Levy Act"),
    ("MV", "cap", "Maldives Green Tax cap (guesthouses: $6/night)", 50,
     {"operator": "AND", "rules": [{"field": "property_type", "op": "in", "value": ["guesthouse", "hostel"]}]},
     {"max_per_person_per_night": 6.0}, "2025-01-01", "Maldives Green Tax Amendment 2024"),
]


# ═══════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════

async def seed(api_base: str, api_key: str):
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    created_rates = skipped_rates = error_rates = 0
    created_rules = skipped_rules = error_rules = 0
    t0 = time.time()

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        h = (await client.get(f"{api_base}/health")).json()
        print(f"API: {h['status']} | DB: {h['database']}")

        # First, get existing rates to avoid duplicates
        existing = set()
        for offset in range(0, 2000, 500):
            resp = await client.get(f"{api_base}/v1/rates", params={"limit": "500", "offset": str(offset)})
            if resp.status_code != 200:
                break
            for r in resp.json():
                existing.add((r["jurisdiction_code"], r["tax_category_code"]))
            if len(resp.json()) < 500:
                break
        print(f"Existing rates: {len(existing)} (jurisdiction+category combos)")

        # Insert rates
        print(f"\nInserting {len(RATES)} tax rates...")
        for jur_code, cat_code, rate_type, rate_value, eff_start, currency, legal_ref, authority in RATES:
            if (jur_code, cat_code) in existing:
                skipped_rates += 1
                continue

            body = {
                "jurisdiction_code": jur_code,
                "tax_category_code": cat_code,
                "rate_type": rate_type,
                "rate_value": rate_value,
                "effective_start": eff_start,
                "currency_code": currency,
                "status": "active",
                "legal_reference": legal_ref,
                "authority_name": authority,
                "created_by": "data_research",
            }
            resp = await client.post(f"{api_base}/v1/rates", json=body)
            if resp.status_code == 201:
                created_rates += 1
            elif resp.status_code == 409:
                skipped_rates += 1
            else:
                error_rates += 1
                err = resp.text[:100]
                print(f"  ! {jur_code}/{cat_code}: {resp.status_code} - {err}")

        print(f"Rates: {created_rates} created, {skipped_rates} skipped, {error_rates} errors")

        # Insert rules
        print(f"\nInserting {len(RULES)} exemption/cap rules...")
        for jur_code, rule_type, name, priority, conditions, action, eff_start, legal_ref in RULES:
            body = {
                "jurisdiction_code": jur_code,
                "rule_type": rule_type,
                "name": name,
                "priority": priority,
                "conditions": conditions,
                "action": action,
                "effective_start": eff_start,
                "legal_reference": legal_ref,
                "created_by": "data_research",
            }
            resp = await client.post(f"{api_base}/v1/rules", json=body)
            if resp.status_code == 201:
                created_rules += 1
            elif resp.status_code == 409:
                skipped_rules += 1
            else:
                error_rules += 1
                err = resp.text[:100]
                print(f"  ! {jur_code}/{name}: {resp.status_code} - {err}")

        print(f"Rules: {created_rules} created, {skipped_rules} skipped, {error_rules} errors")

    elapsed = int(time.time() - t0)
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed}s")
    print(f"  Rates:  {created_rates} created, {skipped_rates} skipped, {error_rates} errors")
    print(f"  Rules:  {created_rules} created, {skipped_rules} skipped, {error_rules} errors")
    print(f"{'='*60}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default="http://localhost:8001")
    p.add_argument("--api-key", default="dev-api-key-change-me")
    args = p.parse_args()
    asyncio.run(seed(args.api_url, args.api_key))


if __name__ == "__main__":
    main()
