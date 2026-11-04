#!/usr/bin/env python3
"""Generate eight original synthetic invoices, their key, and frozen protocol.

Requires ReportLab. No extraction/provider calls or imports from accuracy_eval.
Output must not already exist: creating a different pack requires a new path.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

PACK_ID = "ipp-frozen-challenge-v1"
DATE = "2026-11-04"
SPECS = [
    ("usd-01", "USD", "Larkspur Example Services", "LXS-6101", "0", [
        ("Equipment inspection", "3", "42.50"), ("Site planning hours", "1.5", "96.00")]),
    ("usd-02", "USD", "Larkspur Example Services", "LXS-6102", "0", [
        ("Packing labels", "12", "8.75"), ("Assembly support hours", "2.25", "80.00")]),
    ("gbp-01", "GBP", "Bracken Example Studio", "BES-7201", "0.20", [
        ("Print preparation", "4", "32.50"), ("Proof review", "2", "47.25")]),
    ("gbp-02", "GBP", "Bracken Example Studio", "BES-7202", "0.20", [
        ("Design consultation hours", "1.5", "110.00"), ("Display panels", "6", "18.75")]),
    ("eur-01", "EUR", "Aster Example Supplies", "AES-8301", "0.20", [
        ("Storage trays", "7", "19.50"), ("Installation hours", "2.5", "64.00")]),
    ("eur-02", "EUR", "Aster Example Supplies", "AES-8302", "0.20", [
        ("Workshop cabinets", "3", "124.25"), ("Label holders", "8", "6.80")]),
    ("zar-01", "ZAR", "Cedar Example Engineering", "CEE-9401", "0.15", [
        ("Mounting brackets", "4", "245.75"), ("Calibration hours", "1.5", "560.00")]),
    ("zar-02", "ZAR", "Cedar Example Engineering", "CEE-9402", "0.15", [
        ("Seal kits", "6", "185.50"), ("Machining hours", "2.5", "320.00")]),
]


def money(value):
    return format(Decimal(value).quantize(Decimal("0.01")), ".2f")


def cases():
    out = {}
    for case_id, currency, vendor, number, rate, raw_lines in SPECS:
        lines = [{"description": d, "quantity": q, "unit_price": p, "amount": money(Decimal(q) * Decimal(p))} for d, q, p in raw_lines]
        subtotal = sum(Decimal(line["amount"]) for line in lines)
        tax = Decimal(money(subtotal * Decimal(rate)))
        total = subtotal + tax + (Decimal("40") if case_id == "zar-02" else 0)
        out[case_id] = {"file": f"invoices/{case_id}.pdf", "layout": currency.lower(),
                        "fields": {"vendor_name": vendor, "invoice_number": number, "invoice_date": "2026-11-03",
                                   "due_date": "2026-12-03", "currency": currency, "subtotal": money(subtotal),
                                   "tax": money(tax), "total": money(total), "document_type": "invoice"},
                        "lines": lines, "tax_rate": rate,
                        "math_status": "mismatch" if case_id == "zar-02" else "ok",
                        "note": "Printed total exceeds subtotal plus tax by ZAR 40.00; preserve the printed total and flag the arithmetic." if case_id == "zar-02" else "Printed arithmetic is consistent."}
    return out


def render(path, spec):
    # Four independent one-page layouts designed here; no old corpus renderer.
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import HexColor
    c = canvas.Canvas(str(path), pagesize=(595.28, 841.89), invariant=1, pageCompression=1)
    c.setTitle(spec["fields"]["invoice_number"])
    c.setAuthor("InvoiceParser Pro synthetic challenge")
    f, cur = spec["fields"], spec["fields"]["currency"]
    def text(x, y, s, size=10, bold=False, right=False):
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        (c.drawRightString if right else c.drawString)(x, y, str(s))
    def line(y):
        c.setStrokeColor(HexColor("#a7b4bd")); c.line(45, y, 550, y)
    def num(value):
        return value.replace(".", ",") if cur == "EUR" else value
    if cur == "USD":
        c.setFillColor(HexColor("#143a52")); c.rect(0, 715, 595.28, 126, fill=1, stroke=0)
        c.setFillColor(HexColor("#ffffff")); text(45, 788, f["vendor_name"], 20, True); text(45, 752, "INVOICE", 12, True)
        c.setFillColor(HexColor("#182c39")); text(45, 678, "Bill to: Example Client LLC", 11)
        text(550, 678, f["invoice_number"], 16, True, True)
        text(45, 643, "Invoice date: 03 November 2026"); text(550, 643, "Due: 03 December 2026", right=True)
        text(45, 615, "Currency: USD"); table_y, total_y = 557, 391
    elif cur == "GBP":
        c.setFillColor(HexColor("#285d4c")); c.rect(35, 674, 9, 119, fill=1, stroke=0)
        c.setFillColor(HexColor("#182c39")); text(60, 780, "INVOICE", 25, True); text(60, 750, f["vendor_name"], 16, True)
        text(550, 780, f["invoice_number"], 12, True, True); text(550, 750, "Currency: GBP", right=True)
        text(60, 705, "Invoice date: 03 November 2026"); text(60, 680, "Due date: 03 December 2026")
        text(45, 630, "Customer: Example Design Company", 12)
        table_y, total_y = 569, 405
    elif cur == "EUR":
        c.setFillColor(HexColor("#182c39")); text(45, 785, f["vendor_name"], 20, True); line(760)
        text(45, 725, "INVOICE", 25, True); text(550, 725, f["invoice_number"], 16, True, True)
        text(45, 678, "Bill to: Example Workshop"); text(45, 651, "Invoice date: 03 November 2026")
        text(315, 678, "Currency: EUR"); text(315, 651, "Due date: 03 December 2026")
        text(45, 616, "Amounts use a decimal comma.", 9)
        table_y, total_y = 568, 403
    else:
        c.setFillColor(HexColor("#182c39")); text(45, 790, "TAX INVOICE", 24, True)
        text(45, 757, f["vendor_name"], 17, True); text(550, 790, f["invoice_number"], 12, True, True)
        c.setStrokeColor(HexColor("#a7b4bd")); c.rect(45, 631, 505, 88, stroke=1, fill=0)
        text(60, 692, "Customer: Example Fabrication"); text(340, 692, "Currency: ZAR")
        text(60, 658, "Invoice date: 03 November 2026"); text(340, 658, "Due: 03 December 2026")
        table_y, total_y = 568, 403
    # Keep plain numeric columns legible and aligned across each distinct header layout.
    c.setFillColor(HexColor("#edf2f4")); c.rect(45, table_y - 10, 505, 30, fill=1, stroke=0)
    c.setFillColor(HexColor("#182c39"))
    for x, label, right in [(55, "Description", False), (341, "Quantity", True), (443, "Unit price", True), (540, "Amount", True)]:
        text(x, table_y, label, 10, True, right)
    for i, row in enumerate(spec["lines"]):
        y = table_y - 43 - i * 36
        text(55, y, row["description"], 10)
        for x, key in [(341, "quantity"), (443, "unit_price"), (540, "amount")]:
            text(x, y, num(row[key]), 10, right=True)
    line(table_y - 102)
    for i, (label, val) in enumerate([("Subtotal", f["subtotal"]), (f"{'Sales tax' if cur == 'USD' else 'VAT'} {Decimal(spec['tax_rate']) * 100:g}%", f["tax"]), ("TOTAL " + cur, f["total"])]):
        y = total_y - 31 * i
        text(330, y, label, 12 if i == 2 else 11, i == 2); text(540, y, num(val), 12 if i == 2 else 11, i == 2, True)
    line(total_y - 78)
    text(45, 181, "Payment terms: due on 03 December 2026", 10)
    text(45, 158, "Thank you for your business.", 10)
    c.setFillColor(HexColor("#64737d")); text(45, 71, "Fictional invoice for testing. No payment is due. No real customer data.", 9)
    text(45, 53, PACK_ID + " / " + path.stem, 8)
    c.showPage(); c.save()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def generate(root):
    root.mkdir(parents=True, exist_ok=False)
    (root / "invoices").mkdir()
    key = {"pack_id": PACK_ID, "created_on": DATE, "cases": cases()}
    for spec in key["cases"].values():
        render(root / spec["file"], spec)
    write_json(root / "answer-key.json", key)
    write_json(root / "protocol.json", {
        "pack_id": PACK_ID, "version": 1, "created_on": DATE, "case_count": 8,
        "status_at_freeze": "not_run", "first_run_transport": "IPP connected MCP extract_invoice_data, then get_result for the same job",
        "design": "Eight new authored one-page synthetic invoices, four new independently drawn header layouts. Not sampled from customers, not third-party validation, not an overall accuracy estimate.",
        "freeze_rule": "Commit all source PDFs, answer key, protocol, manifest and scorer before first extraction. Record commit and manifest hash. No post-result edits to frozen files. New version required for changes.",
        "execution_rule": "One submission per case, all eight retained including errors. get_result may retrieve the same job without another extraction. No prompt, extraction or answer-key tuning in response to outcomes. Once inspected this pack is no longer held out for later releases.",
        "scoring": {"headers": ["vendor_name", "invoice_number", "invoice_date", "due_date", "currency", "subtotal", "tax", "total", "document_type"],
                    "lines": "Printed row order, exact row count; description, quantity, unit_price, amount for every row.",
                    "text": "Vendor and description: casefold and collapse whitespace only. Other strings exact, dates YYYY-MM-DD, currency ISO4217, document_type invoice.",
                    "numbers": "Decimal comparison. Quantity exact; money absolute tolerance <=0.005. NaN/infinity rejected. Printed inconsistent values must be preserved, never corrected.",
                    "math_status": "Separate arithmetic result: ok for consistent printed arithmetic, mismatch for zar-02. unchecked or missing is not pass. This does not claim app approval/review state.",
                    "denominator": "Every predefined check for all eight cases. Missing/unobservable fields labeled unobserved and never passed; failed/not-run cases cannot pass. Extra/missing rows fail line_count.",
                    "mcp_mapping": "document.vendor.name -> vendor_name; direct document invoice_number/invoice_date/due_date/currency/document_type; document.totals subtotal/total; tax_total when not null else tax; line_items description/quantity/unit_price/amount; get_result check.result -> math_status. No inferred fields or answer-key substitutions."},
        "limitations": ["All digital PDFs, two short rows each; no handwriting, photos, multipage invoices or credit notes.", "Same authors created fixtures and scorer. Different from historical181-document production-API benchmark. Results must be reported separately.", "MCP transport does not expose model/provider versions; do not claim identical provider configuration to historical runs.", "Public normalized results must remove internal IDs, workspace details, tokens and expiring download URLs; retain original evidence privately."]})
    here = Path(__file__).resolve().parent
    shutil.copyfile(here / "verify.py", root / "verify.py")
    shutil.copyfile(__file__, root / "generate.py")
    (root / "README.md").write_text("""# Try eight invoices with known answers

