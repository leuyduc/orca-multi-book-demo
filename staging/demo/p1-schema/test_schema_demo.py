import copy
import json
import pathlib
import unittest

from schema_demo import VERSION, checkpoint, resume, validate

FIXTURE = pathlib.Path(__file__).with_name("fixture_demo_a.json")


def scoped(doc):
    book = doc["BOOK"]
    return {**{key: book[key] for key in ("LEGAL_ENTITY_ID", "BRANCH_ID", "BOOK_ID", "PERIOD")},
            "PROJECT_ID": doc["PROJECT"]["PROJECT_ID"]}


def complete_readonly(doc):
    book = doc["BOOK"]
    doc["SOURCE_PRESENT"] = True
    book["SOURCE_REF"] = {"ID": "SYNREF:DEMO-A-1", **scoped(doc)}
    book["OWNER"] = {"ID": "DEMO-OWNER-A", "KIND": "DEMO_ROLE"}
    book["FISCAL_YEAR"] = {"ID": "DEMO-FY-2027", "START": "2026-07-01", "END": "2027-06-30", "CONFIRMED_BY": "DEMO-OWNER-A"}
    return doc


def backup(doc):
    doc["DESTINATION_WRITE"] = True
    doc["BOOK"]["LAST_SNAPSHOT"] = {"ID": "DEMO-BACKUP-A", "KIND": "DEMO_DESTINATION_BACKUP",
                                      "SHA256": "a" * 64, "RESTORE_TEST": "SIMULATED_PASS", "RESTORE_TEST_ID": "DEMO-RESTORE-1",
                                      "DESTINATION_VERSION": "DEMO-V-1", "PROTECTED_LOCATION_ID": "DEMO-LOCATION-1",
                                      "RESPONSIBLE_OWNER": "DEMO-OWNER-A", "CAPTURED_AT": "2026-11-01T00:00:00+07:00", **scoped(doc)}
    return doc


class SchemaTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def blocked(self, doc, stage, expected):
        result = validate(doc, stage)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn(expected, result["errors"])
        self.assertFalse(result["live_authorized"])

    def test_demo_nulls_are_explicit_unknown(self):
        self.assertEqual(validate(self.doc, "DEMO")["status"], "READY_FOR_DEMO_SIMULATION")
        self.assertIsNone(self.doc["BOOK"]["LAST_SNAPSHOT"])

    def test_missing_columns_are_not_explicit_null(self):
        for name in ("FISCAL_YEAR", "SOURCE_REF", "OWNER", "LAST_SNAPSHOT"):
            with self.subTest(field=name):
                bad = copy.deepcopy(self.doc); del bad["BOOK"][name]
                self.blocked(bad, "DEMO", "BOOK_MISSING_FIELD_" + name)

    def test_pilot_requires_accounting_year_source_and_owner(self):
        result = validate(self.doc, "PILOT_READ")
        self.assertTrue({"MISSING_FISCAL_YEAR", "MISSING_OWNER", "SOURCE_REQUIRED_FOR_READ_OR_WRITE_SIMULATION"}.issubset(result["errors"]))

    def test_noncalendar_fiscal_period_valid(self):
        self.assertEqual(validate(complete_readonly(self.doc), "PILOT_READ")["status"], "READY_FOR_PILOT_READ_SIMULATION")
        self.assertIsNone(self.doc["BOOK"]["LAST_SNAPSHOT"])

    def test_fiscal_year_not_inferred(self):
        doc = complete_readonly(self.doc); doc["BOOK"]["FISCAL_YEAR"]["START"] = "2027-01-01"
        self.blocked(doc, "PILOT_READ", "INVALID_FISCAL_PERIOD")

    def test_invalid_fiscal_date(self):
        doc = complete_readonly(self.doc); doc["BOOK"]["FISCAL_YEAR"]["END"] = "2027-02-30"
        self.blocked(doc, "PILOT_READ", "INVALID_FISCAL_PERIOD")

    def test_fiscal_configuration_requires_demo_confirmation_for_pilot(self):
        doc = complete_readonly(self.doc); del doc["BOOK"]["FISCAL_YEAR"]["CONFIRMED_BY"]
        self.blocked(doc, "PILOT_READ", "FISCAL_CONFIRMATION_MISSING")

    def test_source_required_when_present_even_demo(self):
        self.doc["SOURCE_PRESENT"] = True
        self.blocked(self.doc, "DEMO", "MISSING_SOURCE_REF")

    def test_source_ref_wrong_scope(self):
        doc = complete_readonly(self.doc); doc["BOOK"]["SOURCE_REF"]["BOOK_ID"] = "DEMO-OTHER"
        self.blocked(doc, "PILOT_READ", "SOURCE_REF_MISMATCH_BOOK_ID")
        doc["BOOK"]["SOURCE_REF"]["PROJECT_ID"] = "DEMO-OTHER"
        self.blocked(doc, "PILOT_READ", "SOURCE_REF_MISMATCH_PROJECT_ID")

    def test_filename_is_not_durable_reference(self):
        doc = complete_readonly(self.doc); doc["BOOK"]["SOURCE_REF"]["ID"] = "book.csv"
        self.blocked(doc, "PILOT_READ", "INVALID_SOURCE_REF")

    def test_reviewer_is_not_owner(self):
        doc = complete_readonly(self.doc); doc["BOOK"]["OWNER"] = {"ID": "OWNER", "KIND": "DEMO_ROLE"}
        self.blocked(doc, "PILOT_READ", "INVALID_DEMO_OWNER")

    def test_fake_owner_never_grants_live_authorization(self):
        result = validate(backup(complete_readonly(self.doc)), "PRE_WRITE")
        self.assertEqual(result["status"], "READY_FOR_PRE_WRITE_SIMULATION")
        self.assertFalse(result["live_authorized"])

    def test_prewrite_requires_separate_destination_backup(self):
        self.blocked(complete_readonly(self.doc), "PRE_WRITE", "MISSING_DESTINATION_BACKUP")

    def test_null_backup_never_allows_demo_or_pilot_destination_write(self):
        self.doc["DESTINATION_WRITE"] = True
        self.blocked(self.doc, "DEMO", "DESTINATION_WRITE_NOT_ALLOWED")
        doc = complete_readonly(self.doc)
        self.blocked(doc, "PILOT_READ", "DESTINATION_WRITE_NOT_ALLOWED")

    def test_backup_scope_and_restore_proof_checked(self):
        doc = backup(complete_readonly(self.doc)); doc["BOOK"]["LAST_SNAPSHOT"]["PERIOD"] = "2026-10"
        self.blocked(doc, "PRE_WRITE", "BACKUP_MISMATCH_PERIOD")
        doc["BOOK"]["LAST_SNAPSHOT"]["RESTORE_TEST"] = "NONE"
        self.blocked(doc, "PRE_WRITE", "INVALID_DESTINATION_BACKUP")

    def test_backup_metadata_and_timezone_required(self):
        for key in ("RESTORE_TEST_ID", "DESTINATION_VERSION", "PROTECTED_LOCATION_ID", "RESPONSIBLE_OWNER"):
            with self.subTest(key=key):
                doc = backup(complete_readonly(copy.deepcopy(self.doc))); del doc["BOOK"]["LAST_SNAPSHOT"][key]
                self.blocked(doc, "PRE_WRITE", "INVALID_DESTINATION_BACKUP")
        doc = backup(complete_readonly(self.doc)); doc["BOOK"]["LAST_SNAPSHOT"]["CAPTURED_AT"] = "2026-11-01T00:00:00"
        self.blocked(doc, "PRE_WRITE", "INVALID_BACKUP_TIMESTAMP")

    def test_empty_branch_rejected_but_null_and_na_match(self):
        self.assertEqual(validate(self.doc, "DEMO")["status"], "READY_FOR_DEMO_SIMULATION")
        self.doc["JOB"]["BRANCH_ID"] = ""
        self.blocked(self.doc, "DEMO", "JOB_MISSING_OR_INVALID_BRANCH_ID")

    def test_wrong_scope_blocked(self):
        for key in ("LEGAL_ENTITY_ID", "BOOK_ID", "PERIOD", "BRANCH_ID", "PROJECT_ID"):
            with self.subTest(field=key):
                bad = copy.deepcopy(self.doc); bad["JOB"][key] = "DEMO-WRONG"
                self.assertEqual(validate(bad, "DEMO")["status"], "BLOCKED")

    def test_missing_required_scope_is_blocked(self):
        for obj in ("BOOK", "PROJECT", "JOB"):
            for key in ("LEGAL_ENTITY_ID", "BOOK_ID", "PERIOD", "BRANCH_ID"):
                with self.subTest(obj=obj, key=key):
                    bad = copy.deepcopy(self.doc); del bad[obj][key]
                    self.assertEqual(validate(bad, "DEMO")["status"], "BLOCKED")

    def test_missing_project_is_blocked(self):
        self.doc["PROJECT"]["PROJECT_ID"] = None; self.doc["JOB"]["PROJECT_ID"] = None
        self.blocked(self.doc, "DEMO", "PROJECT_MISSING_PROJECT_ID")

    def test_configuration_versions_fail_closed(self):
        for obj in ("ROOT", "BOOK", "PROJECT", "JOB"):
            with self.subTest(obj=obj):
                bad = copy.deepcopy(self.doc); (bad if obj == "ROOT" else bad[obj])["CONFIG_VERSION"] = "OTHER"
                self.assertEqual(validate(bad, "DEMO")["status"], "BLOCKED")

    def test_legacy_checkpoint_and_version_are_rejected(self):
        self.blocked_checkpoint(resume(self.doc, "DEMO", {"status": "VERIFIED"}), "INCOMPATIBLE_CHECKPOINT_VERSION")
        old = checkpoint(self.doc, "DEMO"); old["CONFIG_VERSION"] = "P0"
        self.blocked_checkpoint(resume(self.doc, "DEMO", old), "INCOMPATIBLE_CHECKPOINT_VERSION")

    def blocked_checkpoint(self, result, error):
        self.assertEqual(result["status"], "BLOCKED"); self.assertIn(error, result["errors"])

    def test_checkpoint_resume_unchanged_and_changed(self):
        saved = checkpoint(self.doc, "DEMO")
        self.assertEqual(resume(self.doc, "DEMO", saved)["status"], "READY_FOR_DEMO_SIMULATION")
        changed = copy.deepcopy(self.doc); changed["BOOK"]["FISCAL_YEAR"] = {"ID": "DEMO-FY", "START": "2026-01-01", "END": "2026-12-31"}
        self.blocked_checkpoint(resume(changed, "DEMO", saved), "CHECKPOINT_CHANGED")

    def test_checkpoint_not_cross_stage(self):
        doc = complete_readonly(self.doc); saved = checkpoint(doc, "DEMO")
        self.blocked_checkpoint(resume(doc, "PILOT_READ", saved), "CHECKPOINT_CHANGED")

    def test_checkpoint_cannot_claim_live_authorization(self):
        saved = checkpoint(self.doc, "DEMO"); saved["live_authorized"] = True
        self.blocked_checkpoint(resume(self.doc, "DEMO", saved), "CHECKPOINT_CHANGED")

    def test_non_synthetic_rejected(self):
        self.doc["DATA_CLASS"] = "LIVE"
        self.blocked(self.doc, "DEMO", "NON_SYNTHETIC_DATA")

    def test_invalid_book_kind_cannot_bypass_fiscal_rule(self):
        doc = complete_readonly(self.doc); doc["BOOK"]["BOOK_KIND"] = "TYPO"; doc["BOOK"]["FISCAL_YEAR"] = None
        self.blocked(doc, "PILOT_READ", "INVALID_BOOK_KIND")

    def test_missing_versions_blocked(self):
        for obj in ("ROOT", "BOOK", "PROJECT", "JOB"):
            with self.subTest(obj=obj):
                bad = copy.deepcopy(self.doc); del (bad if obj == "ROOT" else bad[obj])["CONFIG_VERSION"]
                self.assertEqual(validate(bad, "DEMO")["status"], "BLOCKED")

    def test_real_demo_m2_checkpoint_is_not_a_p1_checkpoint(self):
        path = FIXTURE.with_name("fixture_m2_legacy.json")
        old = json.loads(path.read_text(encoding="utf-8"))
        self.blocked_checkpoint(resume(self.doc, "DEMO", old), "INCOMPATIBLE_CHECKPOINT_VERSION")

    def test_invalid_type_fails_closed(self):
        self.doc["BOOK"]["BOOK_KIND"] = {"unexpected": True}
        self.blocked(self.doc, "DEMO", "INVALID_BOOK_KIND")
        self.assertEqual(validate(self.doc, ["DEMO"])["status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
