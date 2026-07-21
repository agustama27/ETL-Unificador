# Naranja X Unifier MVP Planning Specification

## Purpose

Define the evidence-backed plan for a guarded Naranja X ETL unifier MVP.

## Requirements

### Requirement: Verified inventory and evidence

The plan MUST inventory Chat MA, MA Voice, and MT repositories, documenting presence, sources, entry points, commands, dependencies, tests, and runtime directories. Every factual claim MUST cite a repository path, command result, or authoritative root document; unknowns MUST remain explicit. It MUST record MA PCT as `1 failed, 26 passed` and MT back-results as `1 failed, 6 passed`, without declaring affected adapters ready.

#### Scenario: Evidence review
- GIVEN the completed plan
- WHEN a reviewer traces an inventory or readiness claim
- THEN its evidence and verification status are identifiable
- AND unsupported claims are marked unknown or open

### Requirement: Exact Chat legacy contract

The plan MUST document `python back-base/ejecutar_dia.py [options] --chat`, discovered arguments, required monthly base, PLANES/PAGOS discovery, and ROMAN/CHAT/E1KIA formats. It MUST state that output suffixes and `fecha_limite_sistema` use machine date; state uses monthly current plus immutable daily snapshots; exits are 0/1/2; and writes are non-transactional. Chat and Voice argument policies MUST remain distinct.

#### Scenario: Contract comparison
- GIVEN source evidence and the documented pilot contract
- WHEN commands, inputs, outputs, dates, state, or failures are compared
- THEN no behavior is normalized beyond the legacy evidence

### Requirement: Proposed catalog schema

The plan MUST propose `registry/naranjax.yaml` with schema version and records for Chat daily, Voice daily, Voice PCT, and MT daily. Each record MUST support identity/readiness, project/working paths, command/fixed and mapped arguments, required/optional inputs, output patterns/date format/date source, state scope, retry policy, success exit codes, timeout, environment variables, and postconditions.

#### Scenario: Blocked catalog entry
- GIVEN an ETL with a failing or unresolved contract
- WHEN its catalog record is reviewed
- THEN repository presence and adapter readiness are represented separately

### Requirement: Runner, sandbox, and run evidence

The plan MUST assign responsibilities for models, subprocess execution, run storage, staging/diffing, and log capture. It MUST define an isolated run directory for staged inputs, outputs, logs, processed files, and `run.json`, while durable monthly state remains outside disposable runs. Metadata MUST include run/ETL IDs, lifecycle status, timestamps, command/cwd, input evidence, exit/timeout/error, stdout/stderr and legacy logs, before/after artifacts, postconditions, `business_date`, `artifact_date`, environment, and state lineage.

#### Scenario: Exit zero with missing output
- GIVEN the subprocess exits zero
- WHEN any expected new artifact is absent
- THEN the planned postcondition marks the run failed

### Requirement: State, retry, concurrency, and date policies

The plan MUST require explicit `--mes`/`--fecha` alignment, an ETL/month lock, immutable-snapshot preflight, failed-run preservation, and an approved retry/state-lineage policy. It MUST not promise arbitrary business dates until the machine-date mismatch is accepted or resolved. Timeout and lock ownership MUST be explicit decisions.

#### Scenario: PLANES omitted
- GIVEN a Chat run without PLANES
- WHEN invocation is planned
- THEN it uses no `--planes`, an empty isolated daily directory, and the decided `--sin_planes_hoy` policy

#### Scenario: Existing snapshot
- GIVEN `estado_YYYYMMDD.csv` already exists
- WHEN the same date is requested
- THEN execution is rejected or follows a documented operator-approved retry policy

### Requirement: Final planning document

`docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md` MUST consolidate the inventory, diagnoses, exact contract, schema, architecture, guarded pilot, four implementation phases, acceptance checks, verification, risks, and open decisions. Acceptance MUST cover isolation, metadata/log/error/output evidence, legacy compatibility, and absence of committed real data/build artifacts.

#### Scenario: Planning acceptance
- GIVEN the final document and SDD artifacts
- WHEN the planning checklist is evaluated
- THEN every criterion has evidence or an explicitly unresolved decision

### Requirement: Planning-only boundary

This change MUST NOT add functional runner/catalog/adapter stubs, API/UI, generated data/build artifacts, or modify legacy code, outputs, or business rules. Future changes SHOULD use adapters/configuration with minimal blast radius.

#### Scenario: Scope audit
- GIVEN the change diff
- WHEN files outside planning documentation are inspected
- THEN no product implementation or legacy modification exists
