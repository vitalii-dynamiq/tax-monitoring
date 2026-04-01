"""
Final fixes: add missing exemptions, rules, and US cities.

1. Child exemptions for cities with per-person-per-night taxes
2. Long-stay exemptions for major tourism countries
3. Night caps where applicable
4. Missing US cities with their tax rates

Usage: python -m scripts.seed_final_fixes
"""

import argparse
import asyncio
import time
import httpx


# ── Missing US cities ──────────────────────────────────────────────
US_CITIES = [
    # (code, name, parent_code, timezone)
    ("US-CA-SDG", "San Diego", "US-CA", "America/Los_Angeles"),
    ("US-TX-SAT", "San Antonio", "US-TX", "America/Chicago"),
    ("US-TX-AUS", "Austin", "US-TX", "America/Chicago"),
    ("US-TX-DFW", "Dallas", "US-TX", "America/Chicago"),
    ("US-FL-ORL", "Orlando", "US-FL", "America/New_York"),
    ("US-FL-TPA", "Tampa", "US-FL", "America/New_York"),
    ("US-FL-FLL", "Fort Lauderdale", "US-FL", "America/New_York"),
    ("US-MD", "Maryland", "US", "America/New_York"),
    ("US-MD-BWI", "Baltimore", "US-MD", "America/New_York"),
    ("US-WI", "Wisconsin", "US", "America/Chicago"),
    ("US-WI-MKE", "Milwaukee", "US-WI", "America/Chicago"),
    ("US-CA-SAC", "Sacramento", "US-CA", "America/Los_Angeles"),
    ("US-CA-SJC", "San Jose", "US-CA", "America/Los_Angeles"),
    ("US-SC", "South Carolina", "US", "America/New_York"),
    ("US-SC-CHS", "Charleston", "US-SC", "America/New_York"),
    ("US-MO", "Missouri", "US", "America/Chicago"),
    ("US-MO-MCI", "Kansas City", "US-MO", "America/Chicago"),
    ("US-FL-KEY", "Key West", "US-FL", "America/New_York"),
    ("US-NV-RNO", "Reno", "US-NV", "America/Los_Angeles"),
]

US_RATES = [
    ("US-CA-SDG", "occ_pct", "percentage", 0.1265, "2025-01-01", "USD", "San Diego TOT ~12.65%", "City of San Diego"),
    ("US-TX-SAT", "occ_pct", "percentage", 0.169, "2025-01-01", "USD", "San Antonio hotel tax ~16.9% (state+city+venue)", "City of San Antonio"),
    ("US-TX-AUS", "occ_pct", "percentage", 0.15, "2025-01-01", "USD", "Austin hotel tax ~15% (state+city+venue)", "City of Austin"),
    ("US-TX-DFW", "occ_pct", "percentage", 0.15, "2025-01-01", "USD", "Dallas hotel tax ~15% (state+city+venue)", "City of Dallas"),
    ("US-FL-ORL", "occ_pct", "percentage", 0.125, "2025-01-01", "USD", "Orlando tourist dev tax ~12.5% (state+county+TDT)", "Orange County"),
    ("US-FL-TPA", "occ_pct", "percentage", 0.12, "2025-01-01", "USD", "Tampa tourist dev tax ~12% (state+county+TDT)", "Hillsborough County"),
    ("US-FL-FLL", "occ_pct", "percentage", 0.12, "2025-01-01", "USD", "Fort Lauderdale tourist tax ~12%", "Broward County"),
    ("US-MD", "occ_pct", "percentage", 0.06, "2025-01-01", "USD", "Maryland sales tax on lodging 6%", "MD Comptroller"),
    ("US-MD-BWI", "occ_pct", "percentage", 0.095, "2025-01-01", "USD", "Baltimore hotel tax ~9.5% (state+city)", "City of Baltimore"),
    ("US-WI", "occ_pct", "percentage", 0.05, "2025-01-01", "USD", "Wisconsin state sales tax on lodging 5%", "WI DOR"),
    ("US-WI-MKE", "occ_pct", "percentage", 0.127, "2025-01-01", "USD", "Milwaukee total lodging tax ~12.7%", "City of Milwaukee"),
    ("US-CA-SAC", "occ_pct", "percentage", 0.12, "2025-01-01", "USD", "Sacramento TOT 12%", "City of Sacramento"),
    ("US-CA-SJC", "occ_pct", "percentage", 0.1175, "2025-01-01", "USD", "San Jose TOT 11.75%", "City of San Jose"),
    ("US-SC", "occ_pct", "percentage", 0.07, "2025-01-01", "USD", "South Carolina accommodations tax 7% (2% state + 5% local)", "SC DOR"),
    ("US-SC-CHS", "occ_pct", "percentage", 0.132, "2025-01-01", "USD", "Charleston total lodging tax ~13.2%", "City of Charleston"),
    ("US-MO", "occ_pct", "percentage", 0.04225, "2025-01-01", "USD", "Missouri state sales tax 4.225%", "MO DOR"),
    ("US-MO-MCI", "occ_pct", "percentage", 0.1535, "2025-01-01", "USD", "Kansas City total lodging tax ~15.35%", "City of Kansas City"),
    ("US-FL-KEY", "occ_pct", "percentage", 0.125, "2025-01-01", "USD", "Key West tourist tax ~12.5% (state+county+TDT)", "Monroe County"),
    ("US-NV-RNO", "occ_pct", "percentage", 0.13, "2025-01-01", "USD", "Reno transient lodging tax ~13%", "Washoe County"),
]

