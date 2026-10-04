"""
Benchmark corpus v1: 181 documents across ten categories, from one seed.

    specs = build_corpus(seed=42)

Same seed, same specs (and, with the same fonts, the same files). Each
category builder documents what it is there to measure. Difficulty is the
author's prior, set per document.

  clean       digital PDFs: 20 US invoices (us_specs.py) plus 11 non-US
              layouts and number/date formats
  currency    USD ZAR NAD EUR GBP ZMW; dual-currency payable box; lines in
              several currencies
  tax         VAT inclusive / exclusive, "Sub Total" after VAT, zero-rated,
              percentage lines, withholding
  credit      "Credit Note", NdC, "R -", brackets, CR, unsigned
  multipage   2-8 pages, lines across pages, totals on the last page
  freight     carrier invoices (fuel surcharge, accessorials), clearing and
              forwarding (disbursements), trip references
  handwritten cash-book and delivery-note invoices filled in by hand, graded
  photo       one clean document per degradation x severity (photos)
  scan        scan and fax looks x severity
  hard        several invoices in one file, a statement, PO beside the
              invoice number, no invoice number, totals that do not add up

The published set withholds 10 documents of a document type that is not
public yet (4 in freight, 6 in handwritten). `_skip_withheld` still makes
their random draws, so seed 42 reproduces the other 181 documents byte for
byte as they were scored.
"""

from __future__ import annotations

import random
from dataclasses import replace
from datetime import date, timedelta
from typing import List, Optional, Sequence, Tuple

from . import names as N
from .spec import (
    EU_NUM, US_NUM, ZA_DOT_NUM, ZA_NUM, Charge, Degradation, DocSpec, Layout, Line,
    MoneyStyle, Party, Payable, Render, StatementRow, Tax, money, validate_all,
)

CATEGORIES = ("clean", "currency", "tax", "credit", "multipage", "freight", "handwritten", "photo", "scan", "hard")

VAT = {"ZA": 0.15, "NA": 0.15, "ZM": 0.16, "GB": 0.20, "DE": 0.19, "NL": 0.21, "FR": 0.20}
VAT_LABEL = {"ZA": "VAT", "NA": "VAT", "ZM": "VAT", "GB": "VAT", "DE": "MwSt", "NL": "BTW", "FR": "TVA"}
DATE_STYLES = {
    "US": ["US", "USLONG"], "ZA": ["ZA", "UK", "LONG"], "NA": ["UK", "LONG", "MON"], "ZM": ["UK", "MON"],
    "GB": ["UK", "LONG"], "DE": ["EU"], "NL": ["EU", "MON"], "FR": ["UK", "EU"],
}
ACCENTS = [(30, 30, 30), (20, 60, 110), (120, 30, 40), (25, 95, 70), (90, 60, 20), (70, 40, 110)]
TODAY = date(2026, 9, 28)   # dates stay in the past: check_future_year flags anything ahead


def money_style(currency: str, variant: int = 0) -> MoneyStyle:
    if currency == "USD":
        return MoneyStyle("$", "prefix", False, "minus", US_NUM)
    if currency == "ZAR":
        return [MoneyStyle("R", "prefix", True, "minus", ZA_NUM),
                MoneyStyle("R", "prefix", False, "minus", ZA_DOT_NUM),
                MoneyStyle("ZAR", "prefix", True, "minus", US_NUM)][variant % 3]
    if currency == "NAD":
        return [MoneyStyle("N$", "prefix", True, "minus", US_NUM),
                MoneyStyle("NAD", "prefix", True, "minus", ZA_DOT_NUM),
                MoneyStyle("N$", "prefix", False, "minus", ZA_DOT_NUM)][variant % 3]
    if currency == "EUR":
        return [MoneyStyle("€", "suffix", True, "minus", EU_NUM),
                MoneyStyle("€", "prefix", True, "minus", EU_NUM),
                MoneyStyle("EUR", "suffix", True, "minus", EU_NUM)][variant % 3]
    if currency == "GBP":
        return MoneyStyle("£", "prefix", False, "minus", US_NUM)
    if currency == "ZMW":
        return [MoneyStyle("K", "prefix", True, "minus", US_NUM),
                MoneyStyle("ZMW", "prefix", True, "minus", US_NUM)][variant % 2]
    raise KeyError(currency)


