#!/usr/bin/env python3
"""Read-only toy validator for synthetic multi-book job routing.

DO NOT connect to Google/MISA/Zalo. DO NOT use as production ledger writer.
"""
import argparse
import csv
import json
from pathlib import Path

REQUIRED_BOOK = ('BOOK_ID','LEGAL_ENTITY_ID','BRANCH_ID','PERIOD')
REQUIRED_JOB = ('JOB_ID','BOOK_ID','LEGAL_ENTITY_ID','BRANCH_ID','PERIOD','SOURCE_SNAPSHOT_ID')
ALLOWED_ACTIONS = {'RECONCILE_READ_ONLY','GENERATE_REPORT_OFFLINE','VALIDATE_SYNTHETIC'}

def read_csv(path):
    with Path(path).open('r',encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))

def validate_job(job,books_by_id):
    problems=[]
    for key in REQUIRED_JOB:
        if not (job.get(key) or '').strip():
            problems.append('MISSING_'+key)
    book=books_by_id.get((job.get('BOOK_ID') or '').strip())
    if book is None:
        problems.append('UNKNOWN_BOOK')
    else:
        for key in ('LEGAL_ENTITY_ID','BRANCH_ID','PERIOD'):
            if job.get(key,'') != book.get(key,''):
                problems.append('MISMATCH_'+key)
        if book.get('WRITE_SCOPE') != 'NONE':
            problems.append('UNSAFE_WRITE_SCOPE_IN_DEMO')
        if book.get('READ_SCOPE') != 'SYNTHETIC_ONLY':
            problems.append('NON_SYNTHETIC_BOOK')
    if job.get('ACTION') not in ALLOWED_ACTIONS:
        problems.append('ACTION_NOT_ALLOWED_IN_DEMO')
    return sorted(set(problems))

def validate_batch(books,jobs):
    books_by_id={}
    duplicate_books=set()
    for book in books:
        book_id=(book.get('BOOK_ID') or '').strip()
        if not book_id: continue
        if book_id in books_by_id: duplicate_books.add(book_id)
        books_by_id[book_id]=book
    seen_jobs=set()
    seen_intents=set()
    results=[]
    for job in jobs:
        job_id=job.get('JOB_ID','')
        errors=validate_job(job,books_by_id)
        if job.get('BOOK_ID') in duplicate_books:
            errors.append('AMBIGUOUS_BOOK_REGISTRY')
        if job_id in seen_jobs: errors.append('DUPLICATE_JOB_ID')
        seen_jobs.add(job_id)
        intent=(job.get('BOOK_ID'),job.get('TRANSACTION_ID'),job.get('VERSION'),job.get('ACTION'))
        # This detects duplicated intent in the input; it is NOT a durable production idempotency store.
        if intent in seen_intents:
            errors.append('DUPLICATE_INTENT_IN_BATCH')
        seen_intents.add(intent)
        results.append({'job_id':job_id,'book_id':job.get('BOOK_ID'),
                        'result':'BLOCKED' if errors else 'READY_FOR_OFFLINE_CHECK',
                        'problems':sorted(set(errors))})
    return {'demo_only': True, 'live_writes': False, 'results': results,
            'summary':{'checked':len(results),'ready':sum(x['result']=='READY_FOR_OFFLINE_CHECK' for x in results),
                       'blocked':sum(x['result']=='BLOCKED' for x in results)}}

def main():
    parser=argparse.ArgumentParser(description='Demo multi-ledger routing validator; read only.')
    parser.add_argument('--books',required=True)
    parser.add_argument('--jobs',required=True)
    args=parser.parse_args()
    print(json.dumps(validate_batch(read_csv(args.books),read_csv(args.jobs)),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
