# G3 remediation R1 — synthetic DEMO_A cash pipeline

Status: **CODE FIXED AND TESTED LOCALLY, G3 INDEPENDENT SIGN-OFF PENDING**.
Scope: only offline synthetic DEMO; never real MISA/Sheets/Zalo or bank data.

## Findings received 21 Nov 2026

| Finding | Change | Local proof | Status |
|---|---|---|---|
| P0: check_m3_output checked amount but not amount_out or settled_cost | Recompute those fields from immutable source evidence, distinguishing cash PAYMENT/ADVANCE from settled-cost SETTLEMENT; reject tampering separately | test_tampered_amount_out_detected_independently; test_tampered_settled_cost_detected_independently | FIXED IN DEMO |
| P1: structured PAYMENT+BILL yielded READY_FOR_OWNER with no media/payee/payment reference check | Preserve READY_FOR_OWNER **only as a candidate for a human to check**, attach EVIDENCE_CHECKS_REQUIRED and fail-closed verified flags; prevent DEMO_APPROVE unless source media, payee and payment reference have explicitly passed verification | test_explicit_demo_approval_only_of_ready_transaction (blocks); test_verified_flag_alone_does_not_authorize_live_posting (pure synthetic unit) | GUARDED; ACTUAL SOURCE CHECK NOT IMPLEMENTED |
| P1: audit stored one immutable result and could not append corrections | Append-only version directories v0001, v0002, with previous JSON hash, new timestamp, mandatory change reason, previous decision state, scope and audit CSV | test_append_only_two_versions_with_change_reason, test_revision_conflict_and_missing_reason_block, test_tampered_historical_event_blocks_future_version | FIXED IN DEMO |
| P1: LegacyRegressionTest bypass based on folder name | Removed switch from normal workflow.ps1. Regression harness moved to separate workflow_regression_test_only.ps1, restricted to named synthetic test fixtures. CLI adds CmdletBinding to reject unknown parameters | test_regression_switch_cannot_bypass_real_snapshot, test_m3_direct_without_seal_is_blocked and test_workflow.ps1 | FIXED IN MAIN DEMO ENTRY; TEST-ONLY FILE MUST NOT SHIP LIVE |
| P2: 20 curated cases are separate from raw structured evidence or images | Keep 20-case suite as independent fixture only; no fabricated claim that raw media or 20 unlabelled business cases were verified | test_case20_engine.py versus test_cash_review_flow.py | OPEN (NON-BLOCKING TO CURRENT DEMO PATCH; G3 STILL OPEN) |

## Money semantics

- M3 **amount** is the transaction's source face value.
- M3 **amount_out** is the actual DEMO cash movement from one PAYMENT or ADVANCE, never counted again for a duplicate source.
- M3 **settled_cost** is DEMO SETTLEMENT expense, **not** a BILL amount or suggested cost candidate.
- The cash review proposal field PROPOSED_SETTLED_COST_DEMO can be a *candidate* after matching BILL+PAYMENT; it is not a verified M3 settled_cost event or ledger posting.
- Do not combine any of these values into a real financial or tax record without independently verified source, reviewer identity and scoped authorization.

## Safety limits

A matching amount is not proof that the bill image is genuine, that the payee
matches the bank transaction, or that the transaction context is valid.
Current source contains structured synthetic CSV, **not** original images
or independently verified bank records. The report sets BUSINESS_APPROVAL_ELIGIBLE,
SOURCE_MEDIA_VERIFIED, PAYEE_VERIFIED and PAYMENT_REFERENCE_VERIFIED to false.
READY_FOR_OWNER is NOT approval. The mock reviewer ID is NOT authenticated.

Audit version directories preserve previous files and detect accidental tampering
or inconsistency. A user with full filesystem rights could rewrite an entire
unsigned hash chain; this is **not** external immutability, a certified journal,
or live authorization. Migrating a pre-existing single-file legacy audit
requires a separate explicit plan; the system fails closed rather than deleting
or silently upgrading those files.

The separate workflow_regression_test_only.ps1 is a **test harness** for the
synthetic workflow-test-* fixtures. It must never be included in a real-system
deployment or imported by production code. The primary workflow.ps1 has no
unsealed bypass parameter.

## G3 gates still outstanding

- [ ] Independent reviewer examines the new diff and runs the relevant tests.
- [ ] Business owner validates R01-R10 and expected outcomes; current 20-case spreadsheet is a proposal, not accepted accounting policy.
- [ ] Represent and verify 20 unlabelled structured scenarios as a separate scope without falsely treating missing media as verified.
- [ ] Real reviewer login/authorization, tamper-evident independent audit store, source-media/bank verification, and external writer all require separate architecture and G0-LIVE/G4/G5/G6 approvals.

**Do not merge PRs #1–#4 or this stacked PR as LIVE_READY. No live writes are allowed.**
