# Proposal: Implement Naranja X MA Voice PCT

## Intent

Promote `naranjax.ma.voice.pct` through the verified unifier platform as its
first stateless job. Provide an isolated PCT adapter, a stateless run contract
in the service, catalog promotion, and synthetic evidence — without touching
legacy code or claiming production/UAT acceptance.

## Scope

### In Scope
- Invoke `soho-naranjaX-MA-etl/back-resultados/etl_tipificaciones_ia_voz_pct.py`
  with active Python, an explicitly staged `--input` CSV, and a sandbox
  `--output_dir` — never allowing the legacy `roman/` autodetection.
- Declare the adapter stateless: the service skips state preflight, staging,
  and promotion while keeping the ETL/month lock, sandbox, diff, and evidence.
- Stage the required input under a destination that preserves its validated
  suffix (`input/base.csv`).
- Add the `pct` artifact role; require exactly one new or changed today-dated
  `NARANJAX_PCT_*.csv` before success.
- Reject PLANES, PAGOS, and no-PLANES intent: PCT has no such inputs.
- Promote the catalog entry and wire CLI adapter selection; add synthetic E2E.
- Deliver one autonomous stacked-to-main PR below 400 changed lines.

### Out of Scope
- Legacy/product edits, historical dates, real data, secrets, builds, API/UI.
- MT Voice execution; MA daily production acceptance (UAT remains pending).
- Retry semantics beyond lock fail-fast (stateless runs have no snapshot gate).

## Capabilities

### New Capabilities
- `stateless-run-contract`: the service executes catalog jobs that own no
  monthly state, with unchanged evidence, locking, and postcondition guarantees.

### Modified Capabilities
- `naranjax-ma-chat-daily`: extend the guarded catalog/CLI contract to promote
  PCT while preserving Chat/Voice behavior and keeping MT inert.

## Approach

Add a thin `MaVoicePctAdapter` that owns the exact PCT command and stateless
validation, reusing the shared today-gate and role-driven output classification
from `MaChatAdapter`. Teach `RunService` one flag — `adapter.stateful` — to skip
the three state interactions; teach `_stage_inputs` to derive the staged suffix
from the validated source. Everything else (staging, runner, evidence,
redaction, locking, timeout) is reused unchanged.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `adapters/naranjax/ma_voice_pct.py` | New | PCT command, stateless guards |
| `orchestrator/models.py` | Modified | `ArtifactRole.PCT` |
| `orchestrator/service.py` | Modified | Stateless skip; suffix-preserving staging |
| `orchestrator/run.py` | Modified | Register PCT adapter |
| `registry/naranjax.yaml` | Modified | Promote PCT with complete metadata |
| `tests/adapters/naranjax/test_ma_voice_pct.py` | New | Command, guards, postconditions |
| `tests/e2e/test_naranjax_ma_voice_pct.py` | New | Synthetic lifecycle evidence |
| `tests/orchestrator/test_catalog.py`, `test_service.py` | Modified | Promotion and stateless contracts |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Stateless skip weakens daily state guarantees | Low | Flag defaults to stateful; regression tests pin Chat/Voice promotion |
| Legacy autodetection of residual roman/ inputs | Med | `--input` always passed with staged path |
| Machine/request dates diverge | Med | Shared today-only gate; output date pinned to today |
| Staged suffix change breaks daily staging | Low | Suffix derives from validated extension; Chat/Voice specs only allow `.xlsx` |

## Rollback Plan

Revert the single PR: adapter, role, stateless branch, staging suffix, catalog
promotion, and tests travel together. Failed sandboxes and evidence remain.

## Dependencies

- Current verified catalog, service, runner, file/state stores, locks, and
  evidence model; `MaChatAdapter` classification.
- Green PCT contract suite (27 passed) after PR #36. No new dependency.

## Success Criteria

- [ ] Focused adapter, catalog, service, and synthetic PCT E2E tests pass with
      generated fixtures only; Chat/Voice regressions stay green.
- [ ] Exact PCT command always passes staged `--input` and sandbox
      `--output_dir`; PLANES/PAGOS/no-PLANES intents are blocked.
- [ ] Success requires exactly one changed today-dated `NARANJAX_PCT_*.csv`;
      no state lineage is created or touched by PCT runs.
- [ ] MT remains non-executable; status is implementation-ready only.
