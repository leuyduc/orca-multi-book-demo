"""Deterministic, synthetic-only review of the 20 unapproved pilot scenarios.

No AI guesses, MISA, Zalo, Google Sheets, authentic approvals or live writes.
Scenario type is a CURATED fixture label, not inferred from raw receipts.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping

VERSION = 'CASEBOOK20-DEMO-1'
DEMO_BOOK = 'DEMO-A-CASH-2026'
STAGING_SHEET_NAME = 'stagging'  # Exact spelling of original synthetic template.
LEDGER_SHEET_NAME = 'Nhật ký thu chi'
RECON_SHEET_NAME = 'Đối chiếu dòng tiền'

# The source workbook expected outcomes remain PROPOSED, awaiting business review.
@dataclass(frozen=True)
class ScenarioPolicy:
    classification: str
    expected_status: str
    movement: str = 'NONE'     # NONE, IN, OUT (proposed, never posted)
    code: str = 'NEEDS_REVIEW'
    internal_cost_candidate: bool = False
    note: str = ''

POLICIES: Mapping[str, ScenarioPolicy] = {
    'PAID_MATERIAL': ScenarioPolicy('Chi vật tư', 'Chờ người duyệt', 'OUT', 'READY_FOR_OWNER', True),
    'DELIVERY_UNPAID': ScenarioPolicy('Công nợ / chưa chi', 'Cần bổ sung', code='MISSING_PROOF'),
    'PAID_MATERIAL_NO_VAT': ScenarioPolicy('Chi vật tư; thiếu hồ sơ thuế', 'Chờ người duyệt', 'OUT', 'READY_FOR_OWNER', True, 'MISSING_VAT_DOCUMENT'),
    'DUP_STAGING': ScenarioPolicy('Giao dịch trùng', 'Cần bổ sung', code='POSSIBLE_DUPLICATE'),
    'ALREADY_POSTED': ScenarioPolicy('Đã ghi sổ', 'Từ chối ghi trùng', code='ALREADY_IN_LEDGER'),
    'QUOTE_ONLY': ScenarioPolicy('Dự toán / cam kết chi', 'Không phải thực chi', code='NO_CASH_MOVEMENT'),
    'CUSTOMER_DEPOSIT': ScenarioPolicy('Thu từ khách / tiền cọc', 'Chờ người duyệt', 'IN', 'READY_FOR_OWNER', note='NOT_ACCOUNTING_REVENUE'),
    'STAFF_ADVANCE': ScenarioPolicy('Chi tạm ứng; chưa là giá vốn', 'Chờ người duyệt', 'OUT', 'READY_FOR_OWNER', note='NOT_SETTLED_COST'),
    'STAFF_SETTLEMENT': ScenarioPolicy('Quyết toán tạm ứng', 'Đối chiếu tạm ứng', code='LINK_ADVANCE_NO_NEW_CASH'),
    'STAFF_RETURN': ScenarioPolicy('Thu hoàn tạm ứng; không là doanh thu', 'Chờ người duyệt', 'IN', 'READY_FOR_OWNER', note='ADVANCE_REPAYMENT_NOT_REVENUE'),
    'SUPPLIER_REFUND': ScenarioPolicy('Thu hoàn trả; giảm chi liên quan', 'Chờ người duyệt', 'IN', 'READY_FOR_OWNER', note='LINK_ORIGINAL_PURCHASE'),
    'ATM_INTERNAL': ScenarioPolicy('Luân chuyển nội bộ', 'Đối chiếu, không ghi trùng', code='TRANSFER_NOT_EXPENSE'),
    'PAYROLL_ADVANCE': ScenarioPolicy('Chi tạm ứng lương', 'Chờ người duyệt', 'OUT', 'READY_FOR_OWNER', note='NOT_FINAL_PAYROLL'),
    'BANK_FEE': ScenarioPolicy('Chi phí ngân hàng', 'Chờ người duyệt', 'OUT', 'READY_FOR_OWNER', True),
    'AMOUNT_DIFFERENCE': ScenarioPolicy('Chênh lệch cần giải trình', 'Cần bổ sung', code='AMOUNT_MISMATCH'),
    'UNKNOWN_PROJECT': ScenarioPolicy('Chi chưa phân bổ', 'Cần bổ sung', code='UNKNOWN_PROJECT'),
    'CANCELLED': ScenarioPolicy('Không phát sinh dòng tiền', 'Không ghi sổ', code='CANCELLED_TRANSFER'),
    'DUP_RECEIPTS': ScenarioPolicy('Giao dịch trùng nguồn', 'Chờ đối chiếu trùng', code='DUPLICATE_RECEIPT_IMAGES'),
    'EMPLOYEE_PAID': ScenarioPolicy('Công nợ nhân viên; chưa chi tiền công ty', 'Theo dõi công nợ', code='EMPLOYEE_OWN_MONEY'),
    'CONTRACTOR_ADVANCE': ScenarioPolicy('Chi tạm ứng đội khoán', 'Chờ người duyệt', 'OUT', 'READY_FOR_OWNER', note='CONTRACTOR_ADVANCE_NOT_COST'),
}

STAGING_COLUMNS = [
    'Trạng thái duyệt', 'Ngày', 'Số chứng từ', 'Nội dung thu/chi',
    'Tên công trình', 'Người chi', 'Người nhận', 'Hình thức',
    'Thu (VND)', 'Chi (VND)', 'Ghi chú từ Zalo / lưu ý kế toán',
    'Nguồn / nhóm Zalo', 'Bill / chứng từ', 'Kiểm tra tự động',
    'Phản hồi người phụ trách', 'Ngày đã chuyển',
]
RECON_COLUMNS = [
    'Ngày', 'Mã chứng từ', 'Biến động', 'Số tiền (VND)',
    'Tài khoản / người nhận', 'Trạng thái', 'Nội dung cần đối chiếu',
    'Ảnh chứng từ',
]

class CasebookError(ValueError):
    pass

def require(ok: bool, message: str) -> None:
    if not ok:
        raise CasebookError(message)


def evaluate_case(row: dict, identity: dict) -> dict:
    """No `expected_*` field is read to compute output: it is only used by tests."""
    case_id = row.get('id')
    require(isinstance(case_id, str) and re.fullmatch(r'TC[0-9]{2,3}', case_id), 'BAD_CASE_ID')
    scenario = row.get('type')
    require(scenario in POLICIES, 'UNKNOWN_SCENARIO_REQUIRES_HUMAN_CLASSIFICATION')
    policy = POLICIES[scenario]
    amount = row.get('amount')
    require(type(amount) is int and 0 < amount <= 10**12, 'BAD_AMOUNT')
    doc = row.get('document')
    require(isinstance(doc, str) and re.fullmatch(r'[A-Z0-9-]{3,50}', doc), 'BAD_DOC_ID')
    when = row.get('date')
    require(isinstance(when, str), 'BAD_DATE')
    try:
        parsed_date = date.fromisoformat(when)
    except ValueError as ex:
        raise CasebookError('BAD_DATE') from ex
    require(parsed_date.isoformat() == when and when[:7] == identity['period'], 'WRONG_PERIOD')
    project = row.get('project')
    require(project is None or (isinstance(project, str) and re.fullmatch(r'DEMO-PROJECT-[A-Z]', project)), 'BAD_PROJECT')
    if project is None:
        require(scenario == 'UNKNOWN_PROJECT', 'PROJECT_REQUIRED')
    else:
        require(scenario != 'UNKNOWN_PROJECT', 'UNKNOWN_PROJECT_MUST_BE_UNRESOLVED')
    existing = row.get('already_recorded')
    require(type(existing) is bool, 'BAD_EXISTING_LEDGER_FLAG')
    if existing:
        require(scenario == 'ALREADY_POSTED', 'CONFLICTING_LEDGER_DUPLICATE')
    elif scenario == 'ALREADY_POSTED':
        raise CasebookError('MISSING_EXISTING_LEDGER_FLAG')

    cash_in = amount if policy.movement == 'IN' else 0
    cash_out = amount if policy.movement == 'OUT' else 0
    # Expense candidate is INTERNAL tracking only, not MISA/IRR or VAT eligible.
    cost_internal = amount if policy.internal_cost_candidate else 0
    state = 'READY_FOR_OWNER' if policy.code == 'READY_FOR_OWNER' else 'NEEDS_REVIEW'
    result = {
        'CASE_ID': case_id,
        'LEGAL_ENTITY_ID': identity['legal_entity_id'],
        'BOOK_ID': identity['book_id'],
        'PERIOD': identity['period'],
        'PROJECT_ID': project,
        'SOURCE_DOC_ID': doc,
        'SCENARIO_TYPE': scenario,
        'SOURCE_AMOUNT_VND': amount,
        'CLASSIFICATION': policy.classification,
        'STATUS_LABEL': policy.expected_status,
        'REVIEW_STATE': state,
        'REASON_CODE': policy.code,
        'PROPOSED_IN_VND': cash_in,
        'PROPOSED_OUT_VND': cash_out,
        'INTERNAL_COST_CANDIDATE_VND': cost_internal,
        'CAVEAT': policy.note,
        'APPROVAL_STATUS': 'UNAPPROVED',
        'DESTINATION_WRITE_ALLOWED': False,
        'LIVE_AUTHORIZED': False,
        'SOURCE_EVIDENCE_VALIDATED': False,
    }
    require(not (cash_in and cash_out), 'BOTH_IN_AND_OUT')
    return result


def evaluate_casebook(data: dict) -> dict:
    require(isinstance(data, dict), 'INVALID_FIXTURE')
    require(data.get('data_class') == 'SYNTHETIC_ONLY', 'NON_SYNTHETIC_FORBIDDEN')
    ident = {'legal_entity_id': data.get('legal_entity_id'), 'book_id': data.get('book_id'), 'period': data.get('period')}
    require(ident == {'legal_entity_id':'DEMO_A', 'book_id':DEMO_BOOK, 'period':'2026-11'}, 'WRONG_BOOK_SCOPE')
    rows = data.get('cases')
    require(isinstance(rows, list) and 1 <= len(rows) <= 100, 'INVALID_CASE_COUNT')
    case_ids = set()
    doc_ids = set()
    results = []
    for row in rows:
        require(isinstance(row, dict), 'INVALID_CASE_ROW')
        evaluated = evaluate_case(row, ident)
        case_id, doc_id = evaluated['CASE_ID'], evaluated['SOURCE_DOC_ID']
        require(case_id not in case_ids, 'DUPLICATE_CASE_ID')
        require(doc_id not in doc_ids, 'DUPLICATE_SOURCE_DOC_ID')
        case_ids.add(case_id)
        doc_ids.add(doc_id)
        results.append(evaluated)
    # Under no circumstances is the status Chờ người duyệt proof of an approval.
    return {
        'SCHEMA_VERSION': VERSION,
        'DATA_CLASS': 'SYNTHETIC_ONLY',
        'BUSINESS_EXPECTATIONS_APPROVED': False,
        'APPROVAL_STATUS': 'UNAPPROVED',
        'DESTINATION_WRITE_ALLOWED': False,
        'LIVE_AUTHORIZED': False,
        **{k.upper():v for k,v in ident.items()},
        'RESULTS': results,
        'COUNTS': {
            'CASES': len(results),
            'READY_FOR_OWNER': sum(r['REVIEW_STATE']=='READY_FOR_OWNER' for r in results),
            'NEEDS_REVIEW': sum(r['REVIEW_STATE']=='NEEDS_REVIEW' for r in results),
            'PROPOSED_IN_VND': sum(r['PROPOSED_IN_VND'] for r in results),
            'PROPOSED_OUT_VND': sum(r['PROPOSED_OUT_VND'] for r in results),
        },
    }


def rows_for_stagging(data: dict, result: dict) -> list[dict]:
    lookup = {r['CASE_ID']:r for r in result['RESULTS']}
    rows=[]
    for source in data['cases']:
        r=lookup[source['id']]
        ready=r['REVIEW_STATE']=='READY_FOR_OWNER'
        rows.append(dict(zip(STAGING_COLUMNS, [
            'Chờ kiểm tra' if ready else 'Cần bổ sung',
            source['date'], source['document'], source['description'],
            r['PROJECT_ID'] or 'Chưa xác định',
            '', '', '',  # Not available in synthetic 20-case source; do not invent parties or payment method.
            r['PROPOSED_IN_VND'] if ready and r['PROPOSED_IN_VND'] else '',
            r['PROPOSED_OUT_VND'] if ready and r['PROPOSED_OUT_VND'] else '',
            f"DEMO: {r['CLASSIFICATION']}; {r['CAVEAT'] or r['REASON_CODE']}",
            '20 ca DEMO, chưa xác minh chứng từ',
            '', # No actual bill or transfer is attached to this scenario workbook.
            f"{r['STATUS_LABEL']} / {r['REASON_CODE']} / CẦN NGƯỜI DUYỆT",
            '', '',
        ])))
    return rows


def rows_for_reconciliation(data: dict, result: dict) -> list[dict]:
    lookup={r['CASE_ID']:r for r in result['RESULTS']}
    return [dict(zip(RECON_COLUMNS,[
        c['date'],c['document'],c['description'],c['amount'],'',
        lookup[c['id']]['STATUS_LABEL'],
        f"{lookup[c['id']]['REASON_CODE']} / {lookup[c['id']]['CLASSIFICATION']} / CHƯA DUYỆT",
        ''
    ])) for c in data['cases'] if lookup[c['id']]['REVIEW_STATE']=='NEEDS_REVIEW']


def deterministic_json(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode('utf-8')


def encode_csv(rows:list[dict], columns:list[str]) -> bytes:
    stream=io.StringIO(newline='')
    writer=csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


def safe_publish(out_dir: Path, payloads: dict[str,bytes]) -> str:
    allowed_root = Path(__file__).resolve().parent / '_output'
    require(out_dir.parent.resolve() == allowed_root.resolve(), 'OUTPUT_NOT_IN_DEMO_OUTPUT_ROOT')
    allowed_root.mkdir(parents=True, exist_ok=True)
    require(not out_dir.is_symlink(), 'OUTPUT_SYMLINK')
    if out_dir.exists():
        require(out_dir.is_dir(), 'OUTPUT_NOT_DIRECTORY')
        require(set(p.name for p in out_dir.iterdir())==set(payloads), 'OUTPUT_FILE_SET_CHANGED')
        for name,blob in payloads.items():
            p=out_dir/name
            require(p.is_file() and not p.is_symlink() and p.read_bytes()==blob, 'OUTPUT_ALREADY_CHANGED')
        return 'ALREADY_PREPARED'
    # Export is always an unapproved DEMO artifact, never a writer to a ledger.
    out_dir.mkdir(parents=False,exist_ok=False)
    for name,blob in payloads.items():
        with (out_dir/name).open('xb') as stream:
            stream.write(blob)
    return 'PREPARED_FOR_REVIEW'


def main():
    cli=argparse.ArgumentParser(description='20 synthetic cases -> unapproved staging/reconciliation CSV.')
    cli.add_argument('--fixture',type=Path,default=Path(__file__).with_name('cases20_demo.json'))
    cli.add_argument('--output-dir',type=Path,required=True)
    args=cli.parse_args()
    root=Path(__file__).resolve().parent
    fix=args.fixture.resolve(strict=True)
    require(fix==root/'cases20_demo.json', 'FIXTURE_OUTSIDE_DEMO')
    out=args.output_dir.absolute()
    require(out.parent.resolve() == (root / '_output').resolve(), 'OUTPUT_NOT_IN_DEMO_OUTPUT_ROOT')
    data=json.loads(fix.read_text(encoding='utf-8'))
    result=evaluate_casebook(data)
    payloads={
        'casebook_review.json':deterministic_json(result),
        'stagging_draft.csv':encode_csv(rows_for_stagging(data,result),STAGING_COLUMNS),
        'doi_chieu_draft.csv':encode_csv(rows_for_reconciliation(data,result),RECON_COLUMNS),
    }
    status=safe_publish(out,payloads)
    print(json.dumps({'status':status,'counts':result['COUNTS'],'destination_write_allowed':False},ensure_ascii=False))
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except (CasebookError,ValueError,KeyError,TypeError,OSError) as ex:
        print(json.dumps({'status':'BLOCKED','reason':str(ex) if isinstance(ex,CasebookError) else 'INVALID_DEMO_INPUT'},ensure_ascii=False))
        sys.exit(2)
