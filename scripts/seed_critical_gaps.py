"""
Fill critical jurisdiction gaps — major cities and regions that were missing.

These are the jurisdictions most likely to be asked about by OTAs like Airbnb:
- Edinburgh (new 5% levy July 2026)
- Italy: Florence, Naples, Milan, Venice
- Germany: Hamburg, Munich, Frankfurt
- Japan: Osaka, Fukuoka, Sapporo/Hokkaido
- Indonesia: Bali (Denpasar) with new tourist levy
- Thailand: Phuket
- Portugal: Porto, Algarve, Azores, Madeira
- US: DC, Las Vegas, Boston, Nashville, New Orleans, Atlanta, Phoenix, Denver, Portland, Seattle

Usage: python -m scripts.seed_critical_gaps
"""

import argparse
import asyncio
import time

import httpx


# ── MISSING JURISDICTIONS ──────────────────────────────────────────
# (code, name, type, parent_code, country_code, currency, timezone)
JURISDICTIONS = [
    # UK - Scotland
    ("GB-SCT", "Scotland", "state", "GB", "GB", "GBP", "Europe/London"),
    ("GB-SCT-EDI", "Edinburgh", "city", "GB-SCT", "GB", "GBP", "Europe/London"),
    ("GB-SCT-GLA", "Glasgow", "city", "GB-SCT", "GB", "GBP", "Europe/London"),

    # Italy - Major cities
    ("IT-FI", "Tuscany", "state", "IT", "IT", "EUR", "Europe/Rome"),
    ("IT-FI-FLR", "Florence", "city", "IT-FI", "IT", "EUR", "Europe/Rome"),
    ("IT-NA", "Campania", "state", "IT", "IT", "EUR", "Europe/Rome"),
    ("IT-NA-NAP", "Naples", "city", "IT-NA", "IT", "EUR", "Europe/Rome"),
    ("IT-MI", "Lombardy", "state", "IT", "IT", "EUR", "Europe/Rome"),
    ("IT-MI-MIL", "Milan", "city", "IT-MI", "IT", "EUR", "Europe/Rome"),
    ("IT-VE", "Veneto", "state", "IT", "IT", "EUR", "Europe/Rome"),
    ("IT-VE-VCE", "Venice", "city", "IT-VE", "IT", "EUR", "Europe/Rome"),
    ("IT-TO", "Piedmont", "state", "IT", "IT", "EUR", "Europe/Rome"),
    ("IT-TO-TRN", "Turin", "city", "IT-TO", "IT", "EUR", "Europe/Rome"),
    ("IT-BO", "Emilia-Romagna", "state", "IT", "IT", "EUR", "Europe/Rome"),
    ("IT-BO-BLQ", "Bologna", "city", "IT-BO", "IT", "EUR", "Europe/Rome"),
    ("IT-AG", "Sicily", "state", "IT", "IT", "EUR", "Europe/Rome"),
    ("IT-AG-PMO", "Palermo", "city", "IT-AG", "IT", "EUR", "Europe/Rome"),
    ("IT-CA", "Sardinia", "state", "IT", "IT", "EUR", "Europe/Rome"),

    # Germany - Major cities
    ("DE-HH", "Hamburg", "state", "DE", "DE", "EUR", "Europe/Berlin"),
    ("DE-HH-HAM", "Hamburg City", "city", "DE-HH", "DE", "EUR", "Europe/Berlin"),
    ("DE-BY", "Bavaria", "state", "DE", "DE", "EUR", "Europe/Berlin"),
    ("DE-BY-MUC", "Munich", "city", "DE-BY", "DE", "EUR", "Europe/Berlin"),
    ("DE-HE", "Hesse", "state", "DE", "DE", "EUR", "Europe/Berlin"),
    ("DE-HE-FRA", "Frankfurt", "city", "DE-HE", "DE", "EUR", "Europe/Berlin"),
    ("DE-NW", "North Rhine-Westphalia", "state", "DE", "DE", "EUR", "Europe/Berlin"),
    ("DE-NW-CGN", "Cologne", "city", "DE-NW", "DE", "EUR", "Europe/Berlin"),
    ("DE-NW-DUS", "Dusseldorf", "city", "DE-NW", "DE", "EUR", "Europe/Berlin"),
    ("DE-SN", "Saxony", "state", "DE", "DE", "EUR", "Europe/Berlin"),
    ("DE-SN-DRS", "Dresden", "city", "DE-SN", "DE", "EUR", "Europe/Berlin"),

    # Japan - Major tax cities
    ("JP-27", "Osaka Prefecture", "state", "JP", "JP", "JPY", "Asia/Tokyo"),
    ("JP-27-OSA", "Osaka", "city", "JP-27", "JP", "JPY", "Asia/Tokyo"),
    ("JP-40", "Fukuoka Prefecture", "state", "JP", "JP", "JPY", "Asia/Tokyo"),
    ("JP-40-FUK", "Fukuoka", "city", "JP-40", "JP", "JPY", "Asia/Tokyo"),
    ("JP-01", "Hokkaido", "state", "JP", "JP", "JPY", "Asia/Tokyo"),
    ("JP-01-SPK", "Sapporo", "city", "JP-01", "JP", "JPY", "Asia/Tokyo"),
    ("JP-23", "Aichi Prefecture", "state", "JP", "JP", "JPY", "Asia/Tokyo"),
    ("JP-23-NGO", "Nagoya", "city", "JP-23", "JP", "JPY", "Asia/Tokyo"),
    ("JP-14", "Kanagawa Prefecture", "state", "JP", "JP", "JPY", "Asia/Tokyo"),
    ("JP-14-YOK", "Yokohama", "city", "JP-14", "JP", "JPY", "Asia/Tokyo"),

    # Indonesia - Bali
    ("ID-BA-DPS", "Denpasar (Bali)", "city", "ID-BA", "ID", "IDR", "Asia/Makassar"),
    ("ID-JK", "Jakarta", "state", "ID", "ID", "IDR", "Asia/Jakarta"),
    ("ID-JK-CGK", "Jakarta City", "city", "ID-JK", "ID", "IDR", "Asia/Jakarta"),

    # Thailand - Phuket
    ("TH-83", "Phuket Province", "state", "TH", "TH", "THB", "Asia/Bangkok"),
    ("TH-83-HKT", "Phuket", "city", "TH-83", "TH", "THB", "Asia/Bangkok"),
    ("TH-20", "Chonburi Province", "state", "TH", "TH", "THB", "Asia/Bangkok"),
    ("TH-20-PYX", "Pattaya", "city", "TH-20", "TH", "THB", "Asia/Bangkok"),
    ("TH-50", "Chiang Mai Province", "state", "TH", "TH", "THB", "Asia/Bangkok"),
    ("TH-50-CNX", "Chiang Mai", "city", "TH-50", "TH", "THB", "Asia/Bangkok"),

    # Portugal - Porto, Algarve, Azores, Madeira
    ("PT-13", "Porto District", "state", "PT", "PT", "EUR", "Europe/Lisbon"),
    ("PT-13-OPO", "Porto", "city", "PT-13", "PT", "EUR", "Europe/Lisbon"),
    ("PT-FAR", "Faro District (Algarve)", "state", "PT", "PT", "EUR", "Europe/Lisbon"),
    ("PT-FAR-FAO", "Faro", "city", "PT-FAR", "PT", "EUR", "Europe/Lisbon"),
    ("PT-FAR-ALB", "Albufeira", "city", "PT-FAR", "PT", "EUR", "Europe/Lisbon"),
    ("PT-AZ", "Azores", "region", "PT", "PT", "EUR", "Atlantic/Azores"),
    ("PT-AZ-PDL", "Ponta Delgada", "city", "PT-AZ", "PT", "EUR", "Atlantic/Azores"),
    ("PT-MA", "Madeira", "region", "PT", "PT", "EUR", "Atlantic/Madeira"),
    ("PT-MA-FNC", "Funchal", "city", "PT-MA", "PT", "EUR", "Atlantic/Madeira"),

    # US - Major missing cities
    ("US-DC", "District of Columbia", "state", "US", "US", "USD", "America/New_York"),
    ("US-CO", "Colorado", "state", "US", "US", "USD", "America/Denver"),
    ("US-CO-DEN", "Denver", "city", "US-CO", "US", "USD", "America/Denver"),
    ("US-NV", "Nevada", "state", "US", "US", "USD", "America/Los_Angeles"),
    ("US-NV-LAS", "Las Vegas", "city", "US-NV", "US", "USD", "America/Los_Angeles"),
    ("US-WA", "Washington State", "state", "US", "US", "USD", "America/Los_Angeles"),
    ("US-WA-SEA", "Seattle", "city", "US-WA", "US", "USD", "America/Los_Angeles"),
    ("US-MA", "Massachusetts", "state", "US", "US", "USD", "America/New_York"),
    ("US-MA-BOS", "Boston", "city", "US-MA", "US", "USD", "America/New_York"),
    ("US-TN", "Tennessee", "state", "US", "US", "USD", "America/Chicago"),
    ("US-TN-BNA", "Nashville", "city", "US-TN", "US", "USD", "America/Chicago"),
    ("US-LA", "Louisiana", "state", "US", "US", "USD", "America/Chicago"),
    ("US-LA-MSY", "New Orleans", "city", "US-LA", "US", "USD", "America/Chicago"),
    ("US-GA", "Georgia", "state", "US", "US", "USD", "America/New_York"),
    ("US-GA-ATL", "Atlanta", "city", "US-GA", "US", "USD", "America/New_York"),
    ("US-AZ", "Arizona", "state", "US", "US", "USD", "America/Phoenix"),
    ("US-AZ-PHX", "Phoenix", "city", "US-AZ", "US", "USD", "America/Phoenix"),
    ("US-OR", "Oregon", "state", "US", "US", "USD", "America/Los_Angeles"),
    ("US-OR-PDX", "Portland", "city", "US-OR", "US", "USD", "America/Los_Angeles"),
    ("US-MN", "Minnesota", "state", "US", "US", "USD", "America/Chicago"),
    ("US-MN-MSP", "Minneapolis", "city", "US-MN", "US", "USD", "America/Chicago"),
    ("US-PA", "Pennsylvania", "state", "US", "US", "USD", "America/New_York"),
    ("US-PA-PHL", "Philadelphia", "city", "US-PA", "US", "USD", "America/New_York"),
    ("US-NC", "North Carolina", "state", "US", "US", "USD", "America/New_York"),
    ("US-NC-CLT", "Charlotte", "city", "US-NC", "US", "USD", "America/New_York"),

    # Spain - missing
    ("ES-MD", "Community of Madrid", "state", "ES", "ES", "EUR", "Europe/Madrid"),
    ("ES-MD-MAD", "Madrid", "city", "ES-MD", "ES", "EUR", "Europe/Madrid"),
    ("ES-AN", "Andalusia", "state", "ES", "ES", "EUR", "Europe/Madrid"),
    ("ES-AN-SVQ", "Seville", "city", "ES-AN", "ES", "EUR", "Europe/Madrid"),
    ("ES-AN-MLG", "Malaga", "city", "ES-AN", "ES", "EUR", "Europe/Madrid"),
    ("ES-AN-GRX", "Granada", "city", "ES-AN", "ES", "EUR", "Europe/Madrid"),
    ("ES-VC", "Valencia", "state", "ES", "ES", "EUR", "Europe/Madrid"),
    ("ES-VC-VLC", "Valencia City", "city", "ES-VC", "ES", "EUR", "Europe/Madrid"),

    # France - missing
    ("FR-PAC", "Provence-Alpes-Cote d'Azur", "state", "FR", "FR", "EUR", "Europe/Paris"),
    ("FR-PAC-NCE", "Nice", "city", "FR-PAC", "FR", "EUR", "Europe/Paris"),
    ("FR-PAC-MRS", "Marseille", "city", "FR-PAC", "FR", "EUR", "Europe/Paris"),
    ("FR-OCC", "Occitanie", "state", "FR", "FR", "EUR", "Europe/Paris"),
    ("FR-OCC-TLS", "Toulouse", "city", "FR-OCC", "FR", "EUR", "Europe/Paris"),
    ("FR-ARA", "Auvergne-Rhone-Alpes", "state", "FR", "FR", "EUR", "Europe/Paris"),
    ("FR-ARA-LYS", "Lyon", "city", "FR-ARA", "FR", "EUR", "Europe/Paris"),

    # Greece - islands
    ("GR-M", "South Aegean", "state", "GR", "GR", "EUR", "Europe/Athens"),
    ("GR-M-MYK", "Mykonos", "city", "GR-M", "GR", "EUR", "Europe/Athens"),
    ("GR-M-JTR", "Santorini", "city", "GR-M", "GR", "EUR", "Europe/Athens"),
    ("GR-K", "Crete", "state", "GR", "GR", "EUR", "Europe/Athens"),
    ("GR-K-HER", "Heraklion", "city", "GR-K", "GR", "EUR", "Europe/Athens"),

    # UAE - Abu Dhabi
    ("AE-AZ", "Abu Dhabi", "state", "AE", "AE", "AED", "Asia/Dubai"),
    ("AE-AZ-AUH", "Abu Dhabi City", "city", "AE-AZ", "AE", "AED", "Asia/Dubai"),
]