class Factory:
    def __init__(self, seed: int):
        self.rng = random.Random(seed)
        self.used: set = set()
        self.seq = 0

    # ---- small helpers

    def pick(self, seq):
        return self.rng.choice(list(seq))

    def issue(self) -> date:
        return date(2025, 1, 6) + timedelta(days=self.rng.randint(0, (TODAY - date(2025, 1, 6)).days - 25))

    def ambiguous_issue(self) -> date:
        """A day of 1-12, so the printed date reads both ways (05/03 vs 03/05)."""
        d = self.issue()
        return d.replace(day=self.rng.randint(1, 12)) if d.month != d.day else d.replace(day=(d.day % 12) + 1)

    def number(self, kind: str = "invoice") -> str:
        r = self.rng
        n = r.randint(100, 99999)
        if kind == "credit":
            return r.choice([f"CN{n:06d}", f"CRN-{n:05d}", f"CN-2026-{n % 1000:04d}"])
        if kind == "ndc":
            return f"NdC{n:05d}"
        return r.choice([f"INV-2026-{n:05d}", f"TI{n:06d}", f"{r.choice('ABKMRTW')}{r.choice('ACFLNS')}-{n}",
                         f"2026/{n % 10000:04d}", f"F-26-{n % 10000:04d}", f"IN{n:07d}", f"{n:06d}"])

    def po(self) -> str:
        r = self.rng
        return r.choice([f"PO-{r.randint(10000, 99999)}", f"P{r.randint(100000, 999999)}",
                         f"ORD-{r.randint(1000, 9999)}", f"4500{r.randint(100000, 999999)}"])

    def layout(self, **kw) -> Layout:
        r = self.rng
        base = dict(
            family=r.choice(["sans", "sans", "serif", "mono"]),
            header=r.choice(["left", "left", "right", "center", "banner"]),
            table=r.choice(["band", "grid", "plain", "zebra"]),
            two_column=r.random() < 0.25,
            accent=r.choice(ACCENTS),
            logo=r.random() < 0.3,
            totals_box=r.random() < 0.3,
        )
        base.update(kw)
        return Layout(**base)

    def goods_lines(self, trade: str, n: int, *, code: bool = False, vat_rate: Optional[float] = None,
                    price_scale: float = 1.0) -> Tuple[Line, ...]:
        pool = list(N.GOODS[trade])
        self.rng.shuffle(pool)
        out = []
        for i in range(n):
            desc, (lo, hi), (qlo, qhi) = pool[i % len(pool)]
            if i >= len(pool):
                desc = f"{desc} (batch {i // len(pool) + 1})"
            qty = self.rng.randint(qlo, qhi)
            unit = money(self.rng.uniform(lo, hi) * price_scale)
            out.append(Line(desc, money(qty * unit), qty=qty, unit_price=unit,
                            code=f"{desc[:3].upper()}{self.rng.randint(100, 999)}" if code else None,
                            vat_rate=vat_rate))
        return tuple(out)

    def parties(self, country: str, trade: str, cust_country: Optional[str] = None, bank: bool = False):
        vendor = N.party(self.rng, country, trade, self.used, with_bank=bank)
        customer = N.customer(self.rng, cust_country or country, self.used)
        return vendor, customer

    def vat(self, country: str, base: float, rate: Optional[float] = None) -> Tuple[Tax, ...]:
        rate = VAT.get(country, 0.0) if rate is None else rate
        if country == "US":
            rate = rate or self.pick([0.06, 0.0625, 0.07, 0.0825, 0.08875])
            return (Tax(f"Sales Tax ({rate * 100:g}%)", money(base * rate), rate),)
        return (Tax(f"{VAT_LABEL[country]} {rate * 100:g}%", money(base * rate), rate),)

    # ---- a standard invoice

    def invoice(self, doc_id: str, category: str, difficulty: str, description: str, *,
                country: str, currency: Optional[str] = None, trade: str = "supply", n_lines: int = 4,
                style_variant: Optional[int] = None, date_style: Optional[str] = None,
                lines: Optional[Sequence[Line]] = None, charges: Sequence[Charge] = (),
                tax_rate: Optional[float] = None, no_tax: bool = False, layout: Optional[Layout] = None,
                ambiguous_date: bool = False, due: Optional[int] = None, bank: bool = False,
                cust_country: Optional[str] = None, **kw) -> DocSpec:
        currency = currency or N.COUNTRIES[country]["currency"]
        vendor, customer = self.parties(country, trade, cust_country, bank=bank or self.rng.random() < 0.4)
        lines = tuple(lines) if lines is not None else self.goods_lines(trade, n_lines)
        base = money(sum(l.amount for l in lines) - sum(c.amount for c in charges if c.kind == "discount")
                     + sum(c.amount for c in charges if c.kind != "discount"))
        taxes = () if no_tax else self.vat(country, base, tax_rate)
        issue = self.ambiguous_issue() if ambiguous_date else self.issue()
        if due is None:
            due = self.pick([None, 30, 30, 14, 60])
        sv = style_variant if style_variant is not None else self.rng.randint(0, 2)
        fields = dict(
            doc_id=doc_id, category=category, difficulty=difficulty, description=description,
            vendor=vendor, customer=customer, issue_date=issue, currency=currency,
            money_style=money_style(currency, sv),
            date_style=date_style or self.pick(DATE_STYLES[country]),
            title=self.pick(["TAX INVOICE", "INVOICE"]) if country != "US" else "INVOICE",
            number=self.number(), number_label=self.pick(["Invoice No", "Invoice #", "Invoice Number"]),
            due_date=issue + timedelta(days=due) if due else None,
            terms=f"{due} days" if due else self.pick([None, "COD", "Due on receipt"]),
            po_number=self.po() if self.rng.random() < 0.5 else None,
            lines=lines, charges=tuple(charges), taxes=taxes,
            layout=layout or self.layout(paper="LETTER" if country == "US" else "A4"),
        )
        fields.update(kw)
        return DocSpec(**fields)


# ---------------------------------------------------------------------------
# 1. clean digital PDFs
# ---------------------------------------------------------------------------


