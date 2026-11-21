"""Offline regression for twenty UNAPPROVED synthetic workbook scenarios."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
_SPEC=importlib.util.spec_from_file_location('cases20',ROOT/'case20_engine.py')
m=importlib.util.module_from_spec(_SPEC)
import sys
sys.modules['cases20']=m
_SPEC.loader.exec_module(m)

class CasebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=json.loads((ROOT/'cases20_demo.json').read_text('utf-8'))

    def copy(self): return copy.deepcopy(self.source)

    def test_all_20_expected_labels_amounts_match_source_workbook(self):
        data=self.copy(); out=m.evaluate_casebook(data)
        self.assertEqual(len(out['RESULTS']),20)
        for actual,expected in zip(out['RESULTS'],data['cases']):
            with self.subTest(case=expected['id']):
                self.assertEqual(actual['CLASSIFICATION'],expected['classification'])
                self.assertEqual(actual['STATUS_LABEL'],expected['state'])
                self.assertEqual(actual['PROPOSED_IN_VND'],expected['in'])
                self.assertEqual(actual['PROPOSED_OUT_VND'],expected['out'])
                self.assertEqual(actual['APPROVAL_STATUS'],'UNAPPROVED')
                self.assertFalse(actual['LIVE_AUTHORIZED'])
                self.assertFalse(actual['DESTINATION_WRITE_ALLOWED'])
                self.assertFalse(actual['SOURCE_EVIDENCE_VALIDATED'])

    def test_summary_proposed_not_posted(self):
        out=m.evaluate_casebook(self.copy())
        self.assertEqual(out['COUNTS'],{
            'CASES':20,'READY_FOR_OWNER':9,'NEEDS_REVIEW':11,
            'PROPOSED_IN_VND':101700000,'PROPOSED_OUT_VND':19711000})
        self.assertFalse(out['BUSINESS_EXPECTATIONS_APPROVED'])
        self.assertEqual(out['APPROVAL_STATUS'],'UNAPPROVED')
        self.assertFalse(out['DESTINATION_WRITE_ALLOWED'])

    def test_advance_settlement_and_internal_transfer_not_double_cash(self):
        rows={r['CASE_ID']:r for r in m.evaluate_casebook(self.copy())['RESULTS']}
        self.assertEqual(rows['TC08']['PROPOSED_OUT_VND'],5000000)
        self.assertEqual(rows['TC08']['INTERNAL_COST_CANDIDATE_VND'],0)
        self.assertEqual(rows['TC09']['PROPOSED_OUT_VND'],0)
        self.assertEqual(rows['TC10']['PROPOSED_IN_VND'],1200000)
        self.assertEqual(rows['TC12']['PROPOSED_OUT_VND'],0)
        self.assertEqual(rows['TC19']['PROPOSED_OUT_VND'],0)
        self.assertEqual(rows['TC20']['INTERNAL_COST_CANDIDATE_VND'],0)
        self.assertEqual(5000000,3800000+1200000)

    def test_no_posting_if_still_waiting_on_evidence(self):
        rows={r['CASE_ID']:r for r in m.evaluate_casebook(self.copy())['RESULTS']}
        for case in ['TC02','TC04','TC05','TC06','TC09','TC12','TC15','TC16','TC17','TC18','TC19']:
            with self.subTest(case=case):
                self.assertEqual(rows[case]['PROPOSED_IN_VND'],0)
                self.assertEqual(rows[case]['PROPOSED_OUT_VND'],0)
                self.assertEqual(rows[case]['REVIEW_STATE'],'NEEDS_REVIEW')

    def test_template_stagging_spelling_and_review_shape(self):
        data=self.copy(); result=m.evaluate_casebook(data)
        rows=m.rows_for_stagging(data,result)
        self.assertEqual(m.STAGING_SHEET_NAME,'stagging')
        self.assertEqual(len(m.STAGING_COLUMNS),16)
        self.assertEqual(len(rows),20)
        self.assertEqual(set(rows[0]),set(m.STAGING_COLUMNS))
        self.assertEqual(rows[0]['Thu (VND)'],'')
        self.assertEqual(rows[0]['Chi (VND)'],4200000)
        self.assertEqual(rows[0]['Trạng thái duyệt'],'Chờ kiểm tra')
        self.assertEqual(rows[0]['Ngày đã chuyển'],'')
        self.assertEqual(rows[0]['Phản hồi người phụ trách'],'')
        self.assertEqual(rows[0]['Bill / chứng từ'],'')  # Workbook contains description, not actual bill.
        self.assertEqual(rows[8]['Chi (VND)'],'')

    def test_reconciliation_has_all_non_ready_cases(self):
        data=self.copy(); result=m.evaluate_casebook(data)
        rows=m.rows_for_reconciliation(data,result)
        self.assertEqual(len(rows),11)
        self.assertEqual(set(rows[0]),set(m.RECON_COLUMNS))
        self.assertIn('Đối chiếu tạm ứng',[x['Trạng thái'] for x in rows])
        self.assertIn('Từ chối ghi trùng',[x['Trạng thái'] for x in rows])
        self.assertIn('Theo dõi công nợ',[x['Trạng thái'] for x in rows])

    def test_duplicate_case_and_source_doc_fail_closed(self):
        data=self.copy(); data['cases'][1]['id']=data['cases'][0]['id']
        with self.assertRaisesRegex(m.CasebookError,'DUPLICATE_CASE_ID'):
            m.evaluate_casebook(data)
        data=self.copy(); data['cases'][1]['document']=data['cases'][0]['document']
        with self.assertRaisesRegex(m.CasebookError,'DUPLICATE_SOURCE_DOC_ID'):
            m.evaluate_casebook(data)

    def test_wrong_company_scope_blocked(self):
        data=self.copy(); data['legal_entity_id']='DEMO_B'
        with self.assertRaisesRegex(m.CasebookError,'WRONG_BOOK_SCOPE'):
            m.evaluate_casebook(data)

    def test_wrong_period_and_missing_project(self):
        data=self.copy(); data['cases'][0]['date']='2026-12-01'
        with self.assertRaisesRegex(m.CasebookError,'WRONG_PERIOD'):
            m.evaluate_casebook(data)
        data=self.copy(); data['cases'][0]['project']=None
        with self.assertRaisesRegex(m.CasebookError,'PROJECT_REQUIRED'):
            m.evaluate_casebook(data)

    def test_already_posted_not_reopened_as_ready(self):
        data=self.copy(); data['cases'][0]['already_recorded']=True
        with self.assertRaisesRegex(m.CasebookError,'CONFLICTING_LEDGER_DUPLICATE'):
            m.evaluate_casebook(data)

    def test_unrecognized_scenario_never_guessed(self):
        data=self.copy(); data['cases'][0]['type']='UNKNOWN_AI_GUESS'
        with self.assertRaisesRegex(m.CasebookError,'UNKNOWN_SCENARIO'):
            m.evaluate_casebook(data)

    def test_no_output_to_root_or_source(self):
        with self.assertRaisesRegex(m.CasebookError,'OUTPUT_NOT_IN_DEMO_OUTPUT_ROOT'):
            m.safe_publish(ROOT/'outside',{'foo.csv':b'foo'})

    def test_csv_export_headers_and_column_count(self):
        data=self.copy(); result=m.evaluate_casebook(data)
        b=m.encode_csv(m.rows_for_stagging(data,result),m.STAGING_COLUMNS)
        self.assertTrue(b.startswith(b'\xef\xbb\xbf'))
        import csv,io
        records=list(csv.reader(io.StringIO(b.decode('utf-8-sig'))))
        self.assertEqual(len(records),21)
        self.assertTrue(all(len(row)==16 for row in records))

if __name__=='__main__': unittest.main(verbosity=2)
