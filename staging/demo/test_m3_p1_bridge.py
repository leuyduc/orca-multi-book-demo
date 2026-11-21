"""Offline integration regression: exact per-book P1-sealed bytes feed M3 demo."""
from __future__ import annotations
import copy
import csv
import importlib.util
import os
import shutil
import tempfile
import unittest
from pathlib import Path

STAGE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('m3_p1_bridge',STAGE/'m3_p1_bridge.py')
import sys
bridge=importlib.util.module_from_spec(SPEC)
sys.modules['m3_p1_bridge']=bridge
SPEC.loader.exec_module(bridge)

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='.m3-bridge-tests-',dir=STAGE)
        self.addCleanup(self.tmp.cleanup)
        self.old_root=bridge.ROOT
        self.old_input=bridge.INPUT
        bridge.ROOT=Path(self.tmp.name)/'snapshots'
        bridge.INPUT=Path(self.tmp.name)/'source'
        shutil.copytree(STAGE/'input',bridge.INPUT)
        bridge.ROOT.mkdir()
    def tearDown(self):
        bridge.ROOT=self.old_root
        bridge.INPUT=self.old_input

    def test_a_b_have_scope_specific_p1_snapshots(self):
        a=bridge.prepare('DEMO-A-CASH-2026')
        b=bridge.prepare('DEMO-B-MISA-2026')
        self.assertEqual(a['status'],'PREPARED_SYNTHETIC_ONLY')
        self.assertEqual(b['status'],'PREPARED_SYNTHETIC_ONLY')
        self.assertEqual(a['files'],4)
        self.assertEqual(b['files'],4)
        self.assertNotEqual(a['manifest_sha256'],b['manifest_sha256'])
        for book,expected in [('DEMO-A-CASH-2026',6),('DEMO-B-MISA-2026',1)]:
            with self.subTest(book=book):
                root=bridge.ROOT/book
                self.assertEqual(bridge.verify(book)['status'],'VERIFIED_SYNTHETIC_ONLY')
                with (root/'input/evidence.csv').open(encoding='utf-8') as src:
                    rows=list(csv.DictReader(src))
                self.assertEqual(len(rows),expected)
                self.assertEqual({r['BOOK_ID'] for r in rows},{book})
                self.assertFalse((root/'input').is_symlink())

    def test_change_b_file_blocks_b_without_stopping_a(self):
        bridge.prepare('DEMO-A-CASH-2026')
        bridge.prepare('DEMO-B-MISA-2026')
        evidence=bridge.ROOT/'DEMO-B-MISA-2026'/'input/evidence.csv'
        evidence.write_text(evidence.read_text(encoding='utf-8')+'#modified',encoding='utf-8')
        with self.assertRaisesRegex(bridge.BridgeError,'P1_BLOCKED:'):
            bridge.verify('DEMO-B-MISA-2026')
        self.assertEqual(bridge.verify('DEMO-A-CASH-2026')['status'],'VERIFIED_SYNTHETIC_ONLY')

    def test_add_source_file_blocks_and_missing_checkpoint_blocks(self):
        bridge.prepare('DEMO-A-CASH-2026')
        root=bridge.ROOT/'DEMO-A-CASH-2026'
        (root/'input'/'not_listed.csv').write_text('X\nA\n',encoding='utf-8')
        with self.assertRaisesRegex(bridge.BridgeError,'P1_BLOCKED:'):
            bridge.verify('DEMO-A-CASH-2026')
        (root/'input'/'not_listed.csv').unlink()
        (root/'p1-manifest'/'P1-MANIFEST-A-002.json').unlink()
        with self.assertRaises(FileNotFoundError):
            bridge.verify('DEMO-A-CASH-2026')

    def test_same_book_prepare_twice_refuses_overwrite(self):
        bridge.prepare('DEMO-A-CASH-2026')
        with self.assertRaisesRegex(bridge.BridgeError,'SANDBOX_ALREADY_EXISTS'):
            bridge.prepare('DEMO-A-CASH-2026')

    def test_unknown_book_cannot_prepare(self):
        with self.assertRaisesRegex(bridge.BridgeError,'UNKNOWN_DEMO_BOOK'):
            bridge.prepare('DEMO-Z-CASH-2026')

    def test_wrong_queue_scope_blocks(self):
        queue=bridge.INPUT/'queue.csv'
        with queue.open(encoding='utf-8-sig',newline='') as stream:
            rows=list(csv.DictReader(stream))
        for row in rows:
            if row['BOOK_ID']=='DEMO-B-MISA-2026':row['LEGAL_ENTITY_ID']='DEMO_A'
        with queue.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)
        with self.assertRaisesRegex(bridge.BridgeError,'WRONG_ENTITY_ROW'):
            bridge.prepare('DEMO-B-MISA-2026')
        self.assertEqual(bridge.prepare('DEMO-A-CASH-2026')['status'],'PREPARED_SYNTHETIC_ONLY')

    @unittest.skipUnless(os.name=='nt','M3 PowerShell simulation only runs on Windows runner')
    def test_run_and_resume_independent_on_windows(self):
        bridge.prepare('DEMO-A-CASH-2026')
        bridge.prepare('DEMO-B-MISA-2026')
        a=bridge.run_workflow('DEMO-A-CASH-2026')
        b=bridge.run_workflow('DEMO-B-MISA-2026')
        again=bridge.run_workflow('DEMO-A-CASH-2026')
        self.assertEqual((a['record_count'],a['transaction_count']),(6,4))
        self.assertEqual((b['record_count'],b['transaction_count']),(1,1))
        self.assertEqual(again['record_count'],6)
        self.assertFalse(a['destination_write_allowed'])
        self.assertFalse(a['live_authorized'])

if __name__=='__main__':unittest.main(verbosity=2)