def _from_fixture(fx) -> DocSpec:
    """One of us_specs.py's 20 US invoices, laid out by the shared engine."""
    v = fx.vendor
    vendor = Party(v.name, (v.street, v.city_state_zip), "US", v.phone, v.email, v.tax_id, "Tax ID")
    c = fx.customer
    customer = Party(c.name, (c.street, c.city_state_zip), "US")
    charges: List[Charge] = []
    if fx.discount_label and fx.discount_amount:
        charges.append(Charge(fx.discount_label, fx.discount_amount, "discount"))
    if fx.shipping_label is not None:
        charges.append(Charge(fx.shipping_label, fx.shipping_amount, "shipping"))
    if fx.fees_label and fx.fees_amount:
        charges.append(Charge(fx.fees_label, fx.fees_amount, "fees"))
    families = ["sans", "serif", "mono", "sans"]
    headers = ["left", "right", "left", "banner"]
    tables = ["band", "plain", "plain", "zebra"]
    iy, im, idd = (int(p) for p in fx.invoice_date_iso.split("-"))
    due = None
    if fx.due_date_iso:
        dy, dm, dd = (int(p) for p in fx.due_date_iso.split("-"))
        due = date(dy, dm, dd)
    return DocSpec(
        doc_id=f"clean-us-{fx.name.removeprefix('us_').replace('_', '-')}",
        category="clean", difficulty="easy" if fx.expected_math_correct else "hard",
        description=f"US invoice '{fx.name}': {fx.description}",
        vendor=vendor, customer=customer, issue_date=date(iy, im, idd), currency="USD",
        money_style=money_style("USD"), date_style="US", title="INVOICE",
        number=fx.invoice_number, number_label="Invoice #", due_date=due, po_number=fx.po_number,
        po_label="PO #", terms=fx.payment_terms,
        lines=tuple(Line(li.description, li.line_total, qty=li.quantity, unit_price=li.unit_price)
                    for li in fx.line_items),
        charges=tuple(charges),
        taxes=tuple(Tax(t.label, t.amount, t.rate) for t in fx.taxes),
        total_printed=fx.total_printed if not fx.expected_math_correct else None,
        should_flag=not fx.expected_math_correct,
        layout=Layout(family=families[fx.layout_variant], header=headers[fx.layout_variant],
                      table=tables[fx.layout_variant], paper="LETTER"),
        tags=("fixture",) + (() if fx.expected_math_correct else ("inconsistent",)),
    )


def clean(f: Factory) -> List[DocSpec]:
    from .us_specs import SPECS as FIXTURES

    out = [_from_fixture(fx) for fx in FIXTURES]
    L = f.layout
    out += [
        f.invoice("clean-gb-serif", "clean", "easy", "UK supplier, serif letterhead, DD/MM dates.",
                  country="GB", layout=L(family="serif", header="left", table="plain")),
        f.invoice("clean-de-grid-eu-decimals", "clean", "medium",
                  "German supplier, gridded table, 1.234,56 amounts, DD.MM.YYYY dates.",
                  country="DE", style_variant=0, layout=L(table="grid", header="right")),
        f.invoice("clean-za-band-space-groups", "clean", "easy", "SA supplier, 1 234,56 amounts.",
                  country="ZA", style_variant=0, layout=L(table="band", header="left")),
        f.invoice("clean-na-center-letterhead", "clean", "easy", "Namibian supplier, centred letterhead.",
                  country="NA", style_variant=0, layout=L(header="center")),
        f.invoice("clean-fr-right-header", "clean", "medium", "French supplier, vendor block on the right.",
                  country="FR", style_variant=1, layout=L(header="right", table="zebra"), ambiguous_date=True),
        f.invoice("clean-nl-two-column", "clean", "easy", "Dutch supplier, bill-to and deliver-to boxes.",
                  country="NL", layout=L(two_column=True, header="left")),
        f.invoice("clean-zm-banner", "clean", "easy", "Zambian supplier, coloured banner header.",
                  country="ZM", layout=L(header="banner")),
        f.invoice("clean-us-landscape", "clean", "medium", "US supplier, landscape page.",
                  country="US", n_lines=6, layout=L(landscape=True, paper="LETTER", header="left")),
        f.invoice("clean-gb-mono-plain", "clean", "medium", "UK supplier, typewriter font, no table lines.",
                  country="GB", layout=L(family="mono", table="plain"), ambiguous_date=True),
        f.invoice("clean-za-code-zebra", "clean", "easy", "SA supplier, item-code column, striped rows.",
                  country="ZA", style_variant=1, columns="code",
                  lines=f.goods_lines("supply", 6, code=True), layout=L(table="zebra")),
        # Consumables sold by the hundred: the quantity is larger than the line total.
        f.invoice("clean-na-bulk-consumables", "clean", "easy",
                  "Cheap items in bulk: quantities (500, 1 200) larger than their line totals.",
                  country="NA", style_variant=0,
                  lines=(Line("Cable ties 200mm, black", 60.0, qty=500, unit_price=0.12),
                         Line("Split pins 3mm", 96.0, qty=1200, unit_price=0.08),
                         Line("Hose clamps 32mm", 342.0, qty=36, unit_price=9.5))),
    ]
    return out


# ---------------------------------------------------------------------------
# 2. currencies
# ---------------------------------------------------------------------------


