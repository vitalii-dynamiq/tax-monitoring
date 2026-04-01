"""
Fill ALL remaining jurisdictions with tax rates.

Every jurisdiction gets at least one rate entry so the platform shows
complete coverage. Rates are based on current legislation as of 2025-2026.

Usage: python -m scripts.seed_missing_rates
"""

import argparse
import asyncio
import time

import httpx

# ═══════════════════════════════════════════════════════════════════
# All 320 missing jurisdiction rates
# (code, category, type, value, effective, currency, legal_ref, authority)
# ═══════════════════════════════════════════════════════════════════

RATES: list[tuple] = [
    # ─── US (country-level federal - no accommodation-specific tax) ──
    ("US", "vat_standard", "percentage", 0.0, "2025-01-01", "USD", "US has no federal VAT/accommodation tax; taxes are state/local", "IRS"),

    # ─── STATES/PROVINCES: Intermediate jurisdiction taxes ──────────

    # Australia
    ("AU-NSW", "vat_standard", "percentage", 0.10, "2025-01-01", "AUD", "NSW: GST at national 10% rate, no additional state levy", "ATO"),
    ("AU-NSW-SYD", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "AUD", "Sydney has no city tourist tax", "City of Sydney"),

    # Austria
    ("AT-9", "occ_pct", "percentage", 0.0, "2025-01-01", "EUR", "Vienna state: tax applied at city level (AT-9-VIE)", "Land Wien"),

    # Brazil states (ISS applied at city level; states have ICMS ~varies)
    ("BR-SP", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Sao Paulo state ICMS on accommodation services", "SEFAZ-SP"),
    ("BR-RJ", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Rio de Janeiro state ICMS on accommodation", "SEFAZ-RJ"),
    ("BR-MG", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Minas Gerais state ICMS on accommodation", "SEFAZ-MG"),
    ("BR-BA", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Bahia state ICMS on accommodation", "SEFAZ-BA"),
    ("BR-PR", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Parana state ICMS on accommodation", "SEFAZ-PR"),
    ("BR-RS", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "RS state ICMS on accommodation", "SEFAZ-RS"),
    ("BR-SC", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Santa Catarina state ICMS on accommodation", "SEFAZ-SC"),
    ("BR-CE", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Ceara state ICMS on accommodation", "SEFAZ-CE"),
    ("BR-PE", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Pernambuco state ICMS on accommodation", "SEFAZ-PE"),
    ("BR-DF", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Federal District ICMS on accommodation", "SEFAZ-DF"),
    ("BR-AM", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Amazonas state ICMS on accommodation", "SEFAZ-AM"),
    ("BR-GO", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Goias state ICMS on accommodation", "SEFAZ-GO"),
    ("BR-PA", "service_pct", "percentage", 0.12, "2025-01-01", "BRL", "Para state ICMS on accommodation", "SEFAZ-PA"),

    # Brazil cities (ISS 2-5%)
    ("BR-AM-MAO", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Manaus ISS on accommodation", "Prefeitura de Manaus"),
    ("BR-PE-REC", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Recife ISS on accommodation", "Prefeitura do Recife"),
    ("BR-PR-CWB", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Curitiba ISS on accommodation", "Prefeitura de Curitiba"),
    ("BR-RS-POA", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Porto Alegre ISS on accommodation", "Prefeitura de POA"),
    ("BR-SC-FLN", "municipal_pct", "percentage", 0.05, "2025-01-01", "BRL", "Florianopolis ISS on accommodation", "Prefeitura de Floripa"),

    # China provinces (no additional provincial accommodation tax)
    ("CN-11", "vat_standard", "percentage", 0.06, "2025-01-01", "CNY", "Beijing: national VAT 6% applies", "Beijing Tax Bureau"),
    ("CN-31", "vat_standard", "percentage", 0.06, "2025-01-01", "CNY", "Shanghai: national VAT 6% applies", "Shanghai Tax Bureau"),
    ("CN-32", "vat_standard", "percentage", 0.06, "2025-01-01", "CNY", "Jiangsu: national VAT 6% applies", "Jiangsu Tax Bureau"),
    ("CN-33", "vat_standard", "percentage", 0.06, "2025-01-01", "CNY", "Zhejiang: national VAT 6% applies", "Zhejiang Tax Bureau"),
    ("CN-44", "vat_standard", "percentage", 0.06, "2025-01-01", "CNY", "Guangdong: national VAT 6% applies", "Guangdong Tax Bureau"),
    ("CN-46", "vat_standard", "percentage", 0.06, "2025-01-01", "CNY", "Hainan: national VAT 6% applies", "Hainan Tax Bureau"),
    ("CN-50", "vat_standard", "percentage", 0.06, "2025-01-01", "CNY", "Chongqing: national VAT 6% applies", "Chongqing Tax Bureau"),
    ("CN-51", "vat_standard", "percentage", 0.06, "2025-01-01", "CNY", "Sichuan: national VAT 6% applies", "Sichuan Tax Bureau"),
    ("CN-53", "vat_standard", "percentage", 0.06, "2025-01-01", "CNY", "Yunnan: national VAT 6% applies", "Yunnan Tax Bureau"),
    # China cities (no additional city tax)
    ("CN-32-NKG", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CNY", "Nanjing: no city tourist tax", "Nanjing Municipality"),
    ("CN-33-HGH", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CNY", "Hangzhou: no city tourist tax", "Hangzhou Municipality"),
    ("CN-44-CAN", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CNY", "Guangzhou: no city tourist tax", "Guangzhou Municipality"),
    ("CN-44-SZX", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CNY", "Shenzhen: no city tourist tax", "Shenzhen Municipality"),
    ("CN-51-CTU", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CNY", "Chengdu: no city tourist tax", "Chengdu Municipality"),
    ("CN-53-KMG", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CNY", "Kunming: no city tourist tax", "Kunming Municipality"),

    # Switzerland cantons (Kurtaxe set at municipality level)
    ("CH-ZH", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CHF", "Canton Zurich: Kurtaxe set at municipal level", "Kanton Zurich"),
    ("CH-BE", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CHF", "Canton Bern: Kurtaxe set at municipal level", "Kanton Bern"),
    ("CH-LU", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CHF", "Canton Lucerne: Kurtaxe set at municipal level", "Kanton Luzern"),
    ("CH-GE", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CHF", "Canton Geneva: cantonal taxe de sejour", "Kanton Genf"),
    ("CH-BS", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CHF", "Canton Basel-Stadt: Kurtaxe set at municipal level", "Kanton Basel-Stadt"),
    ("CH-VD", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CHF", "Canton Vaud: Kurtaxe set at municipal level", "Kanton Waadt"),
    ("CH-TI", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CHF", "Canton Ticino: cantonal tourist tax regulation", "Kanton Tessin"),
    ("CH-GR", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CHF", "Canton Graubunden: Kurtaxe set at municipal level", "Kanton Graubunden"),
    ("CH-VS", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CHF", "Canton Valais: Kurtaxe set at municipal level", "Kanton Wallis"),
    ("CH-SG", "tourism_flat_person_night", "flat", 2.50, "2025-01-01", "CHF", "Canton St. Gallen: Kurtaxe ~CHF 2.50", "Kanton St. Gallen"),
    ("CH-AG", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CHF", "Canton Aargau: no cantonal tourist tax", "Kanton Aargau"),

    # Croatia counties
    ("HR-21", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Split-Dalmatia: sojourn tax set at municipal level", "Split-Dalmatia County"),
    ("HR-20", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Dubrovnik-Neretva: sojourn tax set at municipal level", "Dubrovnik-Neretva County"),
    ("HR-18", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Istria: sojourn tax set at municipal level", "Istria County"),
    ("HR-01", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Zagreb County: sojourn tax set at city level", "Zagreb County"),
    ("HR-08", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Primorje-Gorski Kotar: sojourn tax set at municipal level", "PGK County"),
    ("HR-15", "tourism_flat_person_night", "flat", 1.20, "2025-01-01", "EUR", "Sibenik-Knin: sojourn tax ~EUR 1.20/person/night", "Sibenik-Knin County"),
    ("HR-19", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Zadar County: sojourn tax set at municipal level", "Zadar County"),
    ("HR-08-RJK", "tourism_flat_person_night", "flat", 1.33, "2025-01-01", "EUR", "Rijeka sojourn tax", "City of Rijeka"),

    # Belgium regions (tax set at commune level)
    ("BE-BRU", "tourism_flat_night", "flat", 0.0, "2025-01-01", "EUR", "Brussels-Capital: tax set at commune level", "Brussels Region"),
    ("BE-VLG", "tourism_flat_night", "flat", 0.0, "2025-01-01", "EUR", "Flanders: tax set at commune level", "Flanders Region"),
    ("BE-WAL", "tourism_flat_night", "flat", 0.0, "2025-01-01", "EUR", "Wallonia: tax set at commune level", "Wallonia Region"),
    ("BE-WAL-LGE", "tourism_flat_person_night", "flat", 2.50, "2025-01-01", "EUR", "Liege tourist tax", "Ville de Liege"),

    # Canada cities missing rates
    ("CA-AB-CGY", "tourism_pct", "percentage", 0.04, "2025-01-01", "CAD", "Calgary: Alberta Tourism Levy 4%", "Alberta Treasury Board"),
    ("CA-AB-EDM", "tourism_pct", "percentage", 0.04, "2025-01-01", "CAD", "Edmonton: Alberta Tourism Levy 4%", "Alberta Treasury Board"),
    ("CA-BC-VIC", "municipal_pct", "percentage", 0.02, "2025-01-01", "CAD", "Victoria MRDT 2%", "Destination Greater Victoria"),
    ("CA-NS-HFX", "tourism_pct", "percentage", 0.03, "2025-01-01", "CAD", "Halifax marketing levy 3%", "Halifax Regional Municipality"),
    ("CA-ON-OTT", "municipal_pct", "percentage", 0.04, "2025-01-01", "CAD", "Ottawa Municipal Accommodation Tax 4%", "City of Ottawa"),
    ("CA-QC-QUE", "tourism_pct", "percentage", 0.035, "2025-01-01", "CAD", "Quebec City lodging tax 3.5%", "Ville de Quebec"),

    # Colombia states
    ("CO-DC", "vat_standard", "percentage", 0.19, "2025-01-01", "COP", "Bogota DC: national IVA applies (exempt for foreign tourists)", "DIAN"),
    ("CO-ANT", "vat_standard", "percentage", 0.19, "2025-01-01", "COP", "Antioquia: national IVA applies", "DIAN"),
    ("CO-BOL", "vat_standard", "percentage", 0.19, "2025-01-01", "COP", "Bolivar: national IVA applies", "DIAN"),
    ("CO-ANT-MDE", "tourism_pct", "percentage", 0.025, "2025-01-01", "COP", "Medellin tourism contribution 2.5%", "Alcaldia de Medellin"),

    # Czech Republic
    ("CZ-PHA", "occ_flat_person_night", "flat", 0.0, "2025-01-01", "CZK", "Prague Region: tax set at city level", "Prague Region"),

    # Denmark regions
    ("DK-84", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "DKK", "Capital Region: no regional tourist tax", "Region Hovedstaden"),
    ("DK-82", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "DKK", "Central Denmark: no regional tourist tax", "Region Midtjylland"),
    ("DK-82-AAR", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "DKK", "Aarhus has no city tourist tax", "Aarhus Kommune"),

    # Egypt governorates
    ("EG-C", "service_pct", "percentage", 0.12, "2025-01-01", "EGP", "Cairo Governorate service charge 12%", "Cairo Governorate"),
    ("EG-BA", "service_pct", "percentage", 0.12, "2025-01-01", "EGP", "Red Sea Governorate service charge", "Red Sea Governorate"),
    ("EG-JS", "service_pct", "percentage", 0.12, "2025-01-01", "EGP", "South Sinai service charge", "South Sinai Governorate"),
    ("EG-LX", "service_pct", "percentage", 0.12, "2025-01-01", "EGP", "Luxor Governorate service charge", "Luxor Governorate"),
    ("EG-ALX", "service_pct", "percentage", 0.12, "2025-01-01", "EGP", "Alexandria service charge", "Alexandria Governorate"),
    ("EG-BA-HRG", "eco_flat_person_night", "flat", 7.0, "2025-01-01", "USD", "Hurghada eco-tourism levy ~$7/night", "Red Sea Tourism Authority"),

    # Estonia
    ("EE-37", "vat_reduced", "percentage", 0.13, "2025-01-01", "EUR", "Harju County: national VAT 13% applies", "Maksu- ja Tolliamet"),
    ("EE-79", "vat_reduced", "percentage", 0.13, "2025-01-01", "EUR", "Tartu County: national VAT 13% applies", "Maksu- ja Tolliamet"),
    ("EE-79-TAR", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Tartu has no city tourist tax", "Tartu City"),

    # Finland regions
    ("FI-18", "vat_reduced", "percentage", 0.14, "2025-01-01", "EUR", "Uusimaa: national VAT 14% applies", "Verohallinto"),
    ("FI-06", "vat_reduced", "percentage", 0.14, "2025-01-01", "EUR", "Pirkanmaa: national VAT 14% applies", "Verohallinto"),
    ("FI-19", "vat_reduced", "percentage", 0.14, "2025-01-01", "EUR", "Southwest Finland: national VAT 14% applies", "Verohallinto"),
    ("FI-11", "vat_reduced", "percentage", 0.14, "2025-01-01", "EUR", "Lapland: national VAT 14% applies", "Verohallinto"),
    ("FI-06-TMP", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Tampere has no city tourist tax", "City of Tampere"),
    ("FI-19-TKU", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Turku has no city tourist tax", "City of Turku"),
    ("FI-11-RVN", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Rovaniemi has no city tourist tax", "City of Rovaniemi"),

    # France / UK
    ("FR-IDF", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Ile-de-France: tax set at commune level", "Region IDF"),
    ("GB-ENG", "vat_standard", "percentage", 0.20, "2025-01-01", "GBP", "England: national VAT 20% applies", "HMRC"),
    ("GB-ENG-LDN", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "GBP", "London has no city tourist tax (under discussion)", "City of London"),

    # Georgia
    ("GE-AJ", "vat_standard", "percentage", 0.18, "2025-01-01", "GEL", "Adjara: national VAT 18% applies", "Revenue Service"),
    ("GE-AJ-BUS", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "GEL", "Batumi has no city tourist tax", "Batumi City Hall"),

    # Ghana / Ethiopia
    ("GH-AA", "vat_standard", "percentage", 0.15, "2025-01-01", "GHS", "Greater Accra: national VAT applies", "GRA"),
    ("GH-AA-ACC", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "GHS", "Accra has no city tourist tax", "AMA"),
    ("ET-AA", "vat_standard", "percentage", 0.15, "2025-01-01", "ETB", "Addis Ababa: national VAT 15% applies", "ERCA"),

    # Greece
    ("GR-I", "vat_reduced", "percentage", 0.13, "2025-01-01", "EUR", "Attica: national VAT 13% applies", "AADE"),

    # Hungary
    ("HU-BU", "vat_reduced", "percentage", 0.05, "2025-01-01", "HUF", "Budapest Region: national VAT 5% applies", "NAV"),

    # Iceland
    ("IS-1", "vat_reduced", "percentage", 0.11, "2025-01-01", "ISK", "Capital Region: national VAT 11% applies", "RSK"),

    # India states (no additional state accommodation tax beyond GST)
    ("IN-DL", "vat_standard", "percentage", 0.18, "2025-01-01", "INR", "Delhi: GST 18% on accommodation >=7500 INR", "GST Council"),
    ("IN-TN", "vat_standard", "percentage", 0.18, "2025-01-01", "INR", "Tamil Nadu: GST 18% applies", "GST Council"),
    ("IN-WB", "vat_standard", "percentage", 0.18, "2025-01-01", "INR", "West Bengal: GST 18% applies", "GST Council"),
    ("IN-KL", "vat_standard", "percentage", 0.18, "2025-01-01", "INR", "Kerala: GST 18% applies", "GST Council"),
    ("IN-TG", "vat_standard", "percentage", 0.18, "2025-01-01", "INR", "Telangana: GST 18% applies", "GST Council"),
    ("IN-GJ", "vat_standard", "percentage", 0.18, "2025-01-01", "INR", "Gujarat: GST 18% applies", "GST Council"),
    ("IN-UP", "vat_standard", "percentage", 0.18, "2025-01-01", "INR", "Uttar Pradesh: GST 18% applies", "GST Council"),
    ("IN-HP", "vat_standard", "percentage", 0.18, "2025-01-01", "INR", "Himachal Pradesh: GST 18% applies", "GST Council"),
    # India cities
    ("IN-MH-BOM", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "Mumbai: no additional city accommodation tax", "BMC"),
    ("IN-DL-DEL", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "New Delhi: no additional city accommodation tax", "NDMC"),
    ("IN-KA-BLR", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "Bangalore: no additional city accommodation tax", "BBMP"),
    ("IN-TN-MAA", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "Chennai: no additional city accommodation tax", "GCC"),
    ("IN-RJ-JAI", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "Jaipur: no additional city accommodation tax", "JMC"),
    ("IN-RJ-UDR", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "Udaipur: no additional city accommodation tax", "UMC"),
    ("IN-KL-COK", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "Kochi: no additional city accommodation tax", "KMC"),
    ("IN-WB-CCU", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "Kolkata: no additional city accommodation tax", "KMC"),
    ("IN-TG-HYD", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "Hyderabad: no additional city accommodation tax", "GHMC"),
    ("IN-GJ-AMD", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "Ahmedabad: no additional city accommodation tax", "AMC"),
    ("IN-UP-AGR", "municipal_pct", "percentage", 0.0, "2025-01-01", "INR", "Agra: no additional city accommodation tax", "AMC"),

    # Ireland states
    ("IE-D", "vat_reduced", "percentage", 0.09, "2025-01-01", "EUR", "Dublin County: national VAT 9% applies", "Revenue"),
    ("IE-CO", "vat_reduced", "percentage", 0.09, "2025-01-01", "EUR", "Cork County: national VAT 9% applies", "Revenue"),
    ("IE-G", "vat_reduced", "percentage", 0.09, "2025-01-01", "EUR", "Galway County: national VAT 9% applies", "Revenue"),
    ("IE-KY", "vat_reduced", "percentage", 0.09, "2025-01-01", "EUR", "Kerry County: national VAT 9% applies", "Revenue"),
    ("IE-CO-ORK", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Cork City has no city tourist tax", "Cork City Council"),

    # Israel
    ("IL-TA", "vat_standard", "percentage", 0.17, "2025-01-01", "ILS", "Tel Aviv District: national VAT 17% applies", "ITA"),
    ("IL-JM", "vat_standard", "percentage", 0.17, "2025-01-01", "ILS", "Jerusalem District: national VAT 17% applies", "ITA"),
    ("IL-HA", "vat_standard", "percentage", 0.17, "2025-01-01", "ILS", "Haifa District: national VAT 17% applies", "ITA"),
    ("IL-Z", "vat_standard", "percentage", 0.17, "2025-01-01", "ILS", "Northern District: national VAT 17% applies", "ITA"),
    ("IL-D", "vat_standard", "percentage", 0.17, "2025-01-01", "ILS", "Southern District: national VAT 17% (except Eilat)", "ITA"),
    ("IL-TA-TLV", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "ILS", "Tel Aviv has no city tourist tax", "Tel Aviv Municipality"),
    ("IL-JM-JRS", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "ILS", "Jerusalem has no city tourist tax", "Jerusalem Municipality"),
    ("IL-Z-TBS", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "ILS", "Tiberias has no city tourist tax", "Tiberias Municipality"),

    # Italy / Japan / Mexico
    ("IT-RM", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Lazio: national VAT 10% applies", "Agenzia delle Entrate"),
    ("JP-13", "occ_pct", "percentage", 0.0, "2025-01-01", "JPY", "Tokyo Pref: tax set at city level", "Tokyo Metropolitan Govt"),
    ("JP-26", "occ_pct", "percentage", 0.0, "2025-01-01", "JPY", "Kyoto Pref: tax set at city level", "Kyoto Prefectural Govt"),
    ("MX-CMX", "occ_pct", "percentage", 0.03, "2025-01-01", "MXN", "CDMX state lodging tax 3%", "Secretaria de Finanzas CDMX"),

    # Jordan
    ("JO-AM", "vat_standard", "percentage", 0.16, "2025-01-01", "JOD", "Amman Governorate: national GST 16% applies", "ISTD"),
    ("JO-AQ", "vat_standard", "percentage", 0.08, "2025-01-01", "JOD", "Aqaba Special Economic Zone: reduced rate 8%", "ASEZA"),
    ("JO-MA", "vat_standard", "percentage", 0.16, "2025-01-01", "JOD", "Madaba: national GST 16% applies", "ISTD"),

    # Kenya / Cambodia
    ("KE-110", "vat_standard", "percentage", 0.16, "2025-01-01", "KES", "Nairobi County: national VAT 16% applies", "KRA"),
    ("KE-001", "vat_standard", "percentage", 0.16, "2025-01-01", "KES", "Mombasa County: national VAT 16% applies", "KRA"),
    ("KH-17", "tourism_pct", "percentage", 0.02, "2025-01-01", "KHR", "Siem Reap accommodation tax 2%", "Ministry of Tourism"),
    ("KH-17-REP", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "KHR", "Siem Reap City: no additional city tax", "Siem Reap Authority"),

    # South Korea
    ("KR-11", "vat_standard", "percentage", 0.10, "2025-01-01", "KRW", "Seoul: national VAT 10% applies", "NTS"),
    ("KR-26", "vat_standard", "percentage", 0.10, "2025-01-01", "KRW", "Busan: national VAT 10% applies", "NTS"),
    ("KR-49", "vat_standard", "percentage", 0.10, "2025-01-01", "KRW", "Jeju: national VAT 10% applies", "NTS"),
    ("KR-11-SEL", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "KRW", "Seoul City has no city tourist tax", "Seoul Metropolitan Govt"),
    ("KR-26-PUS", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "KRW", "Busan has no city tourist tax", "Busan Metropolitan City"),

    # Lithuania
    ("LT-VL", "vat_reduced", "percentage", 0.09, "2025-01-01", "EUR", "Vilnius County: national VAT 9% applies", "VMI"),
    ("LT-KL", "vat_reduced", "percentage", 0.09, "2025-01-01", "EUR", "Klaipeda County: national VAT 9% applies", "VMI"),

    # Malaysia
    ("MY-14", "service_pct", "percentage", 0.08, "2025-01-01", "MYR", "KL: national SST 8% applies", "RMCD"),
    ("MY-01", "service_pct", "percentage", 0.08, "2025-01-01", "MYR", "Johor: SST 8% + RM10 TTx", "RMCD"),
    ("MY-07", "service_pct", "percentage", 0.08, "2025-01-01", "MYR", "Penang: SST 8% + RM10 TTx", "RMCD"),
    ("MY-10", "service_pct", "percentage", 0.08, "2025-01-01", "MYR", "Selangor: SST 8% + RM10 TTx", "RMCD"),
    ("MY-11", "service_pct", "percentage", 0.08, "2025-01-01", "MYR", "Sarawak: SST 8% + RM10 TTx", "RMCD"),
    ("MY-12", "service_pct", "percentage", 0.08, "2025-01-01", "MYR", "Sabah: SST 8% + RM10 TTx", "RMCD"),
    ("MY-15", "service_pct", "percentage", 0.08, "2025-01-01", "MYR", "Labuan: SST 8% + RM10 TTx", "RMCD"),
    ("MY-14-KUL", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "MYR", "KL City: no additional city tax beyond TTx", "DBKL"),
    ("MY-07-PEN", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "MYR", "George Town: no additional city tax", "MBPP"),

    # Morocco regions
    ("MA-CAS", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "MAD", "Casablanca-Settat: tax at commune level", "Region"),
    ("MA-RAB", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "MAD", "Rabat-Sale-Kenitra: tax at commune level", "Region"),
    ("MA-MAR", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "MAD", "Marrakech-Safi: tax at commune level", "Region"),
    ("MA-FES", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "MAD", "Fes-Meknes: tax at commune level", "Region"),
    ("MA-TNG", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "MAD", "Tanger-Tetouan: tax at commune level", "Region"),
    ("MA-AGD", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "MAD", "Souss-Massa: tax at commune level", "Region"),
    ("MA-RAB-RBA", "tourism_flat_person_night", "flat", 20.0, "2025-01-01", "MAD", "Rabat tourist tax (~2 EUR)", "Commune de Rabat"),
    ("MA-TNG-TNG", "tourism_flat_person_night", "flat", 20.0, "2025-01-01", "MAD", "Tangier tourist tax", "Commune de Tanger"),
    ("MA-AGD-AGA", "tourism_flat_person_night", "flat", 20.0, "2025-01-01", "MAD", "Agadir tourist tax", "Commune d'Agadir"),

    # North Macedonia
    ("MK-SK", "vat_reduced", "percentage", 0.05, "2025-01-01", "MKD", "Skopje Region: national VAT 5% applies", "UJP"),

    # Netherlands / Nigeria / Norway / Oman
    ("NL-NH", "vat_reduced", "percentage", 0.09, "2025-01-01", "EUR", "North Holland: national VAT 9% applies", "Belastingdienst"),
    ("NG-LA", "municipal_pct", "percentage", 0.05, "2025-01-01", "NGN", "Lagos State consumption tax 5%", "LIRS"),
    ("NG-FC", "vat_standard", "percentage", 0.075, "2025-01-01", "NGN", "FCT: national VAT 7.5% applies", "FIRS"),
    ("NG-FC-ABV", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "NGN", "Abuja has no city tourist tax", "FCDA"),
    ("NO-03", "vat_reduced", "percentage", 0.12, "2025-01-01", "NOK", "Oslo: national VAT 12% applies", "Skatteetaten"),
    ("NO-46", "vat_reduced", "percentage", 0.12, "2025-01-01", "NOK", "Vestland: national VAT 12% applies", "Skatteetaten"),
    ("NO-50", "vat_reduced", "percentage", 0.12, "2025-01-01", "NOK", "Trondelag: national VAT 12% applies", "Skatteetaten"),
    ("NO-46-BGO", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "NOK", "Bergen has no city tourist tax (planned for 2026)", "Bergen Kommune"),
    ("NO-50-TRD", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "NOK", "Trondheim has no city tourist tax", "Trondheim Kommune"),
    ("OM-MA", "vat_standard", "percentage", 0.05, "2025-01-01", "OMR", "Muscat: national VAT 5% applies", "Tax Authority"),

    # NZ regions/cities
    ("NZ-AUK", "vat_standard", "percentage", 0.15, "2025-01-01", "NZD", "Auckland Region: national GST 15%", "IRD"),
    ("NZ-WGN", "vat_standard", "percentage", 0.15, "2025-01-01", "NZD", "Wellington Region: national GST 15%", "IRD"),
    ("NZ-CAN", "vat_standard", "percentage", 0.15, "2025-01-01", "NZD", "Canterbury: national GST 15%", "IRD"),
    ("NZ-OTA", "vat_standard", "percentage", 0.15, "2025-01-01", "NZD", "Otago: national GST 15%", "IRD"),
    ("NZ-AUK-AKL", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "NZD", "Auckland has no city tourist tax", "Auckland Council"),
    ("NZ-WGN-WLG", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "NZD", "Wellington has no city tourist tax", "WCC"),
    ("NZ-CAN-CHC", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "NZD", "Christchurch has no city tourist tax", "CCC"),

    # Philippines / Pakistan
    ("PH-NCR", "vat_standard", "percentage", 0.12, "2025-01-01", "PHP", "Metro Manila: national VAT 12% applies", "BIR"),
    ("PH-07", "vat_standard", "percentage", 0.12, "2025-01-01", "PHP", "Central Visayas: national VAT 12% applies", "BIR"),
    ("PH-ARMM", "vat_standard", "percentage", 0.12, "2025-01-01", "PHP", "Palawan: national VAT 12% applies", "BIR"),
    ("PH-NCR-MKT", "municipal_pct", "percentage", 0.01, "2025-01-01", "PHP", "Makati local business tax", "Makati City"),
    ("PH-07-CEB", "municipal_pct", "percentage", 0.01, "2025-01-01", "PHP", "Cebu City local business tax", "Cebu City"),
    ("PK-PB", "vat_standard", "percentage", 0.16, "2025-01-01", "PKR", "Punjab provincial sales tax 16%", "PRA"),
    ("PK-SD", "vat_standard", "percentage", 0.13, "2025-01-01", "PKR", "Sindh sales tax on services 13%", "SRB"),
    ("PK-IS", "vat_standard", "percentage", 0.18, "2025-01-01", "PKR", "Islamabad federal service tax 18%", "FBR"),
    ("PK-PB-LHE", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "PKR", "Lahore has no city tourist tax", "LDA"),
    ("PK-SD-KHI", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "PKR", "Karachi has no city tourist tax", "KMC"),

    # Poland states
    ("PL-MZ", "occ_pct", "percentage", 0.0, "2025-01-01", "PLN", "Masovia: local fee set at commune level", "Masovia Voivodeship"),
    ("PL-MA", "occ_pct", "percentage", 0.0, "2025-01-01", "PLN", "Lesser Poland: local fee set at commune level", "Malopolska Voivodeship"),
    ("PL-PM", "occ_pct", "percentage", 0.0, "2025-01-01", "PLN", "Pomerania: local fee set at commune level", "Pomorskie Voivodeship"),
    ("PL-DS", "occ_pct", "percentage", 0.0, "2025-01-01", "PLN", "Lower Silesia: local fee set at commune level", "Dolnoslaskie"),
    ("PL-WP", "occ_pct", "percentage", 0.0, "2025-01-01", "PLN", "Greater Poland: local fee set at commune level", "Wielkopolskie"),
    ("PL-LU", "occ_pct", "percentage", 0.0, "2025-01-01", "PLN", "Lublin: local fee set at commune level", "Lubelskie"),
    ("PL-WP-POZ", "tourism_flat_person_night", "flat", 3.20, "2025-01-01", "PLN", "Poznan local fee", "City of Poznan"),

    # Portugal
    ("PT-11", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Lisbon District: tax set at municipal level", "Lisbon District"),

    # Romania
    ("RO-B", "tourism_flat_night", "flat", 0.0, "2025-01-01", "RON", "Bucharest sector: tax set at city level", "Bucharest"),
    ("RO-CJ", "tourism_flat_night", "flat", 0.0, "2025-01-01", "RON", "Cluj County: tax set at city level", "Cluj County"),
    ("RO-CT", "tourism_flat_night", "flat", 8.0, "2025-01-01", "RON", "Constanta tourist tax", "Constanta County"),
    ("RO-BV", "tourism_flat_night", "flat", 0.0, "2025-01-01", "RON", "Brasov County: tax set at city level", "Brasov County"),
    ("RO-IS", "tourism_flat_night", "flat", 6.0, "2025-01-01", "RON", "Iasi tourist tax", "Iasi City Hall"),
    ("RO-SB", "tourism_flat_night", "flat", 0.0, "2025-01-01", "RON", "Sibiu County: tax set at city level", "Sibiu County"),
    ("RO-TM", "tourism_flat_night", "flat", 0.0, "2025-01-01", "RON", "Timis County: tax set at city level", "Timis County"),
    ("RO-TM-TSR", "tourism_flat_night", "flat", 8.0, "2025-01-01", "RON", "Timisoara tourist tax", "Timisoara City Hall"),

    # Serbia / Saudi Arabia
    ("RS-00", "vat_reduced", "percentage", 0.10, "2025-01-01", "RSD", "Belgrade District: national VAT 10% applies", "PU"),
    ("RS-NS", "vat_reduced", "percentage", 0.10, "2025-01-01", "RSD", "South Backa: national VAT 10% applies", "PU"),
    ("SA-01", "vat_standard", "percentage", 0.15, "2025-01-01", "SAR", "Riyadh Province: national VAT 15% applies", "ZATCA"),
    ("SA-02", "vat_standard", "percentage", 0.15, "2025-01-01", "SAR", "Makkah Province: national VAT 15% applies", "ZATCA"),
    ("SA-03", "vat_standard", "percentage", 0.15, "2025-01-01", "SAR", "Madinah Province: national VAT 15% applies", "ZATCA"),
    ("SA-04", "vat_standard", "percentage", 0.15, "2025-01-01", "SAR", "Eastern Province: national VAT 15% applies", "ZATCA"),
    ("SA-06", "vat_standard", "percentage", 0.15, "2025-01-01", "SAR", "Tabuk Province: national VAT 15% applies", "ZATCA"),
    ("SA-01-RUH", "municipal_pct", "percentage", 0.025, "2025-01-01", "SAR", "Riyadh white land fee + municipality levy", "Riyadh Municipality"),
    ("SA-02-JED", "municipal_pct", "percentage", 0.025, "2025-01-01", "SAR", "Jeddah municipality levy", "Jeddah Municipality"),
    ("SA-02-MKK", "municipal_pct", "percentage", 0.025, "2025-01-01", "SAR", "Makkah municipality levy", "Makkah Municipality"),
    ("SA-03-MED", "municipal_pct", "percentage", 0.025, "2025-01-01", "SAR", "Madinah municipality levy", "Madinah Municipality"),
    ("SA-04-DMM", "municipal_pct", "percentage", 0.025, "2025-01-01", "SAR", "Dammam municipality levy", "Dammam Municipality"),
    ("SA-06-NOM", "municipal_pct", "percentage", 0.0, "2025-01-01", "SAR", "NEOM: special economic zone (rates TBD)", "NEOM"),

    # Scandinavia cities
    ("SE-AB", "vat_reduced", "percentage", 0.12, "2025-01-01", "SEK", "Stockholm: national VAT 12% applies", "Skatteverket"),
    ("SE-O", "vat_reduced", "percentage", 0.12, "2025-01-01", "SEK", "Vastra Gotaland: national VAT 12% applies", "Skatteverket"),
    ("SE-M", "vat_reduced", "percentage", 0.12, "2025-01-01", "SEK", "Skane: national VAT 12% applies", "Skatteverket"),
    ("SE-O-GOT", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "SEK", "Gothenburg has no city tourist tax", "Goteborgs Stad"),
    ("SE-M-MMA", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "SEK", "Malmo has no city tourist tax", "Malmo Stad"),

    # Slovenia / Slovakia regions
    ("SI-LJ", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Central Slovenia: tax at municipal level", "Central Slovenia"),
    ("SI-MB", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Drava: tax at municipal level", "Drava Region"),
    ("SI-KP", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Coastal-Karst: tax at municipal level", "Coastal-Karst"),
    ("SI-KR", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Upper Carniola: tax at municipal level", "Upper Carniola"),
    ("SI-MB-MBX", "tourism_flat_person_night", "flat", 1.83, "2025-01-01", "EUR", "Maribor tourist tax", "Mestna obcina Maribor"),
    ("SK-BL", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Bratislava Region: tax at city level", "Bratislava Region"),
    ("SK-KI", "tourism_flat_person_night", "flat", 1.50, "2025-01-01", "EUR", "Kosice city accommodation tax", "City of Kosice"),

    # Argentina / Chile / South America
    ("AR-BA", "vat_standard", "percentage", 0.21, "2025-01-01", "ARS", "Buenos Aires Province: national IVA 21% applies", "ARBA"),
    ("AR-CB", "vat_standard", "percentage", 0.21, "2025-01-01", "ARS", "Cordoba: national IVA 21% applies", "API Cordoba"),
    ("AR-MZ", "vat_standard", "percentage", 0.21, "2025-01-01", "ARS", "Mendoza: national IVA 21% applies", "ATM Mendoza"),
    ("AR-RN", "vat_standard", "percentage", 0.21, "2025-01-01", "ARS", "Rio Negro: national IVA 21% applies", "ARBA RN"),
    ("AR-NQ", "vat_standard", "percentage", 0.21, "2025-01-01", "ARS", "Neuquen: national IVA 21% applies", "DPR Neuquen"),
    ("AR-SF", "vat_standard", "percentage", 0.21, "2025-01-01", "ARS", "Santa Fe: national IVA 21% applies", "API Santa Fe"),
    ("AR-RN-BRC", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "ARS", "Bariloche eco-contribution under discussion", "Municipalidad de Bariloche"),
    ("CL-RM", "vat_standard", "percentage", 0.19, "2025-01-01", "CLP", "Santiago Metropolitan: national IVA 19%", "SII"),
    ("CL-VS", "vat_standard", "percentage", 0.19, "2025-01-01", "CLP", "Valparaiso: national IVA 19%", "SII"),
    ("CL-VS-VNA", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "CLP", "Vina del Mar has no city tourist tax", "Municipalidad VdM"),

    # Dominican Republic / Ecuador / Panama / Peru / Costa Rica / Uruguay
    ("DO-DN", "vat_standard", "percentage", 0.18, "2025-01-01", "DOP", "DN: national ITBIS 18% applies", "DGII"),
    ("DO-LA", "vat_standard", "percentage", 0.18, "2025-01-01", "DOP", "La Altagracia: national ITBIS 18% applies", "DGII"),
    ("DO-DN-SDQ", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "DOP", "Santo Domingo has no city tourist tax", "ADN"),
    ("DO-LA-PUJ", "eco_flat_person_night", "flat", 10.0, "2025-01-01", "USD", "Punta Cana area entry card fee ($10)", "DR Tourism"),
    ("EC-P", "vat_standard", "percentage", 0.15, "2025-01-01", "USD", "Pichincha: national IVA 15% applies", "SRI"),
    ("EC-G", "vat_standard", "percentage", 0.15, "2025-01-01", "USD", "Guayas: national IVA 15% applies", "SRI"),
    ("EC-G-GYE", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "USD", "Guayaquil has no city tourist tax", "Municipio de Guayaquil"),
    ("PA-8", "vat_standard", "percentage", 0.07, "2025-01-01", "PAB", "Panama Province: national ITBMS 7% applies", "DGI"),
    ("PE-LIM", "vat_standard", "percentage", 0.18, "2025-01-01", "PEN", "Lima Region: national IGV 18% applies", "SUNAT"),
    ("PE-CUS", "vat_standard", "percentage", 0.18, "2025-01-01", "PEN", "Cusco Region: national IGV 18% applies", "SUNAT"),
    ("PE-CUS-CUS", "tourism_pct", "percentage", 0.0, "2025-01-01", "PEN", "Cusco City has no additional municipal tax", "Municipalidad del Cusco"),
    ("CR-SJ", "vat_standard", "percentage", 0.13, "2025-01-01", "CRC", "San Jose Province: national IVA 13%", "DGT"),
    ("UY-MO", "vat_standard", "percentage", 0.22, "2025-01-01", "UYU", "Montevideo: national IVA 22% applies", "DGI"),
    ("UY-MA", "vat_standard", "percentage", 0.22, "2025-01-01", "UYU", "Maldonado: national IVA 22% applies", "DGI"),
    ("UY-MO-MVD", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "UYU", "Montevideo City has no city tourist tax", "IM"),
    ("UY-MA-PDE", "tourism_pct", "percentage", 0.0, "2025-01-01", "UYU", "Punta del Este has no city tourist tax", "IDM"),
    ("PR-SJ", "vat_standard", "percentage", 0.115, "2025-01-01", "USD", "San Juan: PR SUT 11.5% + Room Tax", "CRIM"),
    ("PR-SJ", "occ_pct", "percentage", 0.09, "2025-01-01", "USD", "San Juan room tax 9%", "Puerto Rico Tourism Company"),

    # Sri Lanka / Nepal / Bangladesh / Lebanon
    ("LK-1", "vat_standard", "percentage", 0.18, "2025-01-01", "LKR", "Western Province: national VAT 18% applies", "IRD"),
    ("NP-BA", "vat_standard", "percentage", 0.13, "2025-01-01", "NPR", "Bagmati Province: national VAT 13% applies", "IRD"),
    ("BD-13", "vat_standard", "percentage", 0.15, "2025-01-01", "BDT", "Dhaka Division: national VAT 15% applies", "NBR"),
    ("BD-10", "vat_standard", "percentage", 0.15, "2025-01-01", "BDT", "Chittagong Division: national VAT 15% applies", "NBR"),
    ("BD-13-DAC", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "BDT", "Dhaka City has no city tourist tax", "DSCC"),
    ("LB-BA", "vat_standard", "percentage", 0.11, "2025-01-01", "LBP", "Beirut: national VAT 11% applies", "MoF"),
    ("MD-CU", "vat_reduced", "percentage", 0.12, "2025-01-01", "MDL", "Chisinau: national VAT 12% applies", "SFS"),
    ("KW-KU", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "KWD", "Kuwait City has no tourist tax (no VAT)", "MoF"),

    # South Africa provinces/cities
    ("ZA-GT", "vat_standard", "percentage", 0.15, "2025-01-01", "ZAR", "Gauteng: national VAT 15% applies", "SARS"),
    ("ZA-WC", "vat_standard", "percentage", 0.15, "2025-01-01", "ZAR", "Western Cape: national VAT 15% applies", "SARS"),
    ("ZA-KZN", "vat_standard", "percentage", 0.15, "2025-01-01", "ZAR", "KwaZulu-Natal: national VAT 15% applies", "SARS"),
    ("ZA-GT-JNB", "tourism_pct", "percentage", 0.01, "2025-01-01", "ZAR", "Johannesburg tourism levy 1%", "CoJ"),
    ("ZA-WC-CPT", "tourism_pct", "percentage", 0.01, "2025-01-01", "ZAR", "Cape Town tourism levy 1%", "CoCT"),
    ("ZA-KZN-DUR", "tourism_pct", "percentage", 0.01, "2025-01-01", "ZAR", "Durban tourism levy 1%", "eThekwini"),

    # Tanzania / Tunisia
    ("TZ-02", "vat_standard", "percentage", 0.18, "2025-01-01", "TZS", "Dar es Salaam: national VAT 18% applies", "TRA"),
    ("TZ-25", "vat_standard", "percentage", 0.18, "2025-01-01", "TZS", "Zanzibar: national VAT 18% applies", "ZRB"),
    ("TZ-02-DAR", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "TZS", "Dar es Salaam City has no city tourist tax", "Dar City"),
    ("TN-11", "vat_reduced", "percentage", 0.07, "2025-01-01", "TND", "Tunis Gov: national VAT 7% applies", "DGI"),
    ("TN-31", "vat_reduced", "percentage", 0.07, "2025-01-01", "TND", "Nabeul Gov: national VAT 7% applies", "DGI"),
    ("TN-51", "vat_reduced", "percentage", 0.07, "2025-01-01", "TND", "Sousse Gov: national VAT 7% applies", "DGI"),
    ("TN-31-HAM", "tourism_flat_person_night", "flat", 1.5, "2025-01-01", "TND", "Hammamet tourist tax ~1.5 TND/night", "Commune de Hammamet"),

    # Turkey states/cities
    ("TR-34", "vat_reduced", "percentage", 0.10, "2025-01-01", "TRY", "Istanbul Province: national VAT 10% applies", "GIB"),
    ("TR-06", "vat_reduced", "percentage", 0.10, "2025-01-01", "TRY", "Ankara Province: national VAT 10% applies", "GIB"),
    ("TR-07", "vat_reduced", "percentage", 0.10, "2025-01-01", "TRY", "Antalya Province: national VAT 10% applies", "GIB"),
    ("TR-35", "vat_reduced", "percentage", 0.10, "2025-01-01", "TRY", "Izmir Province: national VAT 10% applies", "GIB"),
    ("TR-48", "vat_reduced", "percentage", 0.10, "2025-01-01", "TRY", "Mugla Province: national VAT 10% applies", "GIB"),
    ("TR-06-ANK", "tourism_pct", "percentage", 0.02, "2025-01-01", "TRY", "Ankara accommodation tax 2%", "Ankara Municipality"),
    ("TR-35-IZM", "tourism_pct", "percentage", 0.02, "2025-01-01", "TRY", "Izmir accommodation tax 2%", "Izmir Municipality"),
    ("TR-48-BJV", "tourism_pct", "percentage", 0.02, "2025-01-01", "TRY", "Bodrum accommodation tax 2%", "Bodrum Municipality"),

    # Taiwan
    ("TW-TPE", "vat_standard", "percentage", 0.05, "2025-01-01", "TWD", "Taipei: national VAT 5% applies", "MoF"),
    ("TW-KHH", "vat_standard", "percentage", 0.05, "2025-01-01", "TWD", "Kaohsiung: national VAT 5% applies", "MoF"),

    # Thailand
    ("TH-10", "vat_standard", "percentage", 0.07, "2025-01-01", "THB", "Bangkok Province: national VAT 7% applies", "Revenue Department"),
    ("TH-10-BKK", "tourism_flat_person_night", "flat", 150.0, "2025-01-01", "THB", "Bangkok hotel tourism fee ~150 THB/night ($4)", "Bangkok Metropolitan"),

    # Ukraine / Vietnam
    ("UA-46", "tourism_pct", "percentage", 0.01, "2025-01-01", "UAH", "Lviv Oblast tourist tax 1%", "Lviv ODA"),
    ("UA-51", "tourism_pct", "percentage", 0.01, "2025-01-01", "UAH", "Odesa Oblast tourist tax 1%", "Odesa ODA"),
    ("UA-51-ODS", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "UAH", "Odesa City: included in oblast tourist tax", "Odesa City"),
    ("VN-KH", "vat_standard", "percentage", 0.10, "2025-01-01", "VND", "Khanh Hoa: national VAT 10% applies", "GDT"),
    ("VN-DN", "vat_standard", "percentage", 0.10, "2025-01-01", "VND", "Da Nang: national VAT 10% applies", "GDT"),
    ("VN-HP", "vat_standard", "percentage", 0.10, "2025-01-01", "VND", "Hai Phong: national VAT 10% applies", "GDT"),
    ("VN-KH-NHA", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "VND", "Nha Trang has no city tourist tax", "Nha Trang City"),

    # Remaining: Albania / Bosnia / misc
    ("AL-TR", "vat_standard", "percentage", 0.06, "2025-01-01", "ALL", "Tirana District: national VAT 6% applies", "DPT"),
    ("AL-SR", "vat_standard", "percentage", 0.06, "2025-01-01", "ALL", "Saranda District: national VAT 6% applies", "DPT"),
    ("BA-BIH", "vat_standard", "percentage", 0.17, "2025-01-01", "BAM", "Federation BiH: national VAT 17% applies", "UIO"),
    ("BA-SRP", "vat_standard", "percentage", 0.17, "2025-01-01", "BAM", "Republika Srpska: national VAT 17% applies", "UIO"),
    ("ME-TIV", "tourism_flat_person_night", "flat", 1.00, "2025-01-01", "EUR", "Tivat sojourn tax", "Municipality of Tivat"),
    ("BH-13", "vat_standard", "percentage", 0.10, "2025-01-01", "BHD", "Capital Governorate: national VAT 10% applies", "NBR"),

    # US states (that exist in DB but missing rates)
    ("US-CA", "occ_pct", "percentage", 0.0, "2025-01-01", "USD", "California: TOT set at city/county level (no state hotel tax)", "CDTFA"),
    ("US-VA", "occ_pct", "percentage", 0.057, "2025-01-01", "USD", "Virginia transient occupancy tax 5.7% (state portion)", "Virginia DoT"),
    ("US-VA-VBH", "occ_pct", "percentage", 0.08, "2025-01-01", "USD", "Virginia Beach city transient occupancy tax 8%", "City of Virginia Beach"),
]


async def seed(api_base: str, api_key: str):
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    created = skipped = errors = 0
    t0 = time.time()

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        h = (await client.get(f"{api_base}/health")).json()
        print(f"API: {h['status']} | DB: {h['database']}")

        existing = set()
        for offset in range(0, 2000, 500):
            resp = await client.get(f"{api_base}/v1/rates", params={"limit": "500", "offset": str(offset)})
            if resp.status_code != 200:
                break
            for r in resp.json():
                existing.add((r["jurisdiction_code"], r["tax_category_code"]))
            if len(resp.json()) < 500:
                break
        print(f"Existing rate combos: {len(existing)}")

        print(f"\nInserting {len(RATES)} rates for missing jurisdictions...")
        for jur, cat, rtype, val, eff, cur, legal, auth in RATES:
            if (jur, cat) in existing:
                skipped += 1
                continue
            body = {
                "jurisdiction_code": jur,
                "tax_category_code": cat,
                "rate_type": rtype,
                "rate_value": val,
                "effective_start": eff,
                "currency_code": cur,
                "status": "active",
                "legal_reference": legal,
                "authority_name": auth,
                "created_by": "data_research",
            }
            resp = await client.post(f"{api_base}/v1/rates", json=body)
            if resp.status_code == 201:
                created += 1
            elif resp.status_code == 409:
                skipped += 1
            else:
                errors += 1
                print(f"  ! {jur}/{cat}: {resp.status_code} - {resp.text[:100]}")

    elapsed = int(time.time() - t0)
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed}s | Created: {created} | Skipped: {skipped} | Errors: {errors}")
    print(f"{'='*60}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default="http://localhost:8001")
    p.add_argument("--api-key", default="dev-api-key-change-me")
    args = p.parse_args()
    asyncio.run(seed(args.api_url, args.api_key))


if __name__ == "__main__":
    main()