# ── Exemption rules (child exemptions, long-stay, caps) ───────────
RULES = [
    # CHILD EXEMPTIONS - per-person-per-night cities
    # Italy - standard under 10 (Rome already has one; add for others missing)
    ("IT-VE-VCE", "exemption", "Venice child exemption (under 10)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 10}]},
     {}, "2025-01-01", "Regolamento comunale Venezia"),
    ("IT-TO-TRN", "exemption", "Turin child exemption (under 10)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 10}]},
     {}, "2025-01-01", "Regolamento comunale Torino"),
    ("IT-BO-BLQ", "exemption", "Bologna child exemption (under 14)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 14}]},
     {}, "2025-01-01", "Regolamento comunale Bologna"),

    # France - standard under 18
    ("FR-IDF-PAR", "exemption", "Paris child exemption (under 18)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 18}]},
     {}, "2025-01-01", "Code General des Collectivites Territoriales"),
    ("FR-PAC-NCE", "exemption", "Nice child exemption (under 18)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 18}]},
     {}, "2025-01-01", "CGCT France"),
    ("FR-ARA-LYS", "exemption", "Lyon child exemption (under 18)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 18}]},
     {}, "2025-01-01", "CGCT France"),

    # Germany - standard under 18
    ("DE-BE-BER", "exemption", "Berlin child exemption (under 18)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 18}]},
     {}, "2025-01-01", "Berlin Ubernachtungsteuergesetz"),
    ("DE-HH-HAM", "exemption", "Hamburg child exemption (under 18)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 18}]},
     {}, "2025-01-01", "HmbKTTG"),
    ("DE-NW-CGN", "exemption", "Cologne child exemption (under 18)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 18}]},
     {}, "2025-01-01", "Kolner Bettensteuer-Satzung"),

    # Spain
    ("ES-CT-BCN", "exemption", "Barcelona child exemption (under 17)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 17}]},
     {}, "2025-01-01", "Catalonia Tourist Tax Act"),

    # Switzerland - standard under 16
    ("CH-ZH-ZRH", "exemption", "Zurich child exemption (under 16)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 16}]},
     {}, "2025-01-01", "Zurich Kurtaxe-Reglement"),
    ("CH-GE-GVA", "exemption", "Geneva child exemption (under 18)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 18}]},
     {}, "2025-01-01", "Loi genevoise taxe de sejour"),

    # Croatia - standard under 12
    ("HR-01-ZAG", "exemption", "Zagreb child exemption (under 12)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 12}]},
     {}, "2025-01-01", "Croatian Tourism Act"),
    ("HR-21-SPU", "exemption", "Split child exemption (under 12)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 12}]},
     {}, "2025-01-01", "Croatian Tourism Act"),

    # Portugal - standard under 13
    ("PT-11-LIS", "exemption", "Lisbon child exemption (under 13)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 13}]},
     {}, "2025-01-01", "Regulamento Municipal Lisboa"),
    ("PT-FAR-ALB", "exemption", "Albufeira child exemption (under 16)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 16}]},
     {}, "2025-01-01", "Regulamento Municipal Albufeira"),

    # Greece
    ("GR-I-ATH", "exemption", "Athens child exemption (under 12)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 12}]},
     {}, "2025-01-01", "Greek Tourism Law"),

    # Romania
    ("RO-B-BUC", "exemption", "Bucharest child exemption (under 18 for students)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 18}]},
     {}, "2025-01-01", "Romanian Local Tax Code"),

    # Belgium
    ("BE-BRU-BRU", "exemption", "Brussels child exemption (under 18)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 18}]},
     {}, "2025-01-01", "Brussels Tax Code"),

    # LONG-STAY EXEMPTIONS for major countries
    # Most apply at city level where the tourist tax is charged
    ("FR-IDF-PAR", "cap", "Paris tourist tax night cap (no cap but common hotel practice)", 50,
     {}, {"max_nights": 365}, "2025-01-01", "CGCT"),
    ("NL-NH-AMS", "exemption", "Amsterdam long-stay exemption (permanent residents)", 100,
     {"operator": "AND", "rules": [{"field": "stay_length_days", "op": ">=", "value": 365}]},
     {}, "2025-01-01", "Amsterdam Toeristenbelasting Verordening"),
    ("DE-BE-BER", "exemption", "Berlin long-stay exemption (business travelers)", 90,
     {"operator": "AND", "rules": [{"field": "guest_type", "op": "==", "value": "business"}]},
     {}, "2025-01-01", "Berlin Ubernachtungsteuergesetz (business travel exempt)"),
    ("AT-9-VIE", "cap", "Vienna tourist tax night cap (max 3 months)", 50,
     {}, {"max_nights": 90}, "2025-01-01", "Wiener Tourismusforderungsgesetz"),
    ("GR-I-ATH", "cap", "Athens tourist tax night cap (max 7 nights taxed)", 50,
     {}, {"max_nights": 7}, "2025-01-01", "Greek Tourism Law"),
    ("IT-RM-ROM", "cap", "Rome tourist tax cap (max 10 nights)", 50,
     {}, {"max_nights": 10}, "2025-01-01", "Regolamento Romano"),
    ("IT-FI-FLR", "cap", "Florence tourist tax cap (max 7 nights)", 50,
     {}, {"max_nights": 7}, "2025-01-01", "Regolamento Fiorentino"),
    ("IT-MI-MIL", "cap", "Milan tourist tax cap (max 14 nights)", 50,
     {}, {"max_nights": 14}, "2025-01-01", "Regolamento Milanese"),
    ("IT-NA-NAP", "cap", "Naples tourist tax cap (max 14 nights)", 50,
     {}, {"max_nights": 14}, "2025-01-01", "Regolamento Napoletano"),
    ("IT-VE-VCE", "cap", "Venice tourist tax cap (max 5 nights)", 50,
     {}, {"max_nights": 5}, "2025-01-01", "Regolamento Veneziano"),
    ("PT-11-LIS", "cap", "Lisbon tourist tax cap (max 7 nights)", 50,
     {}, {"max_nights": 7}, "2025-01-01", "Regulamento Municipal"),
    ("PT-13-OPO", "exemption", "Porto child exemption (under 13)", 100,
     {"operator": "AND", "rules": [{"field": "guest_age", "op": "<", "value": 13}]},
     {}, "2025-01-01", "Regulamento Municipal Porto"),

    # US long-stay (30 days is standard)
    ("US-NY-NYC", "cap", "NYC long-stay partial exemption (occupancy tax exempt after 180 days)", 50,
     {}, {"max_nights": 180}, "2025-01-01", "NYC Admin Code 11-2502"),
    ("US-CA-LAX", "exemption", "LA TOT long-stay exemption (over 30 days)", 100,
     {"operator": "AND", "rules": [{"field": "stay_length_days", "op": ">=", "value": 30}]},
     {}, "2025-01-01", "LA Municipal Code 21.7.3"),
    ("US-CA-SFO", "exemption", "SF TOT long-stay exemption (over 30 days)", 100,
     {"operator": "AND", "rules": [{"field": "stay_length_days", "op": ">=", "value": 30}]},
     {}, "2025-01-01", "SF Business & Tax Regulations Code"),
    ("US-FL-MIA", "exemption", "Miami long-stay exemption (over 6 months)", 100,
     {"operator": "AND", "rules": [{"field": "stay_length_days", "op": ">=", "value": 183}]},
     {}, "2025-01-01", "FL Statute 212.03"),
    ("US-NV-LAS", "exemption", "Las Vegas long-stay exemption (over 28 days)", 100,
     {"operator": "AND", "rules": [{"field": "stay_length_days", "op": ">=", "value": 28}]},
     {}, "2025-01-01", "NRS 244.3352"),
]


