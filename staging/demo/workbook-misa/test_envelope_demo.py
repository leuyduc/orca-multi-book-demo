"""Synthetic scope-envelope checks: explicitly NOT a MISA import/export schema."""
import copy
import json
import pathlib
import unittest

PATH = pathlib.Path(__file__).with_name("FIXTURE_KHONG_PHAI_MISA.json")
SCOPE = {"LEGAL_ENTITY_ID": "DEMO_B", "BOOK_ID": "DEMO-B-MISA-2026",
         "BRANCH_ID": "B_HN", "PERIOD": "2026-11", "SOURCE_SNAPSHOT_ID": "SYN_B_001"}


def validate_demo_envelope(document, scope):
    errors = []
    if document.get("FORMAT_LABEL") != "DEMO_ONLY_NOT_MISA_SCHEMA":
        errors.append("INVALID_DEMO_LABEL")
    for key, expected in scope.items():
        if not expected or document.get(key) != expected:
            errors.append("SCOPE_MISMATCH_" + key)
    rows = document.get("ROWS")
    if not isinstance(rows, list) or not rows:
        errors.append("MISSING_ROWS")
    elif any(not isinstance(row, dict) or not row.get("DEMO_ROW_ID") or
             isinstance(row.get("DEMO_AMOUNT"), bool) or
             not isinstance(row.get("DEMO_AMOUNT"), (int, float)) for row in rows):
        errors.append("INVALID_ROW")
    return {"status": "BLOCKED" if errors else "READY_FOR_DEMO_CHECK", "errors": errors,
            "accepted_rows": 0 if errors else len(rows)}


class DemoEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(PATH.read_text(encoding="utf-8"))

    def test_good_scope(self):
        result = validate_demo_envelope(self.doc, SCOPE)
        self.assertEqual((result["status"], result["accepted_rows"]), ("READY_FOR_DEMO_CHECK", 1))

    def test_each_wrong_scope_is_blocked_without_rows(self):
        for key in SCOPE:
            with self.subTest(key=key):
                bad = copy.deepcopy(self.doc)
                bad[key] = "DEMO_WRONG"
                result = validate_demo_envelope(bad, SCOPE)
                self.assertEqual((result["status"], result["accepted_rows"]), ("BLOCKED", 0))
                self.assertIn("SCOPE_MISMATCH_" + key, result["errors"])

    def test_absent_demo_label(self):
        self.doc.pop("FORMAT_LABEL")
        self.assertIn("INVALID_DEMO_LABEL", validate_demo_envelope(self.doc, SCOPE)["errors"])

    def test_missing_rows(self):
        self.doc["ROWS"] = []
        self.assertEqual(validate_demo_envelope(self.doc, SCOPE)["accepted_rows"], 0)

    def test_invalid_amount(self):
        self.doc["ROWS"][0]["DEMO_AMOUNT"] = "not-a-number"
        self.assertIn("INVALID_ROW", validate_demo_envelope(self.doc, SCOPE)["errors"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