These are fictional invoices you can run through IPP or another invoice reader.
Start with invoices/usd-01.pdf, then compare the output to answer-key.json.
Try https://invoiceparserpro.com/invoice-to-excel with a PDF from this pack.
The last ZAR invoice deliberately prints a total 40.00 too high: a correct read
preserves that printed total and the arithmetic check identifies the mismatch.
No payment is due on any invoice in this pack.

## What to compare

Check the supplier, invoice number, dates, currency, subtotal, tax and total.
Then check every description, quantity, unit price and line amount. Finally,
check whether the printed arithmetic is consistent. Dates in the answer key
use YYYY-MM-DD and money uses decimal strings to avoid binary rounding.

These eight new synthetic cases and rules were frozen before the first IPP run.
This is a small internally authored check, not an estimate of accuracy on your
invoices or independent third-party validation. It does not replace or extend
the 181-document October 3 development-set benchmark. The frozen protocol starts
unmeasured; any subsequent first-run report is published separately at
https://invoiceparserpro.com/accuracy#frozen-challenge .

## Verify and score

Python 3 standard library is enough: `python verify.py verify .` checks the
manifest. `python verify.py score . normalized-results.json` reports every
check, including missing fields and errors. The verify.py docstring describes
the normalized result schema. A checksum detects drift, not a trusted signature;
compare manifest SHA256 to the publication's recorded hash.

