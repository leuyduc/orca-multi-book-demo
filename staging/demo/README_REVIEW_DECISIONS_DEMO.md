# P3 — Review-decision simulation ONLY (no real authentication or ledger write)

This demo follows the sealed P1 -> M3 -> review pipeline. There is NO Google
OAuth identity, bank/MISA/Sheets integration, authentic approval credential,
payment, tax filing, online API or live writer.

Windows commands, from repo root:

1. Build review output for synthetic book A:

    python staging/demo/cash_review_flow.py --book DEMO-A-CASH-2026

2. Generate decision-request.json for a mock human review:

    python staging/demo/review_decisions_demo.py template --book DEMO-A-CASH-2026

3. Optionally edit the existing private DEMO file
   staging/demo/_p1_m3/DEMO-A-CASH-2026/decision-request.json.
   Each transaction has an ACTION from DEMO_APPROVE, DEMO_REJECT,
   DEMO_REQUEST_MORE, plus NOTE and EXPECTED_REVIEW_STATE.
   By default ALL decisions request more: no automatic approvals.

4. Record a SIMULATED reviewer decision, without posting:

    python staging/demo/review_decisions_demo.py apply --book DEMO-A-CASH-2026

This creates an immutable review-decisions directory (JSON + CSV audit)
in the ignored synthetic snapshot. The original review_proposals.json does
not change. No action can set DESTINATION_WRITE_ALLOWED true.

Fail-closed checks: correct synthetic reviewer ID and book scope, P1 manifest
and report SHA256, exact transaction set, timezone, version, valid review state,
and explicit human-edited decision. APPROVE is rejected for NEEDS_REVIEW.
Tampered source/report/audit and wrong-book reviewer IDs are blocked.

The REVIEWER_ID is just a synthetic fixture label, NOT verified identity.
DEMO_APPROVED_ONLY is not legal, tax or financial approval. Passing all
tests does not authorize the source of real documents or any live write.
Independent G3 remains pending. The 20-case scenario regression is separate
from the M3 evidence.csv pipeline, which uses structured rows, not OCR.

Tests:

    python staging/demo/test_review_decisions_demo.py

For a second book, replace the --book argument with DEMO-B-MISA-2026.
