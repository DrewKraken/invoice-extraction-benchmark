"""
DocSpec -> pages of drawing operations.

One layout engine feeds both renderers (render.py): reportlab for a digital
PDF with a real text layer, Pillow for the raster a phone photo or a scan
starts from. Measuring text with reportlab's font metrics in both keeps the
two renderings identical, so a photo of an invoice is a photo of exactly the
PDF the clean category scores.

Coordinates are PDF points (1/72 inch) from the TOP-left corner; a Text's
`y` is its baseline.

Besides the drawing, every page records:
  * `tables`: the line-item table as cells, and
  * the text in reading order (`page_text`).
Neither is written to the corpus; they are there for anyone who wants a
perfect "reading" of a page to test their own post-processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from reportlab.pdfbase.pdfmetrics import stringWidth

from .spec import DocSpec, Line, fmt_date, money

RGB = Tuple[int, int, int]
BLACK: RGB = (0, 0, 0)
GREY: RGB = (110, 110, 110)
LIGHT: RGB = (236, 236, 236)
WHITE: RGB = (255, 255, 255)
INK_BLUE: RGB = (20, 40, 140)

# Logical font -> reportlab standard font (metrics) ; render.py maps the same
# names to the matching Type 1 files for Pillow.
PDF_FONTS = {
    "sans": "Helvetica", "sans-bold": "Helvetica-Bold",
    "serif": "Times-Roman", "serif-bold": "Times-Bold",
    "mono": "Courier", "mono-bold": "Courier-Bold",
    "hand": "Helvetica-Oblique",
}


def text_width(text: str, font: str, size: float) -> float:
    w = stringWidth(text, PDF_FONTS.get(font, "Helvetica"), size)
    return w * 1.08 if font == "hand" else w


@dataclass
class Text:
    x: float
    y: float
    text: str
    font: str = "sans"
    size: float = 9.0
    color: RGB = BLACK
    align: str = "left"            # left | right | center: x is the anchor
    hand: Optional[str] = None     # handwriting legibility: neat | average | poor

    @property
    def left(self) -> float:
        w = text_width(self.text, self.font, self.size)
        if self.align == "right":
            return self.x - w
        if self.align == "center":
            return self.x - w / 2
        return self.x


@dataclass
class Rule:
    x1: float
    y1: float
    x2: float
    y2: float
    width: float = 0.6
    color: RGB = BLACK


@dataclass
class Box:
    x: float
    y: float          # top
    w: float
    h: float
    fill: Optional[RGB] = None
    stroke: Optional[RGB] = None
    width: float = 0.6


@dataclass
class TableModel:
    headers: List[str]
    rows: List[List[str]]


@dataclass
class Page:
    width: float
    height: float
    ops: List[object] = field(default_factory=list)
    tables: List[TableModel] = field(default_factory=list)


A4 = (595.28, 841.89)
LETTER = (612.0, 792.0)


def page_text(page: Page) -> str:
    """The page's words in reading order: rows by baseline, left to right."""
    texts = sorted((op for op in page.ops if isinstance(op, Text) and op.text.strip()),
                   key=lambda t: (t.y, t.left))
    rows: List[List[Text]] = []
    for t in texts:
        if rows and abs(rows[-1][0].y - t.y) <= 3.0:
            rows[-1].append(t)
        else:
            rows.append([t])
    return "\n".join(" ".join(t.text for t in sorted(r, key=lambda t: t.left)) for r in rows)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _qty(spec: DocSpec, q: Optional[float]) -> str:
    if q is None:
        return ""
    if abs(q - round(q)) < 1e-9:
        return str(int(round(q)))
    return spec.money_style.numbers.fmt(q, 2 if abs(q * 100 - round(q * 100)) < 1e-9 else 3)


def _num(spec: DocSpec, x: Optional[float]) -> str:
    if x is None:
        return ""
    return spec.money_style.numbers.fmt(x)