def currency(f: Factory) -> List[DocSpec]:
    out: List[DocSpec] = []
    singles = [("USD", "US", 0), ("USD", "US", 0), ("ZAR", "ZA", 0), ("ZAR", "ZA", 2), ("NAD", "NA", 0),
               ("NAD", "NA", 1), ("EUR", "DE", 0), ("EUR", "NL", 1), ("GBP", "GB", 0), ("GBP", "GB", 0),
               ("ZMW", "ZM", 0), ("ZMW", "ZM", 1)]
    for i, (ccy, country, sv) in enumerate(singles):
        sym = money_style(ccy, sv).symbol
        out.append(f.invoice(f"currency-{ccy.lower()}-{i % 2 + 1}", "currency", "easy",
                             f"{ccy} invoice, amounts printed with '{sym}'.", country=country, currency=ccy,
                             style_variant=sv, layout=f.layout(show_currency_header=(i % 2 == 1))))
    # Namibian vendor printing a bare "$": the dollar-family rule must give NAD
    nad = f.invoice("currency-nad-bare-dollar", "currency", "hard",
                    "Namibian vendor whose amounts print a bare '$' (NAD, not USD).",
                    country="NA", currency="NAD", layout=f.layout(show_currency_header=False))
    out.append(replace(nad, money_style=MoneyStyle("$", "prefix", False, "minus", US_NUM)))

    # dual currency: lines in USD/EUR, payable box in ZAR/NAD
    for i, (line_ccy, country, pay_ccy, line_col, vat_in_pay) in enumerate(
            [("USD", "ZA", "ZAR", True, False), ("EUR", "NA", "NAD", False, False),
             ("USD", "ZA", "ZAR", True, True), ("USD", "NA", "NAD", True, False)]):
        rate = {"USD": 18.4512, "EUR": 20.0137}[line_ccy] if pay_ccy == "ZAR" else {"USD": 18.3920, "EUR": 19.9871}[line_ccy]
        trade = "clearing"
        lines = tuple(Line(d.split(" (")[0], money(f.rng.uniform(lo, hi) / 18), qty=1,
                           unit_price=None) for d, (lo, hi), _q in f.rng.sample(N.GOODS["clearing_fee"], 3))
        lines = tuple(replace(ln, unit_price=ln.amount) for ln in lines)
        pay_style = money_style(pay_ccy, 0)
        base = replace(
            f.invoice(f"currency-dual-{line_ccy.lower()}-{pay_ccy.lower()}-{i + 1}", "currency", "hard",
                      f"Lines in {line_ccy}, 'TOTAL INVOICE AMOUNT PAYABLE' box in {pay_ccy}"
                      + (" with an Amount column per line" if line_col else "") + ".",
                      country=country, currency=line_ccy, trade=trade, lines=lines, no_tax=True,
                      style_variant=0, layout=f.layout(show_currency_header=True), due=30),
            money_style=MoneyStyle("US$" if line_ccy == "USD" else "€", "prefix", True, "minus", US_NUM),
            columns="dual", tags=("dual_currency",),
        )
        pay_tax = 0.0
        if vat_in_pay:
            pay_sub = money(sum(money(ln.amount * rate) for ln in lines))
            pay_tax = money(pay_sub * 0.15)
        out.append(replace(base, payable=Payable(pay_ccy, pay_style, rate, line_column=line_col, tax=pay_tax)))

    # several currencies on the lines, converted into the document currency
    for i, (ccy, country) in enumerate([("ZAR", "ZA"), ("NAD", "NA")]):
        rows = []
        for desc, fccy, famt, rate in [("Ocean freight Shanghai - Walvis Bay", "USD", f.rng.uniform(900, 2400), 18.45),
                                       ("Origin handling", "EUR", f.rng.uniform(150, 600), 20.01),
                                       ("Port dues", ccy, f.rng.uniform(800, 3000), 1.0),
                                       ("Cargo dues", ccy, f.rng.uniform(300, 1200), 1.0)]:
            famt = money(famt)
            rows.append(Line(desc, money(famt * rate), foreign=(fccy, famt, rate) if fccy != ccy else None))
        doc = f.invoice(f"currency-multi-line-{ccy.lower()}", "currency", "hard",
                        f"Line items priced in USD, EUR and {ccy}, each converted to {ccy}.",
                        country=country, currency=ccy, lines=tuple(rows), style_variant=0, trade="clearing")
        out.append(replace(doc, columns="foreign", tags=("multi_currency_lines",)))
    return out


# ---------------------------------------------------------------------------
# 3. tax
# ---------------------------------------------------------------------------


def _inclusive(f: Factory, doc_id: str, desc: str, country: str, order: str, difficulty: str = "medium") -> DocSpec:
    rate = VAT[country]
    lines = f.goods_lines("supply", 4)
    gross = money(sum(l.amount for l in lines))
    tax = money(gross * rate / (1 + rate))
    doc = f.invoice(doc_id, "tax", difficulty, desc, country=country, lines=lines, no_tax=True,
                    layout=f.layout(totals_order=order))
    return replace(doc, taxes=(Tax(f"VAT {rate * 100:g}%", tax, rate),), tax_inclusive=True,
                   tags=("vat_inclusive",))


