"""
DocSpec: one benchmark document, the single source of truth.

The same object drives what is drawn on the page (layout.py) and what a
correct extraction returns (`DocSpec.expected()`), so the two cannot drift.
It covers several currencies and number formats, VAT-inclusive totals,
credit notes, multi-page invoices, freight and clearing documents,
handwriting, photos and scans.

Money is held as positive magnitudes in the document's own currency and
signed only when printed (a credit note may print "-", brackets, "R -" or
nothing at all). The scorer compares credit-note amounts by magnitude and
scores the credit-note decision separately (`document_type`), because the
sign convention (negative or positive amounts on a credit note) is one
decision, not three wrong amounts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Optional, Sequence, Tuple

SEVERITIES = ("mild", "moderate", "severe")
DIFFICULTIES = ("easy", "medium", "hard")
DOC_TYPES = ("invoice", "credit_note", "other")


def money(x: float) -> float:
    """Round half up to the cent (what a till or an accounting package prints)."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# ---------------------------------------------------------------------------
# Printing conventions
# ---------------------------------------------------------------------------

DATE_STYLES: Dict[str, str] = {
    "US": "%m/%d/%Y",      # 03/04/2026 = 4 March
    "UK": "%d/%m/%Y",      # 04/03/2026 = 4 March
    "EU": "%d.%m.%Y",      # 04.03.2026
    "ZA": "%Y/%m/%d",      # 2026/03/04
    "ISO": "%Y-%m-%d",
    "LONG": "%d %B %Y",    # 04 March 2026
    "MON": "%d-%b-%Y",     # 04-Mar-2026
    "USLONG": "%B %d, %Y",  # March 04, 2026
}


def fmt_date(d: date, style: str) -> str:
    text = d.strftime(DATE_STYLES[style])
    if style in ("LONG", "USLONG"):
        text = text.replace(" 0", " ") if style == "USLONG" else text.lstrip("0")
    return text


@dataclass(frozen=True)
class NumberStyle:
    """How a number is grouped and where its decimal mark is."""
    thousands: str = ","
    decimal: str = "."

    def fmt(self, x: float, decimals: int = 2) -> str:
        q = Decimal(str(abs(x))).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
        whole, _, frac = f"{q:f}".partition(".")
        groups = []
        while len(whole) > 3:
            groups.insert(0, whole[-3:])
            whole = whole[:-3]
        groups.insert(0, whole)
        text = self.thousands.join(groups)
        if decimals:
            text += self.decimal + frac
        return text


US_NUM = NumberStyle(",", ".")
EU_NUM = NumberStyle(".", ",")
ZA_NUM = NumberStyle(" ", ",")       # SA standard: 1 234,56
ZA_DOT_NUM = NumberStyle(" ", ".")   # common on SA/NA systems: 1 234.56
PLAIN_NUM = NumberStyle("", ".")


@dataclass(frozen=True)
class MoneyStyle:
    """How an amount is printed: symbol, its position, and negatives.

    negative:
        minus         -$1,234.56  /  -1.234,56 €
        symbol_minus  R -1 234,56  (the "R -" convention)
        brackets      ($1,234.56)
        cr_suffix     $1,234.56 CR
    """
    symbol: str = "$"
    position: str = "prefix"   # prefix | suffix | none
    space: bool = False
    negative: str = "minus"
    numbers: NumberStyle = US_NUM

    def fmt(self, x: float, with_symbol: bool = True) -> str:
        body = self.numbers.fmt(x)
        sym = self.symbol if (with_symbol and self.position != "none" and self.symbol) else ""
        gap = " " if self.space else ""
        neg = x < 0
        if neg and self.negative == "symbol_minus" and sym and self.position == "prefix":
            return f"{sym}{gap}-{body}"
        if sym and self.position == "prefix":
            core = f"{sym}{gap}{body}"
        elif sym and self.position == "suffix":
            core = f"{body}{gap or ' '}{sym}"
        else:
            core = body
        if not neg:
            return core
        if self.negative == "brackets":
            return f"({core})"
        if self.negative == "cr_suffix":
            return f"{core} CR"
        return f"-{core}"


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Party:
    name: str
    address: Tuple[str, ...]
    country: str                     # ISO 3166-1 alpha-2
    phone: Optional[str] = None
    email: Optional[str] = None
    tax_id: Optional[str] = None
    tax_label: str = "VAT No"
    bank: Optional[Tuple[str, ...]] = None   # printed remittance lines


