"""P1 synthetic source-manifest validator.

No network, credentials, MISA, Sheets, live access, or destination writer.
PILOT_READ here is ONLY a schema-validation simulation, never an authorization.
"""

import argparse
import calendar
import copy
import csv
import hashlib
import io
import json
import os
import re
import stat
import sys
import tempfile
import unicodedata
from datetime import date, datetime
from pathlib import Path

from importlib.util import module_from_spec, spec_from_file_location

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / 'p1-schema' / 'schema_demo.py'
_spec = spec_from_file_location('p1_schema_demo_for_manifest', _SCHEMA_PATH)
_schema = module_from_spec(_spec)
_spec.loader.exec_module(_schema)

MANIFEST_VERSION = 'P1-MANIFEST-1'
CONFIG_VERSION = 'P1-DEMO-1'
SOURCE_SCHEMA_VERSION = 'SYN-CSV-1'
MARKER = '.SYNTHETIC_ONLY_P1'
MARKER_TEXT = 'P1 SYNTHETIC FIXTURE ONLY - NO LIVE DATA\n'
ALLOWED_SOURCE_SYSTEM = 'SYNTHETIC_CSV'
MAX_FILES = 100
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 50 * 1024 * 1024
MAX_ROWS = 10_000
ILLEGAL_WINDOWS_CHARS = set('<>:"|?*')
TOP_KEYS = {
    'MANIFEST_VERSION', 'CONFIG_VERSION', 'SCHEMA_VERSION', 'DATA_CLASS',
    'SOURCE_SNAPSHOT_ID', 'LEGAL_ENTITY_ID', 'BRANCH_ID', 'BOOK_ID',
    'PROJECT_ID', 'PERIOD', 'PERIOD_START', 'PERIOD_END', 'SOURCE_SYSTEM',
    'SOURCE_REF', 'EXPORT_TIMESTAMP', 'EXPORTED_BY', 'VERIFIED_BY',
    'VERIFICATION_STATUS', 'CONFIG_FINGERPRINT', 'FILE_COUNT', 'ROW_COUNT', 'FILES',
}
FILE_KEYS = {'FILE_ID', 'REL_PATH', 'SIZE_BYTES', 'SHA256', 'ROW_COUNT', 'CONTENT_TYPE'}
SEAL_KEYS = {'MANIFEST_VERSION', 'SOURCE_SNAPSHOT_ID', 'MANIFEST_SHA256', 'LIVE_AUTHORIZED'}
CHECKPOINT_KEYS = {
    'TICKET', 'CONFIG_VERSION', 'MANIFEST_VERSION', 'STAGE', 'BOOK_ID',
    'SOURCE_SNAPSHOT_ID', 'MANIFEST_SHA256', 'CONFIG_FINGERPRINT',
    'STATUS', 'LIVE_AUTHORIZED',
}


