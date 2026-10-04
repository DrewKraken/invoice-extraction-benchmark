"""
Field-level scoring: what a reader returned against what the document prints.

Pure functions, no I/O. `score_document(expected, extracted)` returns one
FieldResult per scored field; evaluate.py aggregates them. These are the
rules InvoiceParser Pro's published benchmark run was scored with.

Rules:

  vendor_name     normalised fuzzy match: case, punctuation and legal-form
                  words ("(Pty) Ltd", "LLC", "GmbH"...) ignored, then
                  similarity >= 0.85 or one name containing the other
  invoice_number  exact after normalisation (case, spaces, '#', leading
                  "No."); not printed -> correct only when left empty
  dates           the ISO date
  currency        the ISO code
  money           exact to the cent (|diff| < 0.005) is "correct"; a
                  +-1 cent band is reported beside it. Credit notes compare
                  magnitudes (the credit-note decision is document_type)
  line_items      greedy match: amount within a cent (an alternative amount,
                  e.g. the payable-currency column, also counts) and
                  description similarity >= 0.6; correct = F1 of 1.0
  document_type   invoice / credit_note / other
  flag            an inconsistent document (and a file holding several
                  invoices) must be flagged; a consistent one must not
  references      every printed trip/load reference listed
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Sequence, Tuple

CENT = 0.005
BAND = 0.0101

_LEGAL = {"pty", "ltd", "limited", "llc", "inc", "co", "corp", "corporation", "cc", "plc", "gmbh", "kg",
          "bv", "sarl", "sas", "the", "company", "and"}
_EMPTY = {"", "n/a", "na", "none", "null", "unknown", "-"}


@dataclass
class FieldResult:
    field: str
    correct: bool
    expected: Any = None
    got: Any = None
    within_band: Optional[bool] = None    # money: within +-1 cent
    detail: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# normalisers
# ---------------------------------------------------------------------------


def _ascii(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()


def norm_name(s: Optional[str]) -> str:
    if not s:
        return ""
    s = _ascii(s).casefold().replace("&", " and ")
    s = re.sub(r"\(pty\)", " pty ", s)
    words = re.findall(r"[a-z0-9]+", s)
    return " ".join(w for w in words if w not in _LEGAL)


def vendor_match(got: Optional[str], expected: Optional[str]) -> Tuple[bool, float]:
    a, b = norm_name(got), norm_name(expected)
    if not a or not b:
        return (not a and not b), 0.0
    if a == b:
        return True, 1.0
    ratio = SequenceMatcher(None, a, b).ratio()
    short, long_ = sorted((a, b), key=len)
    contains = short in long_ and len(short) >= 0.6 * len(long_)
    return (ratio >= 0.85 or contains), round(ratio, 3)


def norm_number(s: Optional[str]) -> str:
    if s is None:
        return ""
    s = _ascii(str(s)).upper().strip()
    # a label read along with the value: "Invoice No: 123", "No. 123"
    s = re.sub(r"^(?:(?:TAX\s+)?INVOICE\s*(?:NO\.?|NUMBER|#)?|NO\.?)\s*[:#]?\s+(?=\S)", "", s)
    s = re.sub(r"[\s#:]", "", s)
    return "" if s.lower() in _EMPTY else s


def norm_date(s: Any) -> Optional[str]:
    if s is None or s == "":
        return None
    if isinstance(s, date):
        return s.isoformat()
    text = str(s).strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if m:
        return m.group(0)[:10]
    try:
        from dateutil import parser

        return parser.parse(text, dayfirst=True).date().isoformat()
    except Exception:
        return text


def norm_currency(s: Any) -> Optional[str]:
    if not s:
        return None
    t = str(s).strip().upper()
    return None if t.lower() in _EMPTY else t


def to_num(x: Any) -> Optional[float]:
    if x is None or isinstance(x, bool):
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        try:
            return float(str(x).replace(",", "").replace(" ", ""))
        except ValueError:
            return None


def desc_similarity(a: str, b: str) -> float:
    na, nb = " ".join(re.findall(r"[a-z0-9]+", _ascii(a or "").casefold())), \
        " ".join(re.findall(r"[a-z0-9]+", _ascii(b or "").casefold()))
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    short, long_ = sorted((na, nb), key=len)
    if short in long_ and len(short) >= 0.5 * len(long_):
        return 0.95
    return SequenceMatcher(None, na, nb).ratio()


# ---------------------------------------------------------------------------
# field scorers
# ---------------------------------------------------------------------------


def score_money(name: str, got: Any, expected: Optional[float], *, magnitude: bool,
                none_is_zero: bool = False) -> FieldResult:
    g = to_num(got)
    if g is None and none_is_zero:
        g = 0.0
    if g is None:
        return FieldResult(name, False, expected, got, False, "missing")
    e = float(expected)
    a, b = (abs(g), abs(e)) if magnitude else (g, e)
    diff = abs(a - b)
    return FieldResult(name, diff < CENT, expected, g, diff <= BAND,
                       "" if diff < CENT else f"off by {diff:,.2f}")


def match_lines(got: Sequence[Dict[str, Any]], expected: Sequence[Dict[str, Any]], *, magnitude: bool
                ) -> Tuple[int, int, int]:
    """(matched, predicted, expected) under the greedy amount + description rule."""
    preds = []
    for li in got or []:
        amt = to_num(li.get("line_total") if li.get("line_total") is not None else li.get("total"))
        if amt is None:
            amt = to_num(li.get("amount"))
        preds.append((li.get("description") or "", amt))
    used = set()
    matched = 0
    for exp in expected:
        amounts = [exp["amount"]] + list(exp.get("alt_amounts") or [])
        best, best_sim = None, 0.6
        for i, (desc, amt) in enumerate(preds):
            if i in used or amt is None:
                continue
            a = abs(amt) if magnitude else amt
            if not any(abs(a - (abs(x) if magnitude else x)) <= 0.0101 for x in amounts):
                continue
            sim = desc_similarity(desc, exp["description"])
            if sim >= best_sim:
                best, best_sim = i, sim
        if best is not None:
            used.add(best)
            matched += 1
    return matched, len(preds), len(expected)


def f1(matched: int, predicted: int, expected: int) -> float:
    if expected == 0 and predicted == 0:
        return 1.0
    if matched == 0:
        return 0.0
    p, r = matched / predicted, matched / expected
    return 2 * p * r / (p + r)


def predicted_doc_type(ex: Dict[str, Any]) -> str:
    """invoice / credit_note / other. `is_credit: true` also means a credit
    note (the published run's output carried it); anything else that is not
    "other" or a credit note counts as an invoice."""
    dt = re.sub(r"[\s-]+", "_", (ex.get("document_type") or "").strip().lower())
    if ex.get("is_credit") or dt in ("credit_note", "credit_memo", "credit"):
        return "credit_note"
    if dt in ("other",):
        return "other"
    return "invoice"


def score_document(expected: Dict[str, Any], extracted: Optional[Dict[str, Any]]) -> List[FieldResult]:
    """Score one document. `extracted` is None when the reader returned
    nothing for it: every scored field is then wrong ("no result")."""
    scored = list(expected["scored"])
    out: List[FieldResult] = []
    if extracted is None:
        for f in scored:
            exp_val = expected.get("total" if f == "total" else f) if f not in ("line_items", "flag") else None
            out.append(FieldResult(f, False, exp_val, None, False if f in ("subtotal", "tax", "total") else None,
                                   "no result"))
        return out
    magnitude = expected["document_type"] == "credit_note"
    for f in scored:
        if f == "vendor_name":
            ok, ratio = vendor_match(extracted.get("vendor_name"), expected["vendor_name"])
            out.append(FieldResult(f, ok, expected["vendor_name"], extracted.get("vendor_name"),
                                   detail=f"similarity {ratio}"))
        elif f == "invoice_number":
            e, g = norm_number(expected["invoice_number"]), norm_number(extracted.get("invoice_number"))
            out.append(FieldResult(f, e == g, expected["invoice_number"], extracted.get("invoice_number"),
                                   detail="" if e == g else ("should be empty" if not e else "")))
        elif f in ("invoice_date", "due_date"):
            e, g = expected[f], norm_date(extracted.get(f))
            out.append(FieldResult(f, e == g, e, g))
        elif f == "currency":
            e, g = norm_currency(expected["currency"]), norm_currency(extracted.get("currency"))
            out.append(FieldResult(f, e == g, e, g))
        elif f in ("subtotal", "tax", "total"):
            key = "total_amount" if f == "total" else f
            out.append(score_money(f, extracted.get(key), expected[f], magnitude=magnitude,
                                   none_is_zero=(f == "tax" and not expected[f])))
        elif f == "document_type":
            g = predicted_doc_type(extracted)
            out.append(FieldResult(f, g == expected["document_type"], expected["document_type"], g))
        elif f == "line_items":
            m, p, e = match_lines(extracted.get("line_items") or [], expected["lines"], magnitude=magnitude)
            score = f1(m, p, e)
            out.append(FieldResult(f, score >= 0.999, e, p, detail=f"F1 {score:.2f} ({m} of {e} matched, {p} read)"))
        elif f == "flag":
            flagged = bool(extracted.get("flagged"))
            out.append(FieldResult(f, flagged == expected["should_flag"], expected["should_flag"], flagged))
        elif f == "references":
            got = {str(r.get("value", "")).casefold() for r in (extracted.get("references") or [])}
            want = [r.casefold() for r in expected["references"]]
            missing = [r for r in expected["references"] if r.casefold() not in got]
            out.append(FieldResult(f, not missing, expected["references"],
                                   [r.get("value") for r in extracted.get("references") or []],
                                   detail=f"missing {missing}" if missing else ""))
    return out


def line_f1(results: Sequence[FieldResult]) -> Optional[float]:
    for r in results:
        if r.field == "line_items":
            m = re.search(r"F1 ([0-9.]+)", r.detail)
            return float(m.group(1)) if m else (1.0 if r.correct else 0.0)
    return None


def fully_correct(results: Sequence[FieldResult], key_fields: Sequence[str]) -> bool:
    keyed = [r for r in results if r.field in key_fields]
    return bool(keyed) and all(r.correct for r in keyed)
