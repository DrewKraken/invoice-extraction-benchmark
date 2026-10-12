"""Offline checks of frozen synthetic source fields and recorded CSV/XLSX exports.

Python 3.10+, standard library only. No OCR, product imports, network, workbook
recalculation or independent duplicate detection. The duplicate observations
are supplied by the run operator who reviewed the workspace; they are not derived from
exports. Files are read without modification.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import posixpath
import re
import sys
import zipfile
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
P = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"s": S, "r": R, "p": P}


class CheckError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CheckError(message)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_path(base, name):
    require(isinstance(name, str) and name and "\\" not in name,
            "File references must be nonempty relative POSIX paths")
    raw = PurePosixPath(name)
    require(not raw.is_absolute() and ".." not in raw.parts and ":" not in name,
            f"Unsafe file reference: {name}")
    target = (base / name).resolve()
    require(target.is_relative_to(base.resolve()), f"File leaves pack/run directory: {name}")
    require(target.is_file(), f"Missing file: {name}")
    return target


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def number(value, label):
    require(value is not None and value != "" and not isinstance(value, bool),
            f"Missing or invalid number: {label}")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise CheckError(f"Invalid decimal: {label}") from exc
    require(result.is_finite(), f"Nonfinite number: {label}")
    return result


def source_arithmetic(document):
    expected = document["expected"]
    money, lines = expected["money"], expected["lines"]
    residuals = [number(line["line_total"], "line_total") -
                 number(line["quantity"], "quantity") * number(line["unit_price"], "unit_price")
                 for line in lines]
    mismatch = [i for i, residual in enumerate(residuals) if residual != 0]
    line_sum = sum((number(line["line_total"], "line_total") for line in lines), Decimal(0))
    totals = (number(money["total_amount"], "total_amount") -
              (number(money["subtotal"], "subtotal") + number(money["tax"], "tax") +
               number(money["shipping"], "shipping") - number(money["discount"], "discount")))
    arithmetic = expected["arithmetic"]
    require(mismatch == arithmetic["mismatch_line_indices"],
            f"{document['id']}: frozen line mismatch label disagrees with printed numbers")
    outcome = "mismatch" if mismatch or totals != 0 or line_sum != number(money["subtotal"], "subtotal") else "pass"
    require(outcome == arithmetic["outcome"], f"{document['id']}: frozen arithmetic outcome disagrees")
    require(residuals == [number(value, "frozen line residual") for value in arithmetic["line_residuals"]],
            f"{document['id']}: frozen line residuals disagree")
    require(line_sum == number(arithmetic["printed_line_sum"], "frozen printed line sum") and
            number(money["subtotal"], "subtotal") - line_sum == number(arithmetic["subtotal_residual"], "frozen subtotal residual") and
            totals == number(arithmetic["totals_residual"], "frozen totals residual"),
            f"{document['id']}: frozen totals residuals disagree")
    return {"outcome": outcome, "line_residuals": [str(v) for v in residuals],
            "printed_line_sum": str(line_sum), "totals_residual": str(totals)}


def verify_inputs(pack):
    manifest_path = pack / "manifest.json"
    manifest, freeze = load_json(manifest_path), load_json(pack / "freeze.json")
    require(manifest.get("schema") == "ipp-paired-source-evaluation/1" and manifest.get("synthetic_only") is True,
            "Unsupported or non-synthetic manifest")
    require(freeze.get("schema") == "ipp-paired-source-freeze/1", "Unsupported freeze schema")
    require(sha256(manifest_path) == freeze["manifest_sha256"], "Frozen manifest bytes changed")
    documents = manifest["documents"]
    require(isinstance(documents, list) and documents, "No source documents")
    ids = [document["id"] for document in documents]
    require(len(ids) == len(set(ids)), "Duplicate source document IDs")
    require(len(documents) == freeze["document_count"] == manifest["upload_count"], "Source count disagrees with freeze")
    require(len({document["sha256"] for document in documents}) == freeze["unique_pdf_sha256_count"] == manifest["unique_pdf_hashes"],
            "Unique source count disagrees with freeze")
    require({document["file"]: document["sha256"] for document in documents} == freeze["source_file_sha256"],
            "Source file/hash mapping disagrees with freeze")
    seen = set()
    calculations = {}
    for document in documents:
        require(sha256(local_path(pack, document["file"])) == document["sha256"],
                f"{document['id']}: source PDF bytes changed")
        for counterpart in document["expected_current_duplicate"]["counterpart_ids"]:
            require(counterpart in seen, f"{document['id']}: counterpart must be an earlier upload")
        calculations[document["id"]] = source_arithmetic(document)
        seen.add(document["id"])
    return manifest, calculations


def read_xlsx(path):
    """Read the product's static SpreadsheetML values; do not execute formulas."""
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        require(len(infos) <= 1000 and sum(info.file_size for info in infos) <= 20_000_000,
                "Workbook exceeds the small-pack reader's bounds")
        require(len({info.filename for info in infos}) == len(infos), "Duplicate ZIP members")
        require(not any("vbaProject" in info.filename for info in infos), "Macro workbook is unsupported")
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        require(workbook.tag == f"{{{S}}}workbook", "Unsupported workbook XML namespace")
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rels = {rel.attrib["Id"]: rel for rel in relationships}
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared = ["".join(node.text or "" for node in item.findall(".//s:t", NS)) for item in strings]
        sheets = {}
        for sheet in workbook.findall("s:sheets/s:sheet", NS):
            name = sheet.attrib["name"]
            require(name not in sheets, "Duplicate worksheet names")
            rel = rels[sheet.attrib[f"{{{R}}}id"]]
            require(rel.get("TargetMode") != "External", "External sheet relationship is unsupported")
            target = rel.attrib["Target"]
            member = posixpath.normpath(target.lstrip("/") if target.startswith("/") else "xl/" + target)
            require(member.startswith("xl/") and ".." not in PurePosixPath(member).parts,
                    "Unsafe sheet relationship")
            xml = ET.fromstring(archive.read(member))
            cells = {}
            for cell in xml.findall(".//s:sheetData/s:row/s:c", NS):
                address = cell.attrib["r"]
                require(address not in cells, "Duplicate worksheet cell")
                require(cell.find("s:f", NS) is None,
                        f"{name}!{address}: formula cells require a separate engine; cached values are not proof")
                kind = cell.get("t", "n")
                raw = cell.findtext("s:v", None, NS)
                if kind == "inlineStr":
                    value = "".join(node.text or "" for node in cell.findall(".//s:t", NS))
                elif kind == "s":
                    require(raw is not None and raw.isdigit() and int(raw) < len(shared), "Invalid shared string index")
                    value = shared[int(raw)]
                elif raw in (None, ""):
                    value = None
                elif kind == "n":
                    value = number(raw, f"{name}!{address}")
                elif kind in ("str", "d"):
                    value = raw
                else:
                    raise CheckError(f"{name}!{address}: unsupported cell type {kind}")
                cells[address] = value
            sheets[name] = cells
        return sheets