class ManifestError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def require(condition, code):
    if not condition:
        raise ManifestError(code)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha_obj(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def validate_token(value, pattern, code):
    require(isinstance(value, str) and re.fullmatch(pattern, value) is not None, code)
    return value


def validate_timestamp(value):
    require(isinstance(value, str), 'INVALID_EXPORT_TIMESTAMP')
    try:
        dt = datetime.fromisoformat(value)
        require(dt.tzinfo is not None and dt.utcoffset() is not None, 'INVALID_EXPORT_TIMESTAMP')
    except ValueError as ex:
        raise ManifestError('INVALID_EXPORT_TIMESTAMP') from ex
    return value


def canonical_branch(v):
    require(v is None or (isinstance(v, str) and v != ''), 'INVALID_BRANCH')
    return 'NA' if v is None or v == 'NA' else v


def secure_name(name):
    require(isinstance(name, str) and bool(name), 'INVALID_SOURCE_PATH')
    require(name == unicodedata.normalize('NFC', name), 'NON_CANONICAL_SOURCE_PATH')
    require(not name.startswith('/') and not name.endswith('/') and '\\' not in name and '\x00' not in name, 'INVALID_SOURCE_PATH')
    parts = name.split('/')
    require(all(part not in ('', '.', '..') for part in parts), 'SOURCE_PATH_TRAVERSAL')
    for part in parts:
        require(not (part.startswith('.') or part.endswith(' ') or part.endswith('.')), 'INVALID_WINDOWS_SOURCE_PATH')
        require(not any(ch in ILLEGAL_WINDOWS_CHARS or ord(ch) < 32 for ch in part), 'INVALID_WINDOWS_SOURCE_PATH')
        base = part.split('.')[0].upper()
        require(base not in {'CON','PRN','AUX','NUL'} and not re.fullmatch(r'(COM|LPT)[1-9]', base), 'RESERVED_WINDOWS_SOURCE_PATH')
    require(name.endswith('.csv'), 'UNSUPPORTED_SOURCE_TYPE')
    return name


def is_regular_no_links(root, relative):
    path = root
    for part in relative.split('/'):
        path = path / part
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError as ex:
            raise ManifestError('MISSING_SOURCE_FILE') from ex
        require(not stat.S_ISLNK(mode), 'SOURCE_SYMLINK_FORBIDDEN')
    require(stat.S_ISREG(mode), 'NOT_REGULAR_SOURCE_FILE')
    return path


def validate_root(root):
    root = Path(root)
    require(root.is_dir() and not any(parent.is_symlink() for parent in (root, *root.parents)), 'INVALID_SOURCE_ROOT')
    marker = root / MARKER
    require(marker.is_file() and not marker.is_symlink(), 'SYNTHETIC_ROOT_MARKER_MISSING')
    require(marker.read_text(encoding='utf-8') == MARKER_TEXT, 'INVALID_SYNTHETIC_ROOT_MARKER')
    return root


def inventory(root):
    """List all source files, including unexpected files, without following links."""
    root = validate_root(root)
    discovered = []
    for current, dirs, files in os.walk(root, followlinks=False):
        current = Path(current)
        for dirname in dirs:
            require(not (current / dirname).is_symlink(), 'SOURCE_SYMLINK_FORBIDDEN')
        for filename in files:
            p = current / filename
            rel = p.relative_to(root).as_posix()
            if rel == MARKER:
                continue
            require(not p.is_symlink(), 'SOURCE_SYMLINK_FORBIDDEN')
            require(p.is_file(), 'NOT_REGULAR_SOURCE_FILE')
            secure_name(rel)
            discovered.append(rel)
    require(len(discovered) <= MAX_FILES, 'TOO_MANY_SOURCE_FILES')
    require(len({x.casefold() for x in discovered}) == len(discovered), 'DUPLICATE_SOURCE_PATH')
    return sorted(discovered, key=lambda p: (p.casefold(), p))


def file_info(root, name, expected=None):
    name = secure_name(name)
    path = is_regular_no_links(root, name)
    before = path.stat()
    require(before.st_size <= MAX_FILE_BYTES, 'SOURCE_FILE_TOO_LARGE')
    require(before.st_size > 0, 'EMPTY_SOURCE_FILE')
    # O_NOFOLLOW prevents replacement by a symlink at the final component on Unix.
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags)
    except OSError as ex:
        raise ManifestError('SOURCE_FILE_NOT_OPENABLE') from ex
    try:
        first = os.fstat(fd)
        require(stat.S_ISREG(first.st_mode), 'NOT_REGULAR_SOURCE_FILE')
        require((first.st_dev, first.st_ino, first.st_size) == (before.st_dev, before.st_ino, before.st_size), 'SOURCE_CHANGED_DURING_READ')
        with os.fdopen(fd, 'rb') as fh:
            fd = -1
            contents = fh.read(MAX_FILE_BYTES + 1)
    finally:
        if fd != -1:
            os.close(fd)
    require(len(contents) <= MAX_FILE_BYTES, 'SOURCE_FILE_TOO_LARGE')
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'SOURCE_CHANGED_DURING_READ')
    require(len(contents) == after.st_size, 'SOURCE_CHANGED_DURING_READ')
    digest = hashlib.sha256(contents).hexdigest()
    try:
        text = contents.decode('utf-8-sig', errors='strict')
        lines = list(csv.reader(io.StringIO(text, newline=''), strict=True))
    except (UnicodeError, csv.Error) as ex:
        raise ManifestError('INVALID_SOURCE_CSV') from ex
    require(bool(lines) and bool(lines[0]) and all(col and col.strip() == col for col in lines[0]), 'CSV_HEADER_REQUIRED')
    require(len(set(lines[0])) == len(lines[0]), 'CSV_DUPLICATE_HEADER')
    require(all(len(row) == len(lines[0]) for row in lines[1:]), 'CSV_ROW_WIDTH_MISMATCH')
    require(len(lines)-1 <= MAX_ROWS, 'TOO_MANY_CSV_ROWS')
    # If a synthetic CSV declares scope columns, validate EACH row, not only its
    # metadata. Otherwise a correctly labeled manifest could hide B rows in A.
    if expected is not None:
        declared = {'LEGAL_ENTITY_ID', 'BRANCH_ID', 'BOOK_ID', 'PROJECT_ID', 'PERIOD'}
        indexed = {key: lines[0].index(key) for key in declared if key in lines[0]}
        for row in lines[1:]:
            for key, index in indexed.items():
                value = row[index]
                if key == 'BRANCH_ID':
                    value = canonical_branch(value)
                require(value == expected[key], 'SOURCE_ROW_SCOPE_MISMATCH')
    return {'REL_PATH': name, 'SIZE_BYTES': len(contents), 'SHA256': digest,
            'ROW_COUNT': len(lines) - 1, 'CONTENT_TYPE': 'text/csv'}


