"""Offline integration tests: P1 SHA manifest -> unapproved cash proposals."""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
STAGE = HERE.parent
P1 = STAGE / "p1-manifest"
_SPEC = importlib.util.spec_from_file_location("synthetic_cash_pilot", HERE / "pilot_cash_demo.py")
cash = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cash)
manifest = cash.load_manifest_module()


class SyntheticCashPilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix=".pilot-cash-test-", dir=STAGE)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.setup_a = self.make_fixture("A")

    def make_fixture(self, label):
        part = self.root / label
        src = part / "input"
        shutil.copytree(P1 / "input-A", src)
        doc = json.loads((P1 / "fixture_manifest_A.json").read_text(encoding="utf-8"))
        if label == "B":
            for section in ("BOOK", "PROJECT", "JOB"):
                doc[section]["LEGAL_ENTITY_ID"] = "DEMO_B"
                doc[section]["BOOK_ID"] = "DEMO-B-CASH-2026"
            doc["PROJECT"]["PROJECT_ID"] = "DEMO-PROJECT-B"
            doc["BOOK"]["SOURCE_REF"].update(
                {"ID": "SYNREF:DEMO-B-CASH-1",
                 "LEGAL_ENTITY_ID": "DEMO_B", "BOOK_ID": "DEMO-B-CASH-2026",
                 "PROJECT_ID": "DEMO-PROJECT-B"})
            doc["BOOK"]["OWNER"]["ID"] = "DEMO-OWNER-B"
            doc["BOOK"]["FISCAL_YEAR"]["CONFIRMED_BY"] = "DEMO-OWNER-B"
            doc["JOB"]["PROJECT_ID"] = "DEMO-PROJECT-B"
            doc["JOB"]["SOURCE_SNAPSHOT_ID"] = "SYN_B_001"
            doc["DEMO_OWNER_DIRECTORY"] = ["DEMO-OWNER-B", "DEMO-REVIEWER-B"]
            cash_csv = src / "chung_tu.csv"
            cash_csv.write_text(cash_csv.read_text().replace("DEMO-PROJECT-A", "DEMO-PROJECT-B")
                                .replace("A-R", "B-R").replace("A-TX", "B-TX"), encoding="utf-8")
            rev = src / "doi_chieu.csv"
            rev.write_text(rev.read_text().replace("A-R", "B-R"), encoding="utf-8")
        doc_path = part / "book.json"
        doc_path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        return part, src, doc_path, doc

    def seal(self, fixture, suffix=None):
        part, src, path, doc = fixture
        owner = "DEMO-OWNER-A" if doc["BOOK"]["LEGAL_ENTITY_ID"] == "DEMO_A" else "DEMO-OWNER-B"
        reviewer = "DEMO-REVIEWER-A" if owner.endswith("A") else "DEMO-REVIEWER-B"
        mani = manifest.build_manifest(src, doc, doc["JOB"]["SOURCE_SNAPSHOT_ID"],
                                       "2026-11-21T02:00:00+07:00", owner, reviewer)
        out = part / ("seal" if suffix is None else suffix)
        out.mkdir(exist_ok=False)
        (out / "source_manifest.json").write_text(json.dumps(mani), encoding="utf-8")
        (out / "source_seal.json").write_text(json.dumps(manifest.make_seal(mani)), encoding="utf-8")
        (out / (manifest.ticket_id(doc) + ".json")).write_text(
            json.dumps(manifest.make_checkpoint(mani, doc)), encoding="utf-8")
        return out

    def test_bill_plus_transfer_one_transaction_never_auto_write(self):
        folder = self.seal(self.setup_a)
        report = cash.build_review_report(self.setup_a[2], self.setup_a[1], folder)
        self.assertEqual(report["SOURCE_FILE_COUNT"], 2)
        self.assertEqual(report["EVIDENCE_RECORD_COUNT"], 3)
        self.assertEqual(report["TRANSACTION_COUNT"], 2)
        self.assertEqual(report["READY_FOR_OWNER_COUNT"], 1)
        self.assertEqual(report["NEEDS_REVIEW_COUNT"], 1)
        self.assertFalse(report["DESTINATION_WRITE_ALLOWED"])
        self.assertEqual(report["PROPOSALS"][0]["PROPOSED_CASH_OUT"], "100.00")
        self.assertEqual(report["PROPOSALS"][0]["PROPOSED_COST"], "100.00")
        self.assertEqual(report["PROPOSALS"][0]["APPROVAL_STATUS"], "UNAPPROVED")
        self.assertEqual(len(report["PROPOSALS"][0]["RECORD_IDS"]), 2)
        self.assertEqual(report["PROPOSALS"][1]["PROPOSED_CASH_OUT"], "0.00")
        self.assertEqual(report["PROPOSALS"][1]["REVIEW_STATE"], "NEEDS_REVIEW")
        self.assertEqual(report["PROPOSALS"][1]["REASON"], "MISSING_TRANSFER")

    def test_idempotent_repeat_and_tamper_output_blocks(self):
        folder = self.seal(self.setup_a)
        report = cash.build_review_report(self.setup_a[2], self.setup_a[1], folder)
        out = self.root / "proposals"
        self.assertEqual(cash.save_once(report, out), "PREPARED_FOR_REVIEW")
        self.assertEqual(cash.save_once(report, out), "ALREADY_PREPARED")
        p = out / cash.RESULT_FILE
        data = p.read_bytes()
        p.write_bytes(data + b" ")
        with self.assertRaisesRegex(cash.PilotError, "OUTPUT_CHANGED"):
            cash.save_once(report, out)
        self.assertEqual(p.read_bytes(), data + b" ")

    def test_modified_source_blocks_even_when_original_manifest_exists(self):
        folder = self.seal(self.setup_a)
        src = self.setup_a[1] / "chung_tu.csv"
        src.write_text(src.read_text().replace("100", "200", 1), encoding="utf-8")
        with self.assertRaisesRegex(cash.PilotError, "P1_BLOCKED:"):
            cash.build_review_report(self.setup_a[2], self.setup_a[1], folder)

    def test_changed_document_or_scope_blocks(self):
        folder = self.seal(self.setup_a)
        path = self.setup_a[2]
        doc = json.loads(path.read_text())
        doc["JOB"]["SOURCE_SNAPSHOT_ID"] = "SYN_A_NEW"
        path.write_text(json.dumps(doc))
        with self.assertRaisesRegex(cash.PilotError, "P1_BLOCKED:"):
            cash.build_review_report(path, self.setup_a[1], folder)

    def test_missing_checkpoint_blocks(self):
        folder = self.seal(self.setup_a)
        (folder / "P1-MANIFEST-A-002.json").unlink()
        with self.assertRaises(FileNotFoundError):
            cash.build_review_report(self.setup_a[2], self.setup_a[1], folder)

    def test_two_transfers_do_not_multiply_cash(self):
        src = self.setup_a[1]
        cash_csv = src / "chung_tu.csv"
        cash_csv.write_text(cash_csv.read_text() +
                            "A-R004,A-TX01,TRANSFER,100,DEMO-PROJECT-A\n", encoding="utf-8")
        status = src / "doi_chieu.csv"
        status.write_text(status.read_text() + "A-R004,WAIT_REVIEW,DEMO\n", encoding="utf-8")
        folder = self.seal(self.setup_a)
        report = cash.build_review_report(self.setup_a[2], src, folder)
        x = report["PROPOSALS"][0]
        self.assertEqual(x["REVIEW_STATE"], "NEEDS_REVIEW")
        self.assertEqual(x["PROPOSED_CASH_OUT"], "0.00")
        self.assertEqual(x["REASON"], "AMBIGUOUS_OR_FLAGGED_EVIDENCE")

    def test_flagged_evidence_needs_review(self):
        f = self.setup_a[1] / "doi_chieu.csv"
        f.write_text(f.read_text().replace("A-R001,WAIT_REVIEW", "A-R001,FLAGGED"), encoding="utf-8")
        folder = self.seal(self.setup_a)
        report = cash.build_review_report(self.setup_a[2], self.setup_a[1], folder)
        self.assertEqual(report["READY_FOR_OWNER_COUNT"], 0)
        self.assertEqual(report["PROPOSALS"][0]["REVIEW_STATE"], "NEEDS_REVIEW")

    def test_missing_review_blocks(self):
        rev = self.setup_a[1] / "doi_chieu.csv"
        rev.write_text(rev.read_text().replace("A-R003,WAIT_REVIEW,DEMO\n", ""), encoding="utf-8")
        folder = self.seal(self.setup_a)
        with self.assertRaisesRegex(cash.PilotError, "CASH_REVIEW_SET_MISMATCH"):
            cash.build_review_report(self.setup_a[2], self.setup_a[1], folder)

    def test_wrong_project_is_blocked_at_manifest(self):
        csv_path = self.setup_a[1] / "chung_tu.csv"
        csv_path.write_text(csv_path.read_text().replace("DEMO-PROJECT-A", "DEMO-PROJECT-B"),
                            encoding="utf-8")
        with self.assertRaisesRegex(manifest.ManifestError, "SOURCE_ROW_SCOPE_MISMATCH"):
            self.seal(self.setup_a)

    def test_b_book_does_not_block_a(self):
        folder_a = self.seal(self.setup_a)
        setup_b = self.make_fixture("B")
        folder_b = self.seal(setup_b)
        def task(fixture, seal_dir):
            return cash.build_review_report(fixture[2], fixture[1], seal_dir)
        with ThreadPoolExecutor(max_workers=2) as ex:
            future_a = ex.submit(task, self.setup_a, folder_a)
            future_b = ex.submit(task, setup_b, folder_b)
            a, b = future_a.result(), future_b.result()
        self.assertNotEqual(a["LEGAL_ENTITY_ID"], b["LEGAL_ENTITY_ID"])
        self.assertNotEqual(a["BOOK_ID"], b["BOOK_ID"])
        self.assertNotEqual(a["P1_MANIFEST_SHA256"], b["P1_MANIFEST_SHA256"])
        self.assertEqual(a["READY_FOR_OWNER_COUNT"], 1)
        self.assertEqual(b["READY_FOR_OWNER_COUNT"], 1)
        (setup_b[1] / "chung_tu.csv").write_text("BROKEN", encoding="utf-8")
        with self.assertRaisesRegex(cash.PilotError, "P1_BLOCKED"):
            task(setup_b, folder_b)
        self.assertEqual(task(self.setup_a, folder_a)["READY_FOR_OWNER_COUNT"], 1)

    def test_paths_must_be_inside_staging(self):
        outside = STAGE.parent / "not-a-staging-source"
        with self.assertRaisesRegex(cash.PilotError, "PATH_OUTSIDE_DEMO"):
            cash.guard_path(outside, "SOURCE_ROOT", allow_absent=True)
        report = {"DEMO": True}
        with self.assertRaisesRegex(cash.PilotError, "PATH_OUTSIDE_DEMO"):
            cash.save_once(report, outside)

    def test_no_other_files_may_exist_in_output(self):
        self.seal(self.setup_a)
        output = self.root / "out"
        output.mkdir()
        (output / "legacy.txt").write_text("unexpected", encoding="utf-8")
        with self.assertRaisesRegex(cash.PilotError, "OUTPUT_CONTAINS_OTHER_FILES"):
            cash.save_once({"DEMO": True}, output)


    def test_modified_seal_is_blocked(self):
        folder = self.seal(self.setup_a)
        path = folder / "source_seal.json"
        seal = json.loads(path.read_text(encoding="utf-8"))
        seal["MANIFEST_SHA256"] = "0" * 64
        path.write_text(json.dumps(seal), encoding="utf-8")
        with self.assertRaisesRegex(cash.PilotError, "P1_BLOCKED:"):
            cash.build_review_report(self.setup_a[2], self.setup_a[1], folder)

    def test_duplicate_record_id_is_blocked(self):
        src = self.setup_a[1]
        cash_csv = src / "chung_tu.csv"
        cash_csv.write_text(cash_csv.read_text() +
                            "A-R001,A-TX99,BILL,90,DEMO-PROJECT-A\n", encoding="utf-8")
        folder = self.seal(self.setup_a)
        with self.assertRaisesRegex(cash.PilotError, "DUPLICATE_OR_INVALID_RECORD"):
            cash.build_review_report(self.setup_a[2], src, folder)

    def test_output_inside_source_is_blocked(self):
        folder = self.seal(self.setup_a)
        report = cash.build_review_report(self.setup_a[2], self.setup_a[1], folder)
        with self.assertRaisesRegex(cash.PilotError, "OUTPUT_INSIDE_SOURCE"):
            cash.save_once(report, self.setup_a[1] / "output",
                           source_root=self.setup_a[1])

    def test_excessive_amount_is_blocked(self):
        src = self.setup_a[1]
        cash_csv = src / "chung_tu.csv"
        cash_csv.write_text(cash_csv.read_text().replace(
            "A-R001,A-TX01,BILL,100", "A-R001,A-TX01,BILL,10000000000000"),
            encoding="utf-8")
        folder = self.seal(self.setup_a)
        with self.assertRaisesRegex(cash.PilotError, "INVALID_AMOUNT"):
            cash.build_review_report(self.setup_a[2], src, folder)


if __name__ == "__main__":
    unittest.main(verbosity=2)
