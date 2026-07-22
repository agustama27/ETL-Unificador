# Naranja X MA Chat Daily Specification

## Purpose

Define a guarded, today-only Chat runner with auditable evidence and isolated unifier-owned state.

## Requirements

### Requirement: Catalog contracts and promotion

The catalog MUST declare typed contracts for Chat daily, Voice daily, Voice PCT, and MT daily. Entries MUST remain non-executable until explicit promotion; this change MAY promote only `naranjax.ma.chat.daily`. Project, working, input, output, run, and state paths MUST be relative and resolve within their allowed roots.

#### Scenario: Chat promotion
- GIVEN the final catalog
- WHEN readiness is inspected
- THEN only Chat daily has an executable adapter
- AND the other three entries remain inert

#### Scenario: Escaping path
- GIVEN a path containing traversal or resolving outside its root
- WHEN the catalog or request is validated
- THEN execution is rejected before mutation

### Requirement: Date, sandbox, and metadata

The CLI MUST accept only a business date equal to host-local today and MUST create an isolated run sandbox. Every attempted run MUST end with structured `run.json` recording IDs, lifecycle timestamps/status, dates, redacted command/cwd/environment, input hashes, state lineage, process result, logs, artifacts, postconditions, and error evidence.

#### Scenario: Historical date
- GIVEN a requested date other than host-local today
- WHEN execution is requested
- THEN it fails before lock, state, or subprocess mutation
- AND terminal evidence records the rejection

### Requirement: State prechecks and locking

Canonical current state and immutable dated snapshots MUST be owned outside disposable runs by the unifier. An existing target snapshot MUST fail precheck. A per-ETL/month lock MUST fail fast; stale locks MUST NOT be auto-broken and require manual recovery.

#### Scenario: Collision or contention
- GIVEN the snapshot or lock already exists
- WHEN a run starts
- THEN no subprocess runs and no canonical state changes
- AND failure evidence identifies the blocker

### Requirement: Guarded state promotion

After all postconditions pass, the system MUST promote the immutable snapshot before monthly current state. If snapshot succeeds but current fails, lineage MUST become blocked, evidence MUST be preserved, and later runs MUST require manual recovery.

#### Scenario: Partial promotion
- GIVEN snapshot promotion succeeds and current promotion fails
- WHEN the run terminates
- THEN the run fails with blocked lineage
- AND no automatic rollback or retry occurs

### Requirement: Subprocess and failure evidence

The runner MUST concurrently drain stdout and stderr, preserve both streams and legacy logs, and redact secrets from persisted command, environment, logs, and errors. It MUST allow 900 seconds, terminate, wait 10 seconds, then kill if still running. Nonzero exit, timeout, spawn error, or partial artifacts MUST fail while preserving the sandbox and evidence.

#### Scenario: Interleaved output
- GIVEN a child writes enough interleaved stdout and stderr to fill pipes
- WHEN it runs
- THEN both streams are captured without deadlock
- AND persisted sensitive values are redacted

#### Scenario: Unresponsive timeout
- GIVEN the child exceeds 900 seconds and ignores termination
- WHEN the grace period expires
- THEN it is killed and the run is failed with timeout evidence

### Requirement: Chat invocation and PLANES isolation

The Chat adapter MUST invoke the verified daily entry point through the active Python interpreter with aligned month/date arguments. When PLANES is omitted, it MUST pass no `--planes`, use an empty run-local daily directory, and apply `--sin_planes_hoy`; host PLANES files MUST be inaccessible.

#### Scenario: PLANES omitted
- GIVEN no PLANES input
- WHEN Chat is invoked
- THEN only the empty isolated directory represents daily plans
- AND unrelated host files cannot influence the run

### Requirement: Output postconditions

A successful run MUST produce exactly one new or changed ROMAN, CHAT, and E1KIA artifact matching today. Missing, duplicate, ambiguous, unchanged, wrong-date, or extra expected-class matches MUST fail before promotion.

#### Scenario: Exact output set
- GIVEN exit zero and one qualifying artifact per class
- WHEN outputs are compared with the pre-run inventory
- THEN all three are evidenced and promotion may proceed

#### Scenario: Ambiguous output
- GIVEN two qualifying CHAT artifacts
- WHEN postconditions run
- THEN the run fails and canonical state is unchanged

### Requirement: Test and scope boundary

Verification MUST use dynamically generated synthetic CSV/XLSX fixtures in temporary directories with strict path-scoped TDD. Implementation MUST NOT add API/UI, edit legacy code, use real data or secrets, commit build artifacts, support historical dates, or make Voice/PCT/MT executable.

#### Scenario: Repository scope audit
- GIVEN the implementation diff and focused tests
- WHEN prohibited files and data are inspected
- THEN no excluded behavior or artifact is present
- AND legacy behavior remains unchanged
