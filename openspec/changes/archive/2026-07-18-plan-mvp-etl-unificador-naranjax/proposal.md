# Proposal: Plan Naranja X ETL Unifier MVP

## Intent

Produce the planning baseline for a safe Naranja X ETL Unifier MVP. This change creates SDD artifacts and `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md`; it does **not** implement a runner, refactor legacy ETLs, or alter business rules.

## Scope

### In Scope
- Record verified inventory and Chat/MA Voice/MT diagnosis, including MA PCT (1 failed, 26 passed) and MT back-results (1 failed, 6 passed) contract failures.
- Propose `registry/naranjax.yaml` schema: identity/readiness, paths/command/arguments, inputs, output patterns/date source, state scope, retry policy, exit codes, timeout, environment, and postconditions.
- Design subprocess execution, metadata/log capture, output diffing, per-run sandbox, and durable monthly state.
- Specify pilot `naranjax.ma.chat.daily` over `SOHO-Chat-NX_MA-ETL/back-base/ejecutar_dia.py --chat` with legacy contracts and guardrails.
- Define implementation phases, acceptance criteria, risks, and open decisions.

### Out of Scope
- Functional code, stubs, API/UI, legacy changes, data/build artifacts, and MA Voice/PCT/MT adapters.

## Capabilities

### New Capabilities
- `naranjax-unifier-mvp-planning`: Plan for catalog, runner/sandbox architecture, and guarded Chat pilot.

### Modified Capabilities
- None; no main specs exist.

## Approach

Plan four phases: (1) contracts/catalog; (2) run store, staging, sandbox; (3) subprocess runner and evidence; (4) Chat adapter with end-to-end tests/docs. The pilot isolates mutable paths, keeps durable state outside runs, locks by ETL/month, preflights immutable same-date snapshots, and inventories outputs before/after execution. It reports `business_date` separately from machine-derived `artifact_date`. Missing PLANES requires an empty isolated daily directory because `--sin_planes_hoy` does not disable discovery. Chat and Voice retain separate argument policies, especially PAGOS handling.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md` | New | Planning deliverable |
| `openspec/changes/plan-mvp-etl-unificador-naranjax/` | New | SDD planning artifacts |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Machine-date outputs; non-transactional partial writes | High | Explicit limitation, filesystem evidence, failed-run preservation |
| Same-date retry and concurrent monthly state mutation | High | Preflight policy and ETL/month lock |
| PLANES auto-discovery; Chat/Voice drift | High | Isolated inputs and adapter-specific contracts |
| Existing PCT/MT failures obscure readiness | Med | Catalog as blocked; exclude from pilot |

## Open Decisions

Business-date restriction; state lineage ownership; retry semantics; PLANES omission meaning; timeout/lock scope; whether PCT failures block only their adapters.

## Rollback Plan

Remove only this change’s planning artifacts and plan document; legacy code and runtime state remain untouched.

## Dependencies

- Authoritative root objective/planning documents and verified exploration evidence.

## Success Criteria

- [ ] Plan covers inventory, diagnoses, schema, architecture, pilot contract, phases, acceptance, risks, and decisions with evidence.
- [ ] Plan preserves exact legacy behavior and marks unresolved choices without assumptions.
- [ ] No functional or legacy ETL code is changed.
