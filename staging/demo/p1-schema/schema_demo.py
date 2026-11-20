"""P1 schema rule simulator: synthetic metadata only, never grants access or writes ledgers."""
import calendar
import hashlib
import json
import re
from datetime import date, datetime

VERSION = "P1-DEMO-1"
STAGES = {"DEMO", "PILOT_READ", "PRE_WRITE"}
SCOPE = ("LEGAL_ENTITY_ID", "BRANCH_ID", "BOOK_ID", "PERIOD")
BRANCH_MISSING = object()


def branch(value):
    if value is None or value == "NA":
        return None
    if isinstance(value, str) and value and value.strip() == value:
        return value
    return BRANCH_MISSING


def nonempty(value):
    return isinstance(value, str) and bool(value) and value.strip() == value


def scope_errors(item, expected, prefix):
    errors = []
    if not isinstance(item, dict):
        return [prefix + "_MISSING"]
    for key in SCOPE:
        if key not in item:
            errors.append(prefix + "_MISSING_" + key)
        elif key == "BRANCH_ID":
            if branch(item[key]) is BRANCH_MISSING or branch(item[key]) != branch(expected[key]):
                errors.append(prefix + "_MISMATCH_" + key)
        elif item[key] != expected[key]:
            errors.append(prefix + "_MISMATCH_" + key)
    return errors


