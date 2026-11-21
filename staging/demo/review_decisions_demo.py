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
                 "DESTINATION_WRITE_ALLOWED", "REVISION",
                 "PRIOR_DECISION_STATUS", "CHANGE_REASON"]


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
        "REVISION": 1,
        "PREVIOUS_AUDIT_SHA256": None,
        "CHANGE_REASON": None,
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
            require(source.get("BUSINESS_APPROVAL_ELIGIBLE") is True and
                    source.get("SOURCE_MEDIA_VERIFIED") is True and
                    source.get("PAYEE_VERIFIED") is True and
                    source.get("PAYMENT_REFERENCE_VERIFIED") is True,
                    "DOCUMENT_VERIFICATION_REQUIRED")
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


AUDIT_REVISION_SCHEMA = "DEMO-AUDIT-CHAIN-1"


def audit_bytes(entry):
    return json_bytes(entry)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def audit_csv_bytes(events):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=AUDIT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(events)
    return stream.getvalue().encode("utf-8-sig")


def read_history(target, book, report_sha):
    """Read every immutable revision, verify continuity and JSON/CSV consistency."""
    if not target.exists():
        return []
    require(target.is_dir() and not target.is_symlink(), "AUDIT_OUTPUT_CHANGED")
    names = {x.name for x in target.iterdir()}
    require(all(name.startswith("v") and name[1:].isdigit() for name in names),
            "AUDIT_HISTORY_STRUCTURE_CHANGED")
    names = sorted(names)
    require(names == [f"v{index:04d}" for index in range(1, len(names) + 1)],
            "AUDIT_HISTORY_GAP")
    history = []
    prev_hash = None
    prev_time = None
    for rev, name in enumerate(names, 1):
        folder = target / name
        require(folder.is_dir() and not folder.is_symlink() and
                {x.name for x in folder.iterdir()} ==
                {"review_audit_demo.json", "review_audit_demo.csv"},
                "AUDIT_HISTORY_STRUCTURE_CHANGED")
        json_path = folder / "review_audit_demo.json"
        csv_path = folder / "review_audit_demo.csv"
        require(not json_path.is_symlink() and not csv_path.is_symlink(),
                "AUDIT_OUTPUT_CHANGED")
        raw = json_path.read_bytes()
        entry = json.loads(raw.decode("utf-8"))
        require(raw == audit_bytes(entry), "AUDIT_HISTORY_JSON_MODIFIED")
        require(entry.get("AUDIT_SCHEMA_VERSION") == AUDIT_REVISION_SCHEMA and
                entry.get("BOOK_ID") == book and
                entry.get("REVIEW_REPORT_SHA256") == report_sha and
                entry.get("REVISION") == rev and
                entry.get("PREVIOUS_AUDIT_SHA256") == prev_hash and
                entry.get("REVIEWER_IDENTITY_AUTHENTICATED") is False and
                entry.get("DESTINATION_WRITE_ALLOWED") is False and
                entry.get("LIVE_AUTHORIZED") is False,
                "AUDIT_HISTORY_CHAIN_CHANGED")
        events = entry["EVENTS"]
        require(isinstance(events, list) and
                all(event.get("REVISION") == rev and
                    event.get("BOOK_ID") == book for event in events),
                "AUDIT_HISTORY_EVENTS_CHANGED")
        require(csv_path.read_bytes() == audit_csv_bytes(events),
                "AUDIT_HISTORY_CSV_MODIFIED")
        this_time = datetime.fromisoformat(entry["DECIDED_AT"])
        require(this_time.tzinfo is not None and this_time.utcoffset() is not None,
                "AUDIT_HISTORY_TIMESTAMP_CHANGED")
        if prev_time is not None:
            require(this_time > prev_time, "AUDIT_HISTORY_TIME_OUT_OF_ORDER")
            require(isinstance(entry.get("CHANGE_REASON"), str) and
                    8 <= len(entry["CHANGE_REASON"]) <= 500,
                    "AUDIT_HISTORY_CHANGE_REASON_MISSING")
        prev_time = this_time
        prev_hash = sha_bytes(raw)
        history.append({"entry": entry, "sha256": prev_hash})
    return history


