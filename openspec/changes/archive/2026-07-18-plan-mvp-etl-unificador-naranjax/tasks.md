# Tasks: Plan Naranja X ETL Unifier MVP

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | Current plan: 250–400; future MVP: 1,600–2,300 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes, for future functional work |
| Suggested split | Planning PR → contracts → sandbox/state → process → Chat pilot |
| Delivery strategy | ask-on-risk, resolved by maintainer approval of chained PRs |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

The decision gates functional apply; this change remains planning-only.

## Suggested Work Units

| Unit | Goal / dependency | Verification | Rollback boundary |
|---|---|---|---|
| 0 (current) | Publish evidence-backed plan; depends on approved spec/design | Markdown review and planning-only diff | Remove plan/change artifacts only |
| 1 (future) | Contracts/catalog; depends on product decisions | Catalog path-scoped tests | Revert registry/models/tests |
| 2 (future) | Sandbox, run evidence, state; depends on Unit 1 | Store/file-manager tests | Revert store/sandbox slice |
| 3 (future) | Subprocess/log capture; depends on Unit 2 | Runner/logging tests | Revert execution slice |
| 4 (future) | Chat adapter/CLI; depends on Units 1–3 | Synthetic Chat E2E | Revert pilot slice |

## Phase 0: Current Planning Deliverable

- [x] 0.1 Create `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md` from the approved evidence: inventory/diagnoses, exact Chat contract, schema, architecture, four phases, acceptance, risks, and open decisions.
- [x] 0.2 Review every factual/readiness claim against cited paths or command results; retain MA PCT `1 failed, 26 passed`, MT back-results `1 failed, 6 passed`, and explicit unknowns.
- [x] 0.3 Verify target-file whitespace/content directly and review `git status --short --untracked-files=all`; confirm no code, real data, or generated artifacts.

## Phase 1: Future Contracts/Catalog (Unit 1)

- [ ] 1.1 RED: add `tests/orchestrator/test_catalog.py` cases for schema, duplicate IDs, readiness, and absolute/escaping paths; run `python -m pytest tests/orchestrator/test_catalog.py -q`.
- [ ] 1.2 GREEN/REFACTOR: add `registry/naranjax.yaml`, `orchestrator/models.py`, and catalog service; keep Voice/PCT/MT non-executable and rerun the scoped test.

## Phase 2: Future Sandbox/State (Unit 2)

- [ ] 2.1 RED: add scoped `run_store`/`file_manager` tests for containment, atomic metadata, diffing, lock collision, snapshot rejection, and unchanged canonical state on failure.
- [ ] 2.2 GREEN/REFACTOR: implement `run_store.py` and `file_manager.py`; run `python -m pytest tests/orchestrator/test_run_store.py tests/orchestrator/test_file_manager.py -q`.

## Phase 3: Future Process Evidence (Unit 3)

- [ ] 3.1 RED: add runner tests for exit codes, timeout terminate/kill, concurrent streams, redaction, and partial-file preservation.
- [ ] 3.2 GREEN/REFACTOR: implement `runner.py` and `logging_utils.py`; run `python -m pytest tests/orchestrator/test_runner.py tests/orchestrator/test_logging_utils.py -q`.

## Phase 4: Future Chat Pilot (Unit 4)

- [ ] 4.1 RED: add synthetic E2E cases for arguments, omitted PLANES isolation, ROMAN/CHAT/E1KIA postconditions, missing output, and snapshot collision.
- [ ] 4.2 GREEN/REFACTOR: implement `adapters/naranjax/ma_chat.py` and thin CLI, update the plan beside behavior, then run only the new adapter/E2E test paths.

## Explicit Exclusions

Current work excludes functional stubs, API/UI, legacy edits, MA Voice/PCT/MT adapters, arbitrary historical dates, shared manual lineage, real data, and build artifacts. Future units require separate approval and a resolved chain strategy.
