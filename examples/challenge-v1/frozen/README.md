# Try eight invoices with known answers

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