def tax(f: Factory) -> List[DocSpec]:
    out: List[DocSpec] = []
    for country in ("ZA", "GB"):
        rate = VAT[country]
        lines = f.goods_lines("supply", 5, vat_rate=rate)
        out.append(f.invoice(f"tax-exclusive-vat-column-{country.lower()}", "tax", "easy",
                             "VAT-exclusive prices with a VAT % column per line.", country=country,
                             lines=lines, columns="vat"))
    out.append(_inclusive(f, "tax-inclusive-total-za", "Prices include VAT; 'VAT included in total' note.", "ZA", "standard"))
    out.append(_inclusive(f, "tax-inclusive-total-na", "Prices include VAT; 'VAT included in total' note.", "NA", "standard"))
    out.append(_inclusive(f, "tax-inclusive-subtotal-na", "VAT-inclusive 'Sub Total' equal to the total, VAT shown as included.",
                          "NA", "inclusive_sub", "hard"))
    for i, country in enumerate(("NA", "ZA", "NA")):
        charges = (Charge("Discount", money(f.rng.uniform(50, 400)), "discount"),) if i == 2 else ()
        out.append(f.invoice(f"tax-sage-subtotal-after-vat-{i + 1}", "tax", "hard",
                             "Sage/Pastel totals: Total Exclusive / Total VAT / Sub Total (incl. VAT) / Total.",
                             country=country, charges=charges, layout=f.layout(totals_order="sage"),
                             tags=("sage_layout",)))
    for country in ("NA", "ZA"):
        doc = f.invoice(f"tax-zero-rated-{country.lower()}", "tax", "medium", "Zero-rated export: 'VAT 0% (zero-rated)' 0.00.",
                        country=country, trade="freight", lines=(Line(f"Export transport {f.pick(N.ROUTES)[0]} - Lusaka",
                                                                      money(f.rng.uniform(18000, 42000)), qty=1),),
                        no_tax=True)
        out.append(replace(doc, taxes=(Tax("VAT 0% (zero-rated)", 0.0, 0.0),),
                           lines=tuple(replace(l, unit_price=l.amount) for l in doc.lines)))
    for i, country in enumerate(("NA", "ZA")):
        base = money(f.rng.uniform(60000, 180000))
        pct = f.pick([0.018, 0.0125, 0.025])
        lines = (Line("Customs clearance fee", money(f.rng.uniform(900, 2400)), qty=1),
                 Line("Agency fee on customs value", money(base * pct), qty=base, pct=pct),
                 Line("Documentation fee", money(f.rng.uniform(250, 650)), qty=1))
        lines = tuple(replace(l, unit_price=l.amount) if l.pct is None else l for l in lines)
        out.append(f.invoice(f"tax-percentage-line-{i + 1}", "tax", "hard",
                             "A percentage line: rate column '1.80%', the customs value in the Qty column.",
                             country=country, trade="clearing", lines=lines, columns="pct", tags=("percentage_line",)))
    for i, (country, label, rate) in enumerate([("ZM", "Withholding tax 15%", 0.15), ("NA", "Less: Withholding tax 10%", 0.10)]):
        doc = f.invoice(f"tax-withholding-{country.lower()}", "tax", "hard",
                        "Withholding deducted below the total, then 'Net Amount Due'.", country=country,
                        trade="services", n_lines=2, due=30)
        wht = money(doc.line_sum * rate)
        out.append(replace(doc, withholding=Tax(label, wht, rate), tags=("withholding",)))
    return out


# ---------------------------------------------------------------------------
# 4. credit notes
# ---------------------------------------------------------------------------


def credit(f: Factory) -> List[DocSpec]:
    out: List[DocSpec] = []
    variants = [
        ("credit-note-minus-za", "ZA", "CREDIT NOTE", "Credit Note No", "credit", "minus", True, None, "easy"),
        ("credit-note-minus-gb", "GB", "CREDIT NOTE", "Credit Note No", "credit", "minus", True, None, "easy"),
        ("credit-ndc-na", "NA", "NOTA DE CRÉDITO (NdC)", "NdC No.", "ndc", "minus", True, "ref", "hard"),
        ("credit-ndc-za-ref", "ZA", "NdC", "NdC No.", "ndc", "symbol_minus", True, "ref", "hard"),
        ("credit-r-minus-1", "ZA", "CREDIT NOTE", "Credit Note No", "credit", "symbol_minus", True, "ref", "medium"),
        ("credit-r-minus-2", "ZA", "TAX CREDIT NOTE", "Document No", "credit", "symbol_minus", True, None, "medium"),
        ("credit-brackets-us", "US", "CREDIT MEMO", "Credit Memo #", "credit", "brackets", True, None, "medium"),
        ("credit-brackets-gb", "GB", "CREDIT NOTE", "Credit Note No", "credit", "brackets", True, "ref", "medium"),
        ("credit-unsigned-na", "NA", "CREDIT NOTE", "Credit Note No", "credit", "minus", False, "ref", "hard"),
        ("credit-cr-suffix-za", "ZA", "CREDIT NOTE", "Credit Note No", "credit", "cr_suffix", True, None, "hard"),
    ]
    for doc_id, country, title, label, numkind, neg, signed, ref, diff in variants:
        doc = f.invoice(doc_id, "credit", diff, f"{title}, negatives printed as '{neg}'"
                        + ("" if signed else " (amounts printed unsigned)") + ".",
                        country=country, n_lines=f.rng.randint(1, 3), due=None,
                        style_variant=0 if neg != "symbol_minus" else 0)
        ms = replace(doc.money_style, negative=neg)
        if neg == "symbol_minus" and country == "ZA":
            ms = replace(ms, symbol="R", position="prefix", space=True)
        out.append(replace(doc, kind="credit_note", title=title, number=f.number(numkind), number_label=label,
                           money_style=ms, print_negative=signed, po_number=None, due_date=None, terms=None,
                           credit_ref=f.number() if ref else None, tags=("credit_note", f"neg_{neg}")))
    return out