def validate(document, stage):
    errors = []
    if not isinstance(stage, str) or stage not in STAGES:
        return {"status": "BLOCKED", "errors": ["INVALID_STAGE"], "live_authorized": False}
    if not isinstance(document, dict):
        return {"status": "BLOCKED", "errors": ["INVALID_DOCUMENT"], "live_authorized": False}
    if document.get("CONFIG_VERSION") != VERSION:
        errors.append("INVALID_CONFIG_VERSION")
    if document.get("DATA_CLASS") != "SYNTHETIC_ONLY":
        errors.append("NON_SYNTHETIC_DATA")
    if not isinstance(document.get("SOURCE_PRESENT"), bool):
        errors.append("INVALID_SOURCE_PRESENT")
    if not isinstance(document.get("DESTINATION_WRITE"), bool):
        errors.append("INVALID_DESTINATION_WRITE")
    elif stage in ("DEMO", "PILOT_READ") and document["DESTINATION_WRITE"]:
        errors.append("DESTINATION_WRITE_NOT_ALLOWED")
    elif stage == "PRE_WRITE" and not document["DESTINATION_WRITE"]:
        errors.append("WRITE_INTENT_REQUIRED_FOR_SIMULATION")
    book = document.get("BOOK") if isinstance(document.get("BOOK"), dict) else {}
    project = document.get("PROJECT") if isinstance(document.get("PROJECT"), dict) else {}
    job = document.get("JOB") if isinstance(document.get("JOB"), dict) else {}
    for name, item in (("BOOK", book), ("PROJECT", project), ("JOB", job)):
        if item.get("CONFIG_VERSION") != VERSION:
            errors.append(name + "_INVALID_CONFIG_VERSION")
        for key in SCOPE:
            if key not in item or (key != "BRANCH_ID" and not nonempty(item.get(key))) or (key == "BRANCH_ID" and branch(item.get(key)) is BRANCH_MISSING):
                errors.append(name + "_MISSING_OR_INVALID_" + key)
    for name, item in (("PROJECT", project), ("JOB", job)):
        if not nonempty(item.get("PROJECT_ID")):
            errors.append(name + "_MISSING_PROJECT_ID")
    if not isinstance(book.get("BOOK_KIND"), str) or book.get("BOOK_KIND") not in {"ACCOUNTING", "MISA_LEDGER", "MANAGEMENT", "CASH_LOG", "MATERIAL"}:
        errors.append("INVALID_BOOK_KIND")
    if not re.fullmatch(r"DEMO_[A-Z0-9]+", str(book.get("LEGAL_ENTITY_ID", ""))) or not re.fullmatch(r"DEMO-[A-Z0-9-]+", str(book.get("BOOK_ID", ""))):
        errors.append("NON_DEMO_SCOPE")
    if not re.fullmatch(r"DEMO-[A-Z0-9-]+", str(project.get("PROJECT_ID", ""))):
        errors.append("NON_DEMO_PROJECT")
    for key in ("FISCAL_YEAR", "SOURCE_REF", "OWNER", "LAST_SNAPSHOT"):
        if key not in book:
            errors.append("BOOK_MISSING_FIELD_" + key)
    if all(key in book for key in SCOPE):
        errors.extend(scope_errors(project, book, "PROJECT"))
        errors.extend(scope_errors(job, book, "JOB"))
    if project.get("PROJECT_ID") != job.get("PROJECT_ID"):
        errors.append("JOB_MISMATCH_PROJECT_ID")
    period = book.get("PERIOD", "")
    try:
        if not isinstance(period, str) or not re.fullmatch(r"\d{4}-\d{2}", period):
            raise ValueError
        year, month = map(int, period.split("-"))
        start_period, end_period = date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    except (ValueError, OverflowError):
        errors.append("INVALID_PERIOD")
        start_period = end_period = None
    fiscal = book.get("FISCAL_YEAR")
    if fiscal is None:
        if stage != "DEMO" and book.get("BOOK_KIND") in ("ACCOUNTING", "MISA_LEDGER"):
            errors.append("MISSING_FISCAL_YEAR")
    elif not isinstance(fiscal, dict) or not nonempty(fiscal.get("ID")):
        errors.append("INVALID_FISCAL_YEAR")
    else:
        try:
            if not all(isinstance(fiscal.get(k), str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", fiscal[k]) for k in ("START", "END")):
                raise ValueError
            start, end = date.fromisoformat(fiscal["START"]), date.fromisoformat(fiscal["END"])
            if start > end or (start_period and not (start <= start_period <= end_period <= end)):
                raise ValueError
        except (TypeError, ValueError):
            errors.append("INVALID_FISCAL_PERIOD")
        if stage != "DEMO" and (not re.fullmatch(r"DEMO-[A-Z0-9-]+", str(fiscal.get("CONFIRMED_BY", ""))) or not isinstance(document.get("DEMO_OWNER_DIRECTORY"), list) or fiscal.get("CONFIRMED_BY") not in document["DEMO_OWNER_DIRECTORY"]):
            errors.append("FISCAL_CONFIRMATION_MISSING")
    if stage != "DEMO" and document.get("SOURCE_PRESENT") is not True:
        errors.append("SOURCE_REQUIRED_FOR_READ_OR_WRITE_SIMULATION")
    source = book.get("SOURCE_REF")
    if source is None:
        if document.get("SOURCE_PRESENT") is True:
            errors.append("MISSING_SOURCE_REF")
    elif not isinstance(source, dict) or not re.fullmatch(r"SYNREF:[A-Z0-9-]+", str(source.get("ID", ""))):
        errors.append("INVALID_SOURCE_REF")
    elif all(key in book for key in SCOPE):
        errors.extend(scope_errors(source, book, "SOURCE_REF"))
        if source.get("PROJECT_ID") != project.get("PROJECT_ID") or not nonempty(source.get("PROJECT_ID")):
            errors.append("SOURCE_REF_MISMATCH_PROJECT_ID")
    owner = book.get("OWNER")
    directory = document.get("DEMO_OWNER_DIRECTORY")
    if owner is None:
        if stage != "DEMO":
            errors.append("MISSING_OWNER")
    elif not isinstance(owner, dict) or owner.get("KIND") != "DEMO_ROLE" or not isinstance(directory, list) or owner.get("ID") not in directory or not re.fullmatch(r"DEMO-[A-Z0-9-]+", str(owner.get("ID", ""))):
        errors.append("INVALID_DEMO_OWNER")
    snapshot = book.get("LAST_SNAPSHOT")
    if snapshot is None:
        if stage == "PRE_WRITE":
            errors.append("MISSING_DESTINATION_BACKUP")
    elif not isinstance(snapshot, dict):
        errors.append("INVALID_DESTINATION_BACKUP")
    else:
        if all(key in book for key in SCOPE):
            errors.extend(scope_errors(snapshot, book, "BACKUP"))
        if snapshot.get("PROJECT_ID") != project.get("PROJECT_ID") or not nonempty(snapshot.get("PROJECT_ID")):
            errors.append("BACKUP_MISMATCH_PROJECT_ID")
        if (snapshot.get("KIND") != "DEMO_DESTINATION_BACKUP" or not re.fullmatch(r"DEMO-[A-Z0-9-]+", str(snapshot.get("ID", ""))) or
                not re.fullmatch(r"[a-f0-9]{64}", str(snapshot.get("SHA256", ""))) or
                snapshot.get("RESTORE_TEST") != "SIMULATED_PASS" or
                not re.fullmatch(r"DEMO-[A-Z0-9-]+", str(snapshot.get("RESTORE_TEST_ID", ""))) or
                not re.fullmatch(r"DEMO-[A-Z0-9-]+", str(snapshot.get("DESTINATION_VERSION", ""))) or
                not re.fullmatch(r"DEMO-[A-Z0-9-]+", str(snapshot.get("PROTECTED_LOCATION_ID", ""))) or
                not re.fullmatch(r"DEMO-[A-Z0-9-]+", str(snapshot.get("RESPONSIBLE_OWNER", ""))) or
                not isinstance(directory, list) or snapshot.get("RESPONSIBLE_OWNER") not in directory):
            errors.append("INVALID_DESTINATION_BACKUP")
        try:
            captured = datetime.fromisoformat(snapshot.get("CAPTURED_AT", ""))
            if captured.tzinfo is None or captured.utcoffset() is None:
                raise ValueError
        except (TypeError, ValueError):
            errors.append("INVALID_BACKUP_TIMESTAMP")
    return {"status": "BLOCKED" if errors else "READY_FOR_" + stage + "_SIMULATION",
            "errors": sorted(set(errors)), "live_authorized": False}


def checkpoint(document, stage):
    result = validate(document, stage)
    if result["status"] == "BLOCKED":
        return result
    data = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return {"CONFIG_VERSION": VERSION, "stage": stage, "fingerprint": hashlib.sha256(data).hexdigest(),
            "status": result["status"], "live_authorized": False}


def resume(document, stage, old):
    current = checkpoint(document, stage)
    if current["status"] == "BLOCKED":
        return current
    if not isinstance(old, dict) or old.get("CONFIG_VERSION") != VERSION:
        return {"status": "BLOCKED", "errors": ["INCOMPATIBLE_CHECKPOINT_VERSION"], "live_authorized": False}
    if old.get("stage") != stage or old.get("fingerprint") != current["fingerprint"] or old.get("status") != current["status"] or old.get("live_authorized") is not False:
        return {"status": "BLOCKED", "errors": ["CHECKPOINT_CHANGED"], "live_authorized": False}
    return current
