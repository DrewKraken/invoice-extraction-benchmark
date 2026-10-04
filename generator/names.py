"""
Invented parties, places and goods for the benchmark corpus.

Every company and person name is assembled from neutral word lists, so no
document describes a real business; any resemblance to a real company name
is a coincidence of common words. Towns are real place names, because a
reader may use them to tell currencies and date formats apart; street
numbers, phone numbers, tax numbers and bank codes are generated and
fictional. Phone numbers use the 555 / 0xx test ranges where a country has
one.
"""

from __future__ import annotations

import random
import re
from typing import Dict, List, Optional, Tuple

from .spec import Party

# ---------------------------------------------------------------------------
# Countries: towns, postcode shapes, phone prefixes, tax labels, currencies
# ---------------------------------------------------------------------------

COUNTRIES: Dict[str, Dict] = {
    "US": {
        "towns": [("Columbus", "OH", "432"), ("Dallas", "TX", "752"), ("Denver", "CO", "802"),
                  ("Memphis", "TN", "381"), ("Reno", "NV", "895"), ("Savannah", "GA", "314"),
                  ("Spokane", "WA", "992"), ("Omaha", "NE", "681")],
        "phone": "({a}) 555-0{b:03d}", "tld": ".com", "tax_label": "EIN", "currency": "USD",
        "streets": ["Commerce Parkway", "Industrial Drive", "Harbor Boulevard", "Elm Street",
                    "Freight Road", "Market Street", "Riverside Avenue", "Depot Lane"],
    },
    "ZA": {
        "towns": [("Johannesburg", "Gauteng", "2001"), ("Durban", "KwaZulu-Natal", "4001"),
                  ("Cape Town", "Western Cape", "8001"), ("Gqeberha", "Eastern Cape", "6001"),
                  ("Pretoria", "Gauteng", "0002"), ("Upington", "Northern Cape", "8801")],
        "phone": "+27 {a} 555 {b:04d}", "tld": ".co.za", "tax_label": "VAT No", "currency": "ZAR",
        "streets": ["Voortrekker Road", "Main Reef Road", "Church Street", "Bree Street",
                    "Kerk Street", "Market Road", "Rivonia Road", "Strand Street"],
    },
    "NA": {
        "towns": [("Windhoek", "Khomas", "9000"), ("Walvis Bay", "Erongo", "9000"),
                  ("Swakopmund", "Erongo", "9000"), ("Keetmanshoop", "Karas", "9000"),
                  ("Otjiwarongo", "Otjozondjupa", "9000"), ("Tsumeb", "Oshikoto", "9000"),
                  ("Oshakati", "Oshana", "9000"), ("Rundu", "Kavango East", "9000")],
        "phone": "+264 {a} 555 {b:04d}", "tld": ".com.na", "tax_label": "VAT Reg No", "currency": "NAD",
        "streets": ["Independence Avenue", "Sam Nujoma Drive", "Hage Geingob Street",
                    "Mandume Ndemufayo Avenue", "Rand Street", "Nickel Street", "Theo-Ben Gurirab Street"],
    },
    "ZM": {
        "towns": [("Lusaka", "Lusaka Province", "10101"), ("Ndola", "Copperbelt", "10101"),
                  ("Kitwe", "Copperbelt", "10101"), ("Livingstone", "Southern Province", "10101")],
        "phone": "+260 {a} 555 {b:03d}", "tld": ".co.zm", "tax_label": "TPIN", "currency": "ZMW",
        "streets": ["Cairo Road", "Great East Road", "Kafue Road", "Independence Avenue", "Obote Avenue"],
    },
    "GB": {
        "towns": [("Leeds", "", "LS1 4"), ("Bristol", "", "BS1 6"), ("Felixstowe", "", "IP11 3"),
                  ("Manchester", "", "M1 2"), ("Southampton", "", "SO14 3"), ("Derby", "", "DE1 2")],
        "phone": "+44 {a} 496 0{b:03d}", "tld": ".co.uk", "tax_label": "VAT Reg No", "currency": "GBP",
        "streets": ["Wharf Road", "Station Approach", "Mill Lane", "Dock Street", "Victoria Road", "Canal Side"],
    },
    "DE": {
        "towns": [("Hamburg", "", "20457"), ("Bremen", "", "28195"), ("Duisburg", "", "47051"),
                  ("Hannover", "", "30159")],
        "phone": "+49 {a} 555 {b:04d}", "tld": ".de", "tax_label": "USt-IdNr", "currency": "EUR",
        "streets": ["Hafenstrasse", "Industriestrasse", "Lindenweg", "Am Kai", "Speicherstrasse"],
    },
    "NL": {
        "towns": [("Rotterdam", "", "3011"), ("Venlo", "", "5911"), ("Tilburg", "", "5038")],
        "phone": "+31 {a} 555 {b:04d}", "tld": ".nl", "tax_label": "BTW-nr", "currency": "EUR",
        "streets": ["Havenweg", "Kade", "Industrieweg", "Stationsplein"],
    },
    "FR": {
        "towns": [("Lyon", "", "69002"), ("Marseille", "", "13002"), ("Le Havre", "", "76600")],
        "phone": "+33 {a} 55 {b:04d}", "tld": ".fr", "tax_label": "TVA", "currency": "EUR",
        "streets": ["Rue du Port", "Avenue de la Gare", "Quai des Docks", "Rue de l'Industrie"],
    },
}

