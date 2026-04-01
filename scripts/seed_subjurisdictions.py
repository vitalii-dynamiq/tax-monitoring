"""
Seed sub-jurisdictions for all countries in the database.

Inserts states/provinces/cities that levy their own accommodation taxes.
Runs idempotently — skips jurisdictions that already exist (409 Conflict).

Usage:
    python -m scripts.seed_subjurisdictions
    python -m scripts.seed_subjurisdictions --api-url http://localhost:8001
"""

import argparse
import asyncio
import time

import httpx

# ─── Sub-jurisdiction data ──────────────────────────────────────────
# Format: { country_code: [ (code, name, type, timezone, [children]) ] }
# Children are cities: (code, name, timezone)
# Only includes jurisdictions with their OWN accommodation/tourism taxes.

SUBJURISDICTIONS: dict[str, list] = {
    # ── AMERICAS ────────────────────────────────────────────────────
    "CA": [
        ("CA-ON", "Ontario", "province", "America/Toronto", [
            ("CA-ON-TOR", "Toronto", "America/Toronto"),
            ("CA-ON-OTT", "Ottawa", "America/Toronto"),
        ]),
        ("CA-BC", "British Columbia", "province", "America/Vancouver", [
            ("CA-BC-VAN", "Vancouver", "America/Vancouver"),
            ("CA-BC-VIC", "Victoria", "America/Vancouver"),
        ]),
        ("CA-QC", "Quebec", "province", "America/Montreal", [
            ("CA-QC-MTL", "Montreal", "America/Montreal"),
            ("CA-QC-QUE", "Quebec City", "America/Montreal"),
        ]),
        ("CA-AB", "Alberta", "province", "America/Edmonton", [
            ("CA-AB-CGY", "Calgary", "America/Edmonton"),
            ("CA-AB-EDM", "Edmonton", "America/Edmonton"),
        ]),
        ("CA-MB", "Manitoba", "province", "America/Winnipeg", [
            ("CA-MB-WPG", "Winnipeg", "America/Winnipeg"),
        ]),
        ("CA-SK", "Saskatchewan", "province", "America/Regina", []),
        ("CA-NS", "Nova Scotia", "province", "America/Halifax", [
            ("CA-NS-HFX", "Halifax", "America/Halifax"),
        ]),
        ("CA-NB", "New Brunswick", "province", "America/Moncton", []),
        ("CA-PE", "Prince Edward Island", "province", "America/Halifax", []),
        ("CA-NL", "Newfoundland and Labrador", "province", "America/St_Johns", []),
    ],
    "BR": [
        ("BR-SP", "Sao Paulo", "state", "America/Sao_Paulo", [
            ("BR-SP-SAO", "Sao Paulo City", "America/Sao_Paulo"),
        ]),
        ("BR-RJ", "Rio de Janeiro", "state", "America/Sao_Paulo", [
            ("BR-RJ-RIO", "Rio de Janeiro City", "America/Sao_Paulo"),
        ]),
        ("BR-MG", "Minas Gerais", "state", "America/Sao_Paulo", [
            ("BR-MG-BHZ", "Belo Horizonte", "America/Sao_Paulo"),
        ]),
        ("BR-BA", "Bahia", "state", "America/Bahia", [
            ("BR-BA-SSA", "Salvador", "America/Bahia"),
        ]),
        ("BR-PR", "Parana", "state", "America/Sao_Paulo", [
            ("BR-PR-CWB", "Curitiba", "America/Sao_Paulo"),
        ]),
        ("BR-RS", "Rio Grande do Sul", "state", "America/Sao_Paulo", [
            ("BR-RS-POA", "Porto Alegre", "America/Sao_Paulo"),
        ]),
        ("BR-SC", "Santa Catarina", "state", "America/Sao_Paulo", [
            ("BR-SC-FLN", "Florianopolis", "America/Sao_Paulo"),
        ]),
        ("BR-CE", "Ceara", "state", "America/Fortaleza", [
            ("BR-CE-FOR", "Fortaleza", "America/Fortaleza"),
        ]),
        ("BR-PE", "Pernambuco", "state", "America/Recife", [
            ("BR-PE-REC", "Recife", "America/Recife"),
        ]),
        ("BR-DF", "Federal District", "state", "America/Sao_Paulo", [
            ("BR-DF-BSB", "Brasilia", "America/Sao_Paulo"),
        ]),
        ("BR-AM", "Amazonas", "state", "America/Manaus", [
            ("BR-AM-MAO", "Manaus", "America/Manaus"),
        ]),
        ("BR-GO", "Goias", "state", "America/Sao_Paulo", []),
        ("BR-PA", "Para", "state", "America/Belem", []),
    ],
    "AR": [
        ("AR-BA", "Buenos Aires Province", "province", "America/Argentina/Buenos_Aires", [
            ("AR-BA-BUE", "Buenos Aires City", "America/Argentina/Buenos_Aires"),
        ]),
        ("AR-CB", "Cordoba", "province", "America/Argentina/Cordoba", []),
        ("AR-MZ", "Mendoza", "province", "America/Argentina/Mendoza", []),
        ("AR-RN", "Rio Negro", "province", "America/Argentina/Salta", [
            ("AR-RN-BRC", "Bariloche", "America/Argentina/Salta"),
        ]),
        ("AR-NQ", "Neuquen", "province", "America/Argentina/Salta", []),
        ("AR-SF", "Santa Fe", "province", "America/Argentina/Cordoba", []),
    ],
    "CL": [
        ("CL-RM", "Santiago Metropolitan", "region", "America/Santiago", [
            ("CL-RM-SCL", "Santiago", "America/Santiago"),
        ]),
        ("CL-VS", "Valparaiso", "region", "America/Santiago", [
            ("CL-VS-VNA", "Vina del Mar", "America/Santiago"),
        ]),
    ],
    "CO": [
        ("CO-DC", "Bogota Capital District", "state", "America/Bogota", [
            ("CO-DC-BOG", "Bogota", "America/Bogota"),
        ]),
        ("CO-ANT", "Antioquia", "state", "America/Bogota", [
            ("CO-ANT-MDE", "Medellin", "America/Bogota"),
        ]),
        ("CO-BOL", "Bolivar", "state", "America/Bogota", [
            ("CO-BOL-CTG", "Cartagena", "America/Bogota"),
        ]),
    ],
    "PE": [
        ("PE-LIM", "Lima", "region", "America/Lima", [
            ("PE-LIM-LIM", "Lima City", "America/Lima"),
        ]),
        ("PE-CUS", "Cusco", "region", "America/Lima", [
            ("PE-CUS-CUS", "Cusco City", "America/Lima"),
        ]),
    ],
    "EC": [
        ("EC-P", "Pichincha", "province", "America/Guayaquil", [
            ("EC-P-UIO", "Quito", "America/Guayaquil"),
        ]),
        ("EC-G", "Guayas", "province", "America/Guayaquil", [
            ("EC-G-GYE", "Guayaquil", "America/Guayaquil"),
        ]),
    ],
    "DO": [
        ("DO-DN", "Distrito Nacional", "province", "America/Santo_Domingo", [
            ("DO-DN-SDQ", "Santo Domingo", "America/Santo_Domingo"),
        ]),
        ("DO-LA", "La Altagracia", "province", "America/Santo_Domingo", [
            ("DO-LA-PUJ", "Punta Cana", "America/Santo_Domingo"),
        ]),
    ],
    "CR": [
        ("CR-SJ", "San Jose", "province", "America/Costa_Rica", [
            ("CR-SJ-SJO", "San Jose City", "America/Costa_Rica"),
        ]),
    ],
    "PA": [
        ("PA-8", "Panama Province", "province", "America/Panama", [
            ("PA-8-PTY", "Panama City", "America/Panama"),
        ]),
    ],
    "UY": [
        ("UY-MO", "Montevideo", "state", "America/Montevideo", [
            ("UY-MO-MVD", "Montevideo City", "America/Montevideo"),
        ]),
        ("UY-MA", "Maldonado", "state", "America/Montevideo", [
            ("UY-MA-PDE", "Punta del Este", "America/Montevideo"),
        ]),
    ],
    "PR": [
        ("PR-SJ", "San Juan Municipality", "city", "America/Puerto_Rico", []),
    ],

    # ── EUROPE ──────────────────────────────────────────────────────
    "BE": [
        ("BE-BRU", "Brussels-Capital", "region", "Europe/Brussels", [
            ("BE-BRU-BRU", "Brussels", "Europe/Brussels"),
        ]),
        ("BE-VLG", "Flanders", "region", "Europe/Brussels", [
            ("BE-VLG-ANR", "Antwerp", "Europe/Brussels"),
            ("BE-VLG-BRG", "Bruges", "Europe/Brussels"),
            ("BE-VLG-GNT", "Ghent", "Europe/Brussels"),
        ]),
        ("BE-WAL", "Wallonia", "region", "Europe/Brussels", [
            ("BE-WAL-LGE", "Liege", "Europe/Brussels"),
        ]),
    ],
    "CH": [
        ("CH-ZH", "Zurich", "state", "Europe/Zurich", [
            ("CH-ZH-ZRH", "Zurich City", "Europe/Zurich"),
        ]),
        ("CH-BE", "Bern", "state", "Europe/Zurich", [
            ("CH-BE-BRN", "Bern City", "Europe/Zurich"),
            ("CH-BE-INT", "Interlaken", "Europe/Zurich"),
        ]),
        ("CH-LU", "Lucerne", "state", "Europe/Zurich", [
            ("CH-LU-LUZ", "Lucerne City", "Europe/Zurich"),
        ]),
        ("CH-GE", "Geneva", "state", "Europe/Zurich", [
            ("CH-GE-GVA", "Geneva City", "Europe/Zurich"),
        ]),
        ("CH-BS", "Basel-Stadt", "state", "Europe/Zurich", [
            ("CH-BS-BSL", "Basel", "Europe/Zurich"),
        ]),
        ("CH-VD", "Vaud", "state", "Europe/Zurich", [
            ("CH-VD-LSN", "Lausanne", "Europe/Zurich"),
            ("CH-VD-MTX", "Montreux", "Europe/Zurich"),
        ]),
        ("CH-TI", "Ticino", "state", "Europe/Zurich", [
            ("CH-TI-LUG", "Lugano", "Europe/Zurich"),
        ]),
        ("CH-GR", "Graubunden", "state", "Europe/Zurich", [
            ("CH-GR-DVS", "Davos", "Europe/Zurich"),
            ("CH-GR-STM", "St. Moritz", "Europe/Zurich"),
        ]),
        ("CH-VS", "Valais", "state", "Europe/Zurich", [
            ("CH-VS-ZMT", "Zermatt", "Europe/Zurich"),
        ]),
        ("CH-SG", "St. Gallen", "state", "Europe/Zurich", []),
        ("CH-AG", "Aargau", "state", "Europe/Zurich", []),
    ],
    "PL": [
        ("PL-MZ", "Masovia", "state", "Europe/Warsaw", [
            ("PL-MZ-WAW", "Warsaw", "Europe/Warsaw"),
        ]),
        ("PL-MA", "Lesser Poland", "state", "Europe/Warsaw", [
            ("PL-MA-KRK", "Krakow", "Europe/Warsaw"),
        ]),
        ("PL-PM", "Pomerania", "state", "Europe/Warsaw", [
            ("PL-PM-GDN", "Gdansk", "Europe/Warsaw"),
        ]),
        ("PL-DS", "Lower Silesia", "state", "Europe/Warsaw", [
            ("PL-DS-WRO", "Wroclaw", "Europe/Warsaw"),
        ]),
        ("PL-WP", "Greater Poland", "state", "Europe/Warsaw", [
            ("PL-WP-POZ", "Poznan", "Europe/Warsaw"),
        ]),
        ("PL-LU", "Lublin", "state", "Europe/Warsaw", []),
    ],
    "HR": [
        ("HR-21", "Split-Dalmatia", "state", "Europe/Zagreb", [
            ("HR-21-SPU", "Split", "Europe/Zagreb"),
        ]),
        ("HR-18", "Istria", "state", "Europe/Zagreb", [
            ("HR-18-PUY", "Pula", "Europe/Zagreb"),
            ("HR-18-ROV", "Rovinj", "Europe/Zagreb"),
        ]),
        ("HR-20", "Dubrovnik-Neretva", "state", "Europe/Zagreb", [
            ("HR-20-DBV", "Dubrovnik", "Europe/Zagreb"),
        ]),
        ("HR-01", "Zagreb County", "state", "Europe/Zagreb", [
            ("HR-01-ZAG", "Zagreb", "Europe/Zagreb"),
        ]),
        ("HR-08", "Primorje-Gorski Kotar", "state", "Europe/Zagreb", [
            ("HR-08-RJK", "Rijeka", "Europe/Zagreb"),
        ]),
        ("HR-15", "Sibenik-Knin", "state", "Europe/Zagreb", []),
        ("HR-19", "Zadar", "state", "Europe/Zagreb", [
            ("HR-19-ZAD", "Zadar City", "Europe/Zagreb"),
        ]),
    ],
    "RO": [
        ("RO-B", "Bucharest", "state", "Europe/Bucharest", [
            ("RO-B-BUC", "Bucharest City", "Europe/Bucharest"),
        ]),
        ("RO-CJ", "Cluj", "state", "Europe/Bucharest", [
            ("RO-CJ-CLJ", "Cluj-Napoca", "Europe/Bucharest"),
        ]),
        ("RO-CT", "Constanta", "state", "Europe/Bucharest", []),
        ("RO-BV", "Brasov", "state", "Europe/Bucharest", [
            ("RO-BV-BRV", "Brasov City", "Europe/Bucharest"),
        ]),
        ("RO-TM", "Timis", "state", "Europe/Bucharest", [
            ("RO-TM-TSR", "Timisoara", "Europe/Bucharest"),
        ]),
        ("RO-IS", "Iasi", "state", "Europe/Bucharest", []),
        ("RO-SB", "Sibiu", "state", "Europe/Bucharest", [
            ("RO-SB-SBZ", "Sibiu City", "Europe/Bucharest"),
        ]),
    ],
    "BG": [
        ("BG-22", "Sofia City Province", "state", "Europe/Sofia", [
            ("BG-22-SOF", "Sofia", "Europe/Sofia"),
        ]),
        ("BG-02", "Burgas", "state", "Europe/Sofia", []),
        ("BG-03", "Varna", "state", "Europe/Sofia", [
            ("BG-03-VAR", "Varna City", "Europe/Sofia"),
        ]),
        ("BG-04", "Plovdiv", "state", "Europe/Sofia", [
            ("BG-04-PDV", "Plovdiv City", "Europe/Sofia"),
        ]),
    ],
    "RS": [
        ("RS-00", "Belgrade District", "state", "Europe/Belgrade", [
            ("RS-00-BEG", "Belgrade", "Europe/Belgrade"),
        ]),
        ("RS-NS", "South Backa", "state", "Europe/Belgrade", [
            ("RS-NS-NOS", "Novi Sad", "Europe/Belgrade"),
        ]),
    ],
    "SI": [
        ("SI-LJ", "Central Slovenia", "region", "Europe/Ljubljana", [
            ("SI-LJ-LJU", "Ljubljana", "Europe/Ljubljana"),
        ]),
        ("SI-MB", "Drava", "region", "Europe/Ljubljana", [
            ("SI-MB-MBX", "Maribor", "Europe/Ljubljana"),
        ]),
        ("SI-KP", "Coastal-Karst", "region", "Europe/Ljubljana", [
            ("SI-KP-PIR", "Piran", "Europe/Ljubljana"),
        ]),
        ("SI-KR", "Upper Carniola", "region", "Europe/Ljubljana", [
            ("SI-KR-BLD", "Bled", "Europe/Ljubljana"),
        ]),
    ],
    "SK": [
        ("SK-BL", "Bratislava", "region", "Europe/Bratislava", [
            ("SK-BL-BTS", "Bratislava City", "Europe/Bratislava"),
        ]),
        ("SK-KI", "Kosice", "region", "Europe/Bratislava", []),
    ],
    "SE": [
        ("SE-AB", "Stockholm", "state", "Europe/Stockholm", [
            ("SE-AB-STO", "Stockholm City", "Europe/Stockholm"),
        ]),
        ("SE-O", "Vastra Gotaland", "state", "Europe/Stockholm", [
            ("SE-O-GOT", "Gothenburg", "Europe/Stockholm"),
        ]),
        ("SE-M", "Skane", "state", "Europe/Stockholm", [
            ("SE-M-MMA", "Malmo", "Europe/Stockholm"),
        ]),
    ],
    "NO": [
        ("NO-03", "Oslo", "state", "Europe/Oslo", [
            ("NO-03-OSL", "Oslo City", "Europe/Oslo"),
        ]),
        ("NO-46", "Vestland", "state", "Europe/Oslo", [
            ("NO-46-BGO", "Bergen", "Europe/Oslo"),
        ]),
        ("NO-50", "Trondelag", "state", "Europe/Oslo", [
            ("NO-50-TRD", "Trondheim", "Europe/Oslo"),
        ]),
    ],
    "DK": [
        ("DK-84", "Capital Region", "region", "Europe/Copenhagen", [
            ("DK-84-CPH", "Copenhagen", "Europe/Copenhagen"),
        ]),
        ("DK-82", "Central Denmark", "region", "Europe/Copenhagen", [
            ("DK-82-AAR", "Aarhus", "Europe/Copenhagen"),
        ]),
    ],
    "FI": [
        ("FI-18", "Uusimaa", "region", "Europe/Helsinki", [
            ("FI-18-HEL", "Helsinki", "Europe/Helsinki"),
        ]),
        ("FI-06", "Pirkanmaa", "region", "Europe/Helsinki", [
            ("FI-06-TMP", "Tampere", "Europe/Helsinki"),
        ]),
        ("FI-19", "Southwest Finland", "region", "Europe/Helsinki", [
            ("FI-19-TKU", "Turku", "Europe/Helsinki"),
        ]),
        ("FI-11", "Lapland", "region", "Europe/Helsinki", [
            ("FI-11-RVN", "Rovaniemi", "Europe/Helsinki"),
        ]),
    ],
    "IE": [
        ("IE-D", "Dublin", "state", "Europe/Dublin", [
            ("IE-D-DUB", "Dublin City", "Europe/Dublin"),
        ]),
        ("IE-CO", "Cork", "state", "Europe/Dublin", [
            ("IE-CO-ORK", "Cork City", "Europe/Dublin"),
        ]),
        ("IE-G", "Galway", "state", "Europe/Dublin", []),
        ("IE-KY", "Kerry", "state", "Europe/Dublin", []),
    ],
    "EE": [
        ("EE-37", "Harju County", "state", "Europe/Tallinn", [
            ("EE-37-TLL", "Tallinn", "Europe/Tallinn"),
        ]),
        ("EE-79", "Tartu County", "state", "Europe/Tallinn", [
            ("EE-79-TAR", "Tartu", "Europe/Tallinn"),
        ]),
    ],
    "LV": [
        ("LV-RIX", "Riga", "city", "Europe/Riga", []),
    ],
    "LT": [
        ("LT-VL", "Vilnius County", "state", "Europe/Vilnius", [
            ("LT-VL-VNO", "Vilnius", "Europe/Vilnius"),
        ]),
        ("LT-KL", "Klaipeda County", "state", "Europe/Vilnius", []),
    ],
    "ME": [
        ("ME-BD", "Budva", "city", "Europe/Podgorica", []),
        ("ME-KO", "Kotor", "city", "Europe/Podgorica", []),
        ("ME-TIV", "Tivat", "city", "Europe/Podgorica", []),
        ("ME-PG", "Podgorica", "city", "Europe/Podgorica", []),
    ],
    "AL": [
        ("AL-TR", "Tirana District", "state", "Europe/Tirane", [
            ("AL-TR-TIA", "Tirana", "Europe/Tirane"),
        ]),
        ("AL-SR", "Saranda District", "state", "Europe/Tirane", []),
    ],
    "MK": [
        ("MK-SK", "Skopje Region", "state", "Europe/Skopje", [
            ("MK-SK-SKP", "Skopje", "Europe/Skopje"),
        ]),
        ("MK-OH", "Ohrid", "city", "Europe/Skopje", []),
    ],
    "BA": [
        ("BA-SRP", "Republika Srpska", "state", "Europe/Sarajevo", []),
        ("BA-BIH", "Federation of BiH", "state", "Europe/Sarajevo", [
            ("BA-BIH-SJJ", "Sarajevo", "Europe/Sarajevo"),
        ]),
    ],
    "GE": [
        ("GE-TB", "Tbilisi", "city", "Asia/Tbilisi", []),
        ("GE-AJ", "Adjara", "state", "Asia/Tbilisi", [
            ("GE-AJ-BUS", "Batumi", "Asia/Tbilisi"),
        ]),
    ],
    "UA": [
        ("UA-30", "Kyiv City", "city", "Europe/Kyiv", []),
        ("UA-46", "Lviv Oblast", "state", "Europe/Kyiv", [
            ("UA-46-LWO", "Lviv", "Europe/Kyiv"),
        ]),
        ("UA-51", "Odesa Oblast", "state", "Europe/Kyiv", [
            ("UA-51-ODS", "Odesa", "Europe/Kyiv"),
        ]),
    ],
    "TR": [
        ("TR-34", "Istanbul", "state", "Europe/Istanbul", [
            ("TR-34-IST", "Istanbul City", "Europe/Istanbul"),
        ]),
        ("TR-06", "Ankara", "state", "Europe/Istanbul", [
            ("TR-06-ANK", "Ankara City", "Europe/Istanbul"),
        ]),
        ("TR-07", "Antalya", "state", "Europe/Istanbul", [
            ("TR-07-AYT", "Antalya City", "Europe/Istanbul"),
        ]),
        ("TR-35", "Izmir", "state", "Europe/Istanbul", [
            ("TR-35-IZM", "Izmir City", "Europe/Istanbul"),
        ]),
        ("TR-48", "Mugla", "state", "Europe/Istanbul", [
            ("TR-48-BJV", "Bodrum", "Europe/Istanbul"),
        ]),
    ],
    "IS": [
        ("IS-1", "Capital Region", "region", "Atlantic/Reykjavik", [
            ("IS-1-REK", "Reykjavik", "Atlantic/Reykjavik"),
        ]),
    ],
    "MD": [
        ("MD-CU", "Chisinau", "city", "Europe/Chisinau", []),
    ],

    # ── ASIA ────────────────────────────────────────────────────────
    "IN": [
        ("IN-MH", "Maharashtra", "state", "Asia/Kolkata", [
            ("IN-MH-BOM", "Mumbai", "Asia/Kolkata"),
        ]),
        ("IN-DL", "Delhi", "state", "Asia/Kolkata", [
            ("IN-DL-DEL", "New Delhi", "Asia/Kolkata"),
        ]),
        ("IN-KA", "Karnataka", "state", "Asia/Kolkata", [
            ("IN-KA-BLR", "Bangalore", "Asia/Kolkata"),
        ]),
        ("IN-TN", "Tamil Nadu", "state", "Asia/Kolkata", [
            ("IN-TN-MAA", "Chennai", "Asia/Kolkata"),
        ]),
        ("IN-RJ", "Rajasthan", "state", "Asia/Kolkata", [
            ("IN-RJ-JAI", "Jaipur", "Asia/Kolkata"),
            ("IN-RJ-UDR", "Udaipur", "Asia/Kolkata"),
        ]),
        ("IN-GA", "Goa", "state", "Asia/Kolkata", []),
        ("IN-KL", "Kerala", "state", "Asia/Kolkata", [
            ("IN-KL-COK", "Kochi", "Asia/Kolkata"),
        ]),
        ("IN-WB", "West Bengal", "state", "Asia/Kolkata", [
            ("IN-WB-CCU", "Kolkata", "Asia/Kolkata"),
        ]),
        ("IN-TG", "Telangana", "state", "Asia/Kolkata", [
            ("IN-TG-HYD", "Hyderabad", "Asia/Kolkata"),
        ]),
        ("IN-GJ", "Gujarat", "state", "Asia/Kolkata", [
            ("IN-GJ-AMD", "Ahmedabad", "Asia/Kolkata"),
        ]),
        ("IN-UP", "Uttar Pradesh", "state", "Asia/Kolkata", [
            ("IN-UP-AGR", "Agra", "Asia/Kolkata"),
        ]),
        ("IN-HP", "Himachal Pradesh", "state", "Asia/Kolkata", []),
    ],
    "CN": [
        ("CN-11", "Beijing", "state", "Asia/Shanghai", [
            ("CN-11-PEK", "Beijing City", "Asia/Shanghai"),
        ]),
        ("CN-31", "Shanghai", "state", "Asia/Shanghai", [
            ("CN-31-SHA", "Shanghai City", "Asia/Shanghai"),
        ]),
        ("CN-44", "Guangdong", "state", "Asia/Shanghai", [
            ("CN-44-CAN", "Guangzhou", "Asia/Shanghai"),
            ("CN-44-SZX", "Shenzhen", "Asia/Shanghai"),
        ]),
        ("CN-51", "Sichuan", "state", "Asia/Shanghai", [
            ("CN-51-CTU", "Chengdu", "Asia/Shanghai"),
        ]),
        ("CN-33", "Zhejiang", "state", "Asia/Shanghai", [
            ("CN-33-HGH", "Hangzhou", "Asia/Shanghai"),
        ]),
        ("CN-53", "Yunnan", "state", "Asia/Shanghai", [
            ("CN-53-KMG", "Kunming", "Asia/Shanghai"),
        ]),
        ("CN-46", "Hainan", "state", "Asia/Shanghai", [
            ("CN-46-SYX", "Sanya", "Asia/Shanghai"),
        ]),
        ("CN-50", "Chongqing", "state", "Asia/Shanghai", []),
        ("CN-32", "Jiangsu", "state", "Asia/Shanghai", [
            ("CN-32-NKG", "Nanjing", "Asia/Shanghai"),
        ]),
    ],
    "KR": [
        ("KR-11", "Seoul", "state", "Asia/Seoul", [
            ("KR-11-SEL", "Seoul City", "Asia/Seoul"),
        ]),
        ("KR-26", "Busan", "state", "Asia/Seoul", [
            ("KR-26-PUS", "Busan City", "Asia/Seoul"),
        ]),
        ("KR-49", "Jeju", "state", "Asia/Seoul", [
            ("KR-49-CJU", "Jeju City", "Asia/Seoul"),
        ]),
    ],
    "TW": [
        ("TW-TPE", "Taipei City", "city", "Asia/Taipei", []),
        ("TW-KHH", "Kaohsiung", "city", "Asia/Taipei", []),
    ],
    "MY": [
        ("MY-14", "Kuala Lumpur", "state", "Asia/Kuala_Lumpur", [
            ("MY-14-KUL", "KL City", "Asia/Kuala_Lumpur"),
        ]),
        ("MY-12", "Sabah", "state", "Asia/Kuala_Lumpur", []),
        ("MY-15", "Labuan", "state", "Asia/Kuala_Lumpur", []),
        ("MY-01", "Johor", "state", "Asia/Kuala_Lumpur", []),
        ("MY-10", "Selangor", "state", "Asia/Kuala_Lumpur", []),
        ("MY-07", "Penang", "state", "Asia/Kuala_Lumpur", [
            ("MY-07-PEN", "George Town", "Asia/Kuala_Lumpur"),
        ]),
        ("MY-11", "Sarawak", "state", "Asia/Kuala_Lumpur", []),
    ],
    "VN": [
        ("VN-SG", "Ho Chi Minh City", "city", "Asia/Ho_Chi_Minh", []),
        ("VN-HN", "Hanoi", "city", "Asia/Ho_Chi_Minh", []),
        ("VN-DN", "Da Nang", "city", "Asia/Ho_Chi_Minh", []),
        ("VN-HP", "Hai Phong", "city", "Asia/Ho_Chi_Minh", []),
        ("VN-KH", "Khanh Hoa", "state", "Asia/Ho_Chi_Minh", [
            ("VN-KH-NHA", "Nha Trang", "Asia/Ho_Chi_Minh"),
        ]),
    ],
    "PH": [
        ("PH-NCR", "Metro Manila", "region", "Asia/Manila", [
            ("PH-NCR-MNL", "Manila", "Asia/Manila"),
            ("PH-NCR-MKT", "Makati", "Asia/Manila"),
        ]),
        ("PH-07", "Central Visayas", "region", "Asia/Manila", [
            ("PH-07-CEB", "Cebu City", "Asia/Manila"),
        ]),
        ("PH-ARMM", "Palawan", "region", "Asia/Manila", []),
    ],
    "KH": [
        ("KH-12", "Phnom Penh", "city", "Asia/Phnom_Penh", []),
        ("KH-17", "Siem Reap", "state", "Asia/Phnom_Penh", [
            ("KH-17-REP", "Siem Reap City", "Asia/Phnom_Penh"),
        ]),
    ],
    "LK": [
        ("LK-1", "Western Province", "province", "Asia/Colombo", [
            ("LK-1-CMB", "Colombo", "Asia/Colombo"),
        ]),
    ],
    "NP": [
        ("NP-BA", "Bagmati Province", "province", "Asia/Kathmandu", [
            ("NP-BA-KTM", "Kathmandu", "Asia/Kathmandu"),
        ]),
    ],
    "PK": [
        ("PK-PB", "Punjab", "province", "Asia/Karachi", [
            ("PK-PB-LHE", "Lahore", "Asia/Karachi"),
        ]),
        ("PK-SD", "Sindh", "province", "Asia/Karachi", [
            ("PK-SD-KHI", "Karachi", "Asia/Karachi"),
        ]),
        ("PK-IS", "Islamabad Capital", "city", "Asia/Karachi", []),
    ],
    "BD": [
        ("BD-13", "Dhaka Division", "state", "Asia/Dhaka", [
            ("BD-13-DAC", "Dhaka City", "Asia/Dhaka"),
        ]),
        ("BD-10", "Chittagong Division", "state", "Asia/Dhaka", []),
    ],
    "SA": [
        ("SA-01", "Riyadh Province", "state", "Asia/Riyadh", [
            ("SA-01-RUH", "Riyadh City", "Asia/Riyadh"),
        ]),
        ("SA-02", "Makkah Province", "state", "Asia/Riyadh", [
            ("SA-02-JED", "Jeddah", "Asia/Riyadh"),
            ("SA-02-MKK", "Makkah", "Asia/Riyadh"),
        ]),
        ("SA-04", "Eastern Province", "state", "Asia/Riyadh", [
            ("SA-04-DMM", "Dammam", "Asia/Riyadh"),
        ]),
        ("SA-03", "Madinah Province", "state", "Asia/Riyadh", [
            ("SA-03-MED", "Madinah", "Asia/Riyadh"),
        ]),
        ("SA-06", "Tabuk Province", "state", "Asia/Riyadh", [
            ("SA-06-NOM", "NEOM", "Asia/Riyadh"),
        ]),
    ],
    "QA": [
        ("QA-DA", "Doha", "city", "Asia/Qatar", []),
    ],
    "KW": [
        ("KW-KU", "Kuwait City", "city", "Asia/Kuwait", []),
    ],
    "BH": [
        ("BH-13", "Capital Governorate", "state", "Asia/Bahrain", [
            ("BH-13-BAH", "Manama", "Asia/Bahrain"),
        ]),
    ],
    "OM": [
        ("OM-MA", "Muscat Governorate", "state", "Asia/Muscat", [
            ("OM-MA-MCT", "Muscat City", "Asia/Muscat"),
        ]),
    ],
    "JO": [
        ("JO-AM", "Amman Governorate", "state", "Asia/Amman", [
            ("JO-AM-AMM", "Amman", "Asia/Amman"),
        ]),
        ("JO-AQ", "Aqaba", "state", "Asia/Amman", []),
        ("JO-MA", "Madaba", "state", "Asia/Amman", []),
    ],
    "IL": [
        ("IL-TA", "Tel Aviv District", "state", "Asia/Jerusalem", [
            ("IL-TA-TLV", "Tel Aviv", "Asia/Jerusalem"),
        ]),
        ("IL-JM", "Jerusalem District", "state", "Asia/Jerusalem", [
            ("IL-JM-JRS", "Jerusalem", "Asia/Jerusalem"),
        ]),
        ("IL-HA", "Haifa District", "state", "Asia/Jerusalem", []),
        ("IL-Z", "Northern District", "state", "Asia/Jerusalem", [
            ("IL-Z-TBS", "Tiberias", "Asia/Jerusalem"),
        ]),
        ("IL-D", "Southern District", "state", "Asia/Jerusalem", [
            ("IL-D-ELT", "Eilat", "Asia/Jerusalem"),
        ]),
    ],
    "LB": [
        ("LB-BA", "Beirut", "city", "Asia/Beirut", []),
    ],

    # ── AFRICA ──────────────────────────────────────────────────────
    "ZA": [
        ("ZA-GT", "Gauteng", "province", "Africa/Johannesburg", [
            ("ZA-GT-JNB", "Johannesburg", "Africa/Johannesburg"),
        ]),
        ("ZA-WC", "Western Cape", "province", "Africa/Johannesburg", [
            ("ZA-WC-CPT", "Cape Town", "Africa/Johannesburg"),
        ]),
        ("ZA-KZN", "KwaZulu-Natal", "province", "Africa/Johannesburg", [
            ("ZA-KZN-DUR", "Durban", "Africa/Johannesburg"),
        ]),
    ],
    "EG": [
        ("EG-C", "Cairo Governorate", "state", "Africa/Cairo", [
            ("EG-C-CAI", "Cairo City", "Africa/Cairo"),
        ]),
        ("EG-BA", "Red Sea Governorate", "state", "Africa/Cairo", [
            ("EG-BA-HRG", "Hurghada", "Africa/Cairo"),
        ]),
        ("EG-JS", "South Sinai", "state", "Africa/Cairo", [
            ("EG-JS-SSH", "Sharm el-Sheikh", "Africa/Cairo"),
        ]),
        ("EG-LX", "Luxor", "state", "Africa/Cairo", []),
        ("EG-ALX", "Alexandria", "state", "Africa/Cairo", []),
    ],
    "MA": [
        ("MA-CAS", "Casablanca-Settat", "region", "Africa/Casablanca", [
            ("MA-CAS-CMN", "Casablanca", "Africa/Casablanca"),
        ]),
        ("MA-RAB", "Rabat-Sale-Kenitra", "region", "Africa/Casablanca", [
            ("MA-RAB-RBA", "Rabat", "Africa/Casablanca"),
        ]),
        ("MA-MAR", "Marrakech-Safi", "region", "Africa/Casablanca", [
            ("MA-MAR-RAK", "Marrakech", "Africa/Casablanca"),
        ]),
        ("MA-FES", "Fes-Meknes", "region", "Africa/Casablanca", [
            ("MA-FES-FEZ", "Fez", "Africa/Casablanca"),
        ]),
        ("MA-TNG", "Tanger-Tetouan-Al Hoceima", "region", "Africa/Casablanca", [
            ("MA-TNG-TNG", "Tangier", "Africa/Casablanca"),
        ]),
        ("MA-AGD", "Souss-Massa", "region", "Africa/Casablanca", [
            ("MA-AGD-AGA", "Agadir", "Africa/Casablanca"),
        ]),
    ],
    "KE": [
        ("KE-110", "Nairobi County", "state", "Africa/Nairobi", [
            ("KE-110-NBO", "Nairobi City", "Africa/Nairobi"),
        ]),
        ("KE-001", "Mombasa County", "state", "Africa/Nairobi", [
            ("KE-001-MBA", "Mombasa City", "Africa/Nairobi"),
        ]),
    ],
    "TZ": [
        ("TZ-02", "Dar es Salaam", "state", "Africa/Dar_es_Salaam", [
            ("TZ-02-DAR", "Dar es Salaam City", "Africa/Dar_es_Salaam"),
        ]),
        ("TZ-25", "Zanzibar", "state", "Africa/Dar_es_Salaam", [
            ("TZ-25-ZNZ", "Zanzibar City", "Africa/Dar_es_Salaam"),
        ]),
    ],
    "RW": [
        ("RW-01", "Kigali", "city", "Africa/Kigali", []),
    ],
    "GH": [
        ("GH-AA", "Greater Accra", "state", "Africa/Accra", [
            ("GH-AA-ACC", "Accra", "Africa/Accra"),
        ]),
    ],
    "NG": [
        ("NG-LA", "Lagos State", "state", "Africa/Lagos", [
            ("NG-LA-LOS", "Lagos City", "Africa/Lagos"),
        ]),
        ("NG-FC", "Federal Capital Territory", "state", "Africa/Lagos", [
            ("NG-FC-ABV", "Abuja", "Africa/Lagos"),
        ]),
    ],
    "TN": [
        ("TN-11", "Tunis Governorate", "state", "Africa/Tunis", [
            ("TN-11-TUN", "Tunis City", "Africa/Tunis"),
        ]),
        ("TN-51", "Sousse Governorate", "state", "Africa/Tunis", []),
        ("TN-31", "Nabeul Governorate", "state", "Africa/Tunis", [
            ("TN-31-HAM", "Hammamet", "Africa/Tunis"),
        ]),
    ],
    "ET": [
        ("ET-AA", "Addis Ababa", "city", "Africa/Addis_Ababa", []),
    ],

    # ── OCEANIA ─────────────────────────────────────────────────────
    "NZ": [
        ("NZ-AUK", "Auckland Region", "region", "Pacific/Auckland", [
            ("NZ-AUK-AKL", "Auckland", "Pacific/Auckland"),
        ]),
        ("NZ-WGN", "Wellington Region", "region", "Pacific/Auckland", [
            ("NZ-WGN-WLG", "Wellington", "Pacific/Auckland"),
        ]),
        ("NZ-CAN", "Canterbury", "region", "Pacific/Auckland", [
            ("NZ-CAN-CHC", "Christchurch", "Pacific/Auckland"),
        ]),
        ("NZ-OTA", "Otago", "region", "Pacific/Auckland", [
            ("NZ-OTA-ZQN", "Queenstown", "Pacific/Auckland"),
        ]),
    ],
}


