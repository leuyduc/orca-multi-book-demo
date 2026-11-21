"""P1-sealed M3 workflow DEMO bridge; never touches a real ledger.

Prepare one BOOK snapshot from shared synthetic CSV inputs, seal exactly those
four filtered CSVs with P1, then verify them before and after M3 PowerShell.
Legacy M3 remains available only for regression; this bridge is the P1 path.
"""
from __future__ import annotations
import argparse
import csv
import io
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

STAGE = Path(__file__).resolve().parent
P1 = STAGE / 'p1-manifest'
ROOT = STAGE / '_p1_m3'
INPUT = STAGE / 'input'
COLUMNS = ('books.csv', 'queue.csv', 'projects.csv', 'evidence.csv')
BOOK_MAP = {
    'DEMO-A-CASH-2026': ('fixture_manifest_A.json','DEMO-OWNER-A','DEMO-REVIEWER-A'),
    'DEMO-B-MISA-2026': ('fixture_manifest_B.json','DEMO-OWNER-B','DEMO-REVIEWER-B'),
}

class BridgeError(ValueError):
    pass

def ensure(value,reason):
    if not value: raise BridgeError(reason)

def load_p1():
    spec=spec_from_file_location('p1_manifest_for_m3',P1/'manifest_demo.py')
    module=module_from_spec(spec);spec.loader.exec_module(module)
    return module

def read_csv(name):
    ensure(name in COLUMNS,'UNLISTED_INPUT')
    path=INPUT/name
    ensure(path.is_file() and not path.is_symlink(),'INPUT_NOT_SYNTHETIC_CSV')
    raw=path.read_bytes()
    try:
        text=raw.decode('utf-8-sig')
        reader=csv.DictReader(io.StringIO(text,newline=''),strict=True)
        fields=reader.fieldnames
        ensure(fields and len(set(fields))==len(fields),'BAD_SOURCE_HEADER')
        rows=list(reader)
    except (csv.Error,UnicodeError) as exc:
        raise BridgeError('INVALID_INPUT_CSV') from exc
    ensure(rows and all(None not in row for row in rows),'INVALID_SOURCE_ROWS')
    return list(fields),rows

def select_rows(doc,filename,rows):
    book=doc['BOOK'];project=doc['PROJECT'];job=doc['JOB']
    selected=[]
    for row in rows:
        if row.get('BOOK_ID')!=book['BOOK_ID']:continue
        if filename in ('evidence.csv','projects.csv'):
            if row.get('PROJECT_ID') !=project['PROJECT_ID']:continue
        ensure(row.get('LEGAL_ENTITY_ID')==book['LEGAL_ENTITY_ID'],'WRONG_ENTITY_ROW')
        if 'BRANCH_ID' in row:ensure(row['BRANCH_ID']==('NA' if book['BRANCH_ID'] in (None,'NA') else book['BRANCH_ID']),'WRONG_BRANCH_ROW')
        if 'PERIOD' in row:ensure(row['PERIOD']==book['PERIOD'],'WRONG_PERIOD_ROW')
        if filename=='queue.csv':
            ensure(row.get('PROJECT_ID')==project['PROJECT_ID'],'WRONG_QUEUE_PROJECT')
            ensure(row.get('SOURCE_SNAPSHOT_ID')==job['SOURCE_SNAPSHOT_ID'],'WRONG_QUEUE_SNAPSHOT')
            ensure(row.get('PERMISSION_SCOPE')=='SYNTHETIC_ONLY','NON_SYNTHETIC_QUEUE')
        selected.append(row)
    if filename != 'evidence.csv':ensure(len(selected)==1,'AMBIGUOUS_SCOPED_REGISTRY_OR_QUEUE')
    else:ensure(bool(selected),'MISSING_BOOK_EVIDENCE')
    return selected

