# Eight new synthetic invoices with known answers

Download a [starter invoice](frozen/invoices/usd-01.pdf), inspect its
[actual Excel result](first-run/exports/usd-01.xlsx), and compare it with the
[answer key](frozen/answer-key.json). The
[complete source pack](ipp-frozen-challenge-v1.zip) includes all eight PDFs,
the answers and a portable scorer. Try a file in
[IPP's existing invoice tool](https://invoiceparserpro.com/invoice-to-excel)
or any other invoice reader.

This is a separate, small internal check from November 4, 2026. It does not
extend or replace the original 181-document benchmark. Each PDF has only two
line items, and all eight are digital PDFs: no photos, handwriting, multipage
invoices or credit notes. The four header layouts were drawn independently
of the original corpus renderer; the fixtures and scorer were still authored
by IPP, not an independent evaluator.

## What happened

The source PDFs, answers and scoring rules were frozen before the first IPP
submission. Each case was submitted once through the connected MCP account
lane. The first-run results matched all 152 predefined checks across the eight
cases: 72 header fields, 64 line fields, eight row counts and eight arithmetic
outcomes. There were no failed or unobserved checks in this run. The deliberately
incorrect ZAR total was preserved and flagged; that total received Low field
confidence and still needs review.

This result is not an estimate of accuracy on real customer invoices. The
protocol does not expose exact model/provider versions. After inspecting the
results, these cases become visible development evidence; another held-out
claim needs a new frozen set. See the [complete report](first-run/README.md),
[returned data](first-run/normalized-results.json),
[every comparison](first-run/score.json) and
[additional export checks](first-run/export-verification.json).

The original CSV/XLSX bytes are in [first-run/exports](first-run/exports).
CSV files are invoice summaries; Excel files include the line items. Internal
account/job identifiers and expiring download URLs are excluded. No customer
invoices were used.

## Verify locally

From the repository root, using Python 3:

```sh
python examples/challenge-v1/frozen/verify.py verify examples/challenge-v1/frozen
python examples/challenge-v1/frozen/verify.py score examples/challenge-v1/frozen examples/challenge-v1/first-run/normalized-results.json
```

These commands need only Python's standard library. To independently check
the downloaded CSV/XLSX contents against the answer key, install `openpyxl`
and run:

```sh
python examples/challenge-v1/first-run/verify_exports.py examples/challenge-v1/frozen examples/challenge-v1/first-run/exports
```

The frozen pack and separate first-run artifacts are byte-for-byte mirrors of
the [published site assets](https://invoiceparserpro.com/accuracy#frozen-challenge).
Their embedded reports retain original source-project paths for provenance;
the commands above use this public repository's paths. The manifest SHA256 is
`9b3e396cecefa435aa547b6c397ca7c2ddb796590186746cc85b77710a125180`;
the source ZIP SHA256 is
`33dd94e8eac2a2566df5e647fcf0b5991282c8f6372f0aa3f0ed1a08bea20966`.
Hashes detect changes; they are not an independent audit or trusted signature.

Data/PDFs: CC BY 4.0. Code: MIT; see the
[frozen code license](frozen/LICENSE-CODE.txt) and repository licenses.
