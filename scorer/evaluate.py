"""
Score a predictions file against the corpus answer keys.

    python -m scorer.evaluate predictions.json
    python -m scorer.evaluate predictions.json --out scores.json --markdown scores.md

The predictions file (see examples/predictions.example.json):

    {
      "system": "Tool name and version",
      "run_date": "2026-10-03",
      "documents": {
        "<doc_id>": {
          "vendor_name": "...", "invoice_number": "...",
          "invoice_date": "YYYY-MM-DD", "due_date": "YYYY-MM-DD" or null,
          "currency": "ZAR", "subtotal": 100.0, "tax": 15.0, "total_amount": 115.0,
          "document_type": "invoice" | "credit_note" | "other",
          "line_items": [{"description": "...", "amount": 100.0}],
          "flagged": false,
          "references": ["TR12345"]
        }
      }
    }

`documents` may also be a list of objects that each carry a `doc_id`.
`total` is accepted for `total_amount`, and `line_total` or `total` for a
line's `amount`. A document missing from the file counts as "no result":
every field it is scored on is wrong (pass --allow-missing to score only the
documents present, for a partial run; the summary then says so).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .score import FieldResult, fully_correct, line_f1, score_document

ROOT = Path(__file__).resolve().parents[1]

KEY_FIELDS = (
    "vendor_name", "invoice_number", "invoice_date", "due_date", "currency",
    "subtotal", "tax", "total", "document_type",
)
FIELD_ORDER = KEY_FIELDS + ("line_items", "flag", "references")
CATEGORY_ORDER = ("clean", "currency", "tax", "credit", "multipage", "freight", "scan", "photo",
                  "handwritten", "hard")


def pct(n: int, d: int) -> str:
    """A percentage to one decimal, without a trailing ".0" (100, not 100.0)."""
    if d <= 0:
        return "n/a"
    v = round(n / d * 1000) / 10
    return str(int(v)) if float(v).is_integer() else f"{v:.1f}"


def load_answers(corpus: Path) -> Dict[str, Dict[str, Any]]:
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    return {d["doc_id"]: d for d in manifest["documents"]}


def normalise_prediction(p: Dict[str, Any]) -> Dict[str, Any]:
    p = dict(p)
    if p.get("total_amount") is None and p.get("total") is not None:
        p["total_amount"] = p["total"]
    refs = p.get("references") or []
    p["references"] = [r if isinstance(r, dict) else {"value": r} for r in refs]
    p["flagged"] = bool(p.get("flagged"))
    return p


def load_predictions(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    docs = raw.get("documents", raw) if isinstance(raw, dict) else raw
    if isinstance(docs, list):
        docs = {d["doc_id"]: d for d in docs}
    meta = {k: raw.get(k) for k in ("system", "run_date", "notes")} if isinstance(raw, dict) else {}
    return {"meta": meta, "documents": {k: normalise_prediction(v) for k, v in docs.items() if v is not None}}


def score_all(answers: Dict[str, Dict[str, Any]], preds: Dict[str, Dict[str, Any]],
              allow_missing: bool = False) -> List[Dict[str, Any]]:
    records = []
    for doc_id, ans in answers.items():
        if allow_missing and doc_id not in preds:
            continue
        results: List[FieldResult] = score_document(ans["expected"], preds.get(doc_id))
        records.append({
            "doc_id": doc_id,
            "category": ans["category"],
            "difficulty": ans["difficulty"],
            "severity": ans.get("severity"),
            "kind": ans["kind"],
            "tags": ans.get("tags") or [],
            "should_flag": ans["expected"]["should_flag"],
            "predicted": doc_id in preds,
            "fields": {r.field: r.as_dict() for r in results},
            "fully_correct": fully_correct(results, KEY_FIELDS),
            "line_f1": line_f1(results),
        })
    return records


def _tally(records: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    return {"docs": len(records), "fully_correct": sum(1 for r in records if r["fully_correct"])}


def summarize(records: List[Dict[str, Any]], answers_total: int) -> Dict[str, Any]:
    fields: Dict[str, Dict[str, int]] = {}
    for f in FIELD_ORDER:
        rows = [r["fields"][f] for r in records if f in r["fields"]]
        if rows:
            fields[f] = {"correct": sum(1 for x in rows if x["correct"]), "scored": len(rows)}
    key_scored = sum(v["scored"] for f, v in fields.items() if f in KEY_FIELDS)
    key_correct = sum(v["correct"] for f, v in fields.items() if f in KEY_FIELDS)
    f1s = [r["line_f1"] for r in records if r["line_f1"] is not None]
    flagged = lambda r: bool(r["fields"]["flag"]["got"])  # noqa: E731
    flag_docs = [r for r in records if "flag" in r["fields"]]
    inconsistent = [r for r in flag_docs if r["should_flag"] and r["kind"] != "multi_invoice"]
    multi = [r for r in flag_docs if r["kind"] == "multi_invoice"]
    consistent = [r for r in flag_docs if not r["should_flag"]]
    return {
        "documents": len(records),
        "documents_in_corpus": answers_total,
        "documents_without_prediction": sum(1 for r in records if not r["predicted"]),
        "fully_correct": sum(1 for r in records if r["fully_correct"]),
        "key_fields": {"correct": key_correct, "scored": key_scored},
        "fields": fields,
        "line_items": {"docs": len(f1s), "f1_sum": round(sum(f1s), 2),
                       "f1_mean": round(sum(f1s) / len(f1s), 3) if f1s else None,
                       "all_lines_right": sum(1 for x in f1s if x >= 0.999)},
        "flags": {
            "inconsistent_invoices": {"total": len(inconsistent), "flagged": sum(map(flagged, inconsistent))},
            "multi_invoice_files": {"total": len(multi), "flagged": sum(map(flagged, multi))},
            "consistent_documents": {"total": len(consistent), "flagged": sum(map(flagged, consistent))},
        },
        "categories": {c: _tally([r for r in records if r["category"] == c])
                       for c in CATEGORY_ORDER if any(r["category"] == c for r in records)},
        "difficulty": {d: _tally([r for r in records if r["difficulty"] == d])
                       for d in ("easy", "medium", "hard") if any(r["difficulty"] == d for r in records)},
        "severity": {s: _tally([r for r in records if r["severity"] == s])
                     for s in ("mild", "moderate", "severe") if any(r["severity"] == s for r in records)},
    }


def render_markdown(s: Dict[str, Any], meta: Dict[str, Any]) -> str:
    L = []
    title = meta.get("system") or "predictions"
    L.append(f"# {title}" + (f" ({meta['run_date']})" if meta.get("run_date") else ""))
    L.append("")
    if s["documents"] != s["documents_in_corpus"]:
        L.append(f"**Partial run: {s['documents']} of {s['documents_in_corpus']} documents scored.**\n")
    if s["documents_without_prediction"]:
        L.append(f"{s['documents_without_prediction']} documents had no prediction and count as wrong.\n")
    kf = s["key_fields"]
    li = s["line_items"]
    fl = s["flags"]
    L += [
        "| Measure | Result |", "|---|---|",
        f"| Documents with every key header field right | {pct(s['fully_correct'], s['documents'])}% "
        f"({s['fully_correct']} of {s['documents']}) |",
        f"| Key header fields right | {pct(kf['correct'], kf['scored'])}% ({kf['correct']} of {kf['scored']}) |",
        f"| Line items, mean F1 | {li['f1_mean']} ({li['docs']} documents; all lines right on {li['all_lines_right']}) |",
        f"| Invoices whose figures do not add up, flagged | {fl['inconsistent_invoices']['flagged']} of "
        f"{fl['inconsistent_invoices']['total']} |",
        f"| Files holding several invoices, flagged | {fl['multi_invoice_files']['flagged']} of "
        f"{fl['multi_invoice_files']['total']} |",
        f"| Consistent documents flagged (false alarms) | {fl['consistent_documents']['flagged']} of "
        f"{fl['consistent_documents']['total']} |",
        "", "## Fields", "", "| Field | Right | Scored | % |", "|---|---|---|---|",
    ]
    for f, v in s["fields"].items():
        L.append(f"| {f} | {v['correct']} | {v['scored']} | {pct(v['correct'], v['scored'])} |")
    for name, key in (("Category", "categories"), ("Difficulty", "difficulty"), ("Photo/scan severity", "severity")):
        L += ["", f"## By {name.lower()}", "", f"| {name} | Documents | Fully correct | % |", "|---|---|---|---|"]
        for k, v in s[key].items():
            L.append(f"| {k} | {v['docs']} | {v['fully_correct']} | {pct(v['fully_correct'], v['docs'])} |")
    return "\n".join(L) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Score invoice extraction predictions against the benchmark answer keys.")
    p.add_argument("predictions", type=Path)
    p.add_argument("--corpus", type=Path, default=ROOT / "corpus" / "v1")
    p.add_argument("--out", type=Path, help="write the summary and per-document field results as JSON")
    p.add_argument("--markdown", type=Path, help="write the summary as a Markdown table")
    p.add_argument("--allow-missing", action="store_true",
                   help="score only documents present in the predictions (a partial run)")
    a = p.parse_args(argv)
    answers = load_answers(a.corpus)
    preds = load_predictions(a.predictions)
    unknown = sorted(set(preds["documents"]) - set(answers))
    if unknown:
        print(f"warning: {len(unknown)} predictions for unknown doc ids ignored: {', '.join(unknown[:5])}...",
              file=sys.stderr)
    records = score_all(answers, preds["documents"], a.allow_missing)
    summary = summarize(records, len(answers))
    md = render_markdown(summary, preds["meta"])
    print(md)
    if a.out:
        a.out.write_text(json.dumps({"meta": preds["meta"], "summary": summary, "documents": records},
                                    indent=1, default=str) + "\n", encoding="utf-8")
    if a.markdown:
        a.markdown.write_text(md, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