def table(cells):
    headers = {}
    for address, value in cells.items():
        match = re.fullmatch(r"([A-Z]+)([1-9][0-9]*)", address)
        require(match is not None, f"Unsupported cell address: {address}")
        if match[2] == "1" and value not in (None, ""):
            require(isinstance(value, str) and value not in headers.values(), "Invalid/duplicate table header")
            headers[match[1]] = value
    require(headers, "Missing table headers")
    row_numbers = sorted({int(re.search(r"[0-9]+$", address)[0]) for address in cells} - {1})
    rows = [{label: cells.get(f"{column}{row}") for column, label in headers.items()} for row in row_numbers]
    return [row for row in rows if any(value not in (None, "") for value in row.values())]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), "Missing/duplicate CSV headers")
        rows = list(reader)
        require(all(None not in row for row in rows), "CSV row contains extra fields")
        return rows


def compare_header(row, document, numeric_xlsx):
    expected = document["expected"]
    issues = []
    for required in ("Vendor", "Invoice #", "Currency", "Total", "Subtotal", "Tax", "Discount", "Shipping", "Customer Name", "PO Number"):
        if required not in row:
            issues.append(f"Missing required Full export column: {required}")
    if "Validation Status" not in row and "Validation" not in row:
        issues.append("Missing required arithmetic validation column")
    text_columns = {"Vendor": "vendor_name", "Invoice #": "invoice_number", "Currency": "currency"}
    text_columns.update({column: field for column, field in (("Customer Name", "customer_name"), ("PO Number", "po_number"))
                         if column in row})
    for column, field in text_columns.items():
        if row.get(column) != expected[field]:
            issues.append(f"{column} differs from source: expected {expected[field]!r}, got {row.get(column)!r}")
    date_column = "Invoice Date" if "Invoice Date" in row else "Date"
    if row.get(date_column) != expected["invoice_date"]:
        issues.append(f"Date differs from source: expected {expected['invoice_date']!r}, got {row.get(date_column)!r}")
    for column, field in {"Total": "total_amount", "Subtotal": "subtotal", "Tax": "tax", "Discount": "discount", "Shipping": "shipping"}.items():
        if column != "Total" and column not in row:
            continue
        value = row.get(column)
        if numeric_xlsx and not isinstance(value, Decimal):
            issues.append(f"XLSX {column} is not numeric")
        try:
            if number(value, column) != number(expected["money"][field], field):
                issues.append(f"{column} differs from printed amount/sign: expected {expected['money'][field]}, got {value!r}")
        except CheckError as exc:
            issues.append(str(exc))
    for column in ("Validation Status", "Validation"):
        if column in row and expected["arithmetic"]["outcome"] == "mismatch":
            if str(row[column]).lower() != "mismatch":
                issues.append(f"Printed line error lacks export mismatch: got {row[column]!r}")
    return issues


