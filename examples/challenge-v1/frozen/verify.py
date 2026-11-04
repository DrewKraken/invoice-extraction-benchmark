#!/usr/bin/env python3
"""Portable frozen-challenge integrity checker and scorer. Python 3, stdlib only.

python verify.py verify .
python verify.py score . normalized-results.json
Results schema: {"cases": {"usd-01": {"status": "completed", "fields": {...},
"lines": [{"description":..., "quantity":..., "unit_price":..., "amount":...}],
"math_status": "ok"}}}. No absent field is inferred from the answer key.
"""
import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import sys

HEADERS = ("vendor_name", "invoice_number", "invoice_date", "due_date", "currency",
           "subtotal", "tax", "total", "document_type")
NUMERIC = {"subtotal", "tax", "total", "quantity", "unit_price", "amount"}
LINE_FIELDS = ("description", "quantity", "unit_price", "amount")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root):
    manifest = json.loads((root / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        path = root / name
        if not path.is_file() or digest(path) != expected["sha256"] or path.stat().st_size != expected["bytes"]:
            raise ValueError("Frozen file missing or changed: " + name)
    return manifest


def equal(field, expected, observed):
    if observed is None:
        return False
    if field in NUMERIC:
        try:
            a, b = Decimal(str(expected)), Decimal(str(observed))
            # Quantities exact to the displayed precision; all amounts within half a cent.
            return a.is_finite() and b.is_finite() and abs(a - b) <= (Decimal("0") if field == "quantity" else Decimal("0.005"))
        except (InvalidOperation, ValueError):
            return False
    if field in ("vendor_name", "description"):
        return " ".join(str(expected).casefold().split()) == " ".join(str(observed).casefold().split())
    return expected == observed


def score(root, observed):
    verify(root)
    key = json.loads((root / "answer-key.json").read_text())
    results = []
    extra_cases = sorted(set(observed.get("cases", {})) - set(key["cases"]))
    if extra_cases:
        raise ValueError("Unknown result case IDs: " + ", ".join(extra_cases))
    for case_id, expected in key["cases"].items():
        actual = observed.get("cases", {}).get(case_id, {})
        completed = actual.get("status") == "completed"
        checks = []
        def check(field, want, got):
            checks.append({"field": field, "expected": want, "observed": got,
                           "outcome": "unobserved" if got is None else ("pass" if completed and equal(field.rsplit(".", 1)[-1], want, got) else "fail")})
        fields = actual.get("fields") or {}
        for field in HEADERS:
            check(field, expected["fields"][field], fields.get(field))
        lines = actual.get("lines") or []
        check("line_count", len(expected["lines"]), len(lines) if completed else None)
        for i, line in enumerate(expected["lines"]):
            row = lines[i] if i < len(lines) and isinstance(lines[i], dict) else {}
            for field in LINE_FIELDS:
                check(f"lines.{i}.{field}", line[field], row.get(field))
        check("math_status", expected["math_status"], actual.get("math_status"))
        results.append({"case_id": case_id, "status": actual.get("status", "not_run"),
                        "all_checks_pass": completed and all(c["outcome"] == "pass" for c in checks),
                        "checks": checks})
    return {"pack_id": key["pack_id"], "case_count": len(results),
            "all_checks_pass_count": sum(r["all_checks_pass"] for r in results),
            "checks": {kind: sum(c["outcome"] == kind for r in results for c in r["checks"])
                       for kind in ("pass", "fail", "unobserved")},
            "cases": results,
            "limitation": "Eight authored synthetic cases; not an accuracy estimate or third-party validation."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("verify", "score"))
    parser.add_argument("pack", type=Path)
    parser.add_argument("results", nargs="?", type=Path)
    args = parser.parse_args()
    try:
        manifest = verify(args.pack)
        if args.command == "verify":
            print(json.dumps({"verified": True, "pack_id": manifest["pack_id"], "files": len(manifest["files"])}, indent=2))
        else:
            if not args.results:
                parser.error("score requires normalized-results.json")
            print(json.dumps(score(args.pack, json.loads(args.results.read_text())), indent=2))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
