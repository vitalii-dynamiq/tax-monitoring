"""
Seed regulatory monitoring sources for all countries and key sub-jurisdictions.
Each source is an official government URL the AI agent monitors for tax changes.

Usage: python -m scripts.seed_regulatory_sources
"""

import argparse
import asyncio
import time
import httpx

# (jurisdiction_code, url, source_type, language)
SOURCES: list[tuple[str, str, str, str]] = [
    # ═══════════════════════════════════════════════════════════════
    # EUROPE — Tax authorities + tourism ministries
    # ═══════════════════════════════════════════════════════════════
    ("AT", "https://www.bmf.gv.at/themen/steuern/umsatzsteuer.html", "tax_authority", "de"),
    ("AT-9-VIE", "https://www.wien.gv.at/amtshelfer/finanzielles/rechnungswesen/abgaben/ortstaxe.html", "government_website", "de"),
    ("BE", "https://financien.belgium.be/nl/douane_accijnzen/btw", "tax_authority", "nl"),
    ("BE-BRU-BRU", "https://fiscalite.brussels/taxe-regionale-hebergements-touristiques", "government_website", "fr"),
    ("BG", "https://nra.bg/en/", "tax_authority", "en"),
    ("CH", "https://www.estv.admin.ch/estv/en/home/value-added-tax.html", "tax_authority", "en"),
    ("CH-ZH-ZRH", "https://www.stadt-zuerich.ch/fd/de/index/steuern.html", "government_website", "de"),
    ("CY", "https://www.mof.gov.cy/mof/tax/taxdep.nsf", "tax_authority", "en"),
    ("CZ", "https://www.mfcr.cz/en/taxes/vat", "tax_authority", "en"),
    ("CZ-PHA-PRG", "https://www.praha.eu/jnp/en/business/taxes_and_fees/", "government_website", "en"),
    ("DE", "https://www.bzst.de/EN/Businesses/VAT/vat_node.html", "tax_authority", "en"),
    ("DE-BE-BER", "https://www.berlin.de/sen/finanzen/steuern/informationen-fuer-steuerzahler/", "government_website", "de"),
    ("DE-HH-HAM", "https://www.hamburg.de/fb/hamburg-culture-and-tourism-tax/", "government_website", "en"),
    ("DK", "https://skat.dk/data.aspx?oid=2244283", "tax_authority", "en"),
    ("EE", "https://www.emta.ee/en/business-client/taxes-and-payment/tax-rates", "tax_authority", "en"),
    ("ES", "https://sede.agenciatributaria.gob.es/", "tax_authority", "es"),
    ("ES-CT-BCN", "https://web.gencat.cat/en/temes/turisme/impost-estades-establiments-turistics/", "tax_authority", "en"),
    ("ES-IB", "https://www.caib.es/sites/impostturistic/en/tourist_tax/", "legal_gazette", "en"),
    ("FI", "https://www.vero.fi/en/businesses-and-corporations/taxes-and-charges/vat/rates-of-vat/", "tax_authority", "en"),
    ("FR", "https://www.impots.gouv.fr/professionnel", "tax_authority", "fr"),
    ("FR-IDF-PAR", "https://www.paris.fr/pages/la-taxe-de-sejour-a-paris-137", "government_website", "fr"),
    ("GB", "https://www.gov.uk/guidance/vat-on-hotel-accommodation", "tax_authority", "en"),
    ("GB-SCT-EDI", "https://www.edinburgh.gov.uk/visitorlevy", "government_website", "en"),
    ("GR", "https://www.aade.gr/en", "tax_authority", "en"),
    ("HR", "https://porezna.gov.hr/", "tax_authority", "hr"),
    ("HU", "https://nav.gov.hu/en/taxation/tax_rates", "tax_authority", "en"),
    ("IE", "https://www.revenue.ie/en/vat/index.aspx", "tax_authority", "en"),
    ("IS", "https://www.skatturinn.is/english/", "tax_authority", "en"),
    ("IT", "https://www.agenziaentrate.gov.it/portale/web/english", "tax_authority", "en"),
    ("IT-RM-ROM", "https://www.comune.roma.it/web/it/informazione-di-servizio.page?contentId=IDS198050", "government_website", "it"),
    ("IT-VE-VCE", "https://www.comune.venezia.it/it/content/imposta-di-soggiorno", "government_website", "it"),
    ("IT-FI-FLR", "https://www.comune.fi.it/pagina/imposta-di-soggiorno", "government_website", "it"),
    ("IT-MI-MIL", "https://www.comune.milano.it/servizi/imposta-di-soggiorno", "government_website", "it"),
    ("LT", "https://www.vmi.lt/evmi/en/tax-rates", "tax_authority", "en"),
    ("LU", "https://impotsdirects.public.lu/", "tax_authority", "fr"),
    ("LV", "https://www.vid.gov.lv/en/tax-rates", "tax_authority", "en"),
    ("ME", "https://www.tax.gov.me/", "tax_authority", "me"),
    ("NL", "https://www.belastingdienst.nl/wps/wcm/connect/en/businesses/content/vat-rates", "tax_authority", "en"),
    ("NL-NH-AMS", "https://www.amsterdam.nl/en/municipal-taxes/tourist-tax/", "government_website", "en"),
    ("NO", "https://www.skatteetaten.no/en/business-and-organisation/vat-and-duties/vat/", "tax_authority", "en"),
    ("PL", "https://www.podatki.gov.pl/vat/", "tax_authority", "pl"),
    ("PT", "https://info.portaldasfinancas.gov.pt/pt/informacao_fiscal/codigos_tributarios/civa/", "tax_authority", "pt"),
    ("PT-11-LIS", "https://www.visitlisboa.com/en/p/tourist-tax", "government_website", "en"),
    ("PT-13-OPO", "https://www.cm-porto.pt/taxaturistica", "government_website", "pt"),
    ("RO", "https://www.anaf.ro/", "tax_authority", "ro"),
    ("RS", "https://www.purs.gov.rs/", "tax_authority", "sr"),
    ("SE", "https://www.skatteverket.se/servicelankar/otherlanguages/inenglish.html", "tax_authority", "en"),
    ("SI", "https://www.fu.gov.si/en/taxes_and_other_duties/", "tax_authority", "en"),
    ("SI-LJ-LJU", "https://www.visitljubljana.com/en/visitors/plan-your-visit/tourist-tax/", "government_website", "en"),
    ("SK", "https://www.financnasprava.sk/en/taxes/", "tax_authority", "en"),
    ("TR", "https://www.gib.gov.tr/", "tax_authority", "tr"),
    ("UA", "https://tax.gov.ua/en/", "tax_authority", "en"),
    ("AD", "https://www.govern.ad/economia/impostos", "tax_authority", "ca"),
    ("AL", "https://www.tatime.gov.al/", "tax_authority", "sq"),
    ("BA", "https://www.uino.gov.ba/", "tax_authority", "bs"),
    ("GE", "https://rs.ge/en", "tax_authority", "en"),
    ("MK", "https://www.ujp.gov.mk/", "tax_authority", "mk"),
    ("MD", "https://www.fisc.md/", "tax_authority", "ro"),
    ("MC", "https://www.gouv.mc/Action-Gouvernementale/Finances-et-Economie", "government_website", "fr"),
    ("SM", "https://www.gov.sm/pub1/SanMarino/portal/", "government_website", "it"),
    ("LI", "https://www.llv.li/de/landesverwaltung/steuerverwaltung", "tax_authority", "de"),

    # ═══════════════════════════════════════════════════════════════
    # AMERICAS
    # ═══════════════════════════════════════════════════════════════
    ("US", "https://www.irs.gov/businesses/small-businesses-self-employed/state-government-websites", "tax_authority", "en"),
    ("US-NY-NYC", "https://www.nyc.gov/site/finance/taxes/business-hotel-room-occupancy-tax.page", "government_website", "en"),
    ("US-FL", "https://floridarevenue.com/taxes/taxesfees/Pages/trans_rent_tax.aspx", "tax_authority", "en"),
    ("US-HI", "https://tax.hawaii.gov/geninfo/get/", "tax_authority", "en"),
    ("US-CA", "https://www.cdtfa.ca.gov/taxes-and-fees/sales-and-use-tax.htm", "tax_authority", "en"),
    ("CA", "https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses.html", "tax_authority", "en"),
    ("MX", "https://www.sat.gob.mx/", "tax_authority", "es"),
    ("BR", "https://www.gov.br/receitafederal/pt-br", "tax_authority", "pt"),
    ("AR", "https://www.afip.gob.ar/", "tax_authority", "es"),
    ("CL", "https://www.sii.cl/", "tax_authority", "es"),
    ("CO", "https://www.dian.gov.co/", "tax_authority", "es"),
    ("PE", "https://www.sunat.gob.pe/", "tax_authority", "es"),
    ("CR", "https://www.hacienda.go.cr/", "tax_authority", "es"),
    ("PA", "https://dgi.mef.gob.pa/", "tax_authority", "es"),
    ("DO", "https://dgii.gov.do/", "tax_authority", "es"),
    ("EC", "https://www.sri.gob.ec/", "tax_authority", "es"),
    ("UY", "https://www.gub.uy/direccion-general-impositiva/", "tax_authority", "es"),
    ("BB", "https://bra.gov.bb/", "tax_authority", "en"),
    ("BS", "https://inlandrevenue.finance.gov.bs/", "tax_authority", "en"),
    ("JM", "https://www.taj.gov.jm/", "tax_authority", "en"),
    ("TT", "https://www.ird.gov.tt/", "tax_authority", "en"),
    ("BZ", "https://www.bts.gov.bz/", "tax_authority", "en"),
    ("PR", "https://hacienda.pr.gov/", "tax_authority", "es"),
    ("AW", "https://www.impuesto.aw/", "tax_authority", "nl"),
    ("CW", "https://www.gobiernu.cw/", "tax_authority", "nl"),
    ("KY", "https://www.gov.ky/taxes", "tax_authority", "en"),
    ("TC", "https://www.gov.tc/revenue/", "tax_authority", "en"),
    ("AG", "https://ird.gov.ag/", "tax_authority", "en"),
    ("LC", "https://irdstlucia.gov.lc/", "tax_authority", "en"),
    ("BM", "https://www.gov.bm/online-services/tax-commissioner", "tax_authority", "en"),
    ("GT", "https://portal.sat.gob.gt/", "tax_authority", "es"),
    ("HN", "https://www.dei.gob.hn/", "tax_authority", "es"),
    ("NI", "https://www.dgi.gob.ni/", "tax_authority", "es"),
    ("SV", "https://www.mh.gob.sv/", "tax_authority", "es"),

    # ═══════════════════════════════════════════════════════════════
    # ASIA-PACIFIC
    # ═══════════════════════════════════════════════════════════════
    ("JP", "https://www.nta.go.jp/english/taxes/consumption_tax.htm", "tax_authority", "en"),
    ("JP-26-KYO", "https://www.city.kyoto.lg.jp/sankan/page/0000236942.html", "government_website", "ja"),
    ("JP-13-TYO", "https://www.tax.metro.tokyo.lg.jp/english/hotel_tax.html", "government_website", "en"),
    ("JP-01", "https://www.pref.hokkaido.lg.jp/kz/kkd/shukuhakuzei.html", "government_website", "ja"),
    ("IN", "https://gstcouncil.gov.in/gst-rates", "tax_authority", "en"),
    ("CN", "https://www.chinatax.gov.cn/eng/", "tax_authority", "en"),
    ("KR", "https://www.nts.go.kr/english/main.do", "tax_authority", "en"),
    ("TH", "https://www.rd.go.th/english/", "tax_authority", "en"),
    ("ID", "https://www.pajak.go.id/en", "tax_authority", "en"),
    ("MY", "https://mysst.customs.gov.my/", "tax_authority", "en"),
    ("SG", "https://www.iras.gov.sg/taxes/goods-services-tax-(gst)", "tax_authority", "en"),
    ("PH", "https://www.bir.gov.ph/", "tax_authority", "en"),
    ("VN", "https://www.gdt.gov.vn/", "tax_authority", "vi"),
    ("KH", "https://www.tax.gov.kh/en/", "tax_authority", "en"),
    ("AU", "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes", "tax_authority", "en"),
    ("NZ", "https://www.ird.govt.nz/gst", "tax_authority", "en"),
    ("MV", "https://www.mira.gov.mv/TaxLegislation.aspx", "tax_authority", "en"),
    ("LK", "https://www.ird.gov.lk/", "tax_authority", "en"),
    ("NP", "https://ird.gov.np/", "tax_authority", "en"),
    ("PK", "https://www.fbr.gov.pk/", "tax_authority", "en"),
    ("BD", "https://nbr.gov.bd/", "tax_authority", "en"),
    ("BT", "https://www.tourism.gov.bt/", "government_website", "en"),
    ("TW", "https://www.mof.gov.tw/Eng/", "tax_authority", "en"),
    ("FJ", "https://www.frcs.org.fj/", "tax_authority", "en"),
    ("KZ", "https://kgd.gov.kz/en", "tax_authority", "en"),
    ("UZ", "https://soliq.uz/en", "tax_authority", "en"),
    ("MN", "https://www.mta.mn/", "tax_authority", "mn"),
    ("PW", "https://www.palaugov.pw/", "government_website", "en"),

    # ═══════════════════════════════════════════════════════════════
    # MIDDLE EAST & GULF
    # ═══════════════════════════════════════════════════════════════
    ("AE", "https://tax.gov.ae/en/", "tax_authority", "en"),
    ("AE-DU", "https://www.dubaitourism.gov.ae/en/tourism-dirham", "regulatory_body", "en"),
    ("AE-AZ", "https://dct.gov.ae/en/", "regulatory_body", "en"),
    ("SA", "https://zatca.gov.sa/en/", "tax_authority", "en"),
    ("QA", "https://www.gta.gov.qa/en/", "tax_authority", "en"),
    ("BH", "https://www.nbr.gov.bh/", "tax_authority", "en"),
    ("OM", "https://tad.taxoman.gov.om/", "tax_authority", "en"),
    ("KW", "https://www.mof.gov.kw/", "government_website", "en"),
    ("JO", "https://www.istd.gov.jo/EN/Pages/default.aspx", "tax_authority", "en"),
    ("IL", "https://taxes.gov.il/English/Pages/default.aspx", "tax_authority", "en"),
    ("LB", "https://www.finance.gov.lb/", "government_website", "en"),

    # ═══════════════════════════════════════════════════════════════
    # AFRICA
    # ═══════════════════════════════════════════════════════════════
    ("EG", "https://www.tax.gov.eg/", "tax_authority", "ar"),
    ("MA", "https://tax.gov.ma/", "tax_authority", "fr"),
    ("TN", "https://www.portail.finances.gov.tn/", "tax_authority", "fr"),
    ("ZA", "https://www.sars.gov.za/", "tax_authority", "en"),
    ("KE", "https://www.kra.go.ke/", "tax_authority", "en"),
    ("TZ", "https://www.tra.go.tz/", "tax_authority", "en"),
    ("NG", "https://www.firs.gov.ng/", "tax_authority", "en"),
    ("GH", "https://gra.gov.gh/", "tax_authority", "en"),
    ("RW", "https://www.rra.gov.rw/", "tax_authority", "en"),
    ("ET", "https://www.mor.gov.et/", "tax_authority", "en"),
    ("UG", "https://www.ura.go.ug/", "tax_authority", "en"),
    ("SC", "https://www.src.gov.sc/", "tax_authority", "en"),
    ("MU", "https://www.mra.mu/", "tax_authority", "en"),
    ("DZ", "https://www.mfdgi.gov.dz/", "tax_authority", "fr"),
    ("SN", "https://www.dgid.sn/", "tax_authority", "fr"),
    ("BW", "https://www.burs.org.bw/", "tax_authority", "en"),
    ("NA", "https://www.namra.org.na/", "tax_authority", "en"),
    ("ZM", "https://www.zra.org.zm/", "tax_authority", "en"),
    ("MZ", "https://www.at.gov.mz/", "tax_authority", "pt"),
    ("CM", "https://www.impots.cm/", "tax_authority", "fr"),
    ("CI", "https://www.dgi.gouv.ci/", "tax_authority", "fr"),
    ("CV", "https://dnre.gov.cv/", "tax_authority", "pt"),
    ("MG", "https://www.impots.mg/", "tax_authority", "fr"),
    ("ZW", "https://www.zimra.co.zw/", "tax_authority", "en"),
]


async def seed(api_base: str, api_key: str):
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    created = skipped = errors = 0
    t0 = time.time()

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        h = (await client.get(f"{api_base}/health")).json()
        print(f"API: {h['status']} | DB: {h['database']}")

        # Get existing source URLs to avoid duplicates
        existing_urls = set()
        resp = await client.get(f"{api_base}/v1/monitoring/sources", params={"limit": "500"})
        for s in resp.json():
            existing_urls.add(s.get("url", ""))

        print(f"Existing sources: {len(existing_urls)}")
        print(f"New sources to add: {len(SOURCES)}\n")

        for jur_code, url, source_type, language in SOURCES:
            if url in existing_urls:
                skipped += 1
                continue

            body = {
                "jurisdiction_code": jur_code,
                "url": url,
                "source_type": source_type,
                "language": language,
                "check_frequency_days": 30,
            }
            r = await client.post(f"{api_base}/v1/monitoring/sources", json=body)
            if r.status_code == 201:
                created += 1
            elif r.status_code == 409:
                skipped += 1
            else:
                errors += 1
                err = r.text[:60]
                print(f"  ! {jur_code}: {r.status_code} - {err}")

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