def validate_document(doc):
    require(isinstance(doc, dict) and doc.get('DATA_CLASS') == 'SYNTHETIC_ONLY', 'NON_SYNTHETIC_DOCUMENT')
    require(doc.get('SOURCE_PRESENT') is True and doc.get('DESTINATION_WRITE') is False, 'READ_ONLY_SOURCE_REQUIRED')
    result = _schema.validate(doc, 'PILOT_READ')
    require(result['status'] == 'READY_FOR_PILOT_READ_SIMULATION', 'P1_SCHEMA_BLOCKED')
    return doc


def expected_scope(doc):
    book = doc['BOOK']; project = doc['PROJECT']
    period = book['PERIOD']
    y, m = map(int, period.split('-'))
    return {
        'LEGAL_ENTITY_ID':book['LEGAL_ENTITY_ID'], 'BRANCH_ID':canonical_branch(book['BRANCH_ID']),
        'BOOK_ID':book['BOOK_ID'], 'PROJECT_ID':project['PROJECT_ID'], 'PERIOD':period,
        'PERIOD_START':date(y, m, 1).isoformat(),
        'PERIOD_END':date(y, m, calendar.monthrange(y,m)[1]).isoformat(),
        'SOURCE_REF':book['SOURCE_REF']['ID'],
        'CONFIG_FINGERPRINT':sha_obj(doc),
    }


def validate_owners(doc, exported_by, verified_by):
    owners = doc['DEMO_OWNER_DIRECTORY']
    validate_token(exported_by, r'DEMO-[A-Z0-9-]+', 'INVALID_EXPORTED_BY')
    validate_token(verified_by, r'DEMO-[A-Z0-9-]+', 'INVALID_VERIFIED_BY')
    require(exported_by in owners and verified_by in owners and exported_by != verified_by,
            'INVALID_SIMULATED_VERIFIER')
    require(exported_by == doc['BOOK']['OWNER']['ID'], 'EXPORTED_BY_NOT_BOOK_OWNER')