def verify_exports(pack, base, document, result):
    exports = result["exports"]
    outcomes = {}
    for kind in ("csv", "xlsx"):
        item = exports[kind]
        if item.get("status") == "unavailable":
            require(isinstance(item.get("reason"), str) and item["reason"].strip(),
                    f"{document['id']}: unavailable {kind} needs an explicit reason")
            require("file" not in item and "sha256" not in item, "Unavailable export cannot claim recorded bytes")
            outcomes[kind] = {"recorded_bytes_match_hash": None, "source_fields_match": False,
                              "availability": "unavailable", "issues": [item["reason"]]}
            continue
        path = local_path(base, item["file"])
        require(sha256(path) == item["sha256"], f"{document['id']}: recorded {kind} bytes changed")
        issues = []
        try:
            rows = read_csv(path) if kind == "csv" else table(read_xlsx(path)["All Invoices"])
            if len(rows) != 1:
                issues.append(f"Expected exactly one invoice row, got {len(rows)}")
            for row in rows:
                issues.extend(compare_header(row, document, kind == "xlsx"))
            if kind == "xlsx":
                lines = table(read_xlsx(path)["Line Items"])
                if len(lines) != len(document["expected"]["lines"]):
                    issues.append(f"Line row coverage differs: expected {len(document['expected']['lines'])}, got {len(lines)}")
                for actual, expected in zip(lines, document["expected"]["lines"]):
                    if (actual.get("Invoice #") != document["expected"]["invoice_number"] or
                            actual.get("Vendor") != document["expected"]["vendor_name"]):
                        issues.append("Line belongs to a different invoice")
                    if actual.get("Description") != expected["description"]:
                        issues.append(f"Line description differs: expected {expected['description']!r}, got {actual.get('Description')!r}")
                    for column, field in (("Quantity", "quantity"), ("Unit Price", "unit_price"), ("Total", "line_total")):
                        if not isinstance(actual.get(column), Decimal):
                            issues.append(f"XLSX line {column} is not numeric")
                        if actual.get(column) != number(expected[field], field):
                            issues.append(f"Line {column} differs: expected {expected[field]}, got {actual.get(column)!r}")
        except (CheckError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError, UnicodeError) as exc:
            issues.append(f"Cannot read supported export content: {exc}")
        outcomes[kind] = {"recorded_bytes_match_hash": True, "source_fields_match": not issues, "issues": issues}
    return outcomes