def csv_bytes(fields,rows):
    stream=io.StringIO(newline='')
    writer=csv.DictWriter(stream,fields,lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    return stream.getvalue().encode('utf-8')

def safe_sandbox(book):
    ensure(book in BOOK_MAP,'UNKNOWN_DEMO_BOOK')
    return ROOT/book

def prepare(book):
    sandbox=safe_sandbox(book)
    ensure(not sandbox.exists() and not sandbox.is_symlink(),'SANDBOX_ALREADY_EXISTS')
    p1=load_p1()
    fixture,exporter,reviewer=BOOK_MAP[book]
    doc=json.loads((P1/fixture).read_text(encoding='utf-8'))
    ensure(doc['BOOK']['BOOK_ID']==book and doc['JOB']['BOOK_ID']==book,'P1_DOCUMENT_WRONG_BOOK')
    files={}
    for name in COLUMNS:
        cols,all_rows=read_csv(name)
        files[name]=csv_bytes(cols,select_rows(doc,name,all_rows))
    # All processing data derives from this dedicated, immutable DEMO copy.
    sandbox.mkdir(parents=True)
    target=sandbox/'input';target.mkdir()
    (target/p1.MARKER).write_text(p1.MARKER_TEXT,encoding='utf-8')
    for name,content in files.items():
        with (target/name).open('xb') as stream:stream.write(content)
    (sandbox/'checkpoints').mkdir()
    (sandbox/'p1_document.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # The P1 manifest contains SHA256 of exactly the bytes M3 will read later.
    manifest=p1.build_manifest(target,doc,doc['JOB']['SOURCE_SNAPSHOT_ID'],
         datetime.now(timezone.utc).replace(microsecond=0).isoformat(),exporter,reviewer)
    seal=p1.make_seal(manifest);checkpoint=p1.make_checkpoint(manifest,doc)
    ensure(p1.verify_manifest(target,doc,manifest,seal,checkpoint)['status']=='VERIFIED_SYNTHETIC_ONLY','P1_FAIL')
    dest=sandbox/'p1-manifest';dest.mkdir()
    for name,data in [('source_manifest.json',manifest),('source_seal.json',seal),
                      (p1.ticket_id(doc)+'.json',checkpoint)]:
        (dest/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'status':'PREPARED_SYNTHETIC_ONLY','book':book,'files':manifest['FILE_COUNT'],
            'rows':manifest['ROW_COUNT'],'manifest_sha256':seal['MANIFEST_SHA256'],
            'destination_write_allowed':False}

def verify(book):
    sandbox=safe_sandbox(book);p1=load_p1()
    ensure(sandbox.is_dir() and not sandbox.is_symlink(),'SANDBOX_MISSING')
    target=sandbox/'input';dest=sandbox/'p1-manifest'
    ensure(target.is_dir() and dest.is_dir(),'P1_SNAPSHOT_MISSING')
    doc=json.loads((sandbox/'p1_document.json').read_text('utf-8'))
    manifest=json.loads((dest/'source_manifest.json').read_text('utf-8'))
    seal=json.loads((dest/'source_seal.json').read_text('utf-8'))
    checkpoint=json.loads((dest/(p1.ticket_id(doc)+'.json')).read_text('utf-8'))
    ensure(doc['BOOK']['BOOK_ID']==book,'BOOK_TAMPERED')
    result=p1.verify_manifest(target,doc,manifest,seal,checkpoint)
    ensure(result['status']=='VERIFIED_SYNTHETIC_ONLY','P1_BLOCKED:'+','.join(result['errors']))
    ensure({x['REL_PATH'] for x in manifest['FILES']}==set(COLUMNS),'M3_SOURCE_SET_CHANGED')
    return {'status':'VERIFIED_SYNTHETIC_ONLY','book':book,'manifest_sha256':seal['MANIFEST_SHA256'],
            'destination_write_allowed':False}

def run_workflow(book):
    sandbox=safe_sandbox(book)
    before=verify(book)
    ensure(os.name=='nt','M3_POWERSHELL_REQUIRES_WINDOWS')
    cmd=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(STAGE/'workflow.ps1'),
         '-BookId',book,'-WorkflowRoot',str(sandbox)]
    process=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    ensure(process.returncode==0,'M3_WORKFLOW_FAILED')
    after=verify(book)
    ensure(before['manifest_sha256']==after['manifest_sha256'],'P1_SOURCE_CHANGED_AFTER_M3')
    try:workflow=json.loads(process.stdout)
    except json.JSONDecodeError as exc:raise BridgeError('M3_NON_JSON_RESULT') from exc
    ensure(workflow['status']=='VERIFIED' and workflow['book_id']==book,'M3_NOT_VERIFIED')
    return {'status':'VERIFIED_M3_SYNTHETIC_ONLY','book':book,'record_count':workflow['record_count'],
            'transaction_count':workflow['transaction_count'],
            'p1_manifest_sha256':after['manifest_sha256'],
            'destination_write_allowed':False,'live_authorized':False}

def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('command',choices=('prepare','verify','run'))
    cli.add_argument('--book',required=True,choices=sorted(BOOK_MAP))
    args=cli.parse_args()
    result={'prepare':prepare,'verify':verify,'run':run_workflow}[args.command](args.book)
    print(json.dumps(result,ensure_ascii=False));return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (BridgeError,ValueError,KeyError,OSError,subprocess.TimeoutExpired,TypeError) as exc:
        print(json.dumps({'status':'BLOCKED','reason':str(exc) if isinstance(exc,BridgeError) else 'INVALID_DEMO_INPUT'},ensure_ascii=False));sys.exit(2)