def build_manifest(source_root, doc, snapshot_id, exported_at, exported_by, verified_by, files=None):
    """Build a canonical manifest from synthetic files; no artifact is written."""
    validate_document(doc)
    validate_timestamp(exported_at)
    validate_owners(doc, exported_by, verified_by)
    validate_token(snapshot_id, r'SYN_[A-Z0-9_]+', 'INVALID_SOURCE_SNAPSHOT_ID')
    require(doc['JOB'].get('SOURCE_SNAPSHOT_ID') == snapshot_id, 'SOURCE_SNAPSHOT_JOB_MISMATCH')
    root = validate_root(source_root)
    discovered = inventory(root)
    if files is None:
        requested = discovered
    else:
        require(isinstance(files, list), 'INVALID_FILE_LIST')
        requested = [secure_name(x) for x in files]
        require(len({x.casefold() for x in requested}) == len(requested), 'DUPLICATE_SOURCE_PATH')
        require(set(requested) == set(discovered), 'SOURCE_FILE_SET_CHANGED')
        requested.sort(key=lambda p: (p.casefold(), p))
    require(bool(requested), 'SOURCE_FILES_REQUIRED')
    scope = expected_scope(doc)
    file_rows = []
    total_bytes = 0
    for index, file_name in enumerate(requested, 1):
        row = file_info(root, file_name, expected=scope)
        total_bytes += row['SIZE_BYTES']
        require(total_bytes <= MAX_TOTAL_BYTES, 'SOURCE_SET_TOO_LARGE')
        row['FILE_ID'] = f'F{index:04d}'
        file_rows.append(row)
    return {
        'MANIFEST_VERSION': MANIFEST_VERSION, 'CONFIG_VERSION': CONFIG_VERSION,
        'SCHEMA_VERSION': SOURCE_SCHEMA_VERSION, 'DATA_CLASS': 'SYNTHETIC_ONLY',
        'SOURCE_SNAPSHOT_ID':snapshot_id, **scope,
        'SOURCE_SYSTEM':ALLOWED_SOURCE_SYSTEM, 'EXPORT_TIMESTAMP':exported_at,
        'EXPORTED_BY':exported_by, 'VERIFIED_BY':verified_by,
        'VERIFICATION_STATUS':'SIMULATED_HASHED_ONLY', 'FILE_COUNT':len(file_rows),
        'ROW_COUNT':sum(row['ROW_COUNT'] for row in file_rows), 'FILES':file_rows,
    }


def make_seal(manifest):
    require(isinstance(manifest, dict), 'INVALID_MANIFEST')
    return {'MANIFEST_VERSION': MANIFEST_VERSION,
            'SOURCE_SNAPSHOT_ID':manifest['SOURCE_SNAPSHOT_ID'],
            'MANIFEST_SHA256':sha_obj(manifest), 'LIVE_AUTHORIZED':False}


def ticket_id(doc):
    return 'P1-MANIFEST-' + doc['BOOK']['LEGAL_ENTITY_ID'].removeprefix('DEMO_') + '-002'


def make_checkpoint(manifest, doc):
    return {
        'TICKET': ticket_id(doc), 'CONFIG_VERSION':CONFIG_VERSION,
        'MANIFEST_VERSION':MANIFEST_VERSION, 'STAGE':'SIMULATED_PILOT_READ',
        'BOOK_ID':manifest['BOOK_ID'], 'SOURCE_SNAPSHOT_ID':manifest['SOURCE_SNAPSHOT_ID'],
        'MANIFEST_SHA256':sha_obj(manifest),
        'CONFIG_FINGERPRINT':sha_obj(doc), 'STATUS':'VERIFIED_SYNTHETIC_ONLY',
        'LIVE_AUTHORIZED':False,
    }