def verify_observations(manifest, run):
    require(run.get("schema") == "ipp-paired-source-observations/1", "Unsupported result schema")
    require(run.get("source_mode") == "pdf-workspace-upload", "Recorded run must declare actual PDF workspace uploads")
    results = run["documents"]
    ids = [result["id"] for result in results]
    expected_ids = [document["id"] for document in manifest["documents"]]
    require(ids == expected_ids, "Results must cover every source exactly once in upload order")
    checks = []
    for document, result in zip(manifest["documents"], results):
        observed, expected = result["duplicate"], document["expected_current_duplicate"]
        unavailable = observed is None or (isinstance(observed, dict) and observed.get("status") == "not_evaluated")
        if unavailable:
            status = result.get("duplicate_status") if observed is None else observed.get("status")
            basis = result.get("visible_basis") if observed is None else observed.get("reason", result.get("visible_basis"))
            require(status == "not_evaluated" and isinstance(basis, str) and basis.strip(),
                    f"{document['id']}: unevaluated duplicate needs explicit status and visible basis")
            if observed is not None:
                require(observed.get("potential_match_returned") is None and not observed.get("counterpart_ids"),
                        "An unevaluated duplicate cannot claim a match or no-match")
            require(all(item.get("status") == "unavailable" for item in result["exports"].values()),
                    "An unevaluated duplicate/result cannot claim recorded exports")
            checks.append({"id": document["id"], "duplicate_evaluation_status": "not_evaluated",
                           "declared_observation_matches_frozen_detector_contract": None,
                           "economic_reference": document["economic"], "observed": None, "visible_basis": basis})
            continue
        require(result.get("upload_outcome") != "no_persisted_result",
                "No persisted result cannot establish a duplicate/no-duplicate observation")
        require(isinstance(observed.get("potential_match_returned"), bool), f"{document['id']}: missing duplicate observation")
        require(isinstance(observed.get("method"), str) and observed["method"].strip(), f"{document['id']}: observation method missing")
        counterparts = observed.get("counterpart_ids")
        require(isinstance(counterparts, list) and len(counterparts) == len(set(counterparts)) and
                all(counterpart in expected_ids and counterpart != document["id"] for counterpart in counterparts),
                f"{document['id']}: invalid counterpart IDs")
        contract_met = (observed["potential_match_returned"] == expected["potential_match_returned"] and
                        set(counterparts) == set(expected["counterpart_ids"]))
        checks.append({"id": document["id"], "duplicate_evaluation_status": "evaluated",
                       "declared_observation_matches_frozen_detector_contract": contract_met,
                       "economic_reference": document["economic"], "observed": observed})
    return checks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, default=Path(__file__).resolve().parents[1] / "examples/paired-checks-v1")
    parser.add_argument("--inputs-only", action="store_true", help="Verify source bytes/frozen arithmetic before a live run")
    parser.add_argument("--run", type=Path, help="A reviewer's observation JSON; export paths resolve relative to that JSON")
    parser.add_argument("--require-contract", action="store_true", help="Also return nonzero for product/source contract discrepancies")
    parser.add_argument("--out", type=Path, help="Write a checker report separately; input files remain unchanged")
    args = parser.parse_args(argv)
    try:
        pack = args.pack.resolve()
        manifest, calculations = verify_inputs(pack)
        protected_paths = {pack / "manifest.json", pack / "freeze.json", pack / "recorded-results.json"}
        protected_paths.update(local_path(pack, document["file"]) for document in manifest["documents"])
        report = {"schema": "ipp-paired-pack-verification/1", "pack_integrity": "verified", "source_integrity": "verified",
                  "source_arithmetic": calculations, "pdf_extraction_executed_by_checker": False,
                  "duplicate_ui_replayed_by_checker": False, "workbook_recalculated": False}
        if args.inputs_only:
            report["exports"] = "not checked; inputs-only mode"
            exit_code = 0
        else:
            run_path = args.run.resolve() if args.run else pack / "recorded-results.json"
            run = load_json(run_path)
            protected_paths.add(run_path)
            if "source_manifest_sha256" in run:
                require(run["source_manifest_sha256"] == sha256(pack / "manifest.json"), "Run references a different source manifest")
            observations = verify_observations(manifest, run)
            exports = {document["id"]: verify_exports(pack, run_path.parent, document, result)
                       for document, result in zip(manifest["documents"], run["documents"])}
            protected_paths.update(local_path(run_path.parent, item["file"])
                                   for result in run["documents"] for item in result["exports"].values() if "file" in item)
            report.update(exports=exports, duplicate_observations=observations,
                          duplicate_observation_scope="Validates an operator-recorded workspace observation, not independent UI/duplicate detection")
            if "duplicate_groups" in run:
                groups = run["duplicate_groups"]
                known = {document["id"] for document in manifest["documents"]}
                require(isinstance(groups, list) and all(isinstance(group, list) and len(group) >= 2 for group in groups),
                        "Invalid declared duplicate groups")
                members = [member for group in groups for member in group]
                require(len(members) == len(set(members)) and all(member in known for member in members),
                        "Declared groups must use known IDs without repeated membership")
                report["operator_recorded_duplicate_groups"] = groups
                report["group_scope"] = "Supplied operator observations; UI grouping was not independently replayed"
            if "group_capture" in run:
                capture = run["group_capture"]
                path = local_path(run_path.parent, capture["file"])
                require(sha256(path) == capture["sha256"], "Recorded group capture bytes changed")
                protected_paths.add(path)
                report["group_capture_integrity"] = "verified; visual/content interpretation requires review"
            contract_met = all(check["declared_observation_matches_frozen_detector_contract"] is True for check in observations)
            source_match = all(kind["source_fields_match"] for document in exports.values() for kind in document.values())
            report["frozen_detector_contract_met"] = contract_met
            report["duplicate_observation_counts"] = {
                "evaluated": sum(check["duplicate_evaluation_status"] == "evaluated" for check in observations),
                "not_evaluated": sum(check["duplicate_evaluation_status"] == "not_evaluated" for check in observations),
                "observed_contract_discrepancies": sum(check["declared_observation_matches_frozen_detector_contract"] is False for check in observations)}
            report["exported_source_fields_match"] = source_match
            report["integrity_success_does_not_mean_product_contract_success"] = True
            exit_code = 1 if args.require_contract and not (contract_met and source_match) else 0
        serialized = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
        if args.out:
            require(args.out.resolve() not in {path.resolve() for path in protected_paths},
                    "Report path must not overwrite source/observations")
            require(args.out.suffix.lower() == ".json", "Report path must end in .json")
            if args.out.exists():
                require(load_json(args.out).get("schema") == "ipp-paired-pack-verification/1",
                        "Only an earlier checker report can be overwritten")
            args.out.write_text(serialized, encoding="utf-8")
        print(serialized, end="")
        return exit_code
    except (CheckError, OSError, KeyError, TypeError, IndexError, zipfile.BadZipFile, ET.ParseError, json.JSONDecodeError) as exc:
        print(json.dumps({"schema": "ipp-paired-pack-verification/1", "status": "failed", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
