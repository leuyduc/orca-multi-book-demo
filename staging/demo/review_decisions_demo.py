"""Simulation-only review decisions with scoped audit; NEVER a ledger writer.

Human may explicitly edit a local JSON decision request. Reviewer IDs are DEMO
labels and are NOT cryptographic identity verification or production approval.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import cash_review_flow as review
import m3_p1_bridge as bridge

VERSION = "DEMO_REVIEW_V1"
ACTIONS = {"DEMO_APPROVE", "DEMO_REJECT", "DEMO_REQUEST_MORE"}
AUDIT_COLUMNS = ["BOOK_ID", "TRANSACTION_ID", "REVIEWER_ID", "ACTION",
                 "PREVIOUS_STATUS", "NEW_STATUS", "DECIDED_AT",
                 "REVIEW_REPORT_SHA256", "NOTE", "LIVE_AUTHORIZED",
                 "DESTINATION_WRITE_ALLOWED"]


class DemoReviewError(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise DemoReviewError(code)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def scoped_report(book):
    before = review.propose(book)  # P1->M3 checks source and checkpoint again
    directory = bridge.safe_sandbox(book)
    read_path = directory / review.REVIEW_DIR / "review_proposals.json"
    require(read_path.is_file() and not read_path.is_symlink(), "REVIEW_REPORT_NOT_PREPARED")
    raw = read_path.read_bytes()
    require(raw == review.bytes_for_report(before)["review_proposals.json"],
            "REVIEW_REPORT_TAMPERED")
    return before, hashlib.sha256(raw).hexdigest()


def decision_template(book):
    report, sha = scoped_report(book)
    doc = json.loads((bridge.safe_sandbox(book) / "p1_document.json").read_text(encoding="utf-8"))
    expected = bridge.BOOK_MAP[book][2]  # Fake reviewer from synthetic fixture.
    require(expected in doc["DEMO_OWNER_DIRECTORY"], "DEMO_REVIEWER_NOT_IN_DIRECTORY")
    return {
        "VERSION": VERSION,
        "DATA_CLASS": "SYNTHETIC_ONLY",
        "BOOK_ID": book,
        "LEGAL_ENTITY_ID": report["LEGAL_ENTITY_ID"],
        "PERIOD": report["PERIOD"],
        "P1_MANIFEST_SHA256": report["P1_MANIFEST_SHA256"],
        "REVIEW_REPORT_SHA256": sha,
        "REVIEWER_ID": expected,
        "DECIDED_AT": datetime.now().astimezone().isoformat(timespec="seconds"),
        "LIVE_AUTHORIZED": False,
        "DESTINATION_WRITE_ALLOWED": False,
        "DECISIONS": [
            {
                "TRANSACTION_ID": tx["TRANSACTION_ID"],
                "EXPECTED_REVIEW_STATE": tx["REVIEW_STATE"],
                "ACTION": "DEMO_REQUEST_MORE",
                "NOTE": "CHUA_DUOC_NGUOI_PHU_TRACH_XAC_NHAN",
            } for tx in report["PROPOSALS"]
        ],
    }


def prepare(book):
    sandbox = bridge.safe_sandbox(book)
    # Build review output separately. It is immutable and never a posted ledger.
    report = review.propose(book)
    review.save_once(book, report)
    template = decision_template(book)
    path = sandbox / "decision-request.json"
    payload = json_bytes(template)
    if path.exists():
        require(path.is_file() and not path.is_symlink(), "DECISION_REQUEST_CHANGED")
        # Keep any legitimate manual edits; never overwrite a reviewer decision.
        return {"status": "DECISION_REQUEST_ALREADY_EXISTS", "path": path.name,
                "destination_write_allowed": False}
    with path.open("xb") as f:
        f.write(payload)
    return {"status": "DECISION_TEMPLATE_READY", "path": path.name,
            "decisions": len(template["DECISIONS"]), "destination_write_allowed": False}


def evaluate(book, request, report, review_sha):
    require(isinstance(request, dict) and request.get("DATA_CLASS") == "SYNTHETIC_ONLY"
            and request.get("VERSION") == VERSION, "INVALID_DECISION_VERSION")
    expected_scope = {
        "BOOK_ID": book,
        "LEGAL_ENTITY_ID": report["LEGAL_ENTITY_ID"],
        "PERIOD": report["PERIOD"],
        "P1_MANIFEST_SHA256": report["P1_MANIFEST_SHA256"],
        "REVIEW_REPORT_SHA256": review_sha,
        "LIVE_AUTHORIZED": False,
        "DESTINATION_WRITE_ALLOWED": False,
    }
    for key, value in expected_scope.items():
        require(type(request.get(key)) is type(value) and request[key] == value,
                "DECISION_SCOPE_OR_REPORT_CHANGED")
    reviewer = bridge.BOOK_MAP[book][2]  # Only a fake role label, never real auth.
    require(request.get("REVIEWER_ID") == reviewer, "DEMO_REVIEWER_WRONG_SCOPE")
    timestamp = request.get("DECIDED_AT")
    require(isinstance(timestamp, str), "DECISION_TIMESTAMP_MISSING")
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise DemoReviewError("INVALID_DECISION_TIMESTAMP") from exc
    require(moment.tzinfo is not None and moment.utcoffset() is not None,
            "INVALID_DECISION_TIMESTAMP")
    proposals = {item["TRANSACTION_ID"]: item for item in report["PROPOSALS"]}
    require(len(proposals) == report["TRANSACTION_COUNT"], "DUPLICATE_PROPOSAL")
    decisions = request.get("DECISIONS")
    require(isinstance(decisions, list) and
            len(decisions) == len(proposals), "DECISION_SET_INCOMPLETE")
    seen = set()
    events = []
    for item in decisions:
        require(isinstance(item, dict) and
                set(item) == {"TRANSACTION_ID", "EXPECTED_REVIEW_STATE", "ACTION", "NOTE"},
                "INVALID_DECISION_FIELDS")
        txid = item["TRANSACTION_ID"]
        require(isinstance(txid, str) and txid in proposals and txid not in seen,
                "DUPLICATE_OR_UNKNOWN_TRANSACTION")
        seen.add(txid)
        source = proposals[txid]
        require(item["EXPECTED_REVIEW_STATE"] == source["REVIEW_STATE"],
                "STALE_REVIEW_STATE")
        action = item["ACTION"]
        require(action in ACTIONS, "INVALID_DECISION_ACTION")
        require(isinstance(item["NOTE"], str) and 4 <= len(item["NOTE"]) <= 500,
                "DECISION_NOTE_REQUIRED")
        if action == "DEMO_APPROVE":
            require(source["REVIEW_STATE"] == "READY_FOR_OWNER",
                    "CANNOT_APPROVE_UNREADY_TRANSACTION")
        new_status = {
            "DEMO_APPROVE": "DEMO_APPROVED_ONLY",
            "DEMO_REJECT": "DEMO_REJECTED_ONLY",
            "DEMO_REQUEST_MORE": "DEMO_NEEDS_MORE_ONLY",
        }[action]
        events.append({
            "BOOK_ID": book,
            "TRANSACTION_ID": txid,
            "REVIEWER_ID": reviewer,
            "ACTION": action,
            "PREVIOUS_STATUS": source["REVIEW_STATE"],
            "NEW_STATUS": new_status,
            "DECIDED_AT": timestamp,
            "REVIEW_REPORT_SHA256": review_sha,
            "NOTE": item["NOTE"],
            "LIVE_AUTHORIZED": False,
            "DESTINATION_WRITE_ALLOWED": False,
        })
    events.sort(key=lambda x: x["TRANSACTION_ID"])
    return {
        "VERSION": VERSION,
        "DATA_CLASS": "SYNTHETIC_ONLY",
        "BOOK_ID": book,
        "REVIEW_REPORT_SHA256": review_sha,
        "REVIEWER_ID": reviewer,
        "REVIEWER_IDENTITY_AUTHENTICATED": False,
        "DECIDED_AT": timestamp,
        "EVENTS": events,
        "COUNTS": {
            "DEMO_APPROVED": sum(e["ACTION"] == "DEMO_APPROVE" for e in events),
            "DEMO_REJECTED": sum(e["ACTION"] == "DEMO_REJECT" for e in events),
            "DEMO_REQUEST_MORE": sum(e["ACTION"] == "DEMO_REQUEST_MORE" for e in events),
        },
        "APPROVAL_STATUS": "DEMO_SIMULATED_ONLY",
        "DESTINATION_WRITE_ALLOWED": False,
        "LIVE_AUTHORIZED": False,
    }


def persist_once(book, decisions):
    sandbox = bridge.safe_sandbox(book)
    target = sandbox / "review-decisions"
    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=AUDIT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(decisions["EVENTS"])
    payload = {
        "review_audit_demo.json": json_bytes(decisions),
        "review_audit_demo.csv": csv_buffer.getvalue().encode("utf-8-sig"),
    }
    if target.exists():
        require(target.is_dir() and not target.is_symlink(), "AUDIT_OUTPUT_CHANGED")
        require({p.name for p in target.iterdir()} == set(payload),
                "AUDIT_OUTPUT_CHANGED")
        for name, data in payload.items():
            p = target / name
            require(p.is_file() and not p.is_symlink() and p.read_bytes() == data,
                    "AUDIT_OUTPUT_CHANGED")
        return "SIMULATED_REVIEW_ALREADY_RECORDED"
    with tempfile.TemporaryDirectory(prefix=".demo-review-pending-", dir=sandbox) as temp:
        for name, blob in payload.items():
            (Path(temp) / name).write_bytes(blob)
        require(not target.exists(), "AUDIT_WRITE_RACE")
        try:
            os.rename(temp, target)
        except OSError as exc:
            raise DemoReviewError("AUDIT_WRITE_RACE") from exc
    return "SIMULATED_REVIEW_RECORDED"


def apply(book):
    report, sha = scoped_report(book)
    sandbox = bridge.safe_sandbox(book)
    input_file = sandbox / "decision-request.json"
    require(input_file.is_file() and not input_file.is_symlink(),
            "DECISION_REQUEST_MISSING")
    decision_request = json.loads(input_file.read_text(encoding="utf-8"))
    evaluated = evaluate(book, decision_request, report, sha)
    bridge.verify(book)  # fail closed if source has changed before audit publication
    status = persist_once(book, evaluated)
    return {
        "status": status, "book_id": book,
        "counts": evaluated["COUNTS"],
        "reviewer_identity_authenticated": False,
        "destination_write_allowed": False,
        "live_authorized": False,
    }


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("template", "apply"))
    parser.add_argument("--book", choices=sorted(bridge.BOOK_MAP), required=True)
    args = parser.parse_args()
    result = prepare(args.book) if args.command == "template" else apply(args.book)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(cli())
    except (DemoReviewError, review.CashFlowError, bridge.BridgeError,
            ValueError, KeyError, TypeError, OSError) as exc:
        msg = str(exc) if isinstance(
            exc, (DemoReviewError, review.CashFlowError, bridge.BridgeError)) \
            else "INVALID_DEMO_REVIEW"
        print(json.dumps({"status": "BLOCKED", "reason": msg,
                          "destination_write_allowed": False}, ensure_ascii=False))
        sys.exit(2)