def verify_manifest(source_root, doc, manifest, seal, old_checkpoint=None):
    """Fail closed on any manifest, source-file, config, or checkpoint change."""
    try:
        validate_document(doc)
        require(isinstance(manifest, dict) and set(manifest) == TOP_KEYS, 'INVALID_MANIFEST_FIELDS')
        require(manifest['MANIFEST_VERSION'] == MANIFEST_VERSION and
                manifest['CONFIG_VERSION'] == CONFIG_VERSION and
                manifest['SCHEMA_VERSION'] == SOURCE_SCHEMA_VERSION, 'MANIFEST_VERSION_MISMATCH')
        require(manifest['DATA_CLASS'] == 'SYNTHETIC_ONLY' and
                manifest['SOURCE_SYSTEM'] == ALLOWED_SOURCE_SYSTEM and
                manifest['VERIFICATION_STATUS'] == 'SIMULATED_HASHED_ONLY', 'INVALID_MANIFEST_SCOPE')
        validate_token(manifest['SOURCE_SNAPSHOT_ID'], r'SYN_[A-Z0-9_]+', 'INVALID_SOURCE_SNAPSHOT_ID')
        require(manifest['SOURCE_SNAPSHOT_ID'] == doc['JOB'].get('SOURCE_SNAPSHOT_ID'), 'SOURCE_SNAPSHOT_JOB_MISMATCH')
        validate_timestamp(manifest['EXPORT_TIMESTAMP'])
        for k,v in expected_scope(doc).items():
            require(manifest[k] == v, 'MANIFEST_MISMATCH_' + k)
        validate_owners(doc, manifest['EXPORTED_BY'], manifest['VERIFIED_BY'])
        require(isinstance(manifest['FILES'], list) and bool(manifest['FILES']), 'SOURCE_FILES_REQUIRED')
        require(isinstance(manifest['FILE_COUNT'], int) and not isinstance(manifest['FILE_COUNT'],bool) and
                manifest['FILE_COUNT'] == len(manifest['FILES']) and manifest['FILE_COUNT'] <= MAX_FILES,
                'MANIFEST_FILE_COUNT_MISMATCH')
        root = validate_root(source_root)
        names = []
        actual_rows = []
        for i,record in enumerate(manifest['FILES'], 1):
            require(isinstance(record, dict) and set(record) == FILE_KEYS, 'INVALID_MANIFEST_FILE_FIELDS')
            name = secure_name(record['REL_PATH']); names.append(name)
            require(record['FILE_ID'] == f'F{i:04d}', 'INVALID_FILE_ID_OR_ORDER')
            require(isinstance(record['ROW_COUNT'], int) and not isinstance(record['ROW_COUNT'], bool) and
                    isinstance(record['SIZE_BYTES'],int) and not isinstance(record['SIZE_BYTES'],bool), 'INVALID_FILE_NUMBERS')
            actual = file_info(root, name, expected=expected_scope(doc))
            require(all(record[k] == actual[k] for k in actual), 'SOURCE_FILE_CHANGED')
            actual_rows.append(actual)
        require(len({x.casefold() for x in names}) == len(names), 'DUPLICATE_SOURCE_PATH')
        require(names == sorted(names, key=lambda p:(p.casefold(),p)), 'INVALID_FILE_ID_OR_ORDER')
        require(set(names) == set(inventory(root)), 'SOURCE_FILE_SET_CHANGED')
        require(isinstance(manifest['ROW_COUNT'],int) and not isinstance(manifest['ROW_COUNT'],bool) and
                manifest['ROW_COUNT'] == sum(x['ROW_COUNT'] for x in actual_rows), 'MANIFEST_ROW_COUNT_MISMATCH')
        require(isinstance(seal, dict) and set(seal) == SEAL_KEYS, 'INVALID_MANIFEST_SEAL')
        require(seal['MANIFEST_VERSION'] == MANIFEST_VERSION and
                seal['SOURCE_SNAPSHOT_ID'] == manifest['SOURCE_SNAPSHOT_ID'] and
                seal['LIVE_AUTHORIZED'] is False and seal['MANIFEST_SHA256'] == sha_obj(manifest),
                'MANIFEST_SEAL_MISMATCH')
        current = make_checkpoint(manifest, doc)
        if old_checkpoint is not None:
            require(isinstance(old_checkpoint,dict) and set(old_checkpoint) == CHECKPOINT_KEYS and
                    old_checkpoint == current, 'CHECKPOINT_CHANGED_OR_LEGACY')
        return {'status':'VERIFIED_SYNTHETIC_ONLY','live_authorized':False,
                'errors':[],'file_count':manifest['FILE_COUNT'],
                'row_count':manifest['ROW_COUNT'], 'checkpoint':current}
    except (ManifestError, KeyError, TypeError, ValueError, OverflowError) as ex:
        err = ex.code if isinstance(ex,ManifestError) else 'INVALID_MANIFEST_DATA'
        return {'status':'BLOCKED','live_authorized':False,'errors':[err]}


