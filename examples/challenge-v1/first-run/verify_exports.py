#!/usr/bin/env python3
"""Additional export QA, separate from the predeclared MCP-field score.

Requires openpyxl. Reads existing exports only; never submits an invoice.
"""
import argparse
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import openpyxl


def verify_exports(pack, exports):
    key = json.loads((pack / 'answer-key.json').read_text())
    checks = []
    for case_id, case in key['cases'].items():
        fields = case['fields']
        expected_header = {'Vendor': fields['vendor_name'], 'Invoice #': fields['invoice_number'],
                           'Date': fields['invoice_date'], 'Total': fields['total'],
                           'Currency': fields['currency'], 'Line Items Count': len(case['lines']),
                           'Validation Status': 'mismatch' if case['math_status'] == 'mismatch' else 'valid',
                           'Document Type': fields['document_type']}
        for fmt in ('csv', 'xlsx'):
            path = exports / f'{case_id}.{fmt}'
            if fmt == 'csv':
                with path.open(encoding='utf-8-sig', newline='') as f:
                    rows = list(csv.DictReader(f))
            else:
                book = openpyxl.load_workbook(path, data_only=True)
                values = list(book['All Invoices'].values)
                rows = [dict(zip(values[0], row)) for row in values[1:]]
            assert len(rows) == 1, (case_id, fmt, 'header row count')
            for field, expected in expected_header.items():
                got = rows[0][field]
                if field in ('Total', 'Line Items Count'):
                    assert Decimal(str(got)) == Decimal(str(expected)), (case_id, fmt, field)
                else:
                    assert got == expected, (case_id, fmt, field)
            if fmt == 'xlsx':
                values = list(book['Line Items'].values)
                lines = [dict(zip(values[0], row)) for row in values[1:]]
                assert len(lines) == len(case['lines']), (case_id, 'line row count')
                for got, expected in zip(lines, case['lines']):
                    assert got['Invoice #'] == fields['invoice_number']
                    assert got['Description'] == expected['description']
                    for column, field in [('Quantity', 'quantity'), ('Unit Price', 'unit_price'), ('Total', 'amount')]:
                        assert Decimal(str(got[column])) == Decimal(expected[field]), (case_id, column)
            checks.append({'case_id': case_id, 'format': fmt, 'bytes': path.stat().st_size,
                           'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                           'verified': 'header fields and line rows' if fmt == 'xlsx' else 'header fields (CSV is invoice summary)'})
    return {'exports_checked': len(checks), 'all_passed': True, 'checks': checks,
            'scope': 'Additional downloaded-file QA; separate from the frozen MCP-field score. CSV exports are invoice summaries; XLSX includes line items.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('pack', type=Path)
    p.add_argument('exports', type=Path)
    args = p.parse_args()
    print(json.dumps(verify_exports(args.pack, args.exports), indent=2))
