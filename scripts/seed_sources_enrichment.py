"""Enrich all jurisdictions that have zero monitored sources with relevant
government/tax authority regulatory URLs.

Sources are researched manually — no AI API calls required.
Run:  DATABASE_URL_SYNC="..." python -m scripts.seed_sources_enrichment
"""

import os
import sys

import psycopg2

# ── Tax authority / government URLs per country code ──────────────────────────
# Each entry: list of (url, source_type) tuples.
# source_type: "tax_authority" | "government_website" | "regulatory_body" | "legal_gazette"

COUNTRY_SOURCES: dict[str, list[tuple[str, str]]] = {
    # ─── Americas ─────────────────────────────────────────────────────────────
    "US": [("irs.gov", "tax_authority"), ("treasury.gov", "government_website")],
    "CA": [("canada.ca/en/revenue-agency", "tax_authority")],
    "MX": [("sat.gob.mx", "tax_authority")],
    "BR": [("gov.br/receitafederal", "tax_authority")],
    "AR": [("afip.gob.ar", "tax_authority")],
    "CL": [("sii.cl", "tax_authority")],
    "CO": [("dian.gov.co", "tax_authority")],
    "PE": [("sunat.gob.pe", "tax_authority")],
    "EC": [("sri.gob.ec", "tax_authority")],
    "UY": [("dgi.gub.uy", "tax_authority")],
    "PY": [("set.gov.py", "tax_authority")],
    "BO": [("impuestos.gob.bo", "tax_authority")],
    "VE": [("seniat.gob.ve", "tax_authority")],
    "CR": [("hacienda.go.cr", "tax_authority")],
    "PA": [("dgi.mef.gob.pa", "tax_authority")],
    "GT": [("sat.gob.gt", "tax_authority")],
    "DO": [("dgii.gov.do", "tax_authority")],
    "CU": [("onat.gob.cu", "tax_authority")],
    "HT": [("dgi.gouv.ht", "tax_authority")],
    "PR": [("hacienda.pr.gov", "tax_authority")],
    "GY": [("gra.gov.gy", "tax_authority")],
    "SR": [("belastingdienst.sr", "tax_authority")],
    "BZ": [("incometaxbelize.gov.bz", "tax_authority")],
    "BS": [("bahamas.gov.bs", "government_website")],
    "JM": [("tajgov.jm", "tax_authority")],
    "TT": [("ird.gov.tt", "tax_authority")],
    "BB": [("bra.gov.bb", "tax_authority")],
    "AG": [("ab.gov.ag", "government_website")],
    "DM": [("ird.gov.dm", "tax_authority")],
    "GD": [("ird.gd", "tax_authority")],
    "KN": [("sknird.com", "tax_authority")],
    "LC": [("ird.gov.lc", "tax_authority")],
    "VC": [("svgird.com", "tax_authority")],
    "AI": [("gov.ai", "government_website")],
    "BQ": [("belastingdienst-cn.nl", "tax_authority")],
    "VI": [("bir.vi.gov", "tax_authority")],
    "VG": [("bvi.gov.vg", "government_website")],
    "MS": [("gov.ms", "government_website")],
    "FK": [("fig.gov.fk", "government_website")],
    "GF": [("impots.gouv.fr", "tax_authority")],
    "GP": [("impots.gouv.fr", "tax_authority")],
    "MQ": [("impots.gouv.fr", "tax_authority")],
    "BL": [("comstbarth.fr", "government_website")],
    "MF": [("com-saint-martin.fr", "government_website")],
    "SX": [("sintmaartengov.org", "government_website")],
    "GU": [("guamtax.com", "tax_authority")],
    "AS": [("americansamoa.gov", "government_website")],
    "MP": [("cnmifinance.gov.mp", "tax_authority")],

    # ─── Europe ───────────────────────────────────────────────────────────────
    "GB": [("gov.uk/government/organisations/hm-revenue-customs", "tax_authority")],
    "DE": [("bundesfinanzministerium.de", "tax_authority")],
    "FR": [("impots.gouv.fr", "tax_authority")],
    "IT": [("agenziaentrate.gov.it", "tax_authority")],
    "ES": [("agenciatributaria.es", "tax_authority")],
    "PT": [("portaldasfinancas.gov.pt", "tax_authority")],
    "NL": [("belastingdienst.nl", "tax_authority")],
    "BE": [("finance.belgium.be", "tax_authority")],
    "AT": [("bmf.gv.at", "tax_authority")],
    "CH": [("estv.admin.ch", "tax_authority")],
    "SE": [("skatteverket.se", "tax_authority")],
    "NO": [("skatteetaten.no", "tax_authority")],
    "DK": [("skat.dk", "tax_authority")],
    "FI": [("vero.fi", "tax_authority")],
    "IE": [("revenue.ie", "tax_authority")],
    "PL": [("podatki.gov.pl", "tax_authority")],
    "CZ": [("financnisprava.cz", "tax_authority")],
    "SK": [("financnasprava.sk", "tax_authority")],
    "HU": [("nav.gov.hu", "tax_authority")],
    "RO": [("anaf.ro", "tax_authority")],
    "BG": [("nap.bg", "tax_authority")],
    "HR": [("porezna-uprava.hr", "tax_authority")],
    "SI": [("fu.gov.si", "tax_authority")],
    "RS": [("purs.gov.rs", "tax_authority")],
    "BA": [("uino.gov.ba", "tax_authority")],
    "ME": [("tax.gov.me", "tax_authority")],
    "MK": [("ujp.gov.mk", "tax_authority")],
    "AL": [("drejtoriatataksave.gov.al", "tax_authority")],
    "GR": [("aade.gr", "tax_authority")],
    "MT": [("cfr.gov.mt", "tax_authority")],
    "IS": [("rsk.is", "tax_authority")],
    "LT": [("vmi.lt", "tax_authority")],
    "LV": [("vid.gov.lv", "tax_authority")],
    "EE": [("emta.ee", "tax_authority")],
    "LU": [("acd.gouvernement.lu", "tax_authority")],
    "GE": [("rs.ge", "tax_authority")],
    "AM": [("taxservice.am", "tax_authority")],
    "AZ": [("taxes.gov.az", "tax_authority")],
    "BY": [("nalog.gov.by", "tax_authority")],
    "UA": [("tax.gov.ua", "tax_authority")],
    "MD": [("sfs.md", "tax_authority")],
    "RU": [("nalog.gov.ru", "tax_authority")],
    "GG": [("gov.gg/revenue-service", "tax_authority")],
    "JE": [("gov.je/taxesmoney", "tax_authority")],
    "IM": [("gov.im/categories/tax-vat-and-your-money", "tax_authority")],
    "GI": [("gibraltar.gov.gi/income-tax", "tax_authority")],
    "FO": [("taks.fo", "tax_authority")],
    "GL": [("naalakkersuisut.gl", "government_website")],
    "VA": [("vaticanstate.va", "government_website")],

    # ─── Asia-Pacific ─────────────────────────────────────────────────────────
    "JP": [("nta.go.jp", "tax_authority")],
    "CN": [("chinatax.gov.cn", "tax_authority")],
    "KR": [("nts.go.kr", "tax_authority")],
    "IN": [("incometaxindia.gov.in", "tax_authority"), ("gst.gov.in", "tax_authority")],
    "AU": [("ato.gov.au", "tax_authority")],
    "NZ": [("ird.govt.nz", "tax_authority")],
    "TH": [("rd.go.th", "tax_authority")],
    "VN": [("gdt.gov.vn", "tax_authority")],
    "MY": [("hasil.gov.my", "tax_authority")],
    "SG": [("iras.gov.sg", "tax_authority")],
    "ID": [("pajak.go.id", "tax_authority")],
    "PH": [("bir.gov.ph", "tax_authority")],
    "TW": [("tax.nat.gov.tw", "tax_authority")],
    "HK": [("ird.gov.hk", "tax_authority")],
    "MO": [("dsf.gov.mo", "tax_authority")],
    "BD": [("nbr.gov.bd", "tax_authority")],
    "LK": [("ird.gov.lk", "tax_authority")],
    "PK": [("fbr.gov.pk", "tax_authority")],
    "NP": [("ird.gov.np", "tax_authority")],
    "KH": [("tax.gov.kh", "tax_authority")],
    "LA": [("tax.gov.la", "tax_authority")],
    "MM": [("ird.gov.mm", "tax_authority")],
    "MN": [("mta.mn", "tax_authority")],
    "KG": [("sti.gov.kg", "tax_authority")],
    "KZ": [("kgd.gov.kz", "tax_authority")],
    "UZ": [("soliq.uz", "tax_authority")],
    "TJ": [("andoz.tj", "tax_authority")],
    "TM": [("fineconomic.gov.tm", "government_website")],
    "BN": [("mof.gov.bn", "government_website")],
    "TL": [("mof.gov.tl", "government_website")],
    "FJ": [("frcs.org.fj", "tax_authority")],
    "PG": [("irc.gov.pg", "tax_authority")],
    "WS": [("revenue.gov.ws", "tax_authority")],
    "TO": [("revenue.gov.to", "tax_authority")],
    "VU": [("customsinlandrevenue.gov.vu", "tax_authority")],
    "SB": [("ird.gov.sb", "tax_authority")],
    "KI": [("mfed.gov.ki", "government_website")],
    "MH": [("rfrmi.com", "government_website")],
    "FM": [("fsmgov.org", "government_website")],
    "NR": [("naurugov.nr", "government_website")],
    "TV": [("tuvalugov.tv", "government_website")],
    "NU": [("gov.nu", "government_website")],
    "CK": [("revenue.gov.ck", "tax_authority")],
    "PF": [("impot-polynesie.gov.pf", "tax_authority")],
    "NC": [("dsf.gouv.nc", "tax_authority")],
    "WF": [("wallis-et-futuna.gouv.fr", "government_website")],
    "NF": [("norfolkisland.gov.nf", "government_website")],
    "CX": [("cx.gov.au", "government_website")],
    "CC": [("cc.gov.au", "government_website")],
    "TK": [("tokelau.org.nz", "government_website")],

    # ─── Middle East ──────────────────────────────────────────────────────────
    "AE": [("tax.gov.ae", "tax_authority")],
    "SA": [("zatca.gov.sa", "tax_authority")],
    "QA": [("gta.gov.qa", "tax_authority")],
    "KW": [("mof.gov.kw", "government_website")],
    "BH": [("nbr.gov.bh", "tax_authority")],
    "OM": [("taxauthority.gov.om", "tax_authority")],
    "JO": [("istd.gov.jo", "tax_authority")],
    "LB": [("finance.gov.lb", "government_website")],
    "IQ": [("tax.mof.gov.iq", "tax_authority")],
    "IR": [("tax.gov.ir", "tax_authority")],
    "PS": [("mot.gov.ps", "government_website")],
    "IL": [("taxes.gov.il", "tax_authority")],
    "SY": [("syriantax.gov.sy", "tax_authority")],
    "YE": [("tax.gov.ye", "tax_authority")],

    # ─── Africa ───────────────────────────────────────────────────────────────
    "ZA": [("sars.gov.za", "tax_authority")],
    "EG": [("eta.gov.eg", "tax_authority")],
    "MA": [("tax.gov.ma", "tax_authority")],
    "TN": [("finances.gov.tn", "government_website")],
    "DZ": [("mf.gov.dz", "government_website")],
    "LY": [("tax.gov.ly", "tax_authority")],
    "NG": [("firs.gov.ng", "tax_authority")],
    "KE": [("kra.go.ke", "tax_authority")],
    "TZ": [("tra.go.tz", "tax_authority")],
    "UG": [("ura.go.ug", "tax_authority")],
    "RW": [("rra.gov.rw", "tax_authority")],
    "ET": [("mor.gov.et", "tax_authority")],
    "GH": [("gra.gov.gh", "tax_authority")],
    "CI": [("dgi.gouv.ci", "tax_authority")],
    "SN": [("dgid.sn", "tax_authority")],
    "CM": [("dgi.cm", "tax_authority")],
    "CD": [("dgi.gouv.cd", "tax_authority")],
    "CG": [("dgi.cg", "tax_authority")],
    "GA": [("dgi.ga", "tax_authority")],
    "AO": [("agt.minfin.gov.ao", "tax_authority")],
    "MZ": [("at.gov.mz", "tax_authority")],
    "ZM": [("zra.org.zm", "tax_authority")],
    "MW": [("mra.mw", "tax_authority")],
    "BW": [("burs.org.bw", "tax_authority")],
    "NA": [("nra.na", "tax_authority")],
    "LS": [("lra.org.ls", "tax_authority")],
    "SZ": [("sra.org.sz", "tax_authority")],
    "MG": [("impots.mg", "tax_authority")],
    "MU": [("mra.mu", "tax_authority")],
    "SC": [("src.gov.sc", "tax_authority")],
    "CV": [("dnre.gov.cv", "tax_authority")],
    "DJ": [("finances.gouv.dj", "government_website")],
    "ER": [("shabait.com", "government_website")],
    "SO": [("mof.gov.so", "government_website")],
    "SS": [("grss.gov.ss", "government_website")],
    "SD": [("customs.gov.sd", "government_website")],
    "TD": [("finances.td", "government_website")],
    "CF": [("finances.gouv.cf", "government_website")],
    "GQ": [("guineaecuatorialpress.com", "government_website")],
    "ML": [("dgi.ml", "tax_authority")],
    "BF": [("dgi.bf", "tax_authority")],
    "NE": [("dgi.ne", "tax_authority")],
    "BJ": [("dgi.bj", "tax_authority")],
    "TG": [("otr.tg", "tax_authority")],
    "GN": [("dni.gov.gn", "tax_authority")],
    "GW": [("mef.gov.gw", "government_website")],
    "SL": [("nra.gov.sl", "tax_authority")],
    "LR": [("lra.gov.lr", "tax_authority")],
    "GM": [("gra.gm", "tax_authority")],
    "BI": [("obr.bi", "tax_authority")],
    "KM": [("finances.gouv.km", "government_website")],
    "MR": [("finances.gov.mr", "government_website")],
    "ST": [("mfp.gov.st", "government_website")],

    # ─── Misc / Territories ───────────────────────────────────────────────────
    "KP": [("mfa.gov.kp", "government_website")],
    "RE": [("impots.gouv.fr", "tax_authority")],
    "YT": [("impots.gouv.fr", "tax_authority")],
    "XX": [],  # placeholder/test code, no real jurisdiction
}