def persist_once(book, decisions, request):
    """Append one JSON+CSV revision, never replace a previous decision."""
    sandbox = bridge.safe_sandbox(book)
    target = sandbox / "review-decisions"
    # A local process lock serializes simulated writers of the same book.
    # This is not an inter-machine or real Google Sheets lock.
    lock_path = sandbox / ".review-decisions-demo.lock"
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise DemoReviewError("AUDIT_BUSY") from exc
    try:
        os.close(lock_fd)
        bridge.verify(book)
        history = read_history(target, book, decisions["REVIEW_REPORT_SHA256"])
        raw_request = json_bytes(request)
        request_hash = sha_bytes(raw_request)
        prior = history[-1] if history else None
        if prior and prior["entry"]["DECISION_REQUEST_SHA256"] == request_hash:
            return "SIMULATED_REVIEW_ALREADY_RECORDED"
        revision = request.get("REVISION")
        require(type(revision) is int and revision == len(history) + 1,
                "AUDIT_REVISION_CONFLICT")
        require(request.get("PREVIOUS_AUDIT_SHA256") ==
                (prior["sha256"] if prior else None), "AUDIT_PREVIOUS_HASH_CONFLICT")
        reason = request.get("CHANGE_REASON")
        if prior is not None:
            require(isinstance(reason, str) and 8 <= len(reason) <= 500,
                    "AUDIT_CHANGE_REASON_REQUIRED")
            old = {e["TRANSACTION_ID"]: (e["ACTION"], e["NOTE"])
                   for e in prior["entry"]["EVENTS"]}
            new = {e["TRANSACTION_ID"]: (e["ACTION"], e["NOTE"])
                   for e in decisions["EVENTS"]}
            require(old != new, "AUDIT_NO_EFFECTIVE_CHANGE")
            require(datetime.fromisoformat(decisions["DECIDED_AT"]) >
                    datetime.fromisoformat(prior["entry"]["DECIDED_AT"]),
                    "AUDIT_DECISION_TIME_NOT_ADVANCING")
        else:
            require(reason is None, "AUDIT_FIRST_REVISION_REASON_FORBIDDEN")
        old_status = {e["TRANSACTION_ID"]: e["NEW_STATUS"]
                      for e in prior["entry"]["EVENTS"]} if prior else {}
        events = [{**e, "REVISION": revision,
                   "PRIOR_DECISION_STATUS": old_status.get(e["TRANSACTION_ID"], ""),
                   "CHANGE_REASON": reason or ""}
                  for e in decisions["EVENTS"]]
        entry = {**decisions, "EVENTS": events,
                 "AUDIT_SCHEMA_VERSION": AUDIT_REVISION_SCHEMA,
                 "REVISION": revision,
                 "PREVIOUS_AUDIT_SHA256": prior["sha256"] if prior else None,
                 "DECISION_REQUEST_SHA256": request_hash,
                 "CHANGE_REASON": reason,
                 "RECORDED_AT": datetime.now().astimezone().isoformat(timespec="microseconds")}
        if not target.exists():
            target.mkdir()
        dirname = f"v{revision:04d}"
        destination = target / dirname
        require(not destination.exists(), "AUDIT_REVISION_EXISTS")
        with tempfile.TemporaryDirectory(prefix=".pending-review-", dir=target) as tmp:
            (Path(tmp) / "review_audit_demo.json").write_bytes(audit_bytes(entry))
            (Path(tmp) / "review_audit_demo.csv").write_bytes(audit_csv_bytes(events))
            require(not destination.exists(), "AUDIT_WRITE_RACE")
            try:
                os.rename(tmp, destination)
            except OSError as exc:
                raise DemoReviewError("AUDIT_WRITE_RACE") from exc
        # Verify complete chain after publishing a new revision.
        require(len(read_history(target, book, decisions["REVIEW_REPORT_SHA256"])) ==
                revision, "AUDIT_POSTWRITE_VERIFY_FAILED")
        return ("SIMULATED_REVIEW_RECORDED" if revision == 1 else
                "SIMULATED_REVIEW_REVISION_RECORDED")
    finally:
        # The local lock has no authority outside this DEMO.
        lock_path.unlink(missing_ok=True)


def apply(book):
    report, sha = scoped_report(book)
    sandbox = bridge.safe_sandbox(book)
    input_file = sandbox / "decision-request.json"
    require(input_file.is_file() and not input_file.is_symlink(),
            "DECISION_REQUEST_MISSING")
    decision_request = json.loads(input_file.read_text(encoding="utf-8"))
    evaluated = evaluate(book, decision_request, report, sha)
    bridge.verify(book)  # fail closed if source has changed before audit publication
    status = persist_once(book, evaluated, decision_request)
    return {
        "status": status, "book_id": book,
        "audit_revision": decision_request["REVISION"],
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