@dataclass(frozen=True)
class Line:
    """One line item, `amount` in the document currency, positive."""
    description: str
    amount: float
    qty: Optional[float] = None
    unit_price: Optional[float] = None
    code: Optional[str] = None
    vat_rate: Optional[float] = None          # printed VAT % column
    pct: Optional[float] = None               # percentage line: rate column "1.80%", qty column = base
    foreign: Optional[Tuple[str, float, float]] = None  # (ccy, foreign amount, rate) printed beside it
    payable_amount: Optional[float] = None    # the line in the payable-box currency (dual currency)


@dataclass(frozen=True)
class Charge:
    """A totals-block line that is not a line item: shipping, fees, discount."""
    label: str
    amount: float
    kind: str = "fees"   # shipping | fees | discount


@dataclass(frozen=True)
class Tax:
    label: str
    amount: float
    rate: Optional[float] = None


@dataclass(frozen=True)
class Payable:
    """A final "TOTAL INVOICE AMOUNT PAYABLE  ZAR  R 12 345,67" box in a
    second currency (dual-currency clearing and freight invoices)."""
    currency: str
    style: MoneyStyle
    rate: float
    label: str = "TOTAL INVOICE AMOUNT PAYABLE"
    line_column: bool = True     # print an "Amount ZAR" column on the lines
    tax: float = 0.0             # VAT in the payable currency (printed in the box area)


@dataclass(frozen=True)
class StatementRow:
    when: date
    reference: str
    description: str
    debit: float = 0.0
    credit: float = 0.0


# ---------------------------------------------------------------------------
# Presentation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Layout:
    family: str = "sans"            # sans | serif | mono
    header: str = "left"            # left | right | center | banner
    table: str = "band"             # grid | band | plain | zebra
    two_column: bool = False        # bill-to and ship-to/meta boxes side by side
    landscape: bool = False
    paper: str = "A4"               # A4 | LETTER
    accent: Tuple[int, int, int] = (30, 30, 30)
    rows_per_page: int = 24
    totals_box: bool = False
    carried_forward: bool = False   # "Carried forward" / "Brought forward" between pages
    logo: bool = False
    totals_order: str = "standard"  # standard | sage ("Total Exclusive / VAT / Sub Total / Total")
    show_currency_header: bool = False   # "Currency: ZAR" in the meta block


@dataclass(frozen=True)
class Degradation:
    kind: str
    severity: str = "moderate"


@dataclass(frozen=True)
class Render:
    mode: str = "pdf"               # pdf (digital, text layer) | image (raster upload)
    dpi: int = 200                  # raster resolution before degradation
    fmt: str = "jpg"                # jpg | png, for image mode
    degradations: Tuple[Degradation, ...] = ()
    handwriting: Optional[str] = None   # neat | average | poor: values written by hand

    @property
    def severity(self) -> Optional[str]:
        if not self.degradations:
            return None
        return max((d.severity for d in self.degradations), key=SEVERITIES.index)


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExpectedLine:
    description: str
    amount: float
    alt_amounts: Tuple[float, ...] = ()


@dataclass
class Expected:
    """What a correct extraction returns. None means "not printed": a correct
    extraction leaves it empty. `scored` lists the fields this document is
    scored on (a statement is not scored on a due date it does not have)."""
    vendor_name: Optional[str]
    invoice_number: Optional[str]
    invoice_date: Optional[str]
    due_date: Optional[str]
    currency: Optional[str]
    subtotal: Optional[float]
    tax: Optional[float]
    total: Optional[float]
    document_type: str
    lines: List[ExpectedLine]
    should_flag: bool
    references: List[str]
    scored: Tuple[str, ...]
    secondary: Optional[Tuple[str, float]] = None
    notes: str = ""

    def as_dict(self) -> Dict:
        return {
            "vendor_name": self.vendor_name,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "currency": self.currency,
            "subtotal": self.subtotal,
            "tax": self.tax,
            "total": self.total,
            "document_type": self.document_type,
            "lines": [
                {"description": ln.description, "amount": ln.amount, "alt_amounts": list(ln.alt_amounts)}
                for ln in self.lines
            ],
            "should_flag": self.should_flag,
            "references": list(self.references),
            "scored": list(self.scored),
            "secondary": list(self.secondary) if self.secondary else None,
            "notes": self.notes,
        }