def cli():
    p = argparse.ArgumentParser(description='P1 synthetic-only source manifest; never authorizes live.')
    p.add_argument('command', choices=['create','verify'])
    p.add_argument('--document', required=True, type=Path)
    p.add_argument('--source-root', required=True, type=Path)
    p.add_argument('--output-dir', required=True, type=Path)
    p.add_argument('--source-snapshot-id', default='SYN_A_001')
    p.add_argument('--export-time', default='2026-11-21T01:00:00+07:00')
    p.add_argument('--exported-by', default='DEMO-OWNER-A')
    p.add_argument('--verified-by', default='DEMO-REVIEWER-A')
    args=p.parse_args()
    # The demo CLI cannot be redirected to arbitrary machine paths.
    stage_root = Path(__file__).resolve().parent.parent
    require(args.source_root.resolve().is_relative_to(stage_root), 'SOURCE_OUTSIDE_DEMO_STAGING')
    require(args.document.resolve().is_relative_to(stage_root), 'DOCUMENT_OUTSIDE_DEMO_STAGING')
    require(args.output_dir.resolve().is_relative_to(stage_root), 'OUTPUT_OUTSIDE_DEMO_STAGING')
    require(not args.output_dir.resolve().is_relative_to(args.source_root.resolve()), 'OUTPUT_INSIDE_SOURCE')
    doc = json.loads(args.document.read_text(encoding='utf-8'))
    checkpoint_file = ticket_id(doc) + '.json'
    if args.command=='create':
        manifest=build_manifest(args.source_root, doc, args.source_snapshot_id,
            args.export_time, args.exported_by, args.verified_by)
        seal=make_seal(manifest)
        cp=make_checkpoint(manifest,doc)
        result=verify_manifest(args.source_root,doc,manifest,seal,cp)
        require(result['status']=='VERIFIED_SYNTHETIC_ONLY','MANIFEST_PREWRITE_VERIFICATION_FAILED')
        require(not args.output_dir.exists(), 'OUTPUT_ALREADY_EXISTS')
        # Assemble inside a temporary sibling and publish the folder as one rename.
        args.output_dir.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='.p1-manifest-tmp-',dir=args.output_dir.parent) as tmp:
            for name, obj in [('source_manifest.json',manifest),('source_seal.json',seal),(checkpoint_file,cp)]:
                (Path(tmp)/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            require(not args.output_dir.exists(), 'OUTPUT_ALREADY_EXISTS')
            os.rename(tmp, args.output_dir)
    else:
        root=args.output_dir
        manifest=json.loads((root/'source_manifest.json').read_text(encoding='utf-8'))
        seal=json.loads((root/'source_seal.json').read_text(encoding='utf-8'))
        cp=json.loads((root/checkpoint_file).read_text(encoding='utf-8'))
        result=verify_manifest(args.source_root,doc,manifest,seal,cp)
    print(json.dumps({k:v for k,v in result.items() if k!='checkpoint'},ensure_ascii=False))
    return 0 if result['status'] == 'VERIFIED_SYNTHETIC_ONLY' else 2


if __name__ == '__main__':
    try:
        sys.exit(cli())
    except (ManifestError, OSError, ValueError, KeyError) as ex:
        print(json.dumps({'status':'BLOCKED','errors':[ex.code if isinstance(ex,ManifestError) else 'CLI_INPUT_INVALID']},ensure_ascii=False))
        sys.exit(2)
