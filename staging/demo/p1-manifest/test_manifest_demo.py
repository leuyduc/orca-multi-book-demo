"""Synthetic-only P1 manifest security, resume, and cross-book tests."""
import copy
import subprocess
import json
import pathlib
import shutil
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import manifest_demo as m


def doc(letter):
    return json.loads((HERE/f'fixture_manifest_{letter}.json').read_text(encoding='utf-8'))


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='orca-p1-manifest-')
        self.addCleanup(self.tmp.cleanup)
        self.root=pathlib.Path(self.tmp.name)
        self.a=self.root/'A'
        self.b=self.root/'B'
        shutil.copytree(HERE/'input-A',self.a)
        shutil.copytree(HERE/'input-B',self.b)
        self.doc_a=doc('A'); self.doc_b=doc('B')
        self.man_a=self.build_a()
        self.seal_a=m.make_seal(self.man_a)
        self.cp_a=m.make_checkpoint(self.man_a,self.doc_a)

    def build_a(self, **kwargs):
        defaults=dict(source_root=self.a,doc=self.doc_a,snapshot_id='SYN_A_001',
                      exported_at='2026-11-21T01:00:00+07:00',
                      exported_by='DEMO-OWNER-A', verified_by='DEMO-REVIEWER-A')
        defaults.update(kwargs)
        return m.build_manifest(**defaults)

    def build_b(self, **kwargs):
        defaults=dict(source_root=self.b,doc=self.doc_b,snapshot_id='SYN_B_001',
                      exported_at='2026-11-21T01:00:00+07:00',
                      exported_by='DEMO-OWNER-B', verified_by='DEMO-REVIEWER-B')
        defaults.update(kwargs)
        return m.build_manifest(**defaults)

    def ok(self, root=None, doc_=None, manifest=None, seal=None, checkpoint=None):
        return m.verify_manifest(root or self.a,doc_ or self.doc_a,manifest or self.man_a,
                                 seal or self.seal_a, checkpoint or self.cp_a)

    def blocked(self, error, **kwargs):
        result=self.ok(**kwargs)
        self.assertEqual(result['status'],'BLOCKED',result)
        self.assertFalse(result['live_authorized'])
        self.assertIn(error,result['errors'],result)

    def error(self, error, f, *args, **kwargs):
        with self.assertRaises(m.ManifestError) as context:
            f(*args,**kwargs)
        self.assertEqual(context.exception.code,error)

    def test_original_verification(self):
        r=self.ok()
        self.assertEqual(r['status'],'VERIFIED_SYNTHETIC_ONLY')
        self.assertEqual(r['file_count'],2)
        self.assertEqual(r['row_count'],6)
        self.assertFalse(r['live_authorized'])

    def test_manifest_hash_is_outside_manifest(self):
        self.assertNotIn('MANIFEST_SHA256', self.man_a)
        self.assertEqual(m.sha_obj(self.man_a),self.seal_a['MANIFEST_SHA256'])
        self.assertEqual(self.cp_a['MANIFEST_SHA256'],self.seal_a['MANIFEST_SHA256'])

    def test_same_files_different_order_same_manifest(self):
        manifest=self.build_a(files=['doi_chieu.csv','chung_tu.csv'])
        self.assertEqual(self.man_a,manifest)
        self.assertEqual(m.sha_obj(self.man_a),m.sha_obj(manifest))

    def test_changed_file_content_blocks(self):
        p=self.a/'chung_tu.csv';p.write_text(p.read_text().replace('100','101',1))
        self.blocked('SOURCE_FILE_CHANGED')

    def test_added_file_blocks(self):
        (self.a/'new.csv').write_text('K\nV\n',encoding='utf-8')
        self.blocked('SOURCE_FILE_SET_CHANGED')

    def test_deleted_file_blocks(self):
        (self.a/'doi_chieu.csv').unlink()
        self.blocked('MISSING_SOURCE_FILE')

    def test_empty_file_rejected(self):
        (self.a/'chung_tu.csv').write_bytes(b'')
        self.error('EMPTY_SOURCE_FILE',self.build_a)
        self.blocked('EMPTY_SOURCE_FILE')

    def test_header_only_valid_zero_rows(self):
        (self.a/'chung_tu.csv').write_text('RECORD_ID,PROJECT_ID\n',encoding='utf-8')
        manifest=self.build_a()
        self.assertEqual(manifest['ROW_COUNT'],3)
        self.assertEqual(m.verify_manifest(self.a,self.doc_a,manifest,m.make_seal(manifest))['status'],
                         'VERIFIED_SYNTHETIC_ONLY')

    def test_missing_header_blocked(self):
        (self.a/'chung_tu.csv').write_text('\n',encoding='utf-8')
        self.error('CSV_HEADER_REQUIRED',self.build_a)

    def test_row_width_mismatch_blocked(self):
        (self.a/'chung_tu.csv').write_text('A,B\n1\n',encoding='utf-8')
        self.error('CSV_ROW_WIDTH_MISMATCH',self.build_a)

    def test_duplicate_header_blocked(self):
        (self.a/'chung_tu.csv').write_text('A,A\n1,2\n',encoding='utf-8')
        self.error('CSV_DUPLICATE_HEADER',self.build_a)

    def test_invalid_utf8_blocked(self):
        (self.a/'chung_tu.csv').write_bytes(b'A\n\xff')
        self.error('INVALID_SOURCE_CSV',self.build_a)

    def test_csv_scope_project_violation_blocked(self):
        p=self.a/'chung_tu.csv';p.write_text(p.read_text().replace('DEMO-PROJECT-A','DEMO-PROJECT-B',1))
        self.error('SOURCE_ROW_SCOPE_MISMATCH',self.build_a)

    def test_csv_scope_company_violation_blocked(self):
        p=self.b/'so_misa_gia.csv';p.write_text(p.read_text().replace('DEMO_B','DEMO_A',1))
        self.error('SOURCE_ROW_SCOPE_MISMATCH',self.build_b)

    def test_csv_scope_period_violation_blocked(self):
        p=self.b/'so_misa_gia.csv';p.write_text(p.read_text().replace('2026-11','2026-10',1))
        self.error('SOURCE_ROW_SCOPE_MISMATCH',self.build_b)

    def test_csv_scope_branch_violation_blocked(self):
        p=self.b/'so_misa_gia.csv';p.write_text(p.read_text().replace('B_HN','B_HCM',1))
        self.error('SOURCE_ROW_SCOPE_MISMATCH',self.build_b)

    def test_source_ref_change_blocked(self):
        changed=copy.deepcopy(self.doc_a)
        changed['BOOK']['SOURCE_REF']['ID']='SYNREF:DEMO-A-OTHER'
        self.blocked('MANIFEST_MISMATCH_SOURCE_REF',doc_=changed)

    def test_branch_change_in_manifest_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['BRANCH_ID']='B_HN'
        self.blocked('MANIFEST_MISMATCH_BRANCH_ID',manifest=manifest,seal=m.make_seal(manifest))

    def test_book_change_in_manifest_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['BOOK_ID']='DEMO-B-MISA-2026'
        self.blocked('MANIFEST_MISMATCH_BOOK_ID',manifest=manifest,seal=m.make_seal(manifest))

    def test_period_change_in_manifest_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['PERIOD']='2026-10'
        self.blocked('MANIFEST_MISMATCH_PERIOD',manifest=manifest,seal=m.make_seal(manifest))

    def test_invalid_schema_version_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['SCHEMA_VERSION']='SYN-CSV-2'
        self.blocked('MANIFEST_VERSION_MISMATCH',manifest=manifest,seal=m.make_seal(manifest))

    def test_invalid_config_version_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['CONFIG_VERSION']='OTHER'
        self.blocked('MANIFEST_VERSION_MISMATCH',manifest=manifest,seal=m.make_seal(manifest))

    def test_manifest_corrupt_blocks_even_if_files_unchanged(self):
        manifest=copy.deepcopy(self.man_a);manifest['EXPORTED_BY']='DEMO-REVIEWER-A'
        self.blocked('INVALID_SIMULATED_VERIFIER',manifest=manifest)

    def test_seal_hash_mismatch_blocked(self):
        seal=copy.deepcopy(self.seal_a);seal['MANIFEST_SHA256']='a'*64
        self.blocked('MANIFEST_SEAL_MISMATCH',seal=seal)

    def test_duplicate_path_in_manifest_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['FILES'].append(copy.deepcopy(manifest['FILES'][0]))
        manifest['FILE_COUNT']+=1
        self.blocked('INVALID_FILE_ID_OR_ORDER',manifest=manifest,seal=m.make_seal(manifest))

    def test_duplicate_paths_in_request_blocked(self):
        self.error('DUPLICATE_SOURCE_PATH',self.build_a,files=['chung_tu.csv','chung_tu.csv'])

    def test_duplicate_on_windows_casefold_blocked(self):
        if __import__('os').name == 'nt':
            self.error('DUPLICATE_SOURCE_PATH',self.build_a,files=['chung_tu.csv','CHUNG_TU.csv'])
        else:
            (self.a/'CHUNG_TU.csv').write_text('RECORD_ID\nC\n',encoding='utf-8')
            self.error('DUPLICATE_SOURCE_PATH',self.build_a)

    def test_source_path_traversal_blocked(self):
        self.error('SOURCE_PATH_TRAVERSAL',self.build_a,files=['../outside.csv'])
        self.error('INVALID_WINDOWS_SOURCE_PATH',self.build_a,files=['C:/outside.csv'])

    def test_unlisted_source_file_request_blocked(self):
        self.error('SOURCE_FILE_SET_CHANGED',self.build_a,files=['chung_tu.csv'])

    def test_symlink_file_blocked(self):
        target=self.a/'chung_tu.csv'; link=self.a/'alias.csv'
        try:link.symlink_to(target)
        except (OSError,NotImplementedError):self.skipTest('symlinks unavailable')
        self.error('SOURCE_SYMLINK_FORBIDDEN',self.build_a)

    def test_missing_marker_blocked(self):
        (self.a/m.MARKER).unlink()
        self.error('SYNTHETIC_ROOT_MARKER_MISSING',self.build_a)

    def test_corrupted_marker_blocked(self):
        (self.a/m.MARKER).write_text('LIVE',encoding='utf-8')
        self.error('INVALID_SYNTHETIC_ROOT_MARKER',self.build_a)

    def test_unknown_data_class_blocked(self):
        doc_=copy.deepcopy(self.doc_a);doc_['DATA_CLASS']='LIVE'
        self.error('NON_SYNTHETIC_DOCUMENT',self.build_a,doc=doc_)

    def test_destination_write_blocked(self):
        doc_=copy.deepcopy(self.doc_a);doc_['DESTINATION_WRITE']=True
        self.error('READ_ONLY_SOURCE_REQUIRED',self.build_a,doc=doc_)

    def test_missing_fiscal_year_blocked(self):
        doc_=copy.deepcopy(self.doc_a);doc_['BOOK']['FISCAL_YEAR']=None
        self.error('P1_SCHEMA_BLOCKED',self.build_a,doc=doc_)

    def test_naive_timestamp_blocked(self):
        self.error('INVALID_EXPORT_TIMESTAMP',self.build_a,exported_at='2026-11-21T01:00:00')

    def test_same_exporter_verifier_blocked(self):
        self.error('INVALID_SIMULATED_VERIFIER',self.build_a,verified_by='DEMO-OWNER-A')

    def test_unknown_verifier_blocked(self):
        self.error('INVALID_SIMULATED_VERIFIER',self.build_a,verified_by='DEMO-OTHER')

    def test_changed_doc_blocks_resume(self):
        doc_=copy.deepcopy(self.doc_a);doc_['JOB']['SOURCE_SNAPSHOT_ID']='SYN_A_002'
        self.blocked('SOURCE_SNAPSHOT_JOB_MISMATCH',doc_=doc_)

    def test_checkpoint_tampering_blocked(self):
        cp=copy.deepcopy(self.cp_a);cp['STATUS']='DONE'
        self.blocked('CHECKPOINT_CHANGED_OR_LEGACY',checkpoint=cp)
        cp=copy.deepcopy(self.cp_a);cp['LIVE_AUTHORIZED']=True
        self.blocked('CHECKPOINT_CHANGED_OR_LEGACY',checkpoint=cp)

    def test_legacy_checkpoint_blocked(self):
        cp={'status':'VERIFIED'}
        self.blocked('CHECKPOINT_CHANGED_OR_LEGACY',checkpoint=cp)

    def test_source_snapshot_job_mismatch_blocked_at_creation(self):
        self.error('SOURCE_SNAPSHOT_JOB_MISMATCH',self.build_a,snapshot_id='SYN_B_001')

    def test_source_snapshot_job_mismatch_blocked_during_verification(self):
        manifest=copy.deepcopy(self.man_a);manifest['SOURCE_SNAPSHOT_ID']='SYN_B_001'
        self.blocked('SOURCE_SNAPSHOT_JOB_MISMATCH',manifest=manifest,seal=m.make_seal(manifest))

    def test_source_snapshot_change_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['SOURCE_SNAPSHOT_ID']='SYN_B_001'
        self.blocked('SOURCE_SNAPSHOT_JOB_MISMATCH',manifest=manifest)

    def test_row_count_tamper_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['ROW_COUNT']+=1
        self.blocked('MANIFEST_ROW_COUNT_MISMATCH',manifest=manifest,seal=m.make_seal(manifest))

    def test_file_size_tamper_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['FILES'][0]['SIZE_BYTES']+=1
        self.blocked('SOURCE_FILE_CHANGED',manifest=manifest,seal=m.make_seal(manifest))

    def test_file_hash_tamper_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['FILES'][0]['SHA256']='0'*64
        self.blocked('SOURCE_FILE_CHANGED',manifest=manifest,seal=m.make_seal(manifest))

    def test_disallow_file_count_bool(self):
        manifest=copy.deepcopy(self.man_a);manifest['FILE_COUNT']=True
        self.blocked('MANIFEST_FILE_COUNT_MISMATCH',manifest=manifest,seal=m.make_seal(manifest))

    def test_disallow_row_count_bool(self):
        manifest=copy.deepcopy(self.man_a);manifest['ROW_COUNT']=True
        self.blocked('MANIFEST_ROW_COUNT_MISMATCH',manifest=manifest,seal=m.make_seal(manifest))

    def test_cross_company_manifest_never_reused(self):
        self.blocked('SOURCE_SNAPSHOT_JOB_MISMATCH',root=self.b,doc_=self.doc_b)

    def test_hidden_file_rejected(self):
        (self.a/'.private.csv').write_text('A\nB\n',encoding='utf-8')
        self.error('INVALID_WINDOWS_SOURCE_PATH',self.build_a)

    def test_unexpected_file_type_rejected(self):
        (self.a/'doc.pdf').write_bytes(b'%PDF-1.7')
        self.error('UNSUPPORTED_SOURCE_TYPE',self.build_a)

    def test_manifest_field_added_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['LIVE_ACCESS']=True
        self.blocked('INVALID_MANIFEST_FIELDS',manifest=manifest,seal=m.make_seal(manifest))

    def test_manifest_file_fields_added_blocked(self):
        manifest=copy.deepcopy(self.man_a);manifest['FILES'][0]['UNKNOWN']='value'
        self.blocked('INVALID_MANIFEST_FILE_FIELDS',manifest=manifest,seal=m.make_seal(manifest))

    def test_two_books_independent_simultaneous(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            fa=pool.submit(self.build_a)
            fb=pool.submit(self.build_b)
            man_a=fa.result();man_b=fb.result()
            ra=pool.submit(m.verify_manifest,self.a,self.doc_a,man_a,m.make_seal(man_a),m.make_checkpoint(man_a,self.doc_a))
            rb=pool.submit(m.verify_manifest,self.b,self.doc_b,man_b,m.make_seal(man_b),m.make_checkpoint(man_b,self.doc_b))
            self.assertEqual(ra.result()['status'],'VERIFIED_SYNTHETIC_ONLY')
            self.assertEqual(rb.result()['status'],'VERIFIED_SYNTHETIC_ONLY')
            self.assertNotEqual(man_a['BOOK_ID'],man_b['BOOK_ID'])
            self.assertNotEqual(m.sha_obj(man_a),m.sha_obj(man_b))

    def test_a_changed_b_unaffected(self):
        mb=self.build_b();sb=m.make_seal(mb);cb=m.make_checkpoint(mb,self.doc_b)
        (self.a/'chung_tu.csv').write_text('BILL\nBAD\n',encoding='utf-8')
        self.blocked('SOURCE_FILE_CHANGED')
        self.assertEqual(m.verify_manifest(self.b,self.doc_b,mb,sb,cb)['status'],'VERIFIED_SYNTHETIC_ONLY')

    def test_cli_atomic_creation_verification_and_mutation(self):
        # CLI is intentionally locked to staging/demo; use a temporary fixture there.
        with tempfile.TemporaryDirectory(dir=HERE,prefix='.cli-fixture-') as temp:
            t=pathlib.Path(temp)
            source=t/'src'; shutil.copytree(HERE/'input-A',source)
            doc_path=t/'doc.json';doc_path.write_text(json.dumps(self.doc_a),encoding='utf-8')
            out=t/'out'
            command=[sys.executable,str(HERE/'manifest_demo.py')]
            flags=['--document',str(doc_path),'--source-root',str(source),'--output-dir',str(out)]
            p=subprocess.run(command+['create']+flags,capture_output=True,text=True,check=False)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertEqual(len(list(out.iterdir())),3)
            self.assertEqual(json.loads(p.stdout)['status'],'VERIFIED_SYNTHETIC_ONLY')
            q=subprocess.run(command+['verify']+flags,capture_output=True,text=True,check=False)
            self.assertEqual(q.returncode,0,q.stdout+q.stderr)
            # No silent overwrite of already checkpointed manifests.
            q=subprocess.run(command+['create']+flags,capture_output=True,text=True,check=False)
            self.assertEqual(q.returncode,2)
            self.assertIn('OUTPUT_ALREADY_EXISTS',q.stdout)
            (source/'doi_chieu.csv').write_text('VALUE\nCHANGED\n',encoding='utf-8')
            q=subprocess.run(command+['verify']+flags,capture_output=True,text=True,check=False)
            self.assertEqual(q.returncode,2)
            self.assertIn('BLOCKED',q.stdout)

    def test_cli_no_access_outside_demo_staging(self):
        command=[sys.executable,str(HERE/'manifest_demo.py'),'create',
                 '--document',str(HERE/'fixture_manifest_A.json'),
                 '--source-root',str(self.a),'--output-dir',str(HERE/'hidden-out')]
        q=subprocess.run(command,capture_output=True,text=True,check=False)
        self.assertEqual(q.returncode,2)
        self.assertIn('SOURCE_OUTSIDE_DEMO_STAGING',q.stdout)

    def test_snapshot_source_cannot_be_destination_backup(self):
        doc_=copy.deepcopy(self.doc_a)
        doc_['DESTINATION_WRITE']=True
        doc_['BOOK']['LAST_SNAPSHOT']=copy.deepcopy(self.man_a)
        result=m._schema.validate(doc_,'PRE_WRITE')
        self.assertEqual(result['status'],'BLOCKED')
        self.assertIn('INVALID_DESTINATION_BACKUP',result['errors'])


if __name__=='__main__':
    unittest.main(verbosity=2)