Recreate sources with Python 3 and ReportLab: `python generate.py /new/path`.
The destination must be new. PDF metadata and ZIP timestamps are deterministic.
No production calls are made by these scripts. Read protocol.json before any
live evaluation; submit each case once and retain failures as well as successes.
After results have been inspected, future evaluations need a new frozen set.

Data and PDFs: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), attribute
InvoiceParser Pro, ipp-frozen-challenge-v1. Code: MIT, see LICENSE-CODE.txt.
""")
    (root / "LICENSE-CODE.txt").write_text("""MIT License

Copyright (c) 2026 InvoiceParser Pro

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, and to permit persons to whom the Software is furnished to do
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""")
    files = {str(p.relative_to(root)): {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
             for p in sorted(root.rglob("*")) if p.is_file()}
    write_json(root / "manifest.json", {"pack_id": PACK_ID, "created_on": DATE, "files": files})
    archive = root.parent / (PACK_ID + ".zip")
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                info = zipfile.ZipInfo(str(p.relative_to(root)), date_time=(2026, 11, 4, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o644 << 16
                z.writestr(info, p.read_bytes())
    print(json.dumps({"pack": str(root), "archive": str(archive), "bytes": archive.stat().st_size,
                      "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                      "manifest_sha256": hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    generate(parser.parse_args().output)
