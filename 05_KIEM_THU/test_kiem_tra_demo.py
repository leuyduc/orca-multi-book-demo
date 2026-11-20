import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from kiem_tra_demo import validate_job, validate_batch

BOOKS=[
 {'BOOK_ID':'A1','LEGAL_ENTITY_ID':'A','BRANCH_ID':'NA','PERIOD':'2026-11','READ_SCOPE':'SYNTHETIC_ONLY','WRITE_SCOPE':'NONE'},
 {'BOOK_ID':'B1','LEGAL_ENTITY_ID':'B','BRANCH_ID':'B_HN','PERIOD':'2026-11','READ_SCOPE':'SYNTHETIC_ONLY','WRITE_SCOPE':'NONE'},
]
def job(job_id='J1',book_id='A1',entity='A',branch='NA',period='2026-11',tx='TX1',action='RECONCILE_READ_ONLY'):
 return {'JOB_ID':job_id,'BOOK_ID':book_id,'LEGAL_ENTITY_ID':entity,'BRANCH_ID':branch,'PERIOD':period,
 'SOURCE_SNAPSHOT_ID':'SYN01','TRANSACTION_ID':tx,'VERSION':'1','ACTION':action}

class DemoTest(unittest.TestCase):
 def test_two_distinct_books_process_independently(self):
  summary=validate_batch(BOOKS,[job(),job('J2','B1','B','B_HN',tx='TX1')]); self.assertEqual(summary['summary']['ready'],2)
 def test_wrong_legal_entity_blocked(self):
  self.assertIn('MISMATCH_LEGAL_ENTITY_ID',validate_job(job(entity='B'),{b['BOOK_ID']:b for b in BOOKS}))
 def test_wrong_branch_blocked(self):
  self.assertIn('MISMATCH_BRANCH_ID',validate_job(job('J2','B1','B','NA'),{b['BOOK_ID']:b for b in BOOKS}))
 def test_wrong_period_blocked(self):
  self.assertIn('MISMATCH_PERIOD',validate_job(job(period='2026-10'),{b['BOOK_ID']:b for b in BOOKS}))
 def test_missing_snapshot_blocked(self):
  j=job();j['SOURCE_SNAPSHOT_ID']='';self.assertIn('MISSING_SOURCE_SNAPSHOT_ID',validate_job(j,{b['BOOK_ID']:b for b in BOOKS}))
 def test_unknown_book_blocked(self):
  self.assertIn('UNKNOWN_BOOK',validate_job(job(book_id='X'),{b['BOOK_ID']:b for b in BOOKS}))
 def test_write_action_not_supported(self):
  self.assertIn('ACTION_NOT_ALLOWED_IN_DEMO',validate_job(job(action='WRITE_LIVE'),{b['BOOK_ID']:b for b in BOOKS}))
 def test_duplicate_intent_same_book_blocked(self):
  out=validate_batch(BOOKS,[job(),job('J2',tx='TX1')]);self.assertEqual(out['results'][1]['result'],'BLOCKED')
  self.assertIn('DUPLICATE_INTENT_IN_BATCH',out['results'][1]['problems'])
 def test_same_tx_other_book_is_not_duplicate(self):
  out=validate_batch(BOOKS,[job(),job('J2','B1','B','B_HN',tx='TX1')]);self.assertNotIn('DUPLICATE_INTENT_IN_BATCH',out['results'][1]['problems'])
 def test_bad_job_does_not_block_good_job(self):
  out=validate_batch(BOOKS,[job(entity='B'),job('J2','B1','B','B_HN',tx='TX2')]);self.assertEqual(out['results'][1]['result'],'READY_FOR_OFFLINE_CHECK')
 def test_duplicate_job_id_is_blocked(self):
  out=validate_batch(BOOKS,[job(),job(tx='TX2')]);self.assertIn('DUPLICATE_JOB_ID',out['results'][1]['problems'])
 def test_demo_never_writes(self):
  out=validate_batch(BOOKS,[job()]);self.assertEqual(out['live_writes'],False)
 def test_registry_duplicate_book_blocked(self):
  out=validate_batch(BOOKS+[BOOKS[0]],[job()]);self.assertIn('AMBIGUOUS_BOOK_REGISTRY',out['results'][0]['problems'])
 def test_guard_non_synthetic_book(self):
  b=dict(BOOKS[0]);b['READ_SCOPE']='LIVE';self.assertIn('NON_SYNTHETIC_BOOK',validate_job(job(),{'A1':b}))
 def test_guard_writer_scope(self):
  b=dict(BOOKS[0]);b['WRITE_SCOPE']='EDIT';self.assertIn('UNSAFE_WRITE_SCOPE_IN_DEMO',validate_job(job(),{'A1':b}))

if __name__=='__main__':unittest.main()