# ─── Runner ─────────────────────────────────────────────────────────


async def seed(api_base: str, api_key: str):
    headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    created = skipped = errors = 0
    t0 = time.time()

    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        # Verify API
        h = (await client.get(f"{api_base}/health")).json()
        print(f"API: {h['status']} | DB: {h['database']}")

        total_countries = len(SUBJURISDICTIONS)
        for ci, (country_code, states) in enumerate(sorted(SUBJURISDICTIONS.items())):
            print(f"\n[{ci+1}/{total_countries}] {country_code}: {len(states)} states/regions")

            for state_code, state_name, state_type, state_tz, cities in states:
                # Create state/province/region
                body = {
                    "code": state_code,
                    "name": state_name,
                    "jurisdiction_type": state_type,
                    "country_code": country_code,
                    "currency_code": _get_currency(country_code),
                    "parent_code": country_code,
                    "timezone": state_tz,
                }
                r = await client.post(f"{api_base}/v1/jurisdictions", json=body)
                if r.status_code == 201:
                    created += 1
                    print(f"  + {state_code} ({state_name})")
                elif r.status_code == 409:
                    skipped += 1
                else:
                    errors += 1
                    print(f"  ! {state_code}: {r.status_code} - {r.text[:80]}")

                # Create cities under this state
                for city_code, city_name, city_tz in cities:
                    body = {
                        "code": city_code,
                        "name": city_name,
                        "jurisdiction_type": "city",
                        "country_code": country_code,
                        "currency_code": _get_currency(country_code),
                        "parent_code": state_code,
                        "timezone": city_tz,
                    }
                    r = await client.post(f"{api_base}/v1/jurisdictions", json=body)
                    if r.status_code == 201:
                        created += 1
                        print(f"    + {city_code} ({city_name})")
                    elif r.status_code == 409:
                        skipped += 1
                    else:
                        errors += 1
                        print(f"    ! {city_code}: {r.status_code} - {r.text[:80]}")

    elapsed = int(time.time() - t0)
    print(f"\n{'='*60}")
    print(f"DONE in {elapsed}s | Created: {created} | Skipped: {skipped} | Errors: {errors}")
    print(f"{'='*60}")