# ---------------------------------------------------------------------------
# 5. multi-page
# ---------------------------------------------------------------------------


def multipage(f: Factory) -> List[DocSpec]:
    out: List[DocSpec] = []
    plan = [(2, "ZA", False), (2, "US", False), (3, "NA", True), (3, "GB", False), (4, "ZA", True),
            (5, "DE", False), (5, "NA", False), (6, "ZA", True), (8, "US", False), (8, "NA", False)]
    for i, (pages, country, cf) in enumerate(plan):
        rpp = f.rng.randint(14, 18)
        n = rpp * (pages - 1) + f.rng.randint(2, max(3, rpp - 8))
        lines = f.goods_lines("supply", n, code=True, price_scale=0.4)
        doc = f.invoice(f"multipage-{pages}p-{country.lower()}-{i + 1}", "multipage",
                        "medium" if pages <= 3 else "hard",
                        f"{pages} pages, {n} lines continuing across pages, totals on the last page"
                        + (", carried/brought forward rows" if cf else "") + ".",
                        country=country, lines=lines, columns="code",
                        layout=f.layout(rows_per_page=rpp, carried_forward=cf,
                                        paper="LETTER" if country == "US" else "A4", landscape=False))
        out.append(replace(doc, tags=("multipage", f"pages_{pages}") + (("carried_forward",) if cf else ())))
    return out


# ---------------------------------------------------------------------------
# 6. freight
# ---------------------------------------------------------------------------


def _trip_meta(f: Factory) -> Tuple[Tuple[Tuple[str, str], ...], Tuple[str, ...]]:
    r = f.rng
    trip = f"TR{r.randint(10000, 99999)}"
    load = f"LD-{r.randint(100000, 999999)}"
    truck = f"N {r.randint(1000, 99999)} W{r.choice(['B', 'K', 'H'])}"
    meta = ((r.choice(["Trip No", "Trip Ref"]), trip), ("Load Ref", load), ("Truck Reg", truck))
    return meta, (trip, load)


def carrier_invoice(f: Factory, doc_id: str, country: str, difficulty: str = "medium") -> DocSpec:
    a, b = f.pick(N.ROUTES)
    linehaul = money(f.rng.uniform(9000, 38000) * (0.07 if country == "US" else 1.0))
    p = f.pick([12.5, 15, 18, 22.5])
    lines = [Line(f"Linehaul {a} - {b}", linehaul, qty=1, unit_price=linehaul),
             Line(f"Fuel surcharge {p:g}%", money(linehaul * p / 100), qty=linehaul, pct=p / 100)]
    for desc, (lo, hi), _q in f.rng.sample(N.GOODS["freight_extra"][1:], f.rng.randint(1, 3)):
        amt = money(f.rng.uniform(lo, hi) * (0.07 if country == "US" else 1.0))
        lines.append(Line(desc.format(h=f.rng.randint(2, 6)), amt, qty=1, unit_price=amt))
    meta, refs = _trip_meta(f)
    doc = f.invoice(doc_id, "freight", difficulty, f"Carrier invoice {a} - {b}: linehaul, fuel surcharge %, accessorials.",
                    country=country, trade="freight", lines=tuple(lines), columns="pct",
                    meta_extra=meta, trip_refs=refs, due=30)
    return replace(doc, tags=("carrier", "fuel_surcharge", "accessorials"))


def clearing_invoice(f: Factory, doc_id: str, country: str, difficulty: str = "hard") -> DocSpec:
    disb = [Line(d, money(f.rng.uniform(lo, hi)), qty=1) for d, (lo, hi), _q in f.rng.sample(N.GOODS["clearing_disb"], 3)]
    fees = [Line(d, money(f.rng.uniform(lo, hi)), qty=1, vat_rate=VAT[country]) for d, (lo, hi), _q in
            f.rng.sample(N.GOODS["clearing_fee"], 3)]
    lines = tuple(replace(l, unit_price=l.amount, vat_rate=l.vat_rate if l.vat_rate else 0.0) for l in disb + fees)
    vat = money(sum(l.amount for l in fees) * VAT[country])
    supplier_inv = f"SI{f.rng.randint(100000, 999999)}"
    meta = (("File Ref", f"CF{f.rng.randint(1000, 9999)}/26"), ("Supplier Inv No", supplier_inv),
            ("Container", f"IPPU{f.rng.randint(1000000, 9999999)}"))
    doc = f.invoice(doc_id, "freight", difficulty,
                    "Clearing & forwarding: VAT-free disbursements plus VAT-able agency fees, 'Supplier Inv No' printed.",
                    country=country, trade="clearing", lines=lines, columns="vat", no_tax=True, meta_extra=meta,
                    trip_refs=(meta[2][1],), due=7, title="TAX INVOICE", number_label="INVOICE No.")
    return replace(doc, taxes=(Tax(f"VAT {VAT[country] * 100:g}% on fees", vat, VAT[country]),),
                   tags=("clearing", "disbursements"))