CURRENCY_COUNTRY = {"USD": "US", "ZAR": "ZA", "NAD": "NA", "ZMW": "ZM", "GBP": "GB", "EUR": "DE"}

# ---------------------------------------------------------------------------
# Company names
# ---------------------------------------------------------------------------

_PLACE_WORDS = {
    "US": ["Prairie", "Redwood", "Granite", "Bluewater", "Ironbridge", "Cedar Point", "Lakeshore", "Summit"],
    "ZA": ["Highveld", "Karoo", "Drakensig", "Blouberg", "Vaalrand", "Klipspruit", "Suidkus", "Kransberg"],
    "NA": ["Kalahari", "Erongo", "Namib Sands", "Kunene", "Okavango", "Brandkop", "Skeleton Bay", "Etosha Gate"],
    "ZM": ["Kafue", "Luangwa", "Copperline", "Zambezi Reach", "Mukuba", "Chisamba"],
    "GB": ["Pennine", "Severn", "Harrowgate", "Mersey", "Wolds", "Fenland", "Thamesmead"],
    "DE": ["Elbtal", "Nordhafen", "Weserland", "Rheinkai", "Ostwall"],
    "NL": ["Maaskant", "Polder", "Rijnpoort", "Waalhaven"],
    "FR": ["Rhodanie", "Port-Vieux", "Seine Aval", "Calanque"],
}
_TRADE_WORDS = {
    "freight": ["Freight", "Haulage", "Line Haul", "Transport", "Logistics", "Trucking", "Carriers", "Cargo"],
    "clearing": ["Clearing & Forwarding", "Customs Brokers", "Forwarding", "Shipping Agencies", "Border Services"],
    # Draws only for the 10 withheld documents (corpus_v1._skip_withheld);
    # the names are discarded. Five entries, as in the original list.
    "withheld": ["Reserved A", "Reserved B", "Reserved C", "Reserved D", "Reserved E"],
    "supply": ["Industrial Supply", "Hardware", "Office Supplies", "Engineering Supplies", "Tyre & Parts",
               "Workshop Supplies", "Packaging"],
    "services": ["IT Services", "Consulting", "Security Services", "Cleaning Services", "Catering",
                 "Telecoms", "Maintenance"],
}
_SUFFIX = {
    "US": ["LLC", "Inc", "Co", "Corp"], "ZA": ["(Pty) Ltd", "CC", "(Pty) Ltd"],
    "NA": ["(Pty) Ltd", "CC", "(Pty) Ltd"], "ZM": ["Limited", "Ltd"], "GB": ["Ltd", "Limited", "plc"],
    "DE": ["GmbH", "GmbH & Co. KG"], "NL": ["B.V."], "FR": ["SARL", "SAS"],
}
_FIRST = ["Ana", "Ben", "Chipo", "Dawid", "Eli", "Femi", "Grace", "Hendrik", "Ines", "Jabu", "Kofi",
          "Lina", "Moses", "Nadia", "Otto", "Petra", "Rui", "Sipho", "Tomas", "Ulla", "Vusi", "Wim"]
_LAST = ["Amupolo", "Becker", "Coetzer", "Dlamini", "Ekandjo", "Fourie", "Garises", "Haufiku",
         "Iyambo", "Jansen", "Kandjii", "Louw", "Mwale", "Nel", "Oosthuizen", "Phiri", "Shilongo",
         "Tjiueza", "Uushona", "Visser", "Zulu"]


def person(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST)} {rng.choice(_LAST)}"


def company_name(rng: random.Random, country: str, trade: str, used: Optional[set] = None) -> str:
    for _ in range(50):
        name = f"{rng.choice(_PLACE_WORDS[country])} {rng.choice(_TRADE_WORDS[trade])} {rng.choice(_SUFFIX[country])}"
        if used is None or name not in used:
            if used is not None:
                used.add(name)
            return name
    raise RuntimeError("ran out of unique company names")


