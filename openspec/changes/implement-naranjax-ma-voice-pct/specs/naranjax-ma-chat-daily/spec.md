# Delta for Naranja X MA Chat Daily

## ADDED Requirements

### Requirement: PCT request and invocation contract

PCT MUST accept only host-local today and invoke active Python with
`back-resultados/etl_tipificaciones_ia_voz_pct.py`, an explicitly staged
`--input` CSV, and a sandbox `--output_dir`. It MUST reject PLANES, PAGOS, and
no-PLANES intent, and MUST NOT allow the legacy `roman/` input autodetection.

#### Scenario: Exact PCT command
- GIVEN today's PCT request with a staged historial CSV
- WHEN the command is prepared
- THEN it exactly matches the declared interpreter, entry point, staged input, and sandbox output directory

#### Scenario: Daily-only intents are rejected
- GIVEN a PCT request carrying PLANES, PAGOS, or no-PLANES intent
- WHEN validation runs
- THEN it is evidenced and rejected before lock or subprocess mutation

#### Scenario: Non-today request
- GIVEN a PCT date different from host-local today
- WHEN execution is requested
- THEN it is evidenced and rejected before lock or subprocess mutation

### Requirement: Stateless run contract

A stateless adapter MUST declare itself so, and the service MUST then skip
state preflight, current-state staging, and promotion while preserving the
ETL/month lock, sandbox isolation, evidence, and postconditions. Stateful
adapters MUST keep the existing state guarantees unchanged.

#### Scenario: Stateless success creates no lineage
- GIVEN a successful PCT run
- WHEN the lifecycle completes
- THEN no state lineage directory, snapshot, or current file is created and state evidence records not-applicable

#### Scenario: Stateful contract preserved
- GIVEN Chat and Voice daily runs
- WHEN their lifecycles complete
- THEN preflight, staged state, and guarded promotion behave exactly as before

### Requirement: Suffix-preserving input staging

Staged required inputs MUST keep their validated source suffix so evidence and
legacy readers see the true format.

#### Scenario: CSV base stays CSV
- GIVEN a PCT request with a `.csv` historial
- WHEN inputs are staged
- THEN the sandbox copy is `input/base.csv` and daily `.xlsx` staging is unchanged

## MODIFIED Requirements

### Requirement: Catalog contracts and promotion

The catalog MUST keep Chat daily, Voice daily, and Voice PCT executable and MT
inert. Selection MUST use `definition.adapter` and reject missing, unknown, or
inert adapters before mutation.
(Previously: Chat and Voice daily were executable while Voice PCT and MT remained inert.)

#### Scenario: PCT promotion
- GIVEN the catalog
- WHEN readiness is inspected
- THEN Chat, Voice daily, and PCT are executable while MT remains inert

### Requirement: Output postconditions

PCT MUST produce exactly one new or changed today-dated `NARANJAX_PCT_*.csv`.
Missing, unchanged, wrong-date, duplicate, or ambiguous matches MUST fail the
run. Daily output sets remain unchanged.
(Previously: Only the Chat and Voice daily output sets were specified.)

#### Scenario: Exact PCT output
- GIVEN exit zero and one qualifying PCT artifact
- WHEN inventory differences are checked
- THEN it is evidenced with the `pct` role and the run may succeed

#### Scenario: Invalid PCT result
- GIVEN a missing, unchanged, wrong-date, or ambiguous PCT result
- WHEN postconditions run
- THEN the run fails with preserved sandbox evidence

### Requirement: Test and scope boundary

Verification MUST use strict path-scoped TDD and generated synthetic fixtures,
including CLI PCT E2E through the stateless lifecycle. Delivery MUST use one
autonomous sub-400-line slice. The change MUST reuse core, keep MT inert, avoid
legacy edits/execution, real data, secrets, and builds, and MUST NOT claim
production/UAT acceptance.
(Previously: Verification covered Chat and Voice daily while PCT remained non-executable.)

#### Scenario: Synthetic implementation evidence
- GIVEN one slice and focused adapter, catalog, service, and CLI E2E tests
- WHEN scope and evidence are audited
- THEN synthetic tests pass, MT is inert, daily behavior is unchanged, and only implementation readiness is claimed