def _skip_withheld(f: Factory) -> None:
    """Make, in order, exactly the random draws one withheld document makes,
    and discard them. Without this every document generated after it would
    change. The draws: two parties (the second from the "withheld" word
    list), a choice of four, two amounts, a date, five numbers, a person's
    name, one coin toss and a small number."""
    r = f.rng
    N.party(r, "NA", "freight", f.used)
    N.party(r, "NA", "withheld", f.used)
    f.pick(range(4))
    r.uniform(80, 420)
    r.uniform(19.2, 23.9)
    f.issue()
    r.randint(1000, 9999)
    r.randint(1000, 99999)
    N.person(r)
    r.randint(120000, 990000)
    r.randint(10000, 999999)
    r.random()
    r.randint(1, 9)


def freight(f: Factory) -> List[DocSpec]:
    out: List[DocSpec] = []
    for i, country in enumerate(["US", "US", "ZA", "ZA", "NA", "NA"]):
        out.append(carrier_invoice(f, f"freight-carrier-{country.lower()}-{i + 1}", country))
    for i, country in enumerate(["NA", "NA", "NA", "ZA", "ZA", "ZA"]):
        out.append(clearing_invoice(f, f"freight-clearing-{country.lower()}-{i + 1}", country))
    for _ in range(4):
        _skip_withheld(f)
    for i, country in enumerate(["NA", "ZA", "ZM", "NA"]):
        meta, refs = _trip_meta(f)
        doc = f.invoice(f"freight-trip-reference-{i + 1}", "freight", "medium",
                        "Transport invoice with Trip No / Load Ref / truck registration printed.",
                        country=country, trade="freight", n_lines=2, meta_extra=meta, trip_refs=refs)
        out.append(replace(doc, tags=("trip_reference",)))
    return out


# ---------------------------------------------------------------------------
# 7. handwritten
# ---------------------------------------------------------------------------


def handwritten(f: Factory) -> List[DocSpec]:
    out: List[DocSpec] = []
    for _ in range(6):
        _skip_withheld(f)
    for i, (country, leg) in enumerate([("NA", "neat"), ("ZA", "neat"), ("ZM", "average"), ("NA", "average"),
                                        ("ZA", "average"), ("NA", "poor"), ("ZM", "poor"), ("ZA", "poor")]):
        title = "CASH INVOICE" if i % 2 == 0 else "DELIVERY NOTE / INVOICE"
        lines = f.goods_lines("supply", f.rng.randint(2, 4))
        doc = f.invoice(f"handwritten-invoice-book-{leg}-{i + 1}", "handwritten",
                        {"neat": "medium", "average": "hard", "poor": "hard"}[leg],
                        f"Pre-printed {title.lower()} book filled in by hand ({leg} handwriting).",
                        country=country, lines=lines, due=None, date_style="UK",
                        layout=f.layout(table="grid", header="left", family="sans", two_column=False))
        out.append(replace(doc, title=title, number=f"{f.rng.randint(1000, 9999)}", number_label="No.",
                           po_number=None, terms=None,
                           render=Render(mode="image", fmt="jpg", handwriting=leg),
                           tags=("handwritten", f"legibility_{leg}")))
    return out


# ---------------------------------------------------------------------------
# 8. photos and 9. scans: degrade clean documents
# ---------------------------------------------------------------------------


def _degraded(base: DocSpec, doc_id: str, category: str, kind: str, sev: str, fmt: str) -> DocSpec:
    diff = {"mild": "easy", "moderate": "medium", "severe": "hard"}[sev]
    return replace(base, doc_id=doc_id, category=category, difficulty=diff,
                   description=f"{base.description} -> {kind.replace('_', ' ')} ({sev}).",
                   render=Render(mode="image", fmt=fmt, degradations=(Degradation(kind, sev),)),
                   base_id=base.doc_id, tags=tuple(base.tags) + (kind,))


def photos_and_scans(f: Factory) -> List[DocSpec]:
    from .degrade import PHOTO_KINDS, SCAN_KINDS

    # A pool of single-page clean documents to photograph (fresh, not reused
    # from other categories, so a photo's score is about the photo).
    bases = [
        f.invoice("base-za", "photo", "easy", "SA tax invoice", country="ZA", style_variant=0),
        f.invoice("base-na", "photo", "easy", "Namibian tax invoice", country="NA", style_variant=0),
        f.invoice("base-us", "photo", "easy", "US invoice", country="US"),
        f.invoice("base-gb", "photo", "easy", "UK invoice", country="GB"),
        carrier_invoice(f, "base-carrier-na", "NA", "easy"),
        f.invoice("base-zm", "photo", "easy", "Zambian invoice", country="ZM"),
    ]
    # The three grades of one degradation share one base document, so the
    # severity curve moves only with the severity.
    out: List[DocSpec] = []
    for k, kind in enumerate(PHOTO_KINDS):
        for sev in ("mild", "moderate", "severe"):
            out.append(_degraded(bases[k % len(bases)], f"photo-{kind.replace('_', '-')}-{sev}", "photo",
                                 kind, sev, "jpg"))
    for k, kind in enumerate(SCAN_KINDS):
        for sev in ("mild", "moderate", "severe"):
            out.append(_degraded(bases[(k + 3) % len(bases)], f"scan-{kind.replace('_', '-')}-{sev}", "scan",
                                 kind, sev, "png"))
    return out


# ---------------------------------------------------------------------------
# 10. hard cases
# ---------------------------------------------------------------------------


