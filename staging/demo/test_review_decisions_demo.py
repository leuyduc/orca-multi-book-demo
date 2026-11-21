"""Synthetic demo review decisions; mock role labels, never actual approval."""
from __future__ import annotations

import json
import hashlib
from datetime import datetime, timedelta
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

STAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE))
import m3_p1_bridge as bridge
import review_decisions_demo as approval


class ReviewDecisionsDemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=STAGE, prefix=".review-gate-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.old_root, self.old_input = bridge.ROOT, bridge.INPUT
        bridge.ROOT = Path(self.tmp.name) / "snapshots"
        bridge.INPUT = Path(self.tmp.name) / "source"
        shutil.copytree(STAGE / "input", bridge.INPUT)
        bridge.ROOT.mkdir()

    def tearDown(self):
        bridge.ROOT, bridge.INPUT = self.old_root, self.old_input

    def stage_book(self, book="DEMO-A-CASH-2026"):
        bridge.prepare(book)
        response = approval.prepare(book)
        self.assertEqual(response["status"], "DECISION_TEMPLATE_READY")
        return bridge.ROOT / book

    def read_decisions(self, root):
        path = root / "decision-request.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def write_decisions(self, root, value):
        (root / "decision-request.json").write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_default_template_requests_more_no_automatic_approval(self):
        root = self.stage_book()
        request = self.read_decisions(root)
        self.assertEqual(len(request["DECISIONS"]), 4)
        self.assertTrue(all(x["ACTION"] == "DEMO_REQUEST_MORE" for x in request["DECISIONS"]))
        result = approval.apply("DEMO-A-CASH-2026")
        self.assertEqual(result["status"], "SIMULATED_REVIEW_RECORDED")
        self.assertEqual(result["counts"]["DEMO_APPROVED"], 0)
        self.assertEqual(result["counts"]["DEMO_REQUEST_MORE"], 4)
        self.assertFalse(result["reviewer_identity_authenticated"])
        self.assertFalse(result["destination_write_allowed"])
        self.assertEqual(approval.apply("DEMO-A-CASH-2026")["status"],
                         "SIMULATED_REVIEW_ALREADY_RECORDED")
        result_file = root / "review-decisions/v0001/review_audit_demo.json"
        audit = json.loads(result_file.read_text(encoding="utf-8"))
        self.assertFalse(audit["REVIEWER_IDENTITY_AUTHENTICATED"])
        self.assertFalse(audit["DESTINATION_WRITE_ALLOWED"])
        self.assertTrue(all(not e["LIVE_AUTHORIZED"] for e in audit["EVENTS"]))

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_explicit_demo_approval_only_of_ready_transaction(self):
        root = self.stage_book()
        request = self.read_decisions(root)
        item = next(x for x in request["DECISIONS"] if x["TRANSACTION_ID"] == "DEMO-T-A1")
        self.assertEqual(item["EXPECTED_REVIEW_STATE"], "READY_FOR_OWNER")
        item.update({"ACTION": "DEMO_APPROVE", "NOTE": "DEMO_ROLE_A_XAC_NHAN_KIEM_THU"})
        self.write_decisions(root, request)
        with self.assertRaisesRegex(approval.DemoReviewError, "DOCUMENT_VERIFICATION_REQUIRED"):
            approval.apply("DEMO-A-CASH-2026")
        self.assertFalse((root / "review-decisions").exists())

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_reject_unready_approval(self):
        root = self.stage_book()
        request = self.read_decisions(root)
        item = next(x for x in request["DECISIONS"] if x["TRANSACTION_ID"] == "DEMO-T-A2")
        self.assertEqual(item["EXPECTED_REVIEW_STATE"], "NEEDS_REVIEW")
        item.update({"ACTION": "DEMO_APPROVE", "NOTE": "THIS_SHOULD_NEVER_BE_APPROVED"})
        self.write_decisions(root, request)
        with self.assertRaisesRegex(approval.DemoReviewError, "CANNOT_APPROVE_UNREADY"):
            approval.apply("DEMO-A-CASH-2026")
        self.assertFalse((root / "review-decisions").exists())

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_wrong_reviewer_or_report_hash_blocked(self):
        root = self.stage_book()
        request = self.read_decisions(root)
        request["REVIEWER_ID"] = "DEMO-REVIEWER-B"
        self.write_decisions(root, request)
        with self.assertRaisesRegex(approval.DemoReviewError, "DEMO_REVIEWER_WRONG_SCOPE"):
            approval.apply("DEMO-A-CASH-2026")
        request["REVIEWER_ID"] = "DEMO-REVIEWER-A"
        request["REVIEW_REPORT_SHA256"] = "0" * 64
        self.write_decisions(root, request)
        with self.assertRaisesRegex(approval.DemoReviewError, "DECISION_SCOPE_OR_REPORT_CHANGED"):
            approval.apply("DEMO-A-CASH-2026")

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_duplicate_or_missing_decision_blocked(self):
        root = self.stage_book()
        request = self.read_decisions(root)
        request["DECISIONS"][1] = dict(request["DECISIONS"][0])
        self.write_decisions(root, request)
        with self.assertRaisesRegex(approval.DemoReviewError, "DUPLICATE_OR_UNKNOWN_TRANSACTION"):
            approval.apply("DEMO-A-CASH-2026")
        request["DECISIONS"].pop()
        self.write_decisions(root, request)
        with self.assertRaisesRegex(approval.DemoReviewError, "DECISION_SET_INCOMPLETE"):
            approval.apply("DEMO-A-CASH-2026")

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_changed_source_or_report_blocks_before_audit(self):
        root = self.stage_book()
        (root / "input/evidence.csv").write_text("CHANGED", encoding="utf-8")
        with self.assertRaisesRegex(bridge.BridgeError, "P1_BLOCKED"):
            approval.apply("DEMO-A-CASH-2026")
        self.assertFalse((root / "review-decisions").exists())

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_edit_template_is_not_overwritten(self):
        root = self.stage_book()
        request = self.read_decisions(root)
        request["DECISIONS"][0]["NOTE"] = "DEMO_CHU_QUAN_SUA"
        self.write_decisions(root, request)
        self.assertEqual(approval.prepare("DEMO-A-CASH-2026")["status"],
                         "DECISION_REQUEST_ALREADY_EXISTS")
        self.assertEqual(self.read_decisions(root)["DECISIONS"][0]["NOTE"],
                         "DEMO_CHU_QUAN_SUA")

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_audit_output_mutation_blocks_retry(self):
        root = self.stage_book()
        approval.apply("DEMO-A-CASH-2026")
        file = root / "review-decisions/v0001/review_audit_demo.json"
        file.write_bytes(file.read_bytes() + b" ")
        with self.assertRaisesRegex(approval.DemoReviewError, "AUDIT_HISTORY_JSON_MODIFIED"):
            approval.apply("DEMO-A-CASH-2026")

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_two_books_can_record_independent_mock_decisions(self):
        for book in ("DEMO-A-CASH-2026", "DEMO-B-MISA-2026"):
            self.stage_book(book)
        a = approval.apply("DEMO-A-CASH-2026")
        b = approval.apply("DEMO-B-MISA-2026")
        self.assertEqual(a["counts"]["DEMO_REQUEST_MORE"], 4)
        self.assertEqual(b["counts"]["DEMO_REQUEST_MORE"], 1)
        self.assertNotEqual(a["book_id"], b["book_id"])

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_append_only_two_versions_with_change_reason(self):
        root = self.stage_book()
        book = "DEMO-A-CASH-2026"
        one = approval.apply(book)
        self.assertEqual(one["status"], "SIMULATED_REVIEW_RECORDED")
        self.assertEqual(one["audit_revision"], 1)
        old_file = root / "review-decisions/v0001/review_audit_demo.json"
        old_bytes = old_file.read_bytes()
        request = self.read_decisions(root)
        request["REVISION"] = 2
        request["PREVIOUS_AUDIT_SHA256"] = hashlib.sha256(old_bytes).hexdigest()
        request["CHANGE_REASON"] = "Demo adjustment after reviewing an additional source"
        request["DECIDED_AT"] = (datetime.fromisoformat(request["DECIDED_AT"]) +
                                 timedelta(minutes=1)).isoformat()
        request["DECISIONS"][0]["ACTION"] = "DEMO_REJECT"
        request["DECISIONS"][0]["NOTE"] = "DEMO_REJECT_AFTER_CHECK"
        self.write_decisions(root, request)
        two = approval.apply(book)
        self.assertEqual(two["status"], "SIMULATED_REVIEW_REVISION_RECORDED")
        self.assertEqual(two["audit_revision"], 2)
        self.assertEqual(old_file.read_bytes(), old_bytes)
        newer = json.loads((root / "review-decisions/v0002/review_audit_demo.json")
                           .read_text(encoding="utf-8"))
        self.assertEqual(newer["PREVIOUS_AUDIT_SHA256"],
                         hashlib.sha256(old_bytes).hexdigest())
        self.assertEqual(newer["CHANGE_REASON"], request["CHANGE_REASON"])
        first_changed = next(e for e in newer["EVENTS"]
                             if e["TRANSACTION_ID"] == request["DECISIONS"][0]["TRANSACTION_ID"])
        self.assertEqual(first_changed["PRIOR_DECISION_STATUS"], "DEMO_NEEDS_MORE_ONLY")
        self.assertEqual(first_changed["NEW_STATUS"], "DEMO_REJECTED_ONLY")
        self.assertEqual(approval.apply(book)["status"],
                         "SIMULATED_REVIEW_ALREADY_RECORDED")

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_revision_conflict_and_missing_reason_block(self):
        root = self.stage_book()
        book = "DEMO-A-CASH-2026"
        approval.apply(book)
        request = self.read_decisions(root)
        request["DECISIONS"][0]["ACTION"] = "DEMO_REJECT"
        request["DECISIONS"][0]["NOTE"] = "CHANGED_MOCK_DECISION"
        self.write_decisions(root, request)
        with self.assertRaisesRegex(approval.DemoReviewError, "AUDIT_REVISION_CONFLICT"):
            approval.apply(book)
        request["REVISION"] = 2
        request["PREVIOUS_AUDIT_SHA256"] = hashlib.sha256(
            (root / "review-decisions/v0001/review_audit_demo.json").read_bytes()).hexdigest()
        request["DECIDED_AT"] = (datetime.fromisoformat(request["DECIDED_AT"]) +
                                 timedelta(minutes=1)).isoformat()
        self.write_decisions(root, request)
        with self.assertRaisesRegex(approval.DemoReviewError, "AUDIT_CHANGE_REASON_REQUIRED"):
            approval.apply(book)
        request["CHANGE_REASON"] = "Reason now present but wrong prior version"
        request["PREVIOUS_AUDIT_SHA256"] = "f" * 64
        self.write_decisions(root, request)
        with self.assertRaisesRegex(approval.DemoReviewError, "AUDIT_PREVIOUS_HASH_CONFLICT"):
            approval.apply(book)
        self.assertFalse((root / "review-decisions/v0002").exists())

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell requires Windows")
    def test_tampered_historical_event_blocks_future_version(self):
        root = self.stage_book()
        book = "DEMO-A-CASH-2026"
        approval.apply(book)
        old = root / "review-decisions/v0001/review_audit_demo.json"
        old.write_bytes(old.read_bytes() + b" ")
        with self.assertRaisesRegex(approval.DemoReviewError, "AUDIT_HISTORY_JSON_MODIFIED"):
            approval.apply(book)
        self.assertFalse((root / "review-decisions/v0002").exists())

    def test_verified_flag_alone_does_not_authorize_live_posting(self):
        # Pure fake unit input, unrelated to real documents or permissions.
        report = {
            "LEGAL_ENTITY_ID": "DEMO_A", "PERIOD": "2026-11",
            "P1_MANIFEST_SHA256": "a" * 64,
            "TRANSACTION_COUNT": 1,
            "PROPOSALS": [{
                "TRANSACTION_ID": "DEMO-T-1", "REVIEW_STATE": "READY_FOR_OWNER",
                "BUSINESS_APPROVAL_ELIGIBLE": True,
                "SOURCE_MEDIA_VERIFIED": True, "PAYEE_VERIFIED": True,
                "PAYMENT_REFERENCE_VERIFIED": True,
            }]
        }
        request = {
            "VERSION": approval.VERSION, "DATA_CLASS": "SYNTHETIC_ONLY",
            "BOOK_ID": "DEMO-A-CASH-2026", "LEGAL_ENTITY_ID": "DEMO_A",
            "PERIOD": "2026-11", "P1_MANIFEST_SHA256": "a" * 64,
            "REVIEW_REPORT_SHA256": "b" * 64, "REVIEWER_ID": "DEMO-REVIEWER-A",
            "DECIDED_AT": "2026-11-21T12:00:00+07:00",
            "LIVE_AUTHORIZED": False, "DESTINATION_WRITE_ALLOWED": False,
            "DECISIONS": [{"TRANSACTION_ID": "DEMO-T-1",
                           "EXPECTED_REVIEW_STATE": "READY_FOR_OWNER",
                           "ACTION": "DEMO_APPROVE", "NOTE": "PURE_FAKE_UNIT_TEST"}]
        }
        result = approval.evaluate("DEMO-A-CASH-2026", request, report, "b" * 64)
        self.assertEqual(result["COUNTS"]["DEMO_APPROVED"], 1)
        self.assertFalse(result["REVIEWER_IDENTITY_AUTHENTICATED"])
        self.assertFalse(result["DESTINATION_WRITE_ALLOWED"])

    def test_plain_scope_validation_and_time_zone(self):
        source_report = {
            "LEGAL_ENTITY_ID": "DEMO_A", "PERIOD": "2026-11",
            "P1_MANIFEST_SHA256": "a" * 64,
            "TRANSACTION_COUNT": 1,
            "PROPOSALS": [{"TRANSACTION_ID":"DEMO-T-1","REVIEW_STATE":"READY_FOR_OWNER"}],
        }
        req = {
            "VERSION":approval.VERSION,"DATA_CLASS":"SYNTHETIC_ONLY",
            "BOOK_ID":"DEMO-A-CASH-2026",
            "LEGAL_ENTITY_ID":"DEMO_A","PERIOD":"2026-11",
            "P1_MANIFEST_SHA256":"a"*64,"REVIEW_REPORT_SHA256":"b"*64,
            "REVIEWER_ID":"DEMO-REVIEWER-A","DECIDED_AT":"2026-11-21T10:00:00",
            "LIVE_AUTHORIZED":False,"DESTINATION_WRITE_ALLOWED":False,
            "DECISIONS":[{"TRANSACTION_ID":"DEMO-T-1",
                          "EXPECTED_REVIEW_STATE":"READY_FOR_OWNER",
                          "ACTION":"DEMO_APPROVE","NOTE":"ONLY_DEMO_NOT_REAL"}],
        }
        with self.assertRaisesRegex(approval.DemoReviewError, "INVALID_DECISION_TIMESTAMP"):
            approval.evaluate("DEMO-A-CASH-2026",req,source_report,"b"*64)
        req["DECIDED_AT"]="2026-11-21T10:00:00+07:00"
        req["LIVE_AUTHORIZED"]=True
        with self.assertRaisesRegex(approval.DemoReviewError, "DECISION_SCOPE_OR_REPORT_CHANGED"):
            approval.evaluate("DEMO-A-CASH-2026",req,source_report,"b"*64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
