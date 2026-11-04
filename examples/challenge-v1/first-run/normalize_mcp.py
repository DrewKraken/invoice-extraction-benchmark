#!/usr/bin/env python3
"""Project private first-run MCP evidence to the frozen public scoring schema.

No API calls. Mapping is defined in the pre-run protocol; no inferred values.
Raw files must be named <case>-extract.json and <case>-result.json. The latter
retrieves the same job and provides its math check and exports. Private IDs,
workspace data and signed URLs are intentionally excluded from public output.
"""
import argparse
import hashlib
import json
from pathlib import Path


def normalize(raw_dir, pack):
    key = json.loads((pack / 'answer-key.json').read_text())
    out = {'pack_id': key['pack_id'], 'transport': 'IPP connected MCP account lane',
           'freeze_commit': '6202e1893d53b2ecf9c4e015dba6f4a7f646c219',
           'manifest_sha256': hashlib.sha256((pack / 'manifest.json').read_bytes()).hexdigest(),
           'mapping': 'protocol.json scoring.mcp_mapping; normalize_mcp.py v1',
           'cases': {}}
    for case_id in key['cases']:
        first_path = raw_dir / (case_id + '-extract.json')
        fetched_path = raw_dir / (case_id + '-result.json')
        first = json.loads(first_path.read_text())
        fetched = json.loads(fetched_path.read_text()) if fetched_path.exists() else None
        original = first['result'].get('structuredContent') or {}
        current = fetched['result'].get('structuredContent', {}) if fetched else original
        if fetched and current.get('job_id') != original.get('job_id'):
            raise ValueError('get_result returned a different job: ' + case_id)
        # Fields come from the first completed extraction response; only if it
        # was processing do we take the subsequently completed same job.
        source = original if original.get('status') == 'completed' else current
        doc = source.get('document') or {}
        totals = doc.get('totals') or {}
        fields = {k: doc.get(k) for k in ('invoice_number', 'invoice_date', 'due_date', 'currency', 'document_type')}
        fields.update({'vendor_name': (doc.get('vendor') or {}).get('name'),
                       'subtotal': totals.get('subtotal'), 'total': totals.get('total'),
                       'tax': totals.get('tax_total') if totals.get('tax_total') is not None else totals.get('tax')})
        out['cases'][case_id] = {
            'status': source.get('status', 'unknown'), 'fields': fields,
            'lines': [{k: line.get(k) for k in ('description', 'quantity', 'unit_price', 'amount')}
                      for line in (doc.get('line_items') or [])],
            'math_status': (current.get('check') or {}).get('result'),
            'math_findings': (current.get('check') or {}).get('findings'),
            'confidence': doc.get('confidence'),
            'submitted_at': first['started_at'], 'first_response_at': first['finished_at'],
            'last_retrieved_at': fetched['finished_at'] if fetched else None,
            'first_response_sha256': hashlib.sha256(first_path.read_bytes()).hexdigest(),
            'retrieved_response_sha256': hashlib.sha256(fetched_path.read_bytes()).hexdigest() if fetched else None,
        }
    return out


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('raw_dir', type=Path)
    p.add_argument('pack', type=Path)
    args = p.parse_args()
    print(json.dumps(normalize(args.raw_dir, args.pack), indent=2, sort_keys=True))