def _slug(name: str) -> str:
    core = re.sub(r"\((pty)\)|\b(ltd|llc|inc|co|corp|cc|limited|plc|gmbh|kg|b\.v\.|sarl|sas)\b", "", name, flags=re.I)
    return re.sub(r"[^a-z0-9]+", "", core.lower())[:18] or "vendor"


def address(rng: random.Random, country: str) -> Tuple[Tuple[str, ...], str]:
    c = COUNTRIES[country]
    town, region, post = rng.choice(c["towns"])
    street = f"{rng.randint(2, 980)} {rng.choice(c['streets'])}"
    if country == "US":
        return (street, f"{town}, {region} {post}{rng.randint(10, 99)}"), town
    if country == "GB":
        return (street, town, f"{post}{rng.choice('ABDEFGHJLNPQRSTUWXYZ')}{rng.choice('ABDEFGHJLNPQRSTUWXYZ')}"), town
    if country in ("DE", "NL", "FR"):
        return (street, f"{post} {town}"), town
    if country == "NA":
        po = f"P.O. Box {rng.randint(100, 9999)}"
        return ((street, town) if rng.random() < 0.6 else (street, po, town)), town
    return (street, f"{town}, {post}" if region else town), town


def phone(rng: random.Random, country: str) -> str:
    return COUNTRIES[country]["phone"].format(a=rng.randint(11, 99), b=rng.randint(0, 999))


def tax_id(rng: random.Random, country: str) -> str:
    if country == "US":
        return f"{rng.randint(10, 99)}-{rng.randint(1000000, 9999999)}"
    if country in ("ZA", "NA"):
        return f"4{rng.randint(100000000, 999999999)}"[:10]
    if country == "ZM":
        return f"10{rng.randint(10000000, 99999999)}"
    if country == "GB":
        return f"GB {rng.randint(100, 999)} {rng.randint(1000, 9999)} {rng.randint(10, 99)}"
    return f"{country}{rng.randint(100000000, 999999999)}"


def bic(rng: random.Random, country: str) -> str:
    letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
    return "".join(rng.choice(letters) for _ in range(4)) + country + rng.choice(["NX", "JJ", "2X", "XX"])


def _iban(rng: random.Random, country: str) -> str:
    bban = "".join(str(rng.randint(0, 9)) for _ in range(18))
    numeric = "".join(str(int(ch, 36)) for ch in bban + country + "00")
    check = 98 - int(numeric) % 97
    raw = f"{country}{check:02d}{bban}"
    return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))


def bank_lines(rng: random.Random, country: str) -> Tuple[str, ...]:
    bank = f"{rng.choice(_PLACE_WORDS[country])} Commercial Bank"
    if country in ("DE", "NL", "FR"):
        return (f"Bank: {bank}", f"IBAN: {_iban(rng, country)}", f"BIC: {bic(rng, country)}")
    if country == "GB":
        return (f"Bank: {bank}", f"Sort code: {rng.randint(10, 99)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}",
                f"Account: {rng.randint(10000000, 99999999)}")
    return (f"Bank: {bank}", f"Account No: {rng.randint(10**9, 10**10 - 1)}",
            f"Branch: {rng.randint(100000, 999999)}", f"SWIFT: {bic(rng, country)}")


def party(rng: random.Random, country: str, trade: str, used: set, *, with_bank: bool = False,
          name: Optional[str] = None) -> Party:
    name = name or company_name(rng, country, trade, used)
    lines, _town = address(rng, country)
    slug = _slug(name)
    return Party(
        name=name,
        address=lines,
        country=country,
        phone=phone(rng, country),
        email=f"{rng.choice(['accounts', 'invoices', 'billing', 'ar', 'admin'])}@{slug}{COUNTRIES[country]['tld']}",
        tax_id=tax_id(rng, country),
        tax_label=COUNTRIES[country]["tax_label"],
        bank=bank_lines(rng, country) if with_bank else None,
    )


def customer(rng: random.Random, country: str, used: set) -> Party:
    trade = rng.choice(["freight", "supply", "services"])
    return party(rng, country, trade, used)


# ---------------------------------------------------------------------------
# Goods and services, by trade: (description, unit price range, qty range)
# ---------------------------------------------------------------------------