# Currency lookup (matches existing DB data)
_CURRENCIES = {
    "CA": "CAD", "BR": "BRL", "AR": "ARS", "CL": "CLP", "CO": "COP", "PE": "PEN",
    "EC": "USD", "DO": "DOP", "CR": "CRC", "PA": "PAB", "UY": "UYU", "PR": "USD",
    "BE": "EUR", "CH": "CHF", "PL": "PLN", "HR": "EUR", "RO": "RON", "BG": "BGN",
    "RS": "RSD", "SI": "EUR", "SK": "EUR", "SE": "SEK", "NO": "NOK", "DK": "DKK",
    "FI": "EUR", "IE": "EUR", "EE": "EUR", "LV": "EUR", "LT": "EUR", "ME": "EUR",
    "AL": "ALL", "MK": "MKD", "BA": "BAM", "GE": "GEL", "UA": "UAH", "TR": "TRY",
    "IS": "ISK", "MD": "MDL",
    "IN": "INR", "CN": "CNY", "KR": "KRW", "TW": "TWD", "MY": "MYR", "VN": "VND",
    "PH": "PHP", "KH": "KHR", "LK": "LKR", "NP": "NPR", "PK": "PKR", "BD": "BDT",
    "SA": "SAR", "QA": "QAR", "KW": "KWD", "BH": "BHD", "OM": "OMR", "JO": "JOD",
    "IL": "ILS", "LB": "LBP",
    "ZA": "ZAR", "EG": "EGP", "MA": "MAD", "KE": "KES", "TZ": "TZS", "RW": "RWF",
    "GH": "GHS", "NG": "NGN", "TN": "TND", "ET": "ETB",
    "NZ": "NZD",
}


def _get_currency(country_code: str) -> str:
    return _CURRENCIES.get(country_code, "USD")


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--api-url", default="http://localhost:8001")
    p.add_argument("--api-key", default="dev-api-key-change-me")
    args = p.parse_args()
    asyncio.run(seed(args.api_url, args.api_key))


if __name__ == "__main__":
    main()
