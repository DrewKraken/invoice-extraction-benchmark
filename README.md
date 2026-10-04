# Invoice extraction benchmark (v1)

A synthetic test set for invoice data extraction (invoice OCR, intelligent document
processing, accounts-payable capture): **181 documents with answer keys and a scorer**.
Run any invoice reader over the documents, write its output as one JSON file, and score it
field by field.

The documents are made to be hard in the ways real accounts-payable inboxes are hard: phone
photos at three damage grades, scans and faxes, invoice books filled in by hand, credit notes
printed five different ways, dual-currency invoices, VAT-inclusive layouts, multi-page
invoices, several invoices in one PDF, supplier statements, and invoices whose printed
figures deliberately do not add up.

**Who made it.** The set, the generator and the scorer were made by
[InvoiceParser Pro](https://invoiceparserpro.com) (IPP), a company that sells an invoice
extraction product. IPP's own results are below. Weigh that when you read them: the
benchmark is not independent, and IPP chose the categories. Everything needed to check the
answer keys and re-score any tool is in this repository.

Also on Hugging Face (same documents and answer keys, with a dataset viewer):
[drew-ipp/invoice-extraction-benchmark](https://huggingface.co/datasets/drew-ipp/invoice-extraction-benchmark).

## Contents

| | |
|---|---|
| `corpus/v1/documents/` | 181 documents: 113 PDF (digital, with a text layer), 53 JPEG (photos and handwritten), 15 PNG (scans) |
| `corpus/v1/answers/` | One answer key per document (JSON) |
| `corpus/v1/manifest.json` | Every document with its category, difficulty, damage, sha256 and answer key |
| `corpus/v1/metadata.jsonl` | The same, one row per document (for dataset viewers) |
| `scorer/` | Scores a predictions file against the answer keys |
| `generator/` | The code that drew the documents and wrote the answer keys, from seed 42 |
| `examples/predictions.example.json` | The predictions format, for two documents |

About 37 MB in all. 220 pages; the longest document is 8 pages.

## What is in the set

| Category | Docs | What it is there to test |
|---|---:|---|
| clean | 31 | Digital PDFs: headers left, right, centred or in a banner; gridded and borderless tables; two columns; landscape; US, UK, EU, South African and long date formats; comma and dot decimals; shipping, discount, fee and multi-tax lines |
| currency | 19 | USD, ZAR, NAD, EUR, GBP, ZMW as symbols or codes; a Namibian invoice printing a bare `$`; 4 dual-currency invoices (lines in USD or EUR, an amount-payable box in ZAR or NAD); lines priced in several currencies |
| tax | 14 | VAT column per line, VAT-inclusive totals, a "Sub Total" printed after VAT, zero-rated exports, percentage lines (a rate column with the customs value in the quantity column), withholding below the total |
| credit | 10 | "Credit Note", "Nota de Crédito (NdC)", `R -1 234,56`, brackets, a `CR` suffix, and a credit note printed with no minus signs at all |
| multipage | 10 | 2 to 8 pages, lines continuing across pages, carried and brought-forward rows, totals only on the last page |
| freight | 16 | Carrier invoices (linehaul, fuel surcharge %, accessorials), clearing and forwarding invoices (VAT-free disbursements beside VAT-able fees, a "Supplier Inv No" that is not the invoice number), trip / load / truck references |
| scan | 15 | 5 scan looks x 3 grades: grayscale scan, noise, fax (binarised), punch holes, stamps over the text |
| photo | 45 | 15 phone-photo problems x 3 grades (mild, moderate, severe): perspective, small rotation, 90/180/270 degrees, motion blur, focus blur, low light, shadow, JPEG quality 40/30/20, low resolution, crumpled and folded, coffee stains, pen marks, cropped edges, a photo of a screen, and a combined phone capture |
| handwritten | 8 | Pre-printed cash-book and delivery-note invoices filled in by hand, at three legibility grades (2 neat, 3 average, 3 poor) |
| hard | 13 | 2 files holding several invoices, 2 supplier statements (not a bill), an order number printed beside the invoice number in the same format (3), no invoice number at all (2), and 4 invoices whose printed figures do not add up |

Each photo or scan problem is drawn at three grades on the same base page, so the severity
curve moves with the damage alone. Difficulty (62 easy, 48 medium, 71 hard) is the author's
prior, set per document. 5 invoices have figures that do not add up (4 in `hard`, 1 in
`clean`); with the 2 multi-invoice files, 7 documents should be flagged for a person rather
than read as if nothing were wrong.

### Synthetic, and how it was checked

Every vendor, customer, person, address, phone number, tax number, bank detail, invoice
number, line item and amount is generated from word lists and a seeded random generator
(`generator/names.py`, `generator/corpus_v1.py`, `generator/us_specs.py`). Company names are
built as *place word + trade + legal form* (for example "Kalahari Office Supplies (Pty)
Ltd"); a name may coincide with a real business by accident of common words, and no
document refers to one. Towns are real place names; phone numbers use reserved test ranges
(555) where a country has one. Every page is drawn by one layout engine
(`generator/layout.py`); no customer document was read, copied or imitated, and none
appears here.

### Limitations

- Synthetic: the documents are drawn by one layout engine with a limited set of templates
  (fonts, header positions, table styles), so they are far less varied in layout than real
  supplier invoices. A tool that does well here can still struggle with a real supplier's
  layout, and the reverse.
- Mostly English, with Southern African, UK, US and EU conventions; no right-to-left or CJK
  documents.
- Photo and scan damage is simulated, not photographed.
- 181 documents is enough to compare tools on these categories, not to estimate accuracy to
  a fraction of a percent; per-category counts are small.

### What is not included

- **10 documents of the original 191** belong to a document type that is not public yet and
  are withheld. IPP's published figures already leave them out, so the 181 here are exactly
  the documents behind the figures below. The generator still makes the withheld documents'
  random draws (`_skip_withheld` in `corpus_v1.py`), so seed 42 reproduces the 181
  byte for byte.
- **The handwriting font.** Handwritten values were drawn with Windows' Ink Free font
  (recorded in the manifest), which is not redistributed. Regenerating on a machine without
  it gives the same text and answer keys in slightly different pixels for the 8 handwritten
  documents; the files in `corpus/v1/` are the reference.
- **No IPP production code.** The scorer is the field-rule module of IPP's benchmark,
  unchanged in its rules; nothing here calls IPP or any paid service.

## Score a tool

```bash
pip install -r requirements.txt
# 1. run your tool over corpus/v1/documents/ and write predictions.json (format below)
# 2. score it
python -m scorer.evaluate predictions.json --markdown scores.md --out scores.json
```

The output gives the headline measures, every field, and the breakdown by category,
difficulty and photo/scan severity. `scores.json` holds each document's field-by-field
result (expected and got), so every miss can be inspected.

### Predictions format

```json
{
  "system": "Tool name and version",
  "run_date": "2026-10-04",
  "documents": {
    "clean-gb-serif": {
      "vendor_name": "Pennine Tyre & Parts Limited",
      "invoice_number": "IN0049923",
      "invoice_date": "2025-08-27",
      "due_date": "2025-09-26",
      "currency": "GBP",
      "subtotal": 18011.58,
      "tax": 3602.32,
      "total_amount": 21613.90,
      "document_type": "invoice",
      "line_items": [
        {"description": "Hydraulic hose 1/2in, per metre", "amount": 2386.40},
        {"description": "LED work lamp 24V", "amount": 4513.60},
        {"description": "Safety boots, steel toe, size 9", "amount": 4764.18},
        {"description": "Brake pads, trailer axle set", "amount": 6347.40}
      ],
      "flagged": false,
      "references": []
    }
  }
}
```

- Keys of `documents` are the doc ids (the file names without extension). A document
  missing from the file counts as "no result": every field it is scored on is wrong.
  `--allow-missing` scores a partial run and says so in the output.
- Dates as ISO `YYYY-MM-DD` (other forms are parsed day first). Amounts as numbers.
  `null` where the document prints nothing.
- `document_type`: `invoice`, `credit_note`, or `other` (a supplier statement).
- `flagged`: `true` when your tool would hold the document for a person (figures that do
  not add up, several invoices in one file).
- `references`: trip, load or container references the tool lists (reported, not part of
  the headline).
- `total` is accepted for `total_amount`, and `line_total` for a line's `amount`.

See `examples/predictions.example.json`.

### Scoring rules

| Field | Right when |
|---|---|
| vendor_name | Equal after dropping case, punctuation and legal-form words (Pty, Ltd, LLC, GmbH...), or similarity 0.85 or more, or one name contains the other |
| invoice_number | Equal after removing case, spaces, `#` and a leading label. Where none is printed, right only when left empty (an order number in its place is wrong) |
| invoice_date, due_date | The ISO date. The due date is scored only where one is printed |
| currency | The ISO code. On a dual-currency invoice, the currency of the amount-payable box |
| subtotal, tax, total | Exact to the cent. The subtotal is the net amount before VAT, on VAT-inclusive layouts too. Credit notes compare magnitudes (the sign is the `document_type` decision). A dual-currency invoice is scored on the payable box. Withholding is not deducted from the total |
| document_type | `invoice`, `credit_note` or `other`; a statement is right only as `other` |
| line_items | Each expected line matched to one predicted line by amount (within a cent; on dual-currency invoices the payable-currency column also counts) and description similarity 0.6 or more; F1 per document, rounded to 2 decimals; right when F1 is 1 |
| flag | Documents that should be flagged must be; consistent ones must not |

A document is **fully correct** when every key header field it is scored on is right:
vendor, invoice number, invoice date, due date (where printed), currency, subtotal, tax,
total and document type. Key header field accuracy is right fields over scored fields
across all documents. Several invoices in one file are scored against the first invoice.
Statements are scored on vendor and document type only. The rules live in
`scorer/score.py`.

## Results

| System | Date | Docs | Every key header field right | Key header fields right | Line items, mean F1 | Inconsistent invoices flagged | Source |
|---|---|---:|---|---|---:|---|---|
| InvoiceParser Pro (production) | 2026-10-03 | 181 | 96.1% (174 of 181) | 98.7% (1,555 of 1,576) | 0.983 | 5 of 5 | [invoiceparserpro.com/accuracy](https://invoiceparserpro.com/accuracy) |

IPP's run sent the documents through its live production service on 3 October 2026 (173
through its public API, 8 handwritten invoices through its app upload) and was scored with
the rules above. In the same run both multi-invoice files were flagged, and 2 of the 172
consistent documents were flagged (two severe-blur photos it misread). The full breakdown,
every miss, and the method are on [invoiceparserpro.com/accuracy](https://invoiceparserpro.com/accuracy).
These are IPP's own measurements on synthetic documents made by IPP; they say nothing about
accuracy on any particular company's real invoices.

### Add your results

Results from any tool are welcome, including tools that compete with IPP. Open a pull
request that adds a folder `results/<system>-<YYYY-MM-DD>/` with:

1. `predictions.json` for all 181 documents, in the format above;
2. `scores.md` written by `python -m scorer.evaluate predictions.json --markdown scores.md`;
3. a short `README.md`: the tool and version, settings or prompt, how the documents were
   sent (API, upload, model), the date, and whether you are affiliated with the tool.

and a row in the table above. Please do not tune a tool on the answer keys before
submitting, and say so if a run used only part of the set. A pull request that disputes an
answer key is just as welcome: say which document and field, and what the page prints.

## Reproduce the corpus

```bash
pip install -r requirements.txt
python -m generator.generate --out /tmp/ieb-v1 --check
```

This regenerates all 181 documents and answer keys from seed 42 and compares each file's
sha256 with `corpus/v1/manifest.json`. With the pinned library versions (reportlab 5.0.1,
Pillow 12.3.0) and the Ink Free font, all 181 match; without the font, the 8 handwritten
documents differ in pixels only. Python 3.10 or later.

## Cite this

```bibtex
@misc{ipp_invoice_extraction_benchmark_2026,
  title        = {Invoice Extraction Benchmark v1: 181 synthetic invoices, photos, scans and handwritten documents with answer keys},
  author       = {{InvoiceParser Pro}},
  year         = {2026},
  month        = oct,
  howpublished = {\url{https://github.com/DrewKraken/invoice-extraction-benchmark}},
  note         = {Synthetic corpus, seed 42; results at https://invoiceparserpro.com/accuracy}
}
```

`CITATION.cff` has the same in GitHub's format (the "Cite this repository" button).

## License

- Code (`generator/`, `scorer/`): [MIT](LICENSE).
- Data (`corpus/`, `examples/`): [Creative Commons Attribution 4.0](DATA_LICENSE) (CC BY 4.0).
  Credit "InvoiceParser Pro, Invoice Extraction Benchmark v1" with a link to this repository.

## Links

- Published results and method: https://invoiceparserpro.com/accuracy
- InvoiceParser Pro: https://invoiceparserpro.com
