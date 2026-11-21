"""D3 synthetic cash workflow: exact P1-sealed M3 evidence -> review-only outputs.

Input rows are structured synthetic CSV, not OCR; no AI inference. This module
never approves, posts to a ledger, contacts an external system, or uses an API.
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
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

import m3_p1_bridge as bridge

VERSION = "CASH_FLOW_DEMO_V1"
STAGE = Path(__file__).resolve().parent
REVIEW_DIR = "cash-review"
STAGING_COLUMNS = [
    "Trạng thái duyệt", "Ngày", "Số chứng từ", "Nội dung thu/chi",
    "Tên công trình", "Người chi", "Người nhận", "Hình thức",
    "Thu (VND)", "Chi (VND)", "Ghi chú từ Zalo / lưu ý kế toán",
    "Nguồn / nhóm Zalo", "Bill / chứng từ", "Kiểm tra tự động",
    "Phản hồi người phụ trách", "Ngày đã chuyển",
]
RECON_COLUMNS = [
    "Ngày", "Mã chứng từ", "Biến động", "Số tiền (VND)",
    "Tài khoản / người nhận", "Trạng thái", "Nội dung cần đối chiếu",
    "Ảnh chứng từ",
]


class CashFlowError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise CashFlowError(reason)


def money(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CashFlowError("INVALID_AMOUNT") from exc
    require(result > 0 and result <= Decimal("1000000000000") and result.is_finite(),
            "INVALID_AMOUNT")
    require(result.as_tuple().exponent >= -2, "INVALID_AMOUNT_PRECISION")
    return result


def number(value):
    return str(value.quantize(Decimal("0.01")))


def read_evidence(book, root):
    doc = json.loads((root / "p1_document.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "p1-manifest/source_manifest.json").read_text(encoding="utf-8"))
    require(doc.get("DATA_CLASS") == "SYNTHETIC_ONLY" and
            doc.get("DESTINATION_WRITE") is False, "NON_SYNTHETIC_DOCUMENT")
    require(doc["BOOK"]["BOOK_ID"] == book and
            doc["JOB"]["BOOK_ID"] == book, "SOURCE_BOOK_MISMATCH")
    path = root / "input/evidence.csv"
    require(path.is_file() and not path.is_symlink(), "EVIDENCE_FILE_MISSING")
    raw = path.read_bytes()
    matches = [row for row in manifest["FILES"] if row["REL_PATH"] == "evidence.csv"]
    require(len(matches) == 1 and
            hashlib.sha256(raw).hexdigest() == matches[0]["SHA256"],
            "SOURCE_HASH_MISMATCH")
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    columns = reader.fieldnames
    fields = {"RECORD_ID", "TRANSACTION_ID", "RAW_SHA256", "EVIDENCE_REF", "KIND",
              "AMOUNT", "SOURCE_DATE", "TRANSACTION_DATE", "BOOK_ID", "LEGAL_ENTITY_ID",
              "BRANCH_ID", "PROJECT_ID", "PERIOD"}
    require(columns is not None and fields.issubset(columns) and
            len(columns) == len(set(columns)), "INVALID_EVIDENCE_SCHEMA")
    rows = list(reader)
    require(rows and all(None not in r for r in rows) and
            len(rows) == matches[0]["ROW_COUNT"], "INVALID_EVIDENCE_ROWS")
    book_info = doc["BOOK"]
    project = doc["PROJECT"]
    seen = set()
    for row in rows:
        rid = row["RECORD_ID"]
        require(rid and rid not in seen, "DUPLICATE_RECORD_ID")
        seen.add(rid)
        require(row["BOOK_ID"] == book and
                row["LEGAL_ENTITY_ID"] == book_info["LEGAL_ENTITY_ID"] and
                row["BRANCH_ID"] == (book_info["BRANCH_ID"] or "NA") and
                row["PERIOD"] == book_info["PERIOD"] and
                row["PROJECT_ID"] == project["PROJECT_ID"], "EVIDENCE_SCOPE_MISMATCH")
        require(row["KIND"] in {"PAYMENT", "BILL", "ADVANCE", "SETTLEMENT"},
                "UNKNOWN_EVIDENCE_KIND")
        require(row["TRANSACTION_ID"] and row["EVIDENCE_REF"] and
                len(row["RAW_SHA256"]) == 64, "EVIDENCE_ID_MISSING")
        money(row["AMOUNT"])
    return doc, rows, matches[0]["SHA256"]


def checkpoint_money(value):
    """A checkpoint amount must be a finite, nonnegative exact 2dp decimal."""
    if isinstance(value, bool) or value is None:
        raise CashFlowError("INVALID_M3_CHECKPOINT_MONEY")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise CashFlowError("INVALID_M3_CHECKPOINT_MONEY") from exc
    require(amount.is_finite() and Decimal(0) <= amount <= Decimal("1000000000000")
            and amount.as_tuple().exponent >= -2, "INVALID_M3_CHECKPOINT_MONEY")
    return amount


def check_m3_output(book, root, rows, result):
    """Recompute source cash movement AND settled cost independently of M3.

    A bill matching a transfer may be a cost *candidate* in the review output.
    It is NOT an M3 settled-cost event; only SETTLEMENT counts for that field.
    Repeated evidence bytes keep their own RECORD_ID but do not add cash.
    """
    checkpoint = json.loads((root / "checkpoints" / f"timeline-{book}.json")
                            .read_text(encoding="utf-8-sig"))
    require(checkpoint.get("book_id") == book and
            checkpoint.get("period") == rows[0]["PERIOD"], "M3_CHECKPOINT_SCOPE")
    source_ids = {r["RECORD_ID"] for r in rows}
    checkpoint_records = checkpoint["records"]
    require(len(checkpoint_records) == len(rows) == result["record_count"] and
            len({r["record_id"] for r in checkpoint_records}) == len(rows) and
            {r["record_id"] for r in checkpoint_records} == source_ids,
            "M3_RECORD_SET_MISMATCH")
    cp_by_record = {r["record_id"]: r for r in checkpoint_records}
    for row in rows:
        cp = cp_by_record[row["RECORD_ID"]]
        require(cp["transaction_id"] == row["TRANSACTION_ID"] and
                cp["raw_sha256"] == row["RAW_SHA256"] and
                cp["kind"] == row["KIND"] and
                cp["evidence_ref"] == row["EVIDENCE_REF"] and
                checkpoint_money(cp["amount"]) == money(row["AMOUNT"]),
                "M3_RECORD_SOURCE_MISMATCH")

    tx_groups = defaultdict(list)
    for row in rows:
        tx_groups[row["TRANSACTION_ID"]].append(row)
    cp_list = checkpoint["transactions"]
    cp_transactions = {tx["transaction_id"]: tx for tx in cp_list}
    require(len(cp_list) == len(cp_transactions) == len(tx_groups) ==
            result["transaction_count"] and set(cp_transactions) == set(tx_groups),
            "M3_TRANSACTION_SET_MISMATCH")
    for txid, group in tx_groups.items():
        snapshot = cp_transactions[txid]
        require(len(snapshot["record_ids"]) == len(group) and
                len(set(snapshot["record_ids"])) == len(group) and
                set(snapshot["record_ids"]) == {r["RECORD_ID"] for r in group},
                "M3_TRANSACTION_RECORD_MISMATCH")
        amounts = {money(r["AMOUNT"]) for r in group}
        require(len(amounts) == 1 and
                checkpoint_money(snapshot["amount"]) == next(iter(amounts)),
                "M3_AMOUNT_MISMATCH")
        unique = {}
        for row in group:
            evidence_hash = row["RAW_SHA256"]
            if evidence_hash in unique:
                prior = unique[evidence_hash]
                require(all(prior[f] == row[f] for f in
                            ("TRANSACTION_ID", "EVIDENCE_REF", "KIND", "AMOUNT")),
                        "M3_CONFLICTING_DUPLICATE")
            else:
                unique[evidence_hash] = row
        kinds = [row["KIND"] for row in unique.values()]
        require(snapshot["kinds"] == kinds, "M3_KINDS_MISMATCH")
        pay_kinds = [kind for kind in kinds if kind in ("PAYMENT", "ADVANCE")]
        settled_kinds = [kind for kind in kinds if kind == "SETTLEMENT"]
        require(len(pay_kinds) <= 1 and len(settled_kinds) <= 1,
                "M3_MULTIPLE_CASH_MOVEMENTS")
        expected_out = next(iter(amounts)) if pay_kinds else Decimal(0)
        expected_settled = next(iter(amounts)) if settled_kinds else Decimal(0)
        require(checkpoint_money(snapshot["amount_out"]) == expected_out,
                "M3_AMOUNT_OUT_MISMATCH")
        require(checkpoint_money(snapshot["settled_cost"]) == expected_settled,
                "M3_SETTLED_COST_MISMATCH")
        # Advance link cannot be invented in a persisted checkpoint.
        related = {row.get("RELATED_ADVANCE_ID", "") for row in unique.values()
                   if row["KIND"] == "SETTLEMENT"}
        require(len(related) <= 1 and snapshot["related_advance_id"] ==
                (next(iter(related)) if related else ""),
                "M3_ADVANCE_LINK_MISMATCH")
    return tx_groups


def classify_tx(txid, events):
    by_unique = {}
    resubmitted = []
    for row in events:
        key = (row["RAW_SHA256"], row["KIND"], row["EVIDENCE_REF"], row["AMOUNT"])
        if key in by_unique:
            resubmitted.append(row["RECORD_ID"])
        else:
            by_unique[key] = row
    unique = list(by_unique.values())
    payments = [r for r in unique if r["KIND"] == "PAYMENT"]
    bills = [r for r in unique if r["KIND"] == "BILL"]
    advances = [r for r in unique if r["KIND"] == "ADVANCE"]
    settlements = [r for r in unique if r["KIND"] == "SETTLEMENT"]
    amounts = {money(r["AMOUNT"]) for r in unique}
    require(len(amounts) == 1, "TRANSACTION_AMOUNT_CONFLICT")
    amt = next(iter(amounts))
    status = "NEEDS_REVIEW"
    reason = "AMBIGUOUS_EVIDENCE"
    out = Decimal(0)
    cost = Decimal(0)
    if len(payments) == 1 and len(bills) == 1 and len(unique) == 2:
        status, reason, out, cost = "READY_FOR_OWNER", "MATCHED_BILL_AND_PAYMENT", amt, amt
    elif len(advances) == 1 and len(unique) == 1:
        status, reason, out = "READY_FOR_OWNER", "ADVANCE_NOT_SETTLED_COST", amt
    elif len(settlements) == 1 and len(unique) == 1:
        reason = "SETTLEMENT_NEEDS_ADVANCE_LINK"
    elif len(payments) == 1 and len(unique) == 1:
        reason = "PAYMENT_MISSING_BILL"
    elif len(bills) == 1 and len(unique) == 1:
        reason = "BILL_MISSING_PAYMENT"
    # csv KIND and matching amounts are only a *structured precheck*.
    # There is no original image, payee, bank reference, or payment context
    # in this fixture, so BUSINESS APPROVAL can NEVER follow automatically.
    required_checks = ["ORIGINAL_RECEIPT_IMAGE", "PAYEE_IDENTITY",
                       "PAYMENT_REFERENCE", "TRANSACTION_CONTEXT"]
    if advances:
        required_checks.append("ADVANCE_AUTHORIZATION")
    if settlements:
        required_checks.append("LINKED_ADVANCE_AND_SETTLEMENT")
    return {
        "EVIDENCE_CHECKS_REQUIRED": required_checks,
        "SOURCE_MEDIA_VERIFIED": False,
        "PAYEE_VERIFIED": False,
        "PAYMENT_REFERENCE_VERIFIED": False,
        "BUSINESS_APPROVAL_ELIGIBLE": False,
        "STRUCTURED_MATCH_CANDIDATE": reason == "MATCHED_BILL_AND_PAYMENT",
        "TRANSACTION_ID": txid,
        "RECORD_IDS": sorted(r["RECORD_ID"] for r in events),
        "RESUBMITTED_RECORD_IDS": sorted(resubmitted),
        "SOURCE_AMOUNT_DEMO": number(amt),
        "PROPOSED_CASH_OUT_DEMO": number(out),
        "PROPOSED_SETTLED_COST_DEMO": number(cost),
        "REVIEW_STATE": status,
        "REASON": reason,
        "WARNINGS": ["DUPLICATE_SOURCE_RESUBMISSION"] if resubmitted else [],
        "APPROVAL_STATUS": "UNAPPROVED",
        "DESTINATION_WRITE_ALLOWED": False,
        "MEDIA_EVIDENCE_VERIFIED": False,
    }


def propose(book):
    """Produce review-only output from the SAME sealed bytes that M3 processed."""
    before = bridge.verify(book)
    result = bridge.run_workflow(book)
    after = bridge.verify(book)
    require(before["manifest_sha256"] == after["manifest_sha256"] ==
            result["p1_manifest_sha256"], "P1_SEAL_CHANGED")
    root = bridge.safe_sandbox(book)
    doc, rows, source_sha = read_evidence(book, root)
    groups = check_m3_output(book, root, rows, result)
    report_rows = []
    for txid, events in sorted(groups.items()):
        proposal = classify_tx(txid, events)
        proposal.update({
            "LEGAL_ENTITY_ID": doc["BOOK"]["LEGAL_ENTITY_ID"],
            "BOOK_ID": book,
            "BRANCH_ID": doc["BOOK"]["BRANCH_ID"] or "NA",
            "PROJECT_ID": doc["PROJECT"]["PROJECT_ID"],
            "PERIOD": doc["BOOK"]["PERIOD"],
            "TRANSACTION_DATE": min(e["TRANSACTION_DATE"] for e in events),
        })
        report_rows.append(proposal)
    # Verify source a final time; a changed CSV cannot generate output.
    bridge.verify(book)
    report = {
        "VERSION": VERSION,
        "DATA_CLASS": "SYNTHETIC_ONLY",
        "BOOK_ID": book,
        "LEGAL_ENTITY_ID": doc["BOOK"]["LEGAL_ENTITY_ID"],
        "PERIOD": doc["BOOK"]["PERIOD"],
        "PROJECT_ID": doc["PROJECT"]["PROJECT_ID"],
        "P1_MANIFEST_SHA256": result["p1_manifest_sha256"],
        "SOURCE_EVIDENCE_SHA256": source_sha,
        "EVIDENCE_COUNT": len(rows),
        "TRANSACTION_COUNT": len(report_rows),
        "READY_FOR_OWNER_COUNT": sum(p["REVIEW_STATE"] == "READY_FOR_OWNER" for p in report_rows),
        "NEEDS_REVIEW_COUNT": sum(p["REVIEW_STATE"] == "NEEDS_REVIEW" for p in report_rows),
        "APPROVAL_STATUS": "UNAPPROVED",
        "LIVE_AUTHORIZED": False,
        "DESTINATION_WRITE_ALLOWED": False,
        "SOURCE_MEDIA_VERIFIED": False,
        "PROPOSALS": report_rows,
    }
    return report


def csv_bytes(columns, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def bytes_for_report(report):
    stage_rows = []
    recon_rows = []
    for item in report["PROPOSALS"]:
        ready = item["REVIEW_STATE"] == "READY_FOR_OWNER"
        ids = "|".join(item["RECORD_IDS"])
        stage_rows.append(dict(zip(STAGING_COLUMNS, [
            "Chờ kiểm tra" if ready else "Cần bổ sung",
            item["TRANSACTION_DATE"], item["TRANSACTION_ID"],
            "DEMO: " + item["REASON"], item["PROJECT_ID"], "", "", "",
            "", item["PROPOSED_CASH_OUT_DEMO"] if ready and
                Decimal(item["PROPOSED_CASH_OUT_DEMO"]) > 0 else "",
            "DEMO STRUCTURED CSV — chưa xác nhận bill/ảnh gốc",
            "staging/demo/_p1_m3/.../input/evidence.csv",
            ids, item["REVIEW_STATE"] + "/" + item["REASON"], "", "",
        ])))
        if not ready:
            recon_rows.append(dict(zip(RECON_COLUMNS, [
                item["TRANSACTION_DATE"], item["TRANSACTION_ID"],
                "Đối chiếu bằng chứng", item["SOURCE_AMOUNT_DEMO"], "",
                item["REVIEW_STATE"], item["REASON"], ids,
            ])))
    output = {
        "review_proposals.json": (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
                                  + "\n").encode("utf-8"),
        "stagging_draft.csv": csv_bytes(STAGING_COLUMNS, stage_rows),
        "doi_chieu_draft.csv": csv_bytes(RECON_COLUMNS, recon_rows),
    }
    return output


def save_once(book, report):
    sandbox = bridge.safe_sandbox(book)
    path = sandbox / REVIEW_DIR
    output = bytes_for_report(report)
    if path.exists():
        require(path.is_dir() and not path.is_symlink(), "REVIEW_OUTPUT_CHANGED")
        require({p.name for p in path.iterdir()} == set(output), "REVIEW_OUTPUT_CHANGED")
        for name, blob in output.items():
            f = path / name
            require(f.is_file() and not f.is_symlink() and f.read_bytes() == blob,
                    "REVIEW_OUTPUT_CHANGED")
        return "ALREADY_PREPARED"
    with tempfile.TemporaryDirectory(dir=sandbox, prefix=".review-pending-") as temp:
        for name, blob in output.items():
            (Path(temp) / name).write_bytes(blob)
        require(not path.exists(), "REVIEW_OUTPUT_RACE")
        try:
            os.rename(temp, path)
        except OSError as exc:
            raise CashFlowError("REVIEW_OUTPUT_RACE") from exc
    return "PREPARED_FOR_REVIEW"


def main():
    parser = argparse.ArgumentParser(description="P1 -> M3 -> review only; synthetic.")
    parser.add_argument("--book", choices=sorted(bridge.BOOK_MAP), required=True)
    args = parser.parse_args()
    if not bridge.safe_sandbox(args.book).exists():
        bridge.prepare(args.book)
    report = propose(args.book)
    status = save_once(args.book, report)
    print(json.dumps({
        "status": status, "book_id": args.book,
        "evidence": report["EVIDENCE_COUNT"],
        "transactions": report["TRANSACTION_COUNT"],
        "ready_for_owner": report["READY_FOR_OWNER_COUNT"],
        "needs_review": report["NEEDS_REVIEW_COUNT"],
        "destination_write_allowed": False,
        "live_authorized": False,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (CashFlowError, bridge.BridgeError, ValueError, OSError, KeyError,
            TypeError, csv.Error) as exc:
        reason = str(exc) if isinstance(exc, (CashFlowError, bridge.BridgeError)) \
                 else "INVALID_DEMO_SOURCE"
        print(json.dumps({"status": "BLOCKED", "reason": reason,
                          "destination_write_allowed": False}, ensure_ascii=False))
        sys.exit(2)
