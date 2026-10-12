# Fictional paired invoice checks v1

Nine ordered uploads, seven unique PDF files, frozen source fields and labels,
and an offline CSV/XLSX verifier. This supplement is made by InvoiceParser Pro,
an invoice-extraction vendor. It is a small set of selected fictional examples,
not an independent benchmark or a population accuracy estimate.

The [181-document extraction benchmark](https://github.com/DrewKraken/invoice-extraction-benchmark)
remains a separate dataset with its own field scorer and results. These paired
checks do not change its corpus, denominator or published scores.

## Source cases

Upload the PDFs in manifest order, one at a time, after each reading finishes.
All documents use a new fictional supplier and invoice namespace. The same
namespace should not already exist in the workspace used for a fresh replay.

1. **d01:** the original USD 300 invoice for ORDER-A.
2. **d02:** a byte-identical resend of d01, with no additional charge.
3. **d03:** only the invoice number changes. Whether this represents another
   charge is unresolved; this case is excluded from economic correctness counts.
4. **d04:** a separate USD 300 invoice with a sequential number and printed
   ORDER-B context.
5. **d05:** a separate EUR 300 invoice for ORDER-E that reuses d01's number.
   USD and EUR are different document units; this does not test FX conversion.
6. **d06:** a renumbered reissue that explicitly references d01's obligation and
   says it creates no additional charge. IPP's current readable-number safeguard
   is expected to withhold a duplicate match. This is a known limitation even
   when the frozen detector expectation is met.
7. **d07:** a signed USD −300 credit note referring to the original invoice.
8. **d08:** a byte-identical resend of that credit note.
9. **d09:** a distinct invoice with a deliberate line arithmetic error: four
   hours at USD 75 print as USD 375. The other line is USD 125, so the printed
   subtotal and total are USD 500. Preserve those printed figures; the first
   line is USD 75 above quantity × rate.

`manifest.json` separates printed source fields, the author's fictional
obligation register, arithmetic labels and expected current duplicate behavior.
`freeze.json` records the manifest/source hashes and author-declared pre-run
freeze. The freeze is an ordinary dated file, not independent timestamping.
The local `.gitattributes` preserves frozen JSON and recorded download bytes
across Git checkouts, including their original line endings.
A duplicate flag does not establish prior payment, and a changed number alone
does not establish a legitimate new bill.

## Verify the files offline

Python 3.10 or later is sufficient. No packages, product checkout, credentials,
network calls or paid service are required for the verifier. From the repository
or the extracted review archive:

```bash
python scorer/verify_pack.py --pack examples/paired-checks-v1 --inputs-only
python scorer/verify_pack.py --pack examples/paired-checks-v1 --out verification.json
```

The first command verifies frozen source bytes and independently computes the
printed arithmetic with Decimal. The second also checks the recorded download
hashes, invoice/date/currency/amount fields and numeric XLSX line rows. Blank
values are distinct from zero. Formula cells are not evaluated or accepted as
recalculation evidence. The workbook files are preserved as generated.

The report separates **pack integrity**, **export agreement with printed source
fields**, and **agreement with the frozen duplicate-detector expectation**.
An integrity success does not mean that extraction or duplicate detection was
correct. Real discrepancies remain in the report. Add `--require-contract` to
return a nonzero exit code for source/export or detector-contract discrepancies.
A referenced file that is missing, an altered hash or an incomplete
document/duplicate/export record fails integrity in normal result-checking runs,
with or without `--require-contract`. Inputs-only mode checks no result record.
An explicitly recorded unavailable download remains unavailable and fails the
product contract; it is not invented or silently counted as correct. A reviewer
reviews the completeness of run provenance, settings, prior history and
intervention notes; the checker does not establish those facts.
If an upload produces no persisted invoice, record that outcome, a visible basis,
`duplicate: null`, `duplicate_status: "not_evaluated"`, and unavailable downloads.
That is an unevaluated duplicate case, not an observed no-match. The report counts
unevaluated cases separately and cannot report a fully met detector contract.

The verifier does not read PDFs, run OCR, call IPP, recalculate Excel, detect
duplicates or replay the workspace. It checks the labels' arithmetic and actual
exported values. Duplicate observations are recorded by the run operator reviewing the
workspace and are checked separately; they are not inferred from CSV/XLSX.
The export reader expects IPP's Full invoice columns and the separate XLSX Line
Items sheet. These ordinary exports do not supply document type or UI group
membership; review those separately in the workspace observation record.

## Repeat the product workflow

Use a workspace with no prior invoices in this fictional namespace. The
anonymous invoice-to-Excel converter has no invoice history and cannot exercise
this duplicate check. Review the product's current allowance before starting;
this pack does not provide an account or change product limits.

1. Upload d01 through d09 in order, waiting for each reading to finish. Keep all
   documents. Leave accounting-provider export off. No removal, dismissal,
   restoration or accounting push is needed.
2. Compare extracted fields with each PDF. Record what the product initially
   read and any existing automatic approval. For the main run, preserve the
   initial reading; do not correct fields to make a result match the answer key.
3. Select the Full ordinary export and save each actual CSV/XLSX download without
   editing it. Record each filename and SHA-256. Note any unavailable download
   explicitly.
4. Record potential-duplicate observations and counterpart document IDs from the
   workspace. Record group memberships separately when inspected. Source PDFs,
   downloaded rows and UI groups are different evidence surfaces.
5. Write a new JSON observation record using `recorded-results.json` as the
   format example. Export paths resolve relative to that record. Run:

```bash
python scorer/verify_pack.py --pack examples/paired-checks-v1 --run my-run/observations.json --out my-run/verification.json
```

Newly generated workbook bytes can differ because of metadata. A repeat run
records its own hashes; its values are checked against the same frozen source
fields. Disclose the tool/version, date, settings, initial history, source
corrections, and affiliation. A disputed source label is useful feedback: identify
the document, field or printed context. Preserve this version's freeze and create
a new version for changed sources or labels.

## Recorded run and coverage

The recorded result is an owner-run fictional exercise. Its dated observation
record describes the source mode, exports and operator-recorded workspace
observations. The company-account run and source checks use AI-assisted browser
operation; this does not establish that Drew personally reviewed each reading.
Package
verification is not an independent endorsement of that record. The renumbered
same-obligation reissue is reported even when it is missed.

The recorded run took place on October 12, 2026, from 20:13 to 20:47 UTC against
IPP release `805f69a2b7551daf31b8d23dd4897096178b70eb`. All nine PDFs produced
persisted readings. The initial readings stayed pending at medium extraction
confidence; no source fields were corrected or manually approved. Existing
auto-approve was enabled, auto-export was off, and settings were unchanged.
The run used nine invoices of the existing allowance.

The unchanged invoice resend d02 linked d01 with a high-confidence exact match;
the credit resend d08 linked d07 likewise. The final Duplicates page showed those
two separate pairs. The distinct EUR invoice d05 and sequential bill d04 stayed
outside them. The renumbered same-obligation reissue d06 was not flagged, as the
frozen current-policy expectation anticipated. d03 remains economically
unresolved and is not counted as a legitimate bill or an economic success.

Per-document potential-match observations were recorded after each completed
reading. Group membership was inspected only once at the final state;
intermediate group snapshots specified by the proposed protocol were not
captured. [The cropped final group capture](recorded/duplicate-groups.jpg) shows
only the two new fictional pairs, before any removal. Its bytes are hash-checked;
interpreting the image and run provenance remains a review task.

For d09, the raw header status was `valid` and the totals label said “Math
verified”: the printed subtotal plus tax agrees with USD 500. A separate line
warning said four times 75 is 300 while the printed line is 375, with 300 suggested.
Both actual Full exports preserve the printed line 375 and total 500 and report
`mismatch`. These are separate observed surfaces; the suggested value was not
applied. The nine CSV/XLSX pairs preserve the checked source fields and numeric
lines, including signed credits. Provider/model versions were not independently
recorded. No removal, dismissal, restoration or accounting-provider write was
performed.

This set does not estimate precision/recall on real invoice populations, compare
competitors, prove accounting posting, prior payment, removal/restoration,
400-day boundaries, cross-workspace isolation, recurring customer use or
assistant recommendation rates. Existing historical raw warnings and automatic
processing holds can remain conservative; a safe removal group does not prove
every older warning disappeared.

## License and attribution

The repository's existing licenses apply without new terms: code in `scorer/`
is [MIT](../../LICENSE); source documents and answer keys in `examples/` are
[CC BY 4.0](../../DATA_LICENSE). Retain the existing notices and credit
“InvoiceParser Pro, Invoice Extraction Benchmark v1” with a link to the
repository. Identify this supplement as `examples/paired-checks-v1`, version
1.0.0, and indicate changes when sharing adaptations.
