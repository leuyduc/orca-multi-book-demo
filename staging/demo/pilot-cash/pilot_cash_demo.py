"""Synthetic cash-book pilot: P1-verified CSV -> review proposals, NEVER a writer.

Usage: python staging/demo/pilot-cash/pilot_cash_demo.py --document ...
All paths remain inside staging/demo. No external service access or real books.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

STAGE_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_MODULE = STAGE_ROOT / "p1-manifest" / "manifest_demo.py"
TEMPLATE_FILES = frozenset({"chung_tu.csv", "doi_chieu.csv"})
CASH_COLUMNS = {"RECORD_ID", "TRANSACTION_ID", "EVIDENCE_TYPE", "AMOUNT", "PROJECT_ID"}
REVIEW_COLUMNS = {"RECORD_ID", "STATUS", "NOTE"}
RESULT_FILE = "cash_proposals.json"
VERSION = "CASH-PILOT-DEMO-1"


class PilotError(ValueError):
    pass


def require(test, reason):
    if not test:
        raise PilotError(reason)


def load_manifest_module():
    spec = spec_from_file_location("p1_manifest_for_cash_pilot", MANIFEST_MODULE)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def guard_path(value: Path, kind: str, allow_absent: bool = False) -> Path:
    original = Path(value).absolute()
    # Every ancestor under the DEMO tree must not be a symlink/junction.
    require(original.resolve().is_relative_to(STAGE_ROOT), "PATH_OUTSIDE_DEMO")
    current = original
    while current != STAGE_ROOT:
        require(not current.is_symlink() and not getattr(current, "is_junction", lambda: False)(),
                "SYMLINK_PATH_FORBIDDEN")
        current = current.parent
    require(allow_absent or original.exists(), f"MISSING_{kind}")
    require(not original.is_symlink() and not getattr(original, "is_junction", lambda: False)(),
            "SYMLINK_PATH_FORBIDDEN")
    return original


def load_csv_checked(root: Path, name: str, expected_sha: str, expected_count: int):
    path = root / name
    require(not path.is_symlink(), "SOURCE_SYMLINK_FORBIDDEN")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha, "SOURCE_CHANGED_DURING_PILOT")
    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True))
    require(len(rows) == expected_count, "SOURCE_ROW_COUNT_CHANGED")
    return rows


def amount(value):
    require(isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d{1,2})?", value) is not None,
            "INVALID_AMOUNT")
    try:
        number = Decimal(value)
    except InvalidOperation as ex:
        raise PilotError("INVALID_AMOUNT") from ex
    require(number > 0 and number.is_finite() and number <= Decimal("1000000000000.00"),
            "INVALID_AMOUNT")
    return number


def decimal_text(value: Decimal):
    return format(value.quantize(Decimal("0.01")), ".2f")


def build_review_report(doc_path: Path, source_root: Path, manifest_dir: Path):
    """Verify actual source bytes against a pre-existing P1 seal and checkpoint.

    Does NOT recreate a changed manifest. No mutation or implicit approval.
    """
    module = load_manifest_module()
    doc_path = guard_path(doc_path, "DOCUMENT")
    source_root = guard_path(source_root, "SOURCE_ROOT")
    manifest_dir = guard_path(manifest_dir, "MANIFEST_DIR")
    require(doc_path.is_file() and source_root.is_dir() and manifest_dir.is_dir(),
            "INVALID_INPUT_TYPE")
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    book = doc["BOOK"]
    require(doc.get("DATA_CLASS") == "SYNTHETIC_ONLY" and doc.get("DESTINATION_WRITE") is False,
            "READ_ONLY_DEMO_REQUIRED")
    require(book["BOOK_KIND"] == "ACCOUNTING", "UNSUPPORTED_BOOK_KIND")
    require(book["BOOK_ID"].startswith("DEMO-"), "NOT_A_DEMO_BOOK")
    manifest = json.loads((manifest_dir / "source_manifest.json").read_text(encoding="utf-8"))
    seal = json.loads((manifest_dir / "source_seal.json").read_text(encoding="utf-8"))
    cp_path = manifest_dir / (module.ticket_id(doc) + ".json")
    checkpoint = json.loads(cp_path.read_text(encoding="utf-8"))
    result = module.verify_manifest(source_root, doc, manifest, seal, checkpoint)
    require(result["status"] == "VERIFIED_SYNTHETIC_ONLY",
            "P1_BLOCKED:" + ",".join(result["errors"]))
    file_rows = {f["REL_PATH"]: f for f in manifest["FILES"]}
    require(set(file_rows) == TEMPLATE_FILES, "CASH_TEMPLATE_FILES_REQUIRED")
    source_rows = load_csv_checked(source_root, "chung_tu.csv",
                                   file_rows["chung_tu.csv"]["SHA256"],
                                   file_rows["chung_tu.csv"]["ROW_COUNT"])
    reviews = load_csv_checked(source_root, "doi_chieu.csv",
                               file_rows["doi_chieu.csv"]["SHA256"],
                               file_rows["doi_chieu.csv"]["ROW_COUNT"])
    require(bool(source_rows) and all(set(r) == CASH_COLUMNS for r in source_rows),
            "INVALID_CASH_COLUMNS")
    require(all(set(r) == REVIEW_COLUMNS for r in reviews), "INVALID_REVIEW_COLUMNS")
    status_by_record = {}
    for r in reviews:
        rid = r["RECORD_ID"]
        require(rid and rid not in status_by_record, "DUPLICATE_REVIEW_RECORD")
        require(r["STATUS"] in {"WAIT_REVIEW", "FLAGGED"}, "INVALID_REVIEW_STATUS")
        status_by_record[rid] = r["STATUS"]
    by_tx = defaultdict(list)
    seen_records = set()
    for row in source_rows:
        rid, tx = row["RECORD_ID"], row["TRANSACTION_ID"]
        require(re.fullmatch(r"[A-Z0-9-]{3,60}", rid) is not None and rid not in seen_records,
                "DUPLICATE_OR_INVALID_RECORD")
        seen_records.add(rid)
        require(re.fullmatch(r"[A-Z0-9-]{3,60}", tx) is not None, "INVALID_TRANSACTION_ID")
        require(row["PROJECT_ID"] == doc["PROJECT"]["PROJECT_ID"], "CASH_PROJECT_SCOPE_MISMATCH")
        require(row["EVIDENCE_TYPE"] in {"BILL", "TRANSFER"}, "UNKNOWN_EVIDENCE_TYPE")
        parsed_amount = amount(row["AMOUNT"])
        by_tx[tx].append({**row, "amount_value": parsed_amount})
    require(seen_records == set(status_by_record), "CASH_REVIEW_SET_MISMATCH")

    proposals = []
    for tx in sorted(by_tx):
        evidence = by_tx[tx]
        bills = [e for e in evidence if e["EVIDENCE_TYPE"] == "BILL"]
        transfers = [e for e in evidence if e["EVIDENCE_TYPE"] == "TRANSFER"]
        unique_match = (len(bills) == 1 and len(transfers) == 1 and
                        bills[0]["amount_value"] == transfers[0]["amount_value"])
        statuses = {status_by_record[e["RECORD_ID"]] for e in evidence}
        ready = unique_match and statuses == {"WAIT_REVIEW"}
        if ready:
            reason = "MATCHED_BILL_AND_TRANSFER"
            cash_out = transfers[0]["amount_value"]
            cost = bills[0]["amount_value"]
        elif len(transfers) == 0:
            reason = "MISSING_TRANSFER"
            cash_out = Decimal(0)
            cost = Decimal(0)
        elif len(bills) == 0:
            reason = "MISSING_BILL"
            cash_out = Decimal(0)
            cost = Decimal(0)
        else:
            reason = "AMBIGUOUS_OR_FLAGGED_EVIDENCE"
            cash_out = Decimal(0)
            cost = Decimal(0)
        proposals.append({
            "TRANSACTION_ID": tx,
            "BOOK_ID": book["BOOK_ID"],
            "LEGAL_ENTITY_ID": book["LEGAL_ENTITY_ID"],
            "PERIOD": book["PERIOD"],
            "PROJECT_ID": doc["PROJECT"]["PROJECT_ID"],
            "RECORD_IDS": sorted(e["RECORD_ID"] for e in evidence),
            "PROPOSED_CASH_OUT": decimal_text(cash_out),
            "PROPOSED_COST": decimal_text(cost),
            "REVIEW_STATE": "READY_FOR_OWNER" if ready else "NEEDS_REVIEW",
            "REASON": reason,
            "APPROVAL_STATUS": "UNAPPROVED",
            "DESTINATION_WRITE_ALLOWED": False,
        })
    report = {
        "VERSION": VERSION,
        "DATA_CLASS": "SYNTHETIC_ONLY",
        "LIVE_AUTHORIZED": False,
        "DESTINATION_WRITE_ALLOWED": False,
        "BOOK_ID": book["BOOK_ID"],
        "LEGAL_ENTITY_ID": book["LEGAL_ENTITY_ID"],
        "PERIOD": book["PERIOD"],
        "SOURCE_SNAPSHOT_ID": doc["JOB"]["SOURCE_SNAPSHOT_ID"],
        "P1_MANIFEST_SHA256": seal["MANIFEST_SHA256"],
        "SOURCE_FILE_COUNT": manifest["FILE_COUNT"],
        "EVIDENCE_RECORD_COUNT": len(source_rows),
        "TRANSACTION_COUNT": len(proposals),
        "READY_FOR_OWNER_COUNT": sum(x["REVIEW_STATE"] == "READY_FOR_OWNER" for x in proposals),
        "NEEDS_REVIEW_COUNT": sum(x["REVIEW_STATE"] == "NEEDS_REVIEW" for x in proposals),
        "PROPOSALS": proposals,
    }
    return report


def save_once(report, output_dir: Path, source_root: Path | None = None):
    output_dir = guard_path(output_dir, "OUTPUT_DIR", allow_absent=True)
    if source_root is not None:
        source_root = guard_path(source_root, "SOURCE_ROOT")
        require(not output_dir.is_relative_to(source_root), "OUTPUT_INSIDE_SOURCE")
    require(not output_dir.is_relative_to(STAGE_ROOT / "p1-manifest" / "input-A") and
            not output_dir.is_relative_to(STAGE_ROOT / "p1-manifest" / "input-B"),
            "OUTPUT_INSIDE_SOURCE")
    require(output_dir != STAGE_ROOT, "OUTPUT_ON_STAGING_ROOT_FORBIDDEN")
    output = output_dir / RESULT_FILE
    require(not output.is_symlink(), "OUTPUT_SYMLINK_FORBIDDEN")
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    if output_dir.exists():
        require(output_dir.is_dir(), "INVALID_OUTPUT_DIR")
        require({p.name for p in output_dir.iterdir()} <= {RESULT_FILE}, "OUTPUT_CONTAINS_OTHER_FILES")
        if output.exists():
            require(output.read_bytes() == encoded, "OUTPUT_CHANGED_OR_SOURCE_MISMATCH")
            return "ALREADY_PREPARED"
    else:
        output_dir.mkdir(parents=False, exist_ok=False)
    # x mode: never overwrite a proposal/checkpoint, including concurrent callers.
    try:
        with output.open("xb") as handle:
            handle.write(encoded)
    except FileExistsError:
        require(output.read_bytes() == encoded, "OUTPUT_CHANGED_OR_SOURCE_MISMATCH")
        return "ALREADY_PREPARED"
    return "PREPARED_FOR_REVIEW"


def cli():
    parser = argparse.ArgumentParser(description="Synthetic-only cash pilot; NEVER records a real book.")
    parser.add_argument("--document", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build_review_report(args.document, args.source_root, args.manifest_dir)
    status = save_once(report, args.output_dir, source_root=args.source_root)
    print(json.dumps({
        "status": status, "book_id": report["BOOK_ID"],
        "transaction_count": report["TRANSACTION_COUNT"],
        "ready_for_owner": report["READY_FOR_OWNER_COUNT"],
        "needs_review": report["NEEDS_REVIEW_COUNT"],
        "live_authorized": False, "destination_write_allowed": False
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(cli())
    except (PilotError, KeyError, TypeError, OSError, ValueError, UnicodeError, csv.Error) as ex:
        code = str(ex) if isinstance(ex, PilotError) else "INVALID_PILOT_DATA"
        print(json.dumps({"status": "BLOCKED", "reason": code,
                          "live_authorized": False}, ensure_ascii=False))
        sys.exit(2)
