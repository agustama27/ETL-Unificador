# Delta for Naranja X MA Chat Daily

## ADDED Requirements

### Requirement: Voice request and invocation contract

Voice MUST accept only host-local today and invoke active Python with `back-base/ejecutar_dia.py`, sandbox paths, `--fecha YYYYMMDD`, and derived `--mes YYYYMM`. It MUST include `--planes` or `--pagos` only for supplied inputs and MUST NOT include `--sin_planes_hoy`.

#### Scenario: Exact supplied-input command
- GIVEN today's Voice request with PLANES and PAGOS
- WHEN the command is prepared
- THEN it exactly matches the declared interpreter, entry point, dates, sandbox paths, and inputs

#### Scenario: Omitted daily inputs are isolated
- GIVEN omitted PLANES and PAGOS with explicit no-PLANES intent
- WHEN Voice runs
- THEN its isolated daily directory excludes both and makes host residue inaccessible

#### Scenario: Non-today request
- GIVEN a Voice date different from host-local today
- WHEN execution is requested
- THEN it is evidenced and rejected before lock, state, or subprocess mutation

### Requirement: Voice terminal evidence and security

Every Voice attempt MUST preserve its sandbox and terminal evidence. Persisted commands, environment, logs, streams, and errors MUST redact secrets and input contents.

#### Scenario: Failed secure evidence
- GIVEN any failed stage containing a sensitive value
- WHEN the attempt terminates
- THEN redacted status, stage, process result, and diagnostics are evidenced without canonical mutation

## MODIFIED Requirements

### Requirement: Catalog contracts and promotion

The catalog MUST keep Chat and Voice executable and Voice PCT and MT inert. Selection MUST use `definition.adapter` and reject missing, unknown, or inert adapters before mutation. Paths MUST remain relative and within allowed roots.
(Previously: Only Chat daily could be promoted and all other entries remained inert.)

#### Scenario: Voice-only promotion
- GIVEN the catalog
- WHEN readiness is inspected
- THEN Chat and Voice daily are executable while Voice PCT and MT remain inert

#### Scenario: Catalog-driven selection preserves Chat
- GIVEN valid Chat and Voice definitions
- WHEN each catalog adapter is selected
- THEN each resolves correctly and focused tests preserve Chat behavior

#### Scenario: Escaping path
- GIVEN a path escaping its allowed root
- WHEN the catalog or request is validated
- THEN execution is rejected before mutation

### Requirement: Output postconditions

Chat MUST produce exactly one new or changed today-dated ROMAN, CHAT, and E1KIA. Voice MUST produce exactly one new or changed today-dated ROMAN and E1KIA plus changed staged current state. Missing, unchanged, wrong-date, duplicate, ambiguous, or extra matches MUST fail before promotion.
(Previously: Every successful run required ROMAN, CHAT, and E1KIA without a Voice-specific output set.)

#### Scenario: Exact Chat output set
- GIVEN exit zero and one qualifying Chat artifact per class
- WHEN inventory differences are checked
- THEN all three are evidenced and promotion may proceed

#### Scenario: Exact Voice output and state set
- GIVEN exit zero, one qualifying Voice ROMAN and E1KIA, and changed staged state
- WHEN postconditions run
- THEN both outputs and state are evidenced and promotion may proceed

#### Scenario: Invalid Voice result
- GIVEN a missing, unchanged, wrong-date, duplicate, or ambiguous Voice result
- WHEN postconditions run
- THEN it fails before promotion without canonical mutation

#### Scenario: Ambiguous Chat output
- GIVEN two qualifying CHAT artifacts
- WHEN postconditions run
- THEN the run fails and canonical state is unchanged

### Requirement: Test and scope boundary

Verification MUST use strict path-scoped TDD and generated synthetic fixtures, including CLI Voice E2E through guarded promotion and evidence. Delivery MUST use two autonomous sub-400-line slices. The change MUST reuse core, keep PCT inert, avoid legacy edits/execution, real data, secrets, and builds, and MUST NOT claim production/UAT acceptance.
(Previously: Verification covered Chat while Voice remained non-executable.)

#### Scenario: Synthetic implementation evidence
- GIVEN two slices and focused Chat, Voice, catalog, and CLI E2E tests
- WHEN scope and evidence are audited
- THEN synthetic tests pass, PCT is inert, Chat remains unchanged, and only implementation readiness is claimed