async def seed(api_base: str, api_key: str):
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    t0 = time.time()
    jc = js = rc = rs = re = rlc = 0

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        h = (await client.get(f"{api_base}/health")).json()
        print(f"API: {h['status']} | DB: {h['database']}\n")

        # US states (parent jurisdictions needed for cities)
        for code, name, parent, tz in US_CITIES:
            if code.count("-") == 1:  # It's a state
                body = {"code": code, "name": name, "jurisdiction_type": "state",
                        "parent_code": parent, "country_code": "US", "currency_code": "USD", "timezone": tz}
            else:
                body = {"code": code, "name": name, "jurisdiction_type": "city",
                        "parent_code": parent, "country_code": "US", "currency_code": "USD", "timezone": tz}
            r = await client.post(f"{api_base}/v1/jurisdictions", json=body)
            if r.status_code == 201:
                jc += 1
                print(f"  + {code} ({name})")
            elif r.status_code == 409:
                js += 1

        print(f"\nJurisdictions: {jc} created, {js} skipped")

        # US rates
        print(f"\nCreating {len(US_RATES)} US city rates...")
        for jur, cat, rtype, val, eff, cur, legal, auth in US_RATES:
            body = {"jurisdiction_code": jur, "tax_category_code": cat, "rate_type": rtype,
                    "rate_value": val, "effective_start": eff, "currency_code": cur,
                    "status": "active", "legal_reference": legal, "authority_name": auth,
                    "created_by": "data_research"}
            r = await client.post(f"{api_base}/v1/rates", json=body)
            if r.status_code == 201: rc += 1
            elif r.status_code == 409: rs += 1
            else:
                re += 1
                print(f"  ! {jur}: {r.status_code} - {r.text[:80]}")

        print(f"Rates: {rc} created, {rs} skipped, {re} errors")

        # Rules
        print(f"\nCreating {len(RULES)} exemption/cap rules...")
        for jur, rtype, name, prio, conds, action, eff, legal in RULES:
            body = {"jurisdiction_code": jur, "rule_type": rtype, "name": name,
                    "priority": prio, "conditions": conds, "action": action,
                    "effective_start": eff, "legal_reference": legal, "created_by": "data_research"}
            r = await client.post(f"{api_base}/v1/rules", json=body)
            if r.status_code == 201: rlc += 1

        print(f"Rules: {rlc} created")

    elapsed = int(time.time() - t0)
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed}s | +{jc} jurisdictions, +{rc} rates, +{rlc} rules")
    print(f"{'='*60}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default="http://localhost:8001")
    p.add_argument("--api-key", default="dev-api-key-change-me")
    args = p.parse_args()
    asyncio.run(seed(args.api_url, args.api_key))


if __name__ == "__main__":
    main()
