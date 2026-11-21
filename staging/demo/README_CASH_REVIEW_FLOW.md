# P0-P1 integrated DEMO: P1 -> M3 -> evidence-derived review

Scope: SYNTHETIC_ONLY, offline, no OCR, no API, no ledger write.
This workflow does not use the curated scenario labels of the separate
20-case regression workbook. Instead, it reads the exact evidence.csv bytes
from the scoped P1 snapshot processed by PowerShell M3.

Run on Windows (from repo root):

    python staging/demo/cash_review_flow.py --book DEMO-A-CASH-2026
    python staging/demo/cash_review_flow.py --book DEMO-B-MISA-2026
    python staging/demo/cash_review_flow.py --book DEMO-A-CASH-2026

First run prepares a synthetic snapshot if missing, seals files with P1,
validates P1, executes M3 on exactly those inputs, re-verifies P1, checks
checkpoint transaction identifiers and amounts against structured source,
then creates three REVIEW-ONLY files under the book's ignored
_p1_m3/<BOOK_ID>/cash-review directory:

- review_proposals.json
- stagging_draft.csv (16 original column positions; no approval)
- doi_chieu_draft.csv (8 original column positions)

Repeated runs return ALREADY_PREPARED, not another transaction or ledger write.
Modified source, manifest, checkpoint or output fails closed, per-book. There
is no external storage, Google Sheets, MISA, Zalo or image extraction.
Source media is explicitly NOT verified; any proposed amount is a demo draft.

Example results with synthetic fixture A: 6 evidence records, 4 transactions,
2 READY_FOR_OWNER, 2 NEEDS_REVIEW. In A1, a repeated payment image remains a
separate RECORD_ID but is not counted twice. The ADVANCE is cash-out only,
not settled cost; standalone settlement needs a verified advance link.
Book B: one payment lacking bill -> NEEDS_REVIEW.

## P0 direct workflow entry gate

workflow.ps1 now requires a valid P1 sealed snapshot for EVERY normal
execution path, including calls after -Library loading. It runs P1 verify
before processing. If P1 is missing or source is modified, it blocks.

- LegacyRegressionTest switch is restricted to named workflow-test-* demo
  fixtures under staging/demo. Its only purpose is regression tests.
- Calling the bare M3 CLI on unsealed data now fails; it is NOT equivalent
  to the verified path.
- A test-only bypass is not security isolation. Do not use staging as a
  protection boundary for real accounting data.

The 20-case fixture and this raw-evidence workflow have separate inputs. They
are both useful tests but are not yet a single 20-case raw-image dataset.
No business reviewer has approved R01-R10; G3 independent QA is not passed.

## Tests

    python staging/demo/test_cash_review_flow.py
    powershell -NoProfile -ExecutionPolicy Bypass -File staging/demo/test_workflow.ps1

The former tests scope isolation, source tampering, P1 enforcement, retry,
review-only export and checkpoint integrity. Real credentials, recording,
payments, tax and authorization remain out of scope.