def hard(f: Factory) -> List[DocSpec]:
    out: List[DocSpec] = []
    # several invoices in one PDF
    for n in (2, 3):
        kids = tuple(f.invoice(f"hard-multi-{n}-child-{k + 1}", "hard", "hard", "child", country="ZA")
                     for k in range(n))
        out.append(replace(kids[0], doc_id=f"hard-multiple-invoices-{n}", kind="multi_invoice", children=kids,
                           description=f"{n} different invoices scanned into one PDF.",
                           tags=("multi_invoice",)))
    # statements
    for i, country in enumerate(("NA", "ZA")):
        doc = f.invoice(f"hard-statement-{country.lower()}", "hard", "hard",
                        "A supplier statement (several invoices and a payment, aged balance) - not a bill.",
                        country=country, n_lines=1, no_tax=True, due=None)
        rows = []
        when = doc.issue_date - timedelta(days=60)
        for k in range(5):
            when += timedelta(days=f.rng.randint(4, 12))
            if k == 3:
                rows.append(StatementRow(when, f"PMT{f.rng.randint(1000, 9999)}", "Payment received - thank you",
                                         credit=money(f.rng.uniform(3000, 9000))))
            else:
                rows.append(StatementRow(when, f.number(), "Invoice", debit=money(f.rng.uniform(1500, 12000))))
        out.append(replace(doc, kind="statement", title="STATEMENT", number=None, po_number=None, terms=None,
                           meta_extra=(("Account No", f"ACC{f.rng.randint(1000, 9999)}"),),
                           statement_rows=tuple(rows), tags=("statement",)))
    # PO number next to the invoice number
    for i, (inv_label, po_label) in enumerate([("Our Reference", "Order No"), ("Invoice No", "Your Ref"),
                                               ("Document No", "Customer Order No")]):
        prefix = f.pick(["ABC", "KLM", "TWS"])
        doc = f.invoice(f"hard-po-beside-invoice-number-{i + 1}", "hard", "hard",
                        f"'{inv_label}' and '{po_label}' printed side by side in the same format.",
                        country=f.pick(["ZA", "NA", "GB"]))
        out.append(replace(doc, number=f"{prefix}INV{f.rng.randint(100000, 999999)}", number_label=inv_label,
                           po_number=f"{prefix}SO{f.rng.randint(100000, 999999)}", po_label=po_label,
                           meta_extra=(("Delivery Note", f"{prefix}DEL{f.rng.randint(100000, 999999)}"),),
                           tags=("po_beside_number",)))
    # missing invoice number
    for i in range(2):
        doc = f.invoice(f"hard-missing-invoice-number-{i + 1}", "hard", "hard",
                        "No invoice number printed; only a PO / delivery note number.", country=f.pick(["NA", "ZA"]))
        out.append(replace(doc, number=None, po_number=f.po(),
                           meta_extra=(("Delivery Note", f"DN{f.rng.randint(10000, 99999)}"),),
                           tags=("missing_number",)))
    # totals that do not add up: must be flagged, not "fixed"
    conflicts = [
        ("hard-total-inflated", "Printed total 19% above subtotal + VAT, no charge line explains it.", 1.19, None),
        ("hard-lines-vs-subtotal", "Printed subtotal 7% above the sum of the lines.", None, 1.07),
        ("hard-total-small-residual", "Printed total 4% above subtotal + VAT: small enough to be 'reconciled' as a charge.", 1.04, None),
        ("hard-wrong-vat-amount", "VAT printed as 15% but the amount is 10% of the subtotal; total follows it.", None, None),
    ]
    for doc_id, desc, total_k, sub_k in conflicts:
        country = f.pick(["ZA", "NA"])
        doc = f.invoice(doc_id, "hard", "hard", desc, country=country)
        if doc_id == "hard-wrong-vat-amount":
            # The printed total adds up with the wrong VAT: the arithmetic is
            # consistent, the VAT is not 15% of anything. Flagging it needs a
            # rate check, which _validate() exempts it from.
            wrong = money(doc.line_sum * 0.10)
            out.append(replace(doc, charges=(), taxes=(Tax("VAT 15%", wrong, 0.15),), should_flag=True,
                               tags=("inconsistent", "wrong_vat")))
            continue
        if total_k:
            doc = replace(doc, total_printed=money(doc.computed_total * total_k), should_flag=True)
        if sub_k:
            doc = replace(doc, subtotal_printed=money(doc.line_sum * sub_k), should_flag=True,
                          total_printed=money(money(doc.line_sum * sub_k) + doc.tax_total))
        out.append(replace(doc, tags=("inconsistent",)))
    return out


# ---------------------------------------------------------------------------


def build_corpus(seed: int = 42) -> List[DocSpec]:
    f = Factory(seed)
    specs: List[DocSpec] = []
    for builder in (clean, currency, tax, credit, multipage, freight, handwritten):
        specs.extend(builder(f))
    specs.extend(photos_and_scans(f))
    specs.extend(hard(f))
    _validate(specs)
    return specs


def _validate(specs: List[DocSpec]) -> None:
    # The wrong-VAT document is consistent arithmetic with a wrong VAT; its
    # flag expectation is checked by the scorer, not by validate().
    checkable = [s for s in specs if "wrong_vat" not in s.tags]
    validate_all(checkable)
    ids = [s.doc_id for s in specs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate doc ids")
    unknown = {s.category for s in specs} - set(CATEGORIES)
    if unknown:
        raise ValueError(f"unknown categories {unknown}")


SETS = {"v1": build_corpus}
