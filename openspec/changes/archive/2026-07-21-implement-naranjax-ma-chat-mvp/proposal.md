# Proposal: Implement Guarded Naranja X MA Chat MVP

## Intent

Deliver a today-only, auditable `naranjax.ma.chat.daily` runner without changing legacy code or business rules. The pilot must reject unsafe execution before state mutation and preserve evidence for every terminal outcome.

## Scope

### In Scope
- Root contracts/catalog, isolated run/state services, subprocess evidence, and Chat adapter/CLI.
- Host-local-today gate; unifier-owned canonical lineage; snapshot preflight rejection; fail-fast ETL/month locks.
- Snapshot-before-current promotion, blocking lineage after partial promotion; explicit no-PLANES isolation.
- 900s timeout plus 10s terminate grace; exactly one new/changed ROMAN, CHAT, and E1KIA output.

### Out of Scope
- API/UI; MA Voice/PCT/MT execution; legacy edits; historical dates; real data, secrets, or builds.

## Capabilities

### New Capabilities
- `naranjax-ma-chat-daily`: Guarded catalog-to-CLI execution, evidence, state, and recovery contract for the Chat daily pilot.

### Modified Capabilities
- None. The existing planning capability remains the approved baseline.

## Approach

Use root Python packages and invoke the legacy daily entry point through `sys.executable`. Keep all four catalog entries non-executable through PR3; PR4 alone assigns the Chat adapter and enables Chat. Generate CSV/XLSX fixtures dynamically under `tmp_path`.

| Stacked slice | Dependency and finish | Focused tests | Rollback |
|---|---|---|---|
| PR1 contracts/catalog | Approved PR0 planning branch; typed contracts and four inert entries | catalog schema, IDs, readiness, paths | Revert root declaration, contracts, catalog, tests |
| PR2 sandbox/state | PR1; sandbox, evidence inventory, lock, seed, collision preflight, guarded promotion | containment, hashes/diff, collision, locks, partial-promotion block | Revert store/file manager; catalog stays inert |
| PR3 process evidence | PR2; concurrent streams, exits, logs, timeout, partial evidence | generated jobs: success, nonzero, interleaving, partial, timeout | Revert runner/logging; prior slices stay inert |
| PR4 Chat adapter/CLI | PR3; adapter, service, CLI, synthetic E2E, Chat executable | args, no-PLANES, three outputs, missing/ambiguous output, collision | Revert wiring/readiness; no executable entry remains |

Each PR targets its predecessor while open, then retargets `main`; target 300–380 changed lines and split before 400.

## Affected Areas

`pyproject.toml`, `registry/`, `orchestrator/`, `adapters/naranjax/`, `tests/`, and planning-document verification status.

## Risks

- Promotion is not a multi-file transaction; snapshot success/current failure requires manual blocked-lineage recovery.
- Locks may survive crashes; never auto-break them. Timeout controls only the verified parent-process contract.
- PR4 has the highest line-budget risk; split rather than grant an implicit exception.

## Dependencies

- PR0 planning (`docs/plan-mvp-etl-unificador-naranjax`, commit `ea03ce8`) must be approved/merged before PR1 reaches `main`.

## Success Criteria

- [ ] Unsafe date, snapshot, lock, PLANES, process, output, or promotion states fail closed with evidence.
- [ ] Only Chat is executable after PR4; focused path-scoped tests pass with synthetic data.
- [ ] No legacy, real-data, secret, or build artifact changes.