# ── Specific sub-national sources (major jurisdictions) ──────────────────────
# key: jurisdiction code → list of (url, source_type)
SPECIFIC_SOURCES: dict[str, list[tuple[str, str]]] = {
    # US states
    "US-NY": [("tax.ny.gov", "tax_authority")],
    "US-CA": [("cdtfa.ca.gov", "tax_authority")],
    "US-FL": [("floridarevenue.com", "tax_authority")],
    "US-TX": [("comptroller.texas.gov", "tax_authority")],
    "US-IL": [("tax.illinois.gov", "tax_authority")],
    "US-HI": [("tax.hawaii.gov", "tax_authority")],
    "US-NV": [("tax.nv.gov", "tax_authority")],
    "US-CO": [("tax.colorado.gov", "tax_authority")],
    "US-WA": [("dor.wa.gov", "tax_authority")],
    "US-MA": [("mass.gov/dor", "tax_authority")],
    "US-DC": [("otr.cfo.dc.gov", "tax_authority")],
    "US-PA": [("revenue.pa.gov", "tax_authority")],
    "US-NJ": [("nj.gov/treasury/taxation", "tax_authority")],
    "US-GA": [("dor.georgia.gov", "tax_authority")],
    "US-VA": [("tax.virginia.gov", "tax_authority")],
    "US-AZ": [("azdor.gov", "tax_authority")],
    "US-OR": [("oregon.gov/dor", "tax_authority")],
    "US-SC": [("dor.sc.gov", "tax_authority")],
    "US-LA": [("revenue.louisiana.gov", "tax_authority")],
    "US-TN": [("tn.gov/revenue", "tax_authority")],
    # Canadian provinces
    "CA-BC": [("gov.bc.ca/gov/content/taxes", "tax_authority")],
    "CA-ON": [("ontario.ca/page/taxes-and-benefits", "tax_authority")],
    "CA-QC": [("revenuquebec.ca", "tax_authority")],
    "CA-AB": [("alberta.ca/tax-levy.aspx", "tax_authority")],
    "CA-NS": [("novascotia.ca/finance/en/home/taxation.aspx", "tax_authority")],
    "CA-MB": [("gov.mb.ca/finance/taxation", "tax_authority")],
    # German states
    "DE-BY": [("finanzamt.bayern.de", "tax_authority")],
    "DE-BE": [("berlin.de/sen/finanzen", "tax_authority")],
    "DE-HH": [("hamburg.de/steuern", "government_website")],
    # Australian states
    "AU-NSW": [("revenue.nsw.gov.au", "tax_authority")],
    "AU-VIC": [("sro.vic.gov.au", "tax_authority")],
    "AU-QLD": [("treasury.qld.gov.au", "tax_authority")],
    # Indian states
    "IN-MH": [("mahagst.gov.in", "tax_authority")],
    "IN-KA": [("gst.kar.nic.in", "tax_authority")],
    "IN-DL": [("dvat.gov.in", "tax_authority")],
    # Spanish regions
    "ES-CT": [("atc.gencat.cat", "tax_authority")],
    "ES-IB": [("atib.es", "tax_authority")],
    "ES-CN": [("gobiernodecanarias.org/tributos", "tax_authority")],
    # Italian regions
    "IT-25": [("regione.lombardia.it", "government_website")],
    "IT-62": [("regione.lazio.it", "government_website")],
    # Japanese prefectures
    "JP-13": [("tax.metro.tokyo.lg.jp", "tax_authority")],
    "JP-27": [("pref.osaka.lg.jp/zei", "tax_authority")],
    "JP-26": [("pref.kyoto.jp/zeimu", "tax_authority")],
    # Major cities
    "US-NY-NYC": [("nyc.gov/site/finance/taxes/business-hotel-room-occupancy-tax.page", "government_website")],
    "US-IL-CHI": [("chicago.gov/city/en/depts/fin.html", "government_website")],
    "US-CA-LAX": [("finance.lacity.gov", "government_website")],
    "US-CA-SFO": [("sftreasurer.org", "government_website")],
    "US-FL-MIA": [("miamidade.gov/finance", "government_website")],
    "US-NV-LAS": [("clarkcountynv.gov", "government_website")],
    "US-DC-WAS": [("otr.cfo.dc.gov", "tax_authority")],
    "FR-IDF-PAR": [("paris.fr", "government_website")],
    "DE-BE-BER": [("berlin.de/sen/finanzen", "government_website")],
    "IT-62-ROM": [("comune.roma.it", "government_website")],
    "ES-CT-BCN": [("ajuntament.barcelona.cat", "government_website")],
    "NL-NH-AMS": [("amsterdam.nl", "government_website")],
    "JP-13-TYO": [("tax.metro.tokyo.lg.jp", "tax_authority")],
    "AU-NSW-SYD": [("cityofsydney.nsw.gov.au", "government_website")],
    "CA-ON-TOR": [("toronto.ca/services-payments/property-taxes-utilities", "government_website")],
    "CA-BC-VAN": [("vancouver.ca/home-property-development/property-tax.aspx", "government_website")],
    "GB-ENG-LON": [("cityoflondon.gov.uk", "government_website")],
    "IN-MH-BOM": [("mcgm.gov.in", "government_website")],
    "IN-DL-DEL": [("delhi.gov.in", "government_website")],
    "BR-SP-SAO": [("prefeitura.sp.gov.br", "government_website")],
    "BR-RJ-RIO": [("rio.rj.gov.br", "government_website")],
    "MX-DIF-MXC": [("finanzas.cdmx.gob.mx", "tax_authority")],
    "CN-11-BJS": [("chinatax.gov.cn", "tax_authority")],
    "CN-31-SHA": [("tax.sh.gov.cn", "tax_authority")],
    "KR-11-SEL": [("etax.seoul.go.kr", "tax_authority")],
    "TH-10-BKK": [("bangkok.go.th", "government_website")],
    "SG-SG-SGP": [("iras.gov.sg", "tax_authority")],
    "AE-DU-DXB": [("dm.gov.ae", "government_website")],
    "AE-AZ-AUH": [("abudhabi.ae", "government_website")],
    "SA-01-RUH": [("zatca.gov.sa", "tax_authority")],
    "TR-34-IST": [("istanbul.bel.tr", "government_website")],
    "ZA-GP-JNB": [("joburg.org.za", "government_website")],
    "EG-C-CAI": [("cairo.gov.eg", "government_website")],
    "MA-CAS": [("casablanca.ma", "government_website")],
    "MA-RAB": [("rabat.ma", "government_website")],
}


