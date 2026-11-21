"""Windows/Linux tests for P1-sealed M3 -> raw-evidence review-only workflow.

Not a business acceptance test. No live books and no network.
"""
from __future__ import annotations
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

STAGE = Path(__file__).resolve().parent
sys.path.insert(0, str(STAGE))
import m3_p1_bridge as bridge
import cash_review_flow as review


class SealedCashFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=STAGE, prefix=".cash-flow-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.old_root = bridge.ROOT
        self.old_input = bridge.INPUT
        bridge.ROOT = Path(self.tmp.name) / "snapshots"
        bridge.INPUT = Path(self.tmp.name) / "source"
        shutil.copytree(STAGE / "input", bridge.INPUT)
        bridge.ROOT.mkdir()

    def tearDown(self):
        bridge.ROOT = self.old_root
        bridge.INPUT = self.old_input

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell runs in Windows")
    def test_full_flow_from_sealed_snapshot_without_scenario_labels(self):
        book = "DEMO-A-CASH-2026"
        bridge.prepare(book)
        report = review.propose(book)
        self.assertEqual(report["EVIDENCE_COUNT"], 6)
        self.assertEqual(report["TRANSACTION_COUNT"], 4)
        self.assertEqual(report["READY_FOR_OWNER_COUNT"], 2)
        self.assertEqual(report["NEEDS_REVIEW_COUNT"], 2)
        self.assertFalse(report["DESTINATION_WRITE_ALLOWED"])
        self.assertFalse(report["LIVE_AUTHORIZED"])
        self.assertFalse(report["SOURCE_MEDIA_VERIFIED"])
        self.assertEqual({tx["TRANSACTION_ID"] for tx in report["PROPOSALS"]},
                         {"DEMO-T-A1", "DEMO-T-A2", "DEMO-T-A3", "DEMO-T-A4"})
        for tx in report["PROPOSALS"]:
            self.assertEqual(tx["APPROVAL_STATUS"], "UNAPPROVED")
            self.assertFalse(tx["MEDIA_EVIDENCE_VERIFIED"])
            self.assertEqual(tx["BOOK_ID"], book)
            self.assertEqual(tx["PROJECT_ID"], "DEMO-PROJECT-A")
        by_id = {tx["TRANSACTION_ID"]: tx for tx in report["PROPOSALS"]}
        self.assertEqual(by_id["DEMO-T-A1"]["PROPOSED_CASH_OUT_DEMO"], "100.00")
        self.assertEqual(by_id["DEMO-T-A1"]["PROPOSED_SETTLED_COST_DEMO"], "100.00")
        self.assertEqual(by_id["DEMO-T-A1"]["RESUBMITTED_RECORD_IDS"], ["DEMO-R-A3"])
        self.assertEqual(by_id["DEMO-T-A3"]["PROPOSED_CASH_OUT_DEMO"], "500.00")
        self.assertEqual(by_id["DEMO-T-A3"]["PROPOSED_SETTLED_COST_DEMO"], "0.00")
        self.assertEqual(by_id["DEMO-T-A2"]["REASON"], "PAYMENT_MISSING_BILL")
        self.assertEqual(by_id["DEMO-T-A4"]["REASON"], "SETTLEMENT_NEEDS_ADVANCE_LINK")
        self.assertEqual(review.save_once(book, report), "PREPARED_FOR_REVIEW")
        self.assertEqual(review.save_once(book, report), "ALREADY_PREPARED")
        out = bridge.ROOT / book / review.REVIEW_DIR
        self.assertEqual({p.name for p in out.iterdir()},
                         {"review_proposals.json", "stagging_draft.csv", "doi_chieu_draft.csv"})
        with (out / "stagging_draft.csv").open(encoding="utf-8-sig", newline="") as f:
            staged = list(csv.DictReader(f))
        with (out / "doi_chieu_draft.csv").open(encoding="utf-8-sig", newline="") as f:
            recon = list(csv.DictReader(f))
        self.assertEqual(len(staged), 4)
        self.assertEqual(len(recon), 2)
        self.assertTrue(all("đã chuyển" not in row["Ngày đã chuyển"].lower()
                            for row in staged))
        self.assertFalse(any("Đã duyệt" in row["Trạng thái duyệt"] for row in staged))

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell runs in Windows")
    def test_two_independent_book_reviews(self):
        names = ("DEMO-A-CASH-2026", "DEMO-B-MISA-2026")
        for book in names:
            bridge.prepare(book)
        with ThreadPoolExecutor(max_workers=2) as ex:
            a, b = list(ex.map(review.propose, names))
        self.assertEqual((a["EVIDENCE_COUNT"], a["TRANSACTION_COUNT"]), (6, 4))
        self.assertEqual((b["EVIDENCE_COUNT"], b["TRANSACTION_COUNT"]), (1, 1))
        self.assertNotEqual(a["P1_MANIFEST_SHA256"], b["P1_MANIFEST_SHA256"])
        self.assertEqual(b["READY_FOR_OWNER_COUNT"], 0)
        self.assertEqual(b["NEEDS_REVIEW_COUNT"], 1)
        self.assertEqual(review.save_once(names[0], a), "PREPARED_FOR_REVIEW")
        self.assertEqual(review.save_once(names[1], b), "PREPARED_FOR_REVIEW")
        self.assertEqual(review.save_once(names[0], review.propose(names[0])),
                         "ALREADY_PREPARED")

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell runs in Windows")
    def test_source_tamper_in_b_does_not_stop_a(self):
        a, b = "DEMO-A-CASH-2026", "DEMO-B-MISA-2026"
        bridge.prepare(a)
        bridge.prepare(b)
        path = bridge.ROOT / b / "input/evidence.csv"
        path.write_text(path.read_text(encoding="utf-8") + "MODIFIED", encoding="utf-8")
        with self.assertRaisesRegex(bridge.BridgeError, "P1_BLOCKED"):
            review.propose(b)
        self.assertEqual(review.propose(a)["TRANSACTION_COUNT"], 4)
        self.assertFalse((bridge.ROOT / b / review.REVIEW_DIR).exists())

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell runs in Windows")
    def test_tampered_child_checkpoint_amount_blocked(self):
        book = "DEMO-A-CASH-2026"
        bridge.prepare(book)
        review.propose(book)
        path = bridge.ROOT / book / "checkpoints" / f"timeline-{book}.json"
        cp = json.loads(path.read_text(encoding="utf-8-sig"))
        cp["transactions"][0]["amount"] = 999999
        path.write_text(json.dumps(cp), encoding="utf-8")
        with self.assertRaisesRegex(review.CashFlowError, "M3_AMOUNT_MISMATCH"):
            review.propose(book)
        self.assertFalse((bridge.ROOT / book / review.REVIEW_DIR).exists())

    @unittest.skipUnless(os.name == "nt", "PowerShell CLI on Windows")
    def test_m3_direct_without_seal_is_blocked(self):
        book = "DEMO-A-CASH-2026"
        bridge.prepare(book)
        sandbox = bridge.ROOT / book
        (sandbox / "p1-manifest/source_manifest.json").unlink()
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
               "-File", str(STAGE / "workflow.ps1"),
               "-BookId", book, "-WorkflowRoot", str(sandbox)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("P1_SEALED_SNAPSHOT_REQUIRED", proc.stdout + proc.stderr)
        self.assertFalse((sandbox / "checkpoints" / f"timeline-{book}.json").exists())

    @unittest.skipUnless(os.name == "nt", "PowerShell CLI on Windows")
    def test_regression_switch_cannot_bypass_real_snapshot(self):
        book = "DEMO-A-CASH-2026"
        bridge.prepare(book)
        sandbox = bridge.ROOT / book
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
               "-File", str(STAGE / "workflow.ps1"), "-LegacyRegressionTest",
               "-BookId", book, "-WorkflowRoot", str(sandbox)]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("LEGACY_TEST_SCOPE_FORBIDDEN", proc.stdout + proc.stderr)

    @unittest.skipUnless(os.name == "nt", "M3 PowerShell runs in Windows")
    def test_output_mutation_is_blocked(self):
        book = "DEMO-A-CASH-2026"
        bridge.prepare(book)
        report = review.propose(book)
        review.save_once(book, report)
        f = bridge.ROOT / book / review.REVIEW_DIR / "review_proposals.json"
        original = f.read_bytes()
        f.write_bytes(original + b"\n")
        with self.assertRaisesRegex(review.CashFlowError, "REVIEW_OUTPUT_CHANGED"):
            review.save_once(book, report)
        self.assertEqual(f.read_bytes(), original + b"\n")

    def test_unknown_kind_not_silently_classified(self):
        self.assertRaisesRegex(review.CashFlowError, "INVALID_AMOUNT",
                               review.money, "not-money")
        with self.assertRaisesRegex(review.CashFlowError, "TRANSACTION_AMOUNT_CONFLICT"):
            review.classify_tx("TX",
                               [{"RECORD_ID":"A", "RAW_SHA256":"a"*64, "KIND":"PAYMENT",
                                 "EVIDENCE_REF":"E-1","AMOUNT":"100"},
                                {"RECORD_ID":"B", "RAW_SHA256":"b"*64, "KIND":"BILL",
                                 "EVIDENCE_REF":"E-1","AMOUNT":"200"}])
        proposal = review.classify_tx("TX",
                                     [{"RECORD_ID":"A", "RAW_SHA256":"a"*64, "KIND":"BILL",
                                       "EVIDENCE_REF":"E-1","AMOUNT":"100"}])
        self.assertEqual(proposal["REVIEW_STATE"], "NEEDS_REVIEW")
        self.assertEqual(proposal["PROPOSED_CASH_OUT_DEMO"], "0.00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