# ── TAX RATES for new jurisdictions ────────────────────────────────
RATES = [
    # Edinburgh - NEW 5% levy from July 2026
    ("GB-SCT", "vat_standard", "percentage", 0.20, "2025-01-01", "GBP", "Scotland: UK VAT 20% applies", "HMRC"),
    ("GB-SCT-EDI", "tourism_pct", "percentage", 0.05, "2026-07-24", "GBP", "Edinburgh Visitor Levy 5% (from July 24, 2026, capped at 7 nights)", "City of Edinburgh Council"),
    ("GB-SCT-GLA", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "GBP", "Glasgow has no city tourist tax", "Glasgow City Council"),

    # Italy cities - updated 2026 rates
    ("IT-FI", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Tuscany: national VAT 10% applies", "AdE"),
    ("IT-FI-FLR", "tourism_flat_person_night", "flat", 8.0, "2026-01-01", "EUR", "Florence imposta di soggiorno (up to EUR 8 for 5-star, max 7 nights, exempt under 12)", "Comune di Firenze"),
    ("IT-NA", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Campania: national VAT 10% applies", "AdE"),
    ("IT-NA-NAP", "tourism_flat_person_night", "flat", 6.0, "2026-05-01", "EUR", "Naples tourist tax EUR 5 (EUR 6 from May 2026, exempt under 14, max 14 nights)", "Comune di Napoli"),
    ("IT-MI", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Lombardy: national VAT 10% applies", "AdE"),
    ("IT-MI-MIL", "tourism_flat_person_night", "flat", 10.0, "2025-01-01", "EUR", "Milan tourist tax (up to EUR 10 for 4-star+, max 14 nights, exempt under 18)", "Comune di Milano"),
    ("IT-VE", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Veneto: national VAT 10% applies", "AdE"),
    ("IT-VE-VCE", "tourism_flat_person_night", "flat", 5.0, "2025-01-01", "EUR", "Venice tourist tax (EUR 3-5/night + EUR 5 day-tripper fee peak season)", "Comune di Venezia"),
    ("IT-VE-VCE", "entry_flat_person_stay", "flat", 5.0, "2025-04-01", "EUR", "Venice day-tripper access fee EUR 5 (peak season Apr-Jul selected dates)", "Comune di Venezia"),
    ("IT-TO", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Piedmont: national VAT 10% applies", "AdE"),
    ("IT-TO-TRN", "tourism_flat_person_night", "flat", 5.5, "2025-01-01", "EUR", "Turin tourist tax (up to EUR 5.50 for 5-star)", "Citta di Torino"),
    ("IT-BO", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Emilia-Romagna: national VAT 10% applies", "AdE"),
    ("IT-BO-BLQ", "tourism_flat_person_night", "flat", 5.0, "2025-01-01", "EUR", "Bologna tourist tax (EUR 3-5 by star rating)", "Comune di Bologna"),
    ("IT-AG", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Sicily: national VAT 10% applies", "AdE"),
    ("IT-AG-PMO", "tourism_flat_person_night", "flat", 3.0, "2025-01-01", "EUR", "Palermo tourist tax", "Comune di Palermo"),
    ("IT-CA", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Sardinia: national VAT 10% applies", "AdE"),

    # Germany cities
    ("DE-HH", "vat_reduced", "percentage", 0.07, "2025-01-01", "EUR", "Hamburg: national VAT 7% applies", "Finanzamt"),
    ("DE-HH-HAM", "tourism_pct", "percentage", 0.075, "2025-01-01", "EUR", "Hamburg Kultur- und Tourismustaxe 7.5% (from 2025, up from 5%)", "City of Hamburg"),
    ("DE-BY", "vat_reduced", "percentage", 0.07, "2025-01-01", "EUR", "Bavaria: national VAT 7% applies", "Finanzamt"),
    ("DE-BY-MUC", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Munich has NO city tax (Bettensteuer)", "City of Munich"),
    ("DE-HE", "vat_reduced", "percentage", 0.07, "2025-01-01", "EUR", "Hesse: national VAT 7% applies", "Finanzamt"),
    ("DE-HE-FRA", "tourism_flat_night", "flat", 2.0, "2025-01-01", "EUR", "Frankfurt Bettensteuer EUR 2/night flat", "Stadt Frankfurt"),
    ("DE-NW", "vat_reduced", "percentage", 0.07, "2025-01-01", "EUR", "NRW: national VAT 7% applies", "Finanzamt"),
    ("DE-NW-CGN", "tourism_pct", "percentage", 0.05, "2025-01-01", "EUR", "Cologne Bettensteuer 5%", "Stadt Koln"),
    ("DE-NW-DUS", "tourism_flat_night", "flat", 2.5, "2025-01-01", "EUR", "Dusseldorf Bettensteuer EUR 2.50/night", "Stadt Dusseldorf"),
    ("DE-SN", "vat_reduced", "percentage", 0.07, "2025-01-01", "EUR", "Saxony: national VAT 7% applies", "Finanzamt"),
    ("DE-SN-DRS", "tourism_flat_person_night", "flat", 1.3, "2025-01-01", "EUR", "Dresden Bettensteuer EUR 1.30/person/night", "Stadt Dresden"),

    # Japan - Osaka tiered, Fukuoka double tax, Hokkaido new Apr 2026
    ("JP-27", "occ_pct", "percentage", 0.0, "2025-01-01", "JPY", "Osaka Pref: tax set at city level", "Osaka Prefectural Govt"),
    ("JP-27-OSA", "tier_price", "tiered", None, "2025-01-01", "JPY", "Osaka accommodation tax: <7000=100, 7000-14999=200, 15000-19999=300, >=20000=varies", "Osaka City"),
    ("JP-40", "occ_flat_person_night", "flat", 50.0, "2025-01-01", "JPY", "Fukuoka Pref accommodation tax 50 JPY/person/night", "Fukuoka Pref Govt"),
    ("JP-40-FUK", "occ_flat_person_night", "flat", 150.0, "2025-01-01", "JPY", "Fukuoka City accommodation tax 150 JPY/person/night (ON TOP of prefectural tax)", "Fukuoka City"),
    ("JP-01", "occ_flat_person_night", "flat", 100.0, "2026-04-01", "JPY", "Hokkaido accommodation tax (NEW Apr 2026, 100 JPY/night)", "Hokkaido Govt"),
    ("JP-01-SPK", "occ_flat_person_night", "flat", 200.0, "2026-04-01", "JPY", "Sapporo accommodation tax 200 JPY/night (ON TOP of prefectural tax)", "Sapporo City"),
    ("JP-23", "occ_pct", "percentage", 0.0, "2025-01-01", "JPY", "Aichi: no prefectural accommodation tax", "Aichi Pref Govt"),
    ("JP-23-NGO", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "JPY", "Nagoya has no city accommodation tax", "Nagoya City"),
    ("JP-14", "occ_pct", "percentage", 0.0, "2025-01-01", "JPY", "Kanagawa: no prefectural accommodation tax", "Kanagawa Pref Govt"),
    ("JP-14-YOK", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "JPY", "Yokohama has no city accommodation tax", "Yokohama City"),

    # Bali - NEW tourist levy
    ("ID-BA-DPS", "eco_flat_person_night", "flat", 150000.0, "2024-02-14", "IDR", "Bali tourist levy IDR 150,000 (~$10) per foreign visitor (one-time, not per night)", "Bali Provincial Govt"),
    ("ID-JK", "vat_standard", "percentage", 0.11, "2025-01-01", "IDR", "Jakarta: national VAT 11% applies", "DJP"),
    ("ID-JK-CGK", "municipal_pct", "percentage", 0.01, "2025-01-01", "IDR", "Jakarta city entertainment/accommodation surcharge 1%", "DKI Jakarta"),

    # Thailand - Phuket, Pattaya, Chiang Mai
    ("TH-83", "vat_standard", "percentage", 0.07, "2025-01-01", "THB", "Phuket Province: national VAT 7% applies", "Revenue Department"),
    ("TH-83-HKT", "tourism_flat_person_night", "flat", 150.0, "2025-01-01", "THB", "Phuket hotel fee ~150 THB/night", "Phuket Municipality"),
    ("TH-20", "vat_standard", "percentage", 0.07, "2025-01-01", "THB", "Chonburi Province: national VAT 7% applies", "Revenue Department"),
    ("TH-20-PYX", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "THB", "Pattaya has no additional city tax", "Pattaya City"),
    ("TH-50", "vat_standard", "percentage", 0.07, "2025-01-01", "THB", "Chiang Mai Province: national VAT 7% applies", "Revenue Department"),
    ("TH-50-CNX", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "THB", "Chiang Mai has no city tourist tax", "Chiang Mai Municipality"),

    # Portugal - Porto, Algarve, Azores, Madeira
    ("PT-13", "vat_reduced", "percentage", 0.06, "2025-01-01", "EUR", "Porto District: national VAT 6% applies", "AT"),
    ("PT-13-OPO", "tourism_flat_person_night", "flat", 2.0, "2025-01-01", "EUR", "Porto tourist tax EUR 2/person/night (max 7 nights, exempt under 13)", "Camara do Porto"),
    ("PT-FAR", "vat_reduced", "percentage", 0.06, "2025-01-01", "EUR", "Faro/Algarve: national VAT 6% applies", "AT"),
    ("PT-FAR-FAO", "tourism_flat_person_night", "flat", 2.0, "2025-01-01", "EUR", "Faro tourist tax EUR 2 (Mar-Oct), EUR 1 (Nov-Feb), max 7 nights", "Camara de Faro"),
    ("PT-FAR-ALB", "tourism_flat_person_night", "flat", 2.0, "2025-01-01", "EUR", "Albufeira tourist tax EUR 2 (Apr-Oct), max 7 nights, exempt under 16", "Camara de Albufeira"),
    ("PT-AZ", "vat_reduced", "percentage", 0.04, "2025-01-01", "EUR", "Azores reduced VAT rate 4% on accommodation", "AT"),
    ("PT-AZ-PDL", "tourism_flat_person_night", "flat", 2.0, "2025-01-01", "EUR", "Ponta Delgada tourist tax EUR 2/person/night (NEW Jan 2025, max 3 nights)", "Camara de Ponta Delgada"),
    ("PT-MA", "vat_reduced", "percentage", 0.05, "2025-01-01", "EUR", "Madeira reduced VAT rate 5% on accommodation", "AT"),
    ("PT-MA-FNC", "tourism_flat_person_night", "flat", 2.0, "2025-01-01", "EUR", "Funchal tourist tax EUR 2/person/night (max 7 nights)", "Camara do Funchal"),

    # US major cities
    ("US-DC", "occ_pct", "percentage", 0.145, "2025-01-01", "USD", "Washington DC transient accommodation tax 14.5%", "DC Office of Tax and Revenue"),
    ("US-CO", "occ_pct", "percentage", 0.0, "2025-01-01", "USD", "Colorado: no state lodging tax (set at local level)", "Colorado DOR"),
    ("US-CO-DEN", "occ_pct", "percentage", 0.1075, "2025-01-01", "USD", "Denver lodging tax 10.75% (city+county+tourism)", "City of Denver"),
    ("US-NV", "occ_pct", "percentage", 0.0, "2025-01-01", "USD", "Nevada: no state lodging tax (set at county level)", "Nevada DT"),
    ("US-NV-LAS", "occ_pct", "percentage", 0.13, "2025-01-01", "USD", "Las Vegas transient lodging tax ~13% (Clark County rate)", "Clark County"),
    ("US-WA", "occ_pct", "percentage", 0.065, "2025-01-01", "USD", "Washington state sales tax on lodging 6.5%", "WA DOR"),
    ("US-WA-SEA", "occ_pct", "percentage", 0.159, "2025-01-01", "USD", "Seattle total lodging tax ~15.9% (state+county+city+convention)", "City of Seattle"),
    ("US-MA", "occ_pct", "percentage", 0.0575, "2025-01-01", "USD", "Massachusetts room occupancy excise 5.75%", "MA DOR"),
    ("US-MA-BOS", "occ_pct", "percentage", 0.145, "2025-01-01", "USD", "Boston total lodging tax ~14.5% (state+city+convention)", "City of Boston"),
    ("US-TN", "occ_pct", "percentage", 0.07, "2025-01-01", "USD", "Tennessee state sales tax on accommodation 7%", "TN DOR"),
    ("US-TN-BNA", "occ_pct", "percentage", 0.155, "2025-01-01", "USD", "Nashville total lodging tax ~15.5% (state+metro+tourism)", "Metro Nashville"),
    ("US-LA", "occ_pct", "percentage", 0.0445, "2025-01-01", "USD", "Louisiana state sales tax on lodging 4.45%", "LA DOR"),
    ("US-LA-MSY", "occ_pct", "percentage", 0.1575, "2025-01-01", "USD", "New Orleans total lodging tax ~15.75% (state+city+parish+tourism)", "City of New Orleans"),
    ("US-GA", "occ_pct", "percentage", 0.04, "2025-01-01", "USD", "Georgia state sales tax on lodging 4%", "GA DOR"),
    ("US-GA-ATL", "occ_pct", "percentage", 0.168, "2025-01-01", "USD", "Atlanta total lodging tax ~16.8% (state+county+city+hotel/motel)", "City of Atlanta"),
    ("US-AZ", "occ_pct", "percentage", 0.056, "2025-01-01", "USD", "Arizona transaction privilege tax on lodging 5.6%", "AZ DOR"),
    ("US-AZ-PHX", "occ_pct", "percentage", 0.138, "2025-01-01", "USD", "Phoenix total lodging tax ~13.8% (state+county+city)", "City of Phoenix"),
    ("US-OR", "occ_pct", "percentage", 0.018, "2025-01-01", "USD", "Oregon statewide transient lodging tax 1.8%", "OR DOR"),
    ("US-OR-PDX", "occ_pct", "percentage", 0.138, "2025-01-01", "USD", "Portland total lodging tax ~13.8% (state+county+city+TID)", "City of Portland"),
    ("US-MN", "occ_pct", "percentage", 0.06875, "2025-01-01", "USD", "Minnesota sales tax on lodging 6.875%", "MN DOR"),
    ("US-MN-MSP", "occ_pct", "percentage", 0.13625, "2025-01-01", "USD", "Minneapolis total lodging tax ~13.625%", "City of Minneapolis"),
    ("US-PA", "occ_pct", "percentage", 0.06, "2025-01-01", "USD", "Pennsylvania sales tax on lodging 6%", "PA DOR"),
    ("US-PA-PHL", "occ_pct", "percentage", 0.158, "2025-01-01", "USD", "Philadelphia total lodging tax ~15.8% (state+city+convention)", "City of Philadelphia"),
    ("US-NC", "occ_pct", "percentage", 0.0475, "2025-01-01", "USD", "North Carolina state+county occupancy tax ~4.75%", "NC DOR"),
    ("US-NC-CLT", "occ_pct", "percentage", 0.128, "2025-01-01", "USD", "Charlotte total lodging tax ~12.8%", "City of Charlotte"),

    # Spain
    ("ES-MD", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Madrid: national VAT 10% applies", "AEAT"),
    ("ES-MD-MAD", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Madrid has no city tourist tax (under discussion)", "Ayuntamiento de Madrid"),
    ("ES-AN", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Andalusia: national VAT 10% applies", "AEAT"),
    ("ES-AN-SVQ", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Seville has no city tourist tax", "Ayuntamiento de Sevilla"),
    ("ES-AN-MLG", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Malaga has no city tourist tax (proposed)", "Ayuntamiento de Malaga"),
    ("ES-AN-GRX", "tourism_flat_person_night", "flat", 0.0, "2025-01-01", "EUR", "Granada has no city tourist tax", "Ayuntamiento de Granada"),
    ("ES-VC", "tourism_pct", "percentage", 0.005, "2025-01-01", "EUR", "Valencia region tourist tax 0.50 EUR/person/night equiv", "Generalitat Valenciana"),
    ("ES-VC-VLC", "tourism_flat_person_night", "flat", 0.50, "2025-01-01", "EUR", "Valencia City tourist tax EUR 0.50/person/night", "Ajuntament de Valencia"),

    # France cities
    ("FR-PAC", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "PACA: national VAT 10% applies", "DGFiP"),
    ("FR-PAC-NCE", "tourism_flat_person_night", "flat", 3.0, "2025-01-01", "EUR", "Nice taxe de sejour (up to EUR 3/person/night by star)", "Metropole Nice"),
    ("FR-PAC-MRS", "tourism_flat_person_night", "flat", 2.5, "2025-01-01", "EUR", "Marseille taxe de sejour", "Ville de Marseille"),
    ("FR-OCC", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Occitanie: national VAT 10% applies", "DGFiP"),
    ("FR-OCC-TLS", "tourism_flat_person_night", "flat", 2.0, "2025-01-01", "EUR", "Toulouse taxe de sejour", "Toulouse Metropole"),
    ("FR-ARA", "vat_reduced", "percentage", 0.10, "2025-01-01", "EUR", "Auvergne-Rhone-Alpes: national VAT 10% applies", "DGFiP"),
    ("FR-ARA-LYS", "tourism_flat_person_night", "flat", 2.3, "2025-01-01", "EUR", "Lyon taxe de sejour", "Metropole de Lyon"),

    # Greece islands
    ("GR-M", "vat_reduced", "percentage", 0.13, "2025-01-01", "EUR", "South Aegean: national VAT 13% applies", "AADE"),
    ("GR-M-MYK", "tourism_flat_person_night", "flat", 4.0, "2025-01-01", "EUR", "Mykonos tourist tax (EUR 4 for 4-star+)", "Mykonos Municipality"),
    ("GR-M-MYK", "entry_flat_person_stay", "flat", 20.0, "2025-06-01", "EUR", "Mykonos cruise passenger fee EUR 20 (Jun-Sep 2026)", "Greek Ministry of Maritime"),
    ("GR-M-JTR", "tourism_flat_person_night", "flat", 4.0, "2025-01-01", "EUR", "Santorini tourist tax (EUR 4 for 4-star+)", "Thira Municipality"),
    ("GR-M-JTR", "entry_flat_person_stay", "flat", 20.0, "2025-06-01", "EUR", "Santorini cruise passenger fee EUR 20 (Jun-Sep 2026)", "Greek Ministry of Maritime"),
    ("GR-K", "vat_reduced", "percentage", 0.13, "2025-01-01", "EUR", "Crete: national VAT 13% applies", "AADE"),
    ("GR-K-HER", "tourism_flat_person_night", "flat", 4.0, "2025-01-01", "EUR", "Heraklion tourist tax (EUR 4 for 4-star+)", "Heraklion Municipality"),

    # UAE - Abu Dhabi
    ("AE-AZ", "municipal_pct", "percentage", 0.04, "2025-01-01", "AED", "Abu Dhabi tourism fee 4%", "Abu Dhabi DCT"),
    ("AE-AZ-AUH", "tourism_flat_night", "flat", 15.0, "2025-01-01", "AED", "Abu Dhabi City municipality fee AED 15/room/night", "Abu Dhabi Municipality"),

    # Update existing: Berlin tax increased to 7.5%
    # (Already exists as 5% in DE-BE-BER but increased in 2025)

    # Update: Hawaii TAT increase to 11%
    # (Already exists but needs update from 10.25% to 11%)
]

# ── EXEMPTION RULES for new jurisdictions ──────────────────────────
RULES = [
    ("GB-SCT-EDI", "cap", "Edinburgh levy night cap (max 7 nights)", 100,
     {}, {"max_nights": 7}, "2026-07-24", "City of Edinburgh Visitor Levy Act"),
    ("IT-FI-FLR", "exemption", "Florence child exemption (under 12)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 12}]},
     {}, "2025-01-01", "Regolamento comunale Firenze"),
    ("IT-MI-MIL", "exemption", "Milan child exemption (under 18)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 18}]},
     {}, "2025-01-01", "Regolamento comunale Milano"),
    ("IT-NA-NAP", "exemption", "Naples child exemption (under 14)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 14}]},
     {}, "2025-01-01", "Regolamento comunale Napoli"),
    ("PT-13-OPO", "cap", "Porto tourist tax cap (max 7 nights)", 100,
     {}, {"max_nights": 7}, "2025-01-01", "Regulamento Porto"),
    ("PT-AZ-PDL", "cap", "Azores tourist tax cap (max 3 nights)", 100,
     {}, {"max_nights": 3}, "2025-01-01", "Regulamento Ponta Delgada"),
    ("US-DC", "exemption", "DC long-stay exemption (over 30 nights)", 100,
     {"operator": "AND", "rules": [{"field": "stay_length_days", "op": ">=", "value": 30}]},
     {}, "2025-01-01", "DC Code 47-2002"),
]


async def seed(api_base: str, api_key: str):
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    jurs_created = jurs_skipped = 0
    rates_created = rates_skipped = rates_errors = 0
    rules_created = 0
    t0 = time.time()

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        h = (await client.get(f"{api_base}/health")).json()
        print(f"API: {h['status']} | DB: {h['database']}\n")

        # Create jurisdictions
        print(f"Creating {len(JURISDICTIONS)} jurisdictions...")
        for code, name, jtype, parent, country, currency, tz in JURISDICTIONS:
            body = {
                "code": code,
                "name": name,
                "jurisdiction_type": jtype,
                "parent_code": parent,
                "country_code": country,
                "currency_code": currency,
                "timezone": tz,
            }
            r = await client.post(f"{api_base}/v1/jurisdictions", json=body)
            if r.status_code == 201:
                jurs_created += 1
                print(f"  + {code} ({name})")
            elif r.status_code == 409:
                jurs_skipped += 1
            else:
                print(f"  ! {code}: {r.status_code} - {r.text[:80]}")

        print(f"\nJurisdictions: {jurs_created} created, {jurs_skipped} skipped")

        # Get existing rates
        existing = set()
        for offset in range(0, 3000, 500):
            resp = await client.get(f"{api_base}/v1/rates", params={"limit": "500", "offset": str(offset)})
            if resp.status_code != 200 or len(resp.json()) == 0:
                break
            for r in resp.json():
                existing.add((r["jurisdiction_code"], r["tax_category_code"]))

        # Create rates
        print(f"\nCreating {len(RATES)} tax rates...")
        for jur, cat, rtype, val, eff, cur, legal, auth in RATES:
            if (jur, cat) in existing:
                rates_skipped += 1
                continue
            body = {
                "jurisdiction_code": jur,
                "tax_category_code": cat,
                "rate_type": rtype,
                "effective_start": eff,
                "currency_code": cur,
                "status": "active",
                "legal_reference": legal,
                "authority_name": auth,
                "created_by": "data_research",
            }
            if val is not None:
                body["rate_value"] = val
            r = await client.post(f"{api_base}/v1/rates", json=body)
            if r.status_code == 201:
                rates_created += 1
            elif r.status_code == 409:
                rates_skipped += 1
            else:
                rates_errors += 1
                print(f"  ! {jur}/{cat}: {r.status_code} - {r.text[:80]}")

        print(f"Rates: {rates_created} created, {rates_skipped} skipped, {rates_errors} errors")

        # Create rules
        print(f"\nCreating {len(RULES)} rules...")
        for jur, rtype, name, prio, conds, action, eff, legal in RULES:
            body = {
                "jurisdiction_code": jur,
                "rule_type": rtype,
                "name": name,
                "priority": prio,
                "conditions": conds,
                "action": action,
                "effective_start": eff,
                "legal_reference": legal,
                "created_by": "data_research",
            }
            r = await client.post(f"{api_base}/v1/rules", json=body)
            if r.status_code == 201:
                rules_created += 1

        print(f"Rules: {rules_created} created")

    elapsed = int(time.time() - t0)
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed}s")
    print(f"  Jurisdictions: {jurs_created} new")
    print(f"  Rates: {rates_created} new")
    print(f"  Rules: {rules_created} new")
    print(f"{'='*60}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default="http://localhost:8001")
    p.add_argument("--api-key", default="dev-api-key-change-me")
    args = p.parse_args()
    asyncio.run(seed(args.api_url, args.api_key))


if __name__ == "__main__":
    main()