def get_dsn() -> str:
    dsn = os.environ.get(
        "DATABASE_URL_SYNC",
        os.environ.get("DATABASE_URL", "postgresql://taxlens:taxlens@localhost:5433/taxlens"),
    )
    dsn = dsn.replace("postgres://", "postgresql://", 1)
    dsn = dsn.replace("postgresql+asyncpg://", "postgresql://", 1)
    return dsn


def main() -> None:
    dsn = get_dsn()
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()

    # Get all jurisdictions with zero sources
    cur.execute("""
        SELECT j.id, j.code, j.name, j.country_code, j.jurisdiction_type
        FROM jurisdictions j
        LEFT JOIN monitored_sources ms ON ms.jurisdiction_id = j.id
        WHERE ms.id IS NULL
        ORDER BY j.country_code, j.code
    """)
    missing = cur.fetchall()
    print(f"[enrich] {len(missing)} jurisdictions without sources")

    created = 0
    skipped = 0

    for jid, code, name, country_code, jtype in missing:
        sources: list[tuple[str, str]] = []

        # 1. Check specific sources first (city/state level)
        if code in SPECIFIC_SOURCES:
            sources.extend(SPECIFIC_SOURCES[code])

        # 2. Fall back to country-level sources
        if not sources and country_code in COUNTRY_SOURCES:
            sources.extend(COUNTRY_SOURCES[country_code])

        if not sources:
            skipped += 1
            continue

        for url, source_type in sources:
            # Check if this exact source already exists
            cur.execute(
                "SELECT 1 FROM monitored_sources WHERE jurisdiction_id = %s AND url = %s",
                (jid, url),
            )
            if cur.fetchone():
                continue

            cur.execute(
                """INSERT INTO monitored_sources
                   (jurisdiction_id, url, source_type, language, status, check_frequency_days, metadata, created_by)
                   VALUES (%s, %s, %s, 'en', 'active', 30, '{}', 'seed')""",
                (jid, url, source_type),
            )
            created += 1

    cur.close()
    conn.close()

    print(f"[enrich] Done. Created {created} sources, skipped {skipped} jurisdictions (no known sources).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[enrich] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
