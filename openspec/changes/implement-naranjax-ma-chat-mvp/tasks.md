# Tasks: Implement Guarded Naranja X MA Chat MVP

## Review Workload Forecast

| Unit | Boundary | Forecast |
|---|---|---:|
| PR4A | adapter/output contract | 300–360 |
| PR4B | service/evidence lifecycle | 330–390 |
| PR4C | CLI/catalog promotion/E2E | 220–300 |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

Delivery is stacked-to-main, in order, with no exception; every slice hard-stops at 399 changed lines including tests and hybrid evidence. The former combined PR4 (685 lines; 7 focused/70 cumulative) and its 7.1–7.3 GREEN claims are superseded non-credit. Status is truthfully 27/27 complete.

## Completed foundation: 18 tasks

- [x] 1.1–1.3 PR1A — contracts/models.
- [x] 2.1–2.3 PR1B — inert catalog.
- [x] 3.1–3.3 PR2A — file manager.
- [x] 4.1–4.3 PR2B-A — run metadata/locks.
- [x] 5.1–5.3 PR2B-B — state promotion/recovery.
- [x] 6.1–6.3 PR3 — process/log evidence.

## PR4A — Adapter/output contract

- [x] 7.1 RED — In `tests/adapters/naranjax/test_ma_chat.py`, freshly fail exact `sys.executable back-base/ejecutar_dia.py --fecha YYYYMMDD --mes YYYYMM --input …` plus five sandbox-dir flags, optional inputs/`--chat`, adapter-boundary host date, and empty isolated no-PLANES behavior.
- [x] 7.2 GREEN — Implement only `adapters/{__init__.py,naranjax/__init__.py,naranjax/ma_chat.py}`; classify exact success and missing, unchanged, wrong-date, ambiguous/duplicate outputs before promotion.
- [x] 7.3 REFACTOR — Table-drive every ROMAN/CHAT/E1KIA classification; run focused then cumulative and static checks; budget ≤360.

Focused: `python -m pytest tests/adapters/naranjax/test_ma_chat.py -q`. Cumulative: `python -m pytest tests/orchestrator tests/adapters/naranjax/test_ma_chat.py -q`. Depends: PR3 merged to `main`. Rollback: revert PR4A; catalog remains inert.

## PR4B — Service/evidence lifecycle

- [x] 8.1 RED — Add `tests/orchestrator/test_service.py` and `tests/support/synthetic_naranjax.py`; freshly fail terminal `run.json` for date/snapshot/lock/process/postcondition/promotion outcomes, including ambiguity no-promotion.
- [x] 8.2 GREEN — Implement only `orchestrator/service.py`; inject adapter/runner/store/state/file-manager/log persister/clock, create evidence before adapter preflight, and persist input hashes, lifecycle/timestamps, redacted relative process/log/legacy-log evidence, postconditions, blockers, and lineage on every terminal path.
- [x] 8.3 REFACTOR — Centralize terminalization/redaction and prove secrets/host paths never persist; no CLI or catalog promotion; focused+cumulative/static green; budget ≤390.

Focused: `python -m pytest tests/orchestrator/test_service.py -q`. Cumulative: `python -m pytest tests/orchestrator tests/adapters/naranjax/test_ma_chat.py -q`. Depends: PR4A merged to `main`. Rollback: revert PR4B; adapter stays unreachable.

## PR4C — CLI/catalog promotion/E2E

- [x] 9.1 RED — In `tests/orchestrator/test_catalog.py` and `tests/e2e/test_naranjax_ma_chat.py`, freshly fail Chat-only executability, thin CLI help/exit mapping, and synthetic success plus rejection evidence with unchanged canonical state.
- [x] 9.2 GREEN — Modify only `orchestrator/run.py` and `registry/naranjax.yaml`; wire injected service, promote only Chat, and keep Voice/PCT/MT inert.
- [x] 9.3 REFACTOR — Keep CLI translation-only; run focused, `python -m pytest tests -q`, static/diff/scope audits; budget ≤300.

Focused: `python -m pytest tests/orchestrator/test_catalog.py tests/e2e/test_naranjax_ma_chat.py -q`. Depends: PR4B merged to `main`. Rollback: revert PR4C readiness/wiring; no executable catalog entry remains.