# The header fields "fully correct" requires (when the document is scored on them).
KEY_FIELDS = (
    "vendor_name", "invoice_number", "invoice_date", "due_date", "currency",
    "subtotal", "tax", "total", "document_type",
)
ALL_FIELDS = KEY_FIELDS + ("line_items", "flag", "references")


@dataclass(frozen=True)
class DocSpec:
    doc_id: str
    category: str
    difficulty: str
    description: str
    vendor: Party
    customer: Party
    issue_date: date
    currency: str
    money_style: MoneyStyle
    date_style: str = "ISO"
    kind: str = "invoice"           # invoice | credit_note | statement | multi_invoice
    title: str = "INVOICE"
    number: Optional[str] = None    # None: no number printed
    number_label: str = "Invoice No"
    due_date: Optional[date] = None
    po_number: Optional[str] = None
    po_label: str = "PO Number"
    terms: Optional[str] = None
    meta_extra: Tuple[Tuple[str, str], ...] = ()     # other printed label/value pairs
    trip_refs: Tuple[str, ...] = ()                  # load/trip references a reader should list
    lines: Tuple[Line, ...] = ()
    columns: str = "std"            # std | vat | code | pct | foreign | dual | hours
    charges: Tuple[Charge, ...] = ()
    taxes: Tuple[Tax, ...] = ()
    tax_inclusive: bool = False
    withholding: Optional[Tax] = None
    payable: Optional[Payable] = None
    subtotal_printed: Optional[float] = None   # override: a deliberately inconsistent document
    total_printed: Optional[float] = None
    print_negative: bool = True     # credit notes: print the amounts negative
    credit_ref: Optional[str] = None  # "Refer Inv No ..." on a credit note
    notes_text: Tuple[str, ...] = ()  # free text printed under the totals
    layout: Layout = Layout()
    render: Render = Render()
    should_flag: bool = False
    children: Tuple["DocSpec", ...] = ()          # multi_invoice: the invoices in the file
    statement_rows: Tuple[StatementRow, ...] = ()
    tags: Tuple[str, ...] = ()
    base_id: Optional[str] = None   # photos/scans: the clean document this one degrades

    # ---- arithmetic -------------------------------------------------------

    @property
    def line_sum(self) -> float:
        return money(sum(ln.amount for ln in self.lines))

    @property
    def discount(self) -> float:
        return money(sum(c.amount for c in self.charges if c.kind == "discount"))

    @property
    def shipping(self) -> float:
        return money(sum(c.amount for c in self.charges if c.kind == "shipping"))

    @property
    def fees(self) -> float:
        return money(sum(c.amount for c in self.charges if c.kind == "fees"))

    @property
    def tax_total(self) -> float:
        return money(sum(t.amount for t in self.taxes))

    @property
    def subtotal(self) -> float:
        """The net subtotal: the lines before tax. On a VAT-inclusive document
        the lines are gross, and the net is total - VAT."""
        if self.subtotal_printed is not None:
            return self.subtotal_printed
        if self.tax_inclusive:
            return money(self.line_sum - self.tax_total)
        return self.line_sum

    @property
    def computed_total(self) -> float:
        if self.tax_inclusive:
            return money(self.line_sum - self.discount + self.shipping + self.fees)
        return money(self.line_sum - self.discount + self.shipping + self.fees + self.tax_total)

    @property
    def total(self) -> float:
        return self.total_printed if self.total_printed is not None else self.computed_total

    @property
    def payable_total(self) -> Optional[float]:
        if self.payable is None:
            return None
        return money(self.payable_subtotal + self.payable.tax)

    @property
    def payable_subtotal(self) -> float:
        assert self.payable is not None
        return money(sum(self.payable_line(ln) for ln in self.lines))

    def payable_line(self, ln: Line) -> float:
        assert self.payable is not None
        if ln.payable_amount is not None:
            return ln.payable_amount
        return money(ln.amount * self.payable.rate)

    @property
    def is_credit(self) -> bool:
        return self.kind == "credit_note"

    @property
    def severity(self) -> Optional[str]:
        return self.render.severity

    def signed(self, x: float) -> float:
        return -x if (self.is_credit and self.print_negative) else x

    # ---- the answer key ----------------------------------------------------

    def expected(self) -> Expected:
        if self.kind == "multi_invoice":
            first = self.children[0].expected()
            first.notes = (
                f"{len(self.children)} invoices in one file. Scored against the first "
                "invoice; the file should be flagged for a person to split."
            )
            first.should_flag = True
            return first
        if self.kind == "statement":
            return Expected(
                vendor_name=self.vendor.name, invoice_number=None,
                invoice_date=self.issue_date.isoformat(), due_date=None,
                currency=self.currency, subtotal=None, tax=None, total=None,
                document_type="other", lines=[], should_flag=False, references=[],
                scored=("vendor_name", "document_type"),
                notes="A statement is not a bill; the right outcome is document_type 'other'.",
            )

        scored = ["vendor_name", "invoice_number", "invoice_date", "currency",
                  "subtotal", "tax", "total", "document_type", "line_items", "flag"]
        if self.due_date is not None:
            scored.append("due_date")
        if self.trip_refs:
            scored.append("references")

        lines = [
            ExpectedLine(
                ln.description,
                ln.amount,
                (self.payable_line(ln),) if (self.payable and self.payable.line_column) else (),
            )
            for ln in self.lines
        ]
        currency, subtotal, tax, total = self.currency, self.subtotal, self.tax_total, self.total
        secondary = None
        notes = ""
        if self.payable is not None:
            # Dual currency: the payable box is the total, in its currency;
            # the line-currency total is the secondary.
            currency = self.payable.currency
            total = self.payable_total
            tax = self.payable.tax
            subtotal = money(total - tax)
            secondary = (self.currency, self.total)
            notes = "Dual currency: the amount-payable box is the total, in its currency."
        if self.withholding is not None:
            notes = ("Withholding is deducted at payment; the expected total is the invoice "
                     "total before it.")
        return Expected(
            vendor_name=self.vendor.name,
            invoice_number=self.number,
            invoice_date=self.issue_date.isoformat(),
            due_date=self.due_date.isoformat() if self.due_date else None,
            currency=currency,
            subtotal=subtotal,
            tax=tax,
            total=total,
            document_type="credit_note" if self.is_credit else "invoice",
            lines=lines,
            should_flag=self.should_flag,
            references=list(self.trip_refs),
            scored=tuple(scored),
            secondary=secondary,
            notes=notes,
        )

    # ---- self-check ----------------------------------------------------------

    def validate(self) -> None:
        """Catch a typo in a spec: the printed arithmetic must add up unless
        the spec says it deliberately does not."""
        if self.kind in ("multi_invoice",):
            for child in self.children:
                child.validate()
            return
        if self.kind == "statement":
            return
        if not self.lines:
            raise ValueError(f"{self.doc_id}: no line items")
        consistent = (
            abs(self.subtotal - (money(self.line_sum - self.tax_total) if self.tax_inclusive else self.line_sum)) <= 0.005
            and abs(self.total - self.computed_total) <= 0.005
        )
        if self.should_flag and consistent:
            raise ValueError(f"{self.doc_id}: marked should_flag but its arithmetic is consistent")
        if not self.should_flag and not consistent:
            raise ValueError(
                f"{self.doc_id}: subtotal {self.subtotal}/{self.line_sum} or total "
                f"{self.total}/{self.computed_total} does not add up"
            )
        for ln in self.lines:
            if ln.qty is not None and ln.unit_price is not None and ln.pct is None:
                if abs(money(ln.qty * ln.unit_price) - ln.amount) > 0.011:
                    raise ValueError(f"{self.doc_id}: line '{ln.description}' qty x price != amount")
        if self.difficulty not in DIFFICULTIES:
            raise ValueError(f"{self.doc_id}: difficulty {self.difficulty!r}")
        for d in self.render.degradations:
            if d.severity not in SEVERITIES:
                raise ValueError(f"{self.doc_id}: severity {d.severity!r}")


def validate_all(specs: Sequence[DocSpec]) -> None:
    ids = [s.doc_id for s in specs]
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise ValueError(f"duplicate doc ids: {dupes}")
    for s in specs:
        s.validate()


__all__ = [
    "money", "fmt_date", "DATE_STYLES", "NumberStyle", "MoneyStyle", "US_NUM", "EU_NUM",
    "ZA_NUM", "ZA_DOT_NUM", "PLAIN_NUM", "Party", "Line", "Charge", "Tax", "Payable",
    "StatementRow", "Layout", "Degradation", "Render", "DocSpec", "Expected",
    "ExpectedLine", "KEY_FIELDS", "ALL_FIELDS", "SEVERITIES", "DIFFICULTIES", "validate_all",
]
