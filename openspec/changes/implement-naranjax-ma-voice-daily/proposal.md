# Proposal: Implement Naranja X MA Voice Daily

## Intent

Promote `naranjax.ma.voice.daily` through the verified unifier platform without rewriting legacy code. Provide an isolated Voice adapter, catalog-selected CLI execution, and synthetic evidence while explicitly withholding production/UAT acceptance.

## Scope

### In Scope
- Invoke `soho-naranjaX-MA-etl/back-base/ejecutar_dia.py` with active Python, `--fecha`, derived `--mes`, sandbox paths, and only supplied PLANES/PAGOS arguments.
- Enforce host-local today, explicit unified no-PLANES intent without nonexistent Voice `--sin_planes_hoy`, and an isolated daily directory preventing residual PLANES/PAGOS discovery.
- Require exactly one new or changed today-dated ROMAN and E1KIA plus staged current state before promotion; wire adapter selection from catalog and add synthetic CLI E2E.
- Deliver two autonomous stacked-to-main PRs, each below 400 changed lines: adapter plus inert catalog contract; then CLI wiring, promotion, and E2E.

### Out of Scope
- Legacy/product edits, historical dates, real data, secrets, builds, API/UI, or root-wide/legacy execution.
- PCT execution or promotion; MA Chat production acceptance (UAT remains pending).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `naranjax-ma-chat-daily`: extend the guarded MA daily contract to promote Voice while preserving Chat behavior and keeping PCT/MT inert.

## Approach

Add a thin `MaVoiceAdapter` that composes existing Chat today/no-PLANES validation and role-driven output classification, but owns the exact Voice command. Reuse unchanged `RunRequest`, staging, runner, evidence/redaction, locking, state lineage, timeout, and guarded promotion. Select adapters by `definition.adapter`; promote Voice only after synthetic path-scoped tests pass.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `adapters/naranjax/ma_voice.py` | New | Voice command and guards |
| `registry/naranjax.yaml` | Modified | Complete/promote Voice; PCT inert |
| `orchestrator/run.py` | Modified | Catalog-driven adapter selection |
| `tests/adapters/naranjax/test_ma_voice.py` | New | Exact command, isolation, postconditions |
| `tests/e2e/test_naranjax_ma_voice.py`, `tests/support/synthetic_naranjax.py` | Modified | Synthetic lifecycle evidence |
| `tests/orchestrator/test_catalog.py` | Modified | Promotion/inertness contract |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Machine/request dates diverge | Med | Today-only gate; derive month |
| Residual daily files influence Voice | Med | Run-local staged-only directory |
| Exit 0 leaves partial outputs/state | Med | Diff both outputs and state before promotion |
| Shared Chat coupling regresses behavior | Low | Focused Chat/service regression tests |

## Rollback Plan

Revert PR 2 to disable Voice promotion/CLI selection, then PR 1 to remove adapter metadata. Preserve failed sandboxes/evidence; do not roll back or overwrite canonical state automatically.

## Dependencies

- Current verified catalog, service, runner, file/state stores, locks, evidence model, `MaChatAdapter` guards, and 900-second timeout.
- Allowlisted `NARANJAX_PLANES_MIN_COVERAGE`; no new dependency.

## Success Criteria

- [ ] Focused adapter, catalog, service, Chat-regression, and synthetic Voice E2E tests pass with generated fixtures only.
- [ ] Exact Voice command has no `--sin_planes_hoy`; omitted PLANES/PAGOS cannot discover residue.
- [ ] Promotion requires exactly one changed today-dated ROMAN and E1KIA plus state; PCT remains non-executable.
- [ ] Status is implementation-ready only: no production run or UAT claim.