GOODS: Dict[str, List[Tuple[str, Tuple[float, float], Tuple[int, int]]]] = {
    "supply": [
        ("Hex bolts M12 x 50 galvanised (box 50)", (180, 420), (1, 12)),
        ("Nitrile work gloves, size L (pack 12)", (60, 140), (2, 20)),
        ("Hydraulic hose 1/2in, per metre", (45, 95), (5, 60)),
        ("Angle grinder discs 115mm (10)", (90, 210), (1, 15)),
        ("Copy paper A4 80gsm, box of 5 reams", (240, 390), (1, 10)),
        ("Toner cartridge, black, high yield", (650, 1480), (1, 6)),
        ("Truck tyre 315/80R22.5 drive", (3900, 6900), (1, 8)),
        ("Brake pads, trailer axle set", (980, 2100), (1, 6)),
        ("Engine oil 15W-40, 20 L drum", (1100, 1900), (1, 10)),
        ("Stretch wrap film 500mm x 300m", (95, 180), (4, 40)),
        ("Pallet strapping kit", (310, 520), (1, 8)),
        ("Safety boots, steel toe, size 9", (540, 980), (1, 10)),
        ("LED work lamp 24V", (230, 480), (1, 10)),
        ("Air filter element, heavy duty", (420, 890), (1, 6)),
        ("Ratchet straps 50mm x 9m (4)", (260, 480), (1, 12)),
    ],
    "services": [
        ("Monthly IT support retainer", (4500, 12500), (1, 1)),
        ("Site security, night shift (per shift)", (850, 1450), (4, 31)),
        ("Office cleaning, monthly contract", (3200, 7800), (1, 1)),
        ("Network switch configuration", (950, 2400), (1, 3)),
        ("Consulting hours, finance systems", (650, 1350), (2, 40)),
        ("Catering, staff function (per head)", (180, 340), (20, 80)),
        ("Mobile data bundle, 50GB", (420, 690), (1, 12)),
        ("Forklift service and inspection", (1800, 3900), (1, 3)),
        ("Air-conditioning maintenance call-out", (750, 1650), (1, 2)),
    ],
    "freight": [
        ("Linehaul {a} - {b}", (9000, 38000), (1, 1)),
        ("Cross-border transit {a} - {b}", (14000, 52000), (1, 1)),
        ("Local delivery, 8t rigid", (1800, 4200), (1, 4)),
        ("Container haulage 40ft {a} depot", (6500, 14500), (1, 2)),
        ("Abnormal load escort", (3500, 8800), (1, 1)),
    ],
    "freight_extra": [
        ("Fuel surcharge {p}%", (0, 0), (1, 1)),
        ("Detention, {h} hours", (450, 750), (1, 1)),
        ("Lumper / offloading fee", (650, 1600), (1, 1)),
        ("Tarping fee", (350, 800), (1, 1)),
        ("Toll fees recovered", (420, 2600), (1, 1)),
        ("Border crossing fee", (650, 1900), (1, 1)),
        ("Waiting time at consignee", (900, 2400), (1, 1)),
        ("Redelivery charge", (1200, 2800), (1, 1)),
    ],
    "clearing_disb": [
        ("Customs duty (disbursement)", (4000, 45000), (1, 1)),
        ("Import VAT paid on behalf (disbursement)", (3000, 38000), (1, 1)),
        ("Port charges - wharfage (disbursement)", (900, 6500), (1, 1)),
        ("Shipping line release fee (disbursement)", (1200, 4800), (1, 1)),
        ("Container storage, 4 days (disbursement)", (800, 5200), (1, 1)),
    ],
    "clearing_fee": [
        ("Customs clearance fee", (950, 2800), (1, 1)),
        ("Documentation fee", (250, 650), (1, 1)),
        ("Bill of entry preparation", (380, 900), (1, 1)),
        ("Delivery order handling", (300, 750), (1, 1)),
        ("Cargo inspection attendance", (450, 1200), (1, 1)),
    ],
}

ROUTES = [("Walvis Bay", "Windhoek"), ("Windhoek", "Lusaka"), ("Durban", "Johannesburg"),
          ("Walvis Bay", "Lubumbashi"), ("Johannesburg", "Gaborone"), ("Cape Town", "Upington"),
          ("Windhoek", "Keetmanshoop"), ("Durban", "Ndola"), ("Dallas", "Memphis"), ("Felixstowe", "Leeds"),
          ("Rotterdam", "Duisburg"), ("Kitwe", "Walvis Bay")]

__all__ = [
    "COUNTRIES", "CURRENCY_COUNTRY", "GOODS", "ROUTES",
    "person", "company_name", "address", "phone", "tax_id", "bic", "bank_lines", "party", "customer",
]