def _cell_money(spec: DocSpec, x: float) -> str:
    """A table cell amount: number only, signed as the document prints it."""
    v = spec.signed(x)
    if v < 0:
        s = spec.money_style.numbers.fmt(-v)
        style = spec.money_style.negative
        if style == "brackets":
            return f"({s})"
        if style == "cr_suffix":
            return f"{s} CR"
        return f"-{s}"
    return spec.money_style.numbers.fmt(v)


def _wrap(text: str, font: str, size: float, width: float) -> List[str]:
    words = text.split()
    lines: List[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if text_width(trial, font, size) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


# ---------------------------------------------------------------------------
# The invoice layout
# ---------------------------------------------------------------------------


class _Builder:
    def __init__(self, spec: DocSpec):
        self.spec = spec
        lay = spec.layout
        w, h = A4 if lay.paper == "A4" else LETTER
        if lay.landscape:
            w, h = h, w
        self.W, self.H = w, h
        self.M = 38.0
        self.pages: List[Page] = []
        self.fam = lay.family
        self.bold = f"{lay.family}-bold"
        self.hand = spec.render.handwriting
        self.y = 0.0
        self.new_page()

    # -- primitives

    @property
    def page(self) -> Page:
        return self.pages[-1]

    def new_page(self) -> None:
        self.pages.append(Page(self.W, self.H))
        self.y = self.M + 6

    def t(self, x, y, text, font=None, size=9.0, color=BLACK, align="left", value=False):
        """Draw text. `value=True` marks a filled-in value: handwritten when the
        document is a hand-filled form."""
        if text is None or text == "":
            return
        if value and self.hand:
            self.page.ops.append(Text(x, y, str(text), "hand", size * 1.15, INK_BLUE, align, self.hand))
        else:
            self.page.ops.append(Text(x, y, str(text), font or self.fam, size, color, align))

    def rule(self, x1, y1, x2, y2, width=0.6, color=BLACK):
        self.page.ops.append(Rule(x1, y1, x2, y2, width, color))

    def box(self, x, y, w, h, fill=None, stroke=None, width=0.6):
        self.page.ops.append(Box(x, y, w, h, fill, stroke, width))

    def money(self, x: float, symbol: bool = True) -> str:
        return self.spec.money_style.fmt(self.spec.signed(x), with_symbol=symbol)

    # -- blocks

    def vendor_lines(self) -> List[str]:
        v = self.spec.vendor
        out = list(v.address)
        contact = " | ".join(p for p in (v.phone and f"Tel {v.phone}", v.email) if p)
        if contact:
            out.append(contact)
        if v.tax_id:
            out.append(f"{v.tax_label}: {v.tax_id}")
        return out

    def meta_rows(self) -> List[Tuple[str, str]]:
        s = self.spec
        rows: List[Tuple[str, str]] = []
        if s.number:
            rows.append((s.number_label, s.number))
        rows.append(("Date" if s.kind != "credit_note" else "Credit Date", fmt_date(s.issue_date, s.date_style)))
        if s.due_date:
            rows.append(("Due Date", fmt_date(s.due_date, s.date_style)))
        if s.po_number:
            rows.append((s.po_label, s.po_number))
        if s.terms:
            rows.append(("Terms", s.terms))
        if s.credit_ref:
            rows.append(("Refer Inv No", s.credit_ref))
        rows.extend(s.meta_extra)
        if s.layout.show_currency_header:
            rows.append(("Currency", s.currency))
        return rows

    def header(self) -> None:
        s, lay = self.spec, self.spec.layout
        L, R = self.M, self.W - self.M
        top = self.y
        meta = self.meta_rows()
        if lay.header == "banner":
            self.box(0, 0, self.W, 62, fill=lay.accent)
            self.t(L, 38, s.vendor.name, self.bold, 16, WHITE)
            self.t(R, 38, s.title, self.bold, 18, WHITE, "right")
            y = 80
            for ln in self.vendor_lines():
                self.t(L, y, ln, size=8.5)
                y += 11
            my = 80
            for label, val in meta:
                self.t(R - 120, my, f"{label}:", size=8.5, color=GREY, align="right")
                self.t(R, my, val, self.bold, 9, align="right", value=True)
                my += 12
            self.y = max(y, my) + 8
            return
        if lay.header == "center":
            cx = self.W / 2
            self.t(cx, top + 12, s.vendor.name, self.bold, 16, lay.accent, "center")
            y = top + 26
            for ln in self.vendor_lines():
                self.t(cx, y, ln, size=8.5, align="center")
                y += 10.5
            self.rule(L, y, R, y, 0.8, lay.accent)
            y += 20
            self.t(cx, y, s.title, self.bold, 17, lay.accent, "center")
            y += 18
            half = (len(meta) + 1) // 2
            for i, (label, val) in enumerate(meta):
                col_x = L if i < half else self.W / 2 + 10
                row_y = y + (i if i < half else i - half) * 12
                self.t(col_x, row_y, f"{label}:", size=8.5, color=GREY)
                self.t(col_x + 95, row_y, val, self.bold, 9, value=True)
            self.y = y + half * 12 + 10
            return
        # left / right
        vendor_right = lay.header == "right"
        vx, va = (R, "right") if vendor_right else (L, "left")
        mx_label, mx_val = (L, L + 105) if vendor_right else (R - 120, R)
        name_x = vx
        if lay.logo:
            initials = "".join(w[0] for w in s.vendor.name.split()[:2]).upper()
            lx = R - 34 if vendor_right else L
            self.box(lx, top, 34, 34, fill=lay.accent)
            self.t(lx + 17, top + 22, initials, self.bold, 13, WHITE, "center")
            name_x = (R - 42) if vendor_right else (L + 42)
        self.t(name_x, top + 12, s.vendor.name, self.bold, 14, lay.accent, va)
        y = top + 48 if lay.logo else top + 26
        for ln in self.vendor_lines():
            self.t(vx, y, ln, size=8.5, align=va)
            y += 10.5
        ty = top + 14
        self.t(L if vendor_right else R, ty, s.title, self.bold, 19, lay.accent, "left" if vendor_right else "right")
        my = ty + 20
        for label, val in meta:
            if vendor_right:
                self.t(mx_label, my, f"{label}:", size=8.5, color=GREY)
                self.t(mx_val, my, val, self.bold, 9, value=True)
            else:
                self.t(mx_label, my, f"{label}:", size=8.5, color=GREY, align="right")
                self.t(mx_val, my, val, self.bold, 9, align="right", value=True)
            my += 12
        self.y = max(y, my) + 10

    def bill_to(self) -> None:
        s, lay = self.spec, self.spec.layout
        L, R = self.M, self.W - self.M
        c = s.customer
        label = "BILL TO" if s.kind != "credit_note" else "CREDIT TO"
        lines = [c.name] + list(c.address) + ([f"{c.tax_label}: {c.tax_id}"] if c.tax_id else [])
        if lay.two_column:
            h = 16 + 11 * len(lines)
            colw = (R - L - 16) / 2
            self.box(L, self.y, colw, h, stroke=GREY)
            self.box(L + colw + 16, self.y, colw, h, stroke=GREY)
            self.t(L + 6, self.y + 11, label, self.bold, 8.5, lay.accent)
            self.t(L + colw + 22, self.y + 11, "DELIVER TO", self.bold, 8.5, lay.accent)
            for i, ln in enumerate(lines):
                self.t(L + 6, self.y + 24 + i * 11, ln, self.bold if i == 0 else None, 9, value=True)
                self.t(L + colw + 22, self.y + 24 + i * 11, ln if i < len(lines) - (1 if c.tax_id else 0) else "",
                       self.bold if i == 0 else None, 9, value=True)
            self.y += h + 14
            return
        self.t(L, self.y + 8, label, self.bold, 9, lay.accent)
        y = self.y + 21
        for i, ln in enumerate(lines):
            self.t(L, y, ln, self.bold if i == 0 else None, 9.5 if i == 0 else 9, value=True)
            y += 11
        self.y = y + 10

    # -- line items

    def columns(self) -> List[Tuple[str, str, float, str]]:
        """(key, header, width share, align) for the spec's column set."""
        s = self.spec
        cur = s.currency
        sets = {
            "std": [("desc", "Description", 0.0, "left"), ("qty", "Qty", 0.09, "right"),
                    ("unit", "Unit Price", 0.15, "right"), ("amount", "Amount", 0.16, "right")],
            "code": [("code", "Code", 0.11, "left"), ("desc", "Description", 0.0, "left"),
                     ("qty", "Qty", 0.08, "right"), ("unit", "Price", 0.14, "right"),
                     ("amount", "Total", 0.15, "right")],
            "vat": [("desc", "Description", 0.0, "left"), ("qty", "Qty", 0.08, "right"),
                    ("unit", "Unit Price", 0.14, "right"), ("vat", "VAT %", 0.08, "right"),
                    ("amount", "Amount Excl", 0.15, "right")],
            "hours": [("desc", "Description", 0.0, "left"), ("qty", "Hours", 0.09, "right"),
                      ("unit", "Rate", 0.13, "right"), ("amount", "Amount", 0.15, "right")],
            "pct": [("desc", "Description", 0.0, "left"), ("qty", "Qty / Value", 0.15, "right"),
                    ("unit", "Rate", 0.11, "right"), ("amount", "Amount", 0.15, "right")],
            "foreign": [("desc", "Description", 0.0, "left"), ("fccy", "Ccy", 0.07, "left"),
                        ("famt", "Foreign Amt", 0.14, "right"), ("frate", "Rate", 0.10, "right"),
                        ("amount", f"Amount {cur}", 0.16, "right")],
            "dual": [("desc", "Description", 0.0, "left"), ("qty", "Qty", 0.07, "right"),
                     ("unit", f"Unit {cur}", 0.13, "right"), ("amount", f"Amount {cur}", 0.14, "right")],
            "simple": [("desc", "Description", 0.0, "left"), ("amount", "Amount", 0.18, "right")],
        }
        cols = list(sets[s.columns])
        if s.columns == "dual" and s.payable and s.payable.line_column:
            cols.append(("pay", f"Amount {s.payable.currency}", 0.15, "right"))
        return cols

    def cell(self, key: str, ln: Line) -> str:
        s = self.spec
        if key == "desc":
            return ln.description
        if key == "code":
            return ln.code or ""
        if key == "qty":
            if ln.pct is not None:
                return s.money_style.numbers.fmt(ln.qty or 0.0, 3) if ln.qty is not None else ""
            return _qty(s, ln.qty)
        if key == "unit":
            if ln.pct is not None:
                return f"{s.money_style.numbers.fmt(ln.pct * 100, 2)}%"
            return _num(s, ln.unit_price)
        if key == "vat":
            return "" if ln.vat_rate is None else f"{s.money_style.numbers.fmt(ln.vat_rate * 100, 0)}%"
        if key == "amount":
            return _cell_money(s, ln.amount)
        if key == "fccy":
            return ln.foreign[0] if ln.foreign else s.currency
        if key == "famt":
            return _num(s, ln.foreign[1]) if ln.foreign else ""
        if key == "frate":
            return s.money_style.numbers.fmt(ln.foreign[2], 4) if ln.foreign else ""
        if key == "pay":
            return _cell_money(s, s.payable_line(ln))
        return ""

    def table(self) -> None:
        s, lay = self.spec, self.spec.layout
        L, R = self.M, self.W - self.M
        width = R - L
        cols = self.columns()
        fixed = sum(c[2] for c in cols)
        widths = [(c[2] or (1.0 - fixed)) * width for c in cols]
        xs = [L]
        for w_ in widths[:-1]:
            xs.append(xs[-1] + w_)
        size = 8.6 if not self.hand else 9
        row_h = 15.0 if not self.hand else 19.0
        bottom_reserved = 150.0
        desc_i = [c[0] for c in cols].index("desc")
        desc_w = widths[desc_i] - 8
        running = 0.0
        table_rows: List[List[str]] = []
        headers = [c[1] for c in cols]

        def draw_header():
            hh = 17.0
            if lay.table in ("band", "zebra"):
                fill = lay.accent if lay.table == "band" else LIGHT
                color = WHITE if lay.table == "band" else BLACK
                self.box(L, self.y, width, hh, fill=fill)
            else:
                color = BLACK
            for (key, head, _w, align), x, w_ in zip(cols, xs, widths):
                ax = x + 4 if align == "left" else x + w_ - 4
                self.t(ax, self.y + 12, head, self.bold, 8.4, color, align)
            if lay.table == "grid":
                self.box(L, self.y, width, hh, stroke=BLACK, width=0.8)
                for x in xs[1:]:
                    self.rule(x, self.y, x, self.y + hh)
            if lay.table == "plain":
                self.rule(L, self.y + hh, R, self.y + hh, 0.9)
            self.y += hh

        draw_header()
        rows_on_page = 0
        for i, ln in enumerate(s.lines):
            desc_lines = _wrap(ln.description, "hand" if self.hand else self.fam, size, desc_w)
            h = row_h + (len(desc_lines) - 1) * (size + 2)
            if rows_on_page >= lay.rows_per_page or self.y + h > self.H - bottom_reserved + 40:
                # page break inside the table
                if lay.carried_forward:
                    self.t(xs[desc_i] + 4, self.y + 13, "Carried forward", self.bold, size)
                    self.t(R - 4, self.y + 13, _cell_money(s, running), self.bold, size, align="right")
                self.footer_note("Continued on next page")
                self.new_page()
                self.continuation_header()
                draw_header()
                rows_on_page = 0
                if lay.carried_forward:
                    self.t(xs[desc_i] + 4, self.y + 12, "Brought forward", self.bold, size)
                    self.t(R - 4, self.y + 12, _cell_money(s, running), self.bold, size, align="right")
                    self.y += row_h
            if lay.table == "zebra" and i % 2 == 1:
                self.box(L, self.y, width, h, fill=(246, 246, 246))
            row_cells = []
            for (key, _head, _w, align), x, w_ in zip(cols, xs, widths):
                txt = self.cell(key, ln)
                row_cells.append(txt)
                if key == "desc":
                    for j, part in enumerate(desc_lines):
                        self.t(x + 4, self.y + 11 + j * (size + 2), part, size=size, value=True)
                else:
                    ax = x + 4 if align == "left" else x + w_ - 4
                    self.t(ax, self.y + 11, txt, size=size, align=align, value=True)
            if lay.table == "grid":
                self.box(L, self.y, width, h, stroke=BLACK, width=0.5)
                for x in xs[1:]:
                    self.rule(x, self.y, x, self.y + h, 0.5)
            table_rows.append(row_cells)
            self.y += h
            running = money(running + ln.amount)
            rows_on_page += 1
            # table model per page: store on the page where the row landed
            if not self.page.tables:
                self.page.tables.append(TableModel(headers, []))
            self.page.tables[-1].rows.append(row_cells)
        if lay.table in ("band", "plain", "zebra"):
            self.rule(L, self.y + 2, R, self.y + 2, 0.8, lay.accent if lay.table == "band" else BLACK)
        self.y += 14

    def continuation_header(self) -> None:
        s = self.spec
        label = f"{s.title} {s.number}" if s.number else s.title
        self.t(self.M, self.y + 8, s.vendor.name, self.bold, 10)
        self.t(self.W - self.M, self.y + 8, f"{label} (continued)", size=8.5, align="right")
        self.y += 24

    def footer_note(self, text: str) -> None:
        self.t(self.W / 2, self.H - self.M + 2, text, size=7.5, color=GREY, align="center")

    # -- totals

    def totals_rows(self) -> List[Tuple[str, str, bool]]:
        s = self.spec
        rows: List[Tuple[str, str, bool]] = []
        sub_printed = s.subtotal_printed if s.subtotal_printed is not None else (
            s.line_sum if not s.tax_inclusive else None)
        order = s.layout.totals_order
        if s.tax_inclusive:
            gross = s.line_sum
            if order == "inclusive_sub":
                rows.append(("Sub Total", self.money(gross), False))
                for t in s.taxes:
                    rows.append((f"{t.label} (included)", self.money(t.amount), False))
                rows.append(("TOTAL", self.money(s.total), True))
            else:
                rows.append(("TOTAL (VAT inclusive)", self.money(s.total), True))
                for t in s.taxes:
                    rows.append((f"{t.label} included in total", self.money(t.amount), False))
            return rows
        if order == "sage":
            rows.append(("Total Exclusive", self.money(sub_printed), False))
            for c in s.charges:
                rows.append((c.label, self.money(-c.amount if c.kind == "discount" else c.amount), False))
            rows.append(("Total VAT", self.money(s.tax_total), False))
            rows.append(("Sub Total", self.money(s.total), False))
            rows.append(("Total", self.money(s.total), True))
            return rows
        rows.append(("Subtotal", self.money(sub_printed), False))
        for c in s.charges:
            rows.append((c.label, self.money(-c.amount if c.kind == "discount" else c.amount), False))
        for t in s.taxes:
            rows.append((t.label, self.money(t.amount), False))
        total_label = "TOTAL" if s.payable is None else f"TOTAL {s.currency}"
        if s.kind == "credit_note":
            total_label = "TOTAL CREDIT"
        rows.append((total_label, self.money(s.total), True))
        if s.withholding is not None:
            rows.append((s.withholding.label, self.money(-s.withholding.amount), False))
            rows.append(("Net Amount Due", self.money(money(s.total - s.withholding.amount)), True))
        return rows

    def totals(self) -> None:
        s, lay = self.spec, self.spec.layout
        R = self.W - self.M
        rows = self.totals_rows()
        needed = 18 * len(rows) + (70 if s.payable else 0) + 40
        if self.y + needed > self.H - self.M - 20:
            self.footer_note("Continued on next page")
            self.new_page()
            self.continuation_header()
        label_x = R - 135
        top = self.y
        for label, amount, emph in rows:
            if emph:
                self.rule(label_x - 60, self.y + 1, R, self.y + 1, 0.9, lay.accent)
                self.y += 4
            font = self.bold if emph else None
            size = 10.5 if emph else 9.2
            self.t(label_x, self.y + 11, label, font, size, align="right")
            self.t(R, self.y + 11, amount, font, size, align="right", value=True)
            self.y += 16 if not emph else 18
        if lay.totals_box:
            self.box(label_x - 70, top - 4, R - label_x + 76, self.y - top + 6, stroke=GREY)
        if s.payable is not None:
            p = s.payable
            self.y += 10
            if p.tax:
                self.t(R - 150, self.y + 10, f"VAT {p.currency}", size=9, align="right")
                self.t(R, self.y + 10, p.style.fmt(s.signed(p.tax)), size=9, align="right")
                self.y += 16
            note = f"Exchange rate: 1 {s.currency} = {s.money_style.numbers.fmt(p.rate, 4)} {p.currency}"
            self.t(self.M, self.y + 10, note, size=8.5, color=GREY)
            self.y += 18
            bw = self.W - 2 * self.M
            self.box(self.M, self.y, bw, 26, fill=LIGHT, stroke=BLACK, width=1.0)
            self.t(self.M + 8, self.y + 17, p.label, self.bold, 10.5)
            self.t(R - 130, self.y + 17, p.currency, self.bold, 10.5, align="right")
            self.t(R - 8, self.y + 17, p.style.fmt(s.signed(s.payable_total)), self.bold, 11, align="right",
                   value=True)
            self.y += 36
        self.y += 8

    def notes(self) -> None:
        s = self.spec
        lines: List[str] = list(s.notes_text)
        if s.vendor.bank:
            lines.append("Banking details: " + "  ".join(s.vendor.bank))
        for ln in lines:
            for part in _wrap(ln, self.fam, 8, self.W - 2 * self.M):
                if self.y > self.H - self.M - 18:
                    return
                self.t(self.M, self.y + 9, part, size=8, color=GREY)
                self.y += 10.5

    def footers(self) -> None:
        n = len(self.pages)
        for i, pg in enumerate(self.pages, 1):
            pg.ops.append(Text(self.W - self.M, self.H - 18, f"Page {i} of {n}", self.fam, 7.5, GREY, "right"))

    def build(self) -> List[Page]:
        self.header()
        self.bill_to()
        self.table()
        self.totals()
        self.notes()
        self.footers()
        return self.pages


def build_invoice(spec: DocSpec) -> List[Page]:
    return _Builder(spec).build()


# ---------------------------------------------------------------------------
# Statement
# ---------------------------------------------------------------------------


def build_statement(spec: DocSpec) -> List[Page]:
    b = _Builder(spec)
    b.header()
    b.bill_to()
    s = spec
    L, R = b.M, b.W - b.M
    cols = [("Date", L + 4, "left"), ("Reference", L + 80, "left"), ("Description", L + 170, "left"),
            ("Debit", R - 170, "right"), ("Credit", R - 90, "right"), ("Balance", R - 4, "right")]
    b.box(L, b.y, R - L, 17, fill=LIGHT)
    for head, x, al in cols:
        b.t(x, b.y + 12, head, b.bold, 8.5, align=al)
    b.y += 17
    bal = 0.0
    rows = []
    for row in s.statement_rows:
        bal = money(bal + row.debit - row.credit)
        cells = [fmt_date(row.when, s.date_style), row.reference, row.description,
                 _num(s, row.debit) if row.debit else "", _num(s, row.credit) if row.credit else "", _num(s, bal)]
        rows.append(cells)
        for (head, x, al), txt in zip(cols, cells):
            b.t(x, b.y + 11, txt, size=8.6, align=al)
        b.y += 15
    b.page.tables.append(TableModel([c[0] for c in cols], rows))
    b.rule(L, b.y + 2, R, b.y + 2)
    b.y += 18
    ages = ["Current", "30 Days", "60 Days", "90 Days+"]
    split = [money(bal * 0.55), money(bal * 0.3), money(bal * 0.15), 0.0]
    split[0] = money(bal - split[1] - split[2])
    for i, (a, v) in enumerate(zip(ages, split)):
        x = L + i * (R - L) / 4
        b.box(x, b.y, (R - L) / 4, 30, stroke=GREY)
        b.t(x + 6, b.y + 11, a, size=8, color=GREY)
        b.t(x + (R - L) / 4 - 6, b.y + 24, _num(s, v), b.bold, 9, align="right")
    b.y += 44
    b.t(R - 140, b.y + 10, "Balance Due", b.bold, 10.5, align="right")
    b.t(R, b.y + 10, s.money_style.fmt(bal), b.bold, 10.5, align="right")
    b.y += 30
    b.t(L, b.y, "Please remit the balance due. This statement is not a tax invoice.", size=8, color=GREY)
    b.footers()
    return b.pages


def build_pages(spec: DocSpec) -> List[Page]:
    if spec.kind == "multi_invoice":
        pages: List[Page] = []
        for child in spec.children:
            pages.extend(build_invoice(child))
        return pages
    if spec.kind == "statement":
        return build_statement(spec)
    return build_invoice(spec)


def document_text(pages: Sequence[Page]) -> str:
    return "\n".join(page_text(p) for p in pages)
