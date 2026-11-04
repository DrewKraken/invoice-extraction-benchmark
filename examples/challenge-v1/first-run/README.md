# Eight fresh invoices, frozen before their first IPP run

On November 4, 2026, IPP read eight new synthetic invoices through the connected
MCP account lane. Every predefined field and arithmetic check matched the frozen
answer key on the first attempt:152 checks, zero failures, zero unobserved fields.
This is a small internal check of eight authored digital PDFs, not an estimate
of production accuracy or independent third-party validation. The existing
181-document October 3 benchmark and its tuning disclosure remain unchanged.

## Customer use

The `/accuracy#frozen-challenge` section offers a starter PDF, its actual Excel
result, the answer key and the existing invoice-to-Excel tool. The full source
pack is `/accuracy/ipp-frozen-challenge-v1.zip`. A customer can inspect a concrete
result immediately, then try the same invoice or their own document.

Sources, answers and scoring rules: `apps/frontend/public/accuracy/challenge-v1`.
Separate observed results and original exports:
`apps/frontend/public/accuracy/challenge-v1-first-run`.

## Frozen before execution

- Freeze commit: `6202e1893d53b2ecf9c4e015dba6f4a7f646c219`.
- Manifest SHA256: `9b3e396cecefa435aa547b6c397ca7c2ddb796590186746cc85b77710a125180`.
- Frozen ZIP SHA256: `33dd94e8eac2a2566df5e647fcf0b5991282c8f6372f0aa3f0ed1a08bea20966` (27085 bytes).
- First submission: `2026-11-04T15:06:44.038Z`.
- Last result retrieval: `2026-11-04T15:10:53.952Z`.
- Independent local reviews checked all source PDFs, key arithmetic, manifest,
  and scoring rules before the first submission. No production answer was used
  to revise the frozen sources, expected values, scorer or extraction pipeline.
- Exactly one extraction submission per case; `get_result` retrieved the same
  job for its math check and available exports. No second extraction or rerun.

The eight one-page invoices use four new header layouts, drawn independently
of the old accuracy_eval renderer, with two rows each. USD services use zero
sales tax; both GBP cases use 20% VAT; EUR cases use decimal commas and 20% VAT;
ZAR cases use 15% VAT. Seven have consistent arithmetic. `zar-02` prints 2239.95
although 1913.00 + 286.95 = 2199.95. Correct behavior preserves 2239.95 and flags the
40.00 difference. All suppliers and customer names are fictional.

## First-run outcomes

| Case | Printed fields and rows | Arithmetic result | Overall confidence |
| --- | --- | --- | --- |
| eur-01 | All checks match | ok | MEDIUM |
| eur-02 | All checks match | ok | MEDIUM |
| gbp-01 | All checks match | ok | MEDIUM |
| gbp-02 | All checks match | ok | MEDIUM |
| usd-01 | All checks match | ok | MEDIUM |
| usd-02 | All checks match | ok | HIGH |
| zar-01 | All checks match | ok | MEDIUM |
| zar-02 | All checks match; printed wrong total retained | mismatch | MEDIUM |

The 152 predeclared checks comprise 72 header fields,64 line fields (description,
quantity, unit price, amount), 8 row counts and 8 arithmetic outcomes. Missing or
unobservable fields cannot pass. Quantities are exact; money tolerance is at
most half a cent. Descriptions/vendors normalize case and whitespace only.
All invoice IDs, dates, currencies and document types are exact. Line pairing
uses printed row order. See the frozen protocol and every per-field comparison
in `score.json`, including observed values.

The total_amount field in `zar-02` is explicitly LOW confidence: the product
returned the printed total correctly and identified its arithmetic mismatch.
All other returned field confidences are high or medium. Correct matching
here does not justify telling a customer to skip document review.

## Real exports checked separately

Every returned CSV and XLSX link downloaded successfully (16 HTTP 200 responses).
CSV files contain invoice summaries; XLSX files include the line items. The
actual returned bytes are available in `challenge-v1-first-run/exports` with
SHA256 checksums in `export-verification.json`. Header identities, dates,
currencies, printed totals, row counts and validation statuses match the key;
all XLSX row descriptions, quantities, rates and amounts also match. The bad
ZAR total remains 2239.95 with mismatch status in both export formats.

Export QA was an additional delivery check, separate from the predeclared
152-check MCP score. It did not cause additional extraction submissions.

## Reproduction and limitations

Run from the repository root:

```sh
python scripts/accuracy_challenge/verify.py verify apps/frontend/public/accuracy/challenge-v1
python scripts/accuracy_challenge/verify.py score apps/frontend/public/accuracy/challenge-v1 apps/frontend/public/accuracy/challenge-v1-first-run/normalized-results.json
python -m unittest discover -s scripts/accuracy_challenge -p test_challenge.py
python scripts/accuracy_challenge/verify_exports.py apps/frontend/public/accuracy/challenge-v1 apps/frontend/public/accuracy/challenge-v1-first-run/exports
```

The first three use only Python standard library. Export verification requires
openpyxl; source generation requires ReportLab. Generating twice in fresh
directories produced identical PDFs, keys, protocol, manifest and ZIP bytes.
PDF text/page-count checks and visual inspection covered all eight documents.
Mutation tests confirm missing rows, extra rows, wrong quantity/unit price,
incorrectly correcting the printed wrong total, missing fields, failures and
frozen-file drift are detected. Oracle data in tests validates only the scorer.

The connector does not expose exact model/provider versions. The transport is
MCP, not the older production API harness. Raw responses are retained privately;
public results use only the field mapping frozen in `protocol.json`. The
normalizer and hashes of the original responses are included for audit. Public
files omit account/firm/job IDs, authentication data and signed download URLs.

No handwritten/photo/multipage/credit invoices were included. Two short rows
on digital PDFs are easier than many real invoices. This pack becomes visible
development evidence after this run; a later held-out claim needs a new frozen
set. Do not merge these eight cases into the old benchmark or claim broader
accuracy, customer impact, revenue or independent validation from this result.

No provider credentials were provisioned, no billing account was added, and
no customer invoices were used. The run used eight existing QA trial documents.
The exact QA firm and eight job IDs are excluded by the analytics agent's
private test-traffic registry; they are not acquisition or signup evidence.
