# Delta for Naranja X MA Chat Daily

## ADDED Requirements

### Requirement: MT request and invocation contract

MT MUST accept only host-local today and invoke active Python with the
unifier-owned wrapper `adapters/naranjax/mt_voice_job.py`, an explicitly
staged `--input` TXT, and a sandbox `--output_dir`, with the legacy MT repo as
cwd. It MUST reject PLANES, PAGOS, and no-PLANES intent, and MUST NOT allow
any legacy mtime-based input or output autodetection.

#### Scenario: Exact MT command
- GIVEN today's MT request with a staged 33-column TXT
- WHEN the command is prepared
- THEN it exactly matches the declared interpreter, wrapper path, staged input, and sandbox output directory

#### Scenario: Daily-only intents are rejected
- GIVEN an MT request carrying PLANES, PAGOS, or no-PLANES intent
- WHEN validation runs
- THEN it is evidenced and rejected before lock or subprocess mutation

#### Scenario: Non-today request
- GIVEN an MT date different from host-local today
- WHEN execution is requested
- THEN it is evidenced and rejected before lock or subprocess mutation

### Requirement: Wrapper fidelity to the legacy daily chain

The wrapper MUST run exactly `procesar_base(input, output_dir)` followed by
`extraer_telefonos(roman, output_dir)` from the legacy `procesos` package and
MUST map `FileNotFoundError`/`ValueError` to stderr plus exit `1`, exiting `0`
only when both steps complete.

#### Scenario: Invalid input fails like main.py
- GIVEN a TXT without exactly 33 columns or an empty file
- WHEN the wrapper runs
- THEN it exits 1 with the legacy error message on stderr and the run fails with preserved evidence

#### Scenario: Success produces the legacy chain outputs
- GIVEN a valid 33-column TXT
- WHEN the wrapper runs
- THEN ROMAN is generated first, E1KIA is derived from that exact ROMAN, and both land only in the sandbox output directory

## MODIFIED Requirements

### Requirement: Catalog contracts and promotion

The catalog MUST keep all four entries — Chat daily, Voice daily, Voice PCT,
and MT daily — executable, with selection by `definition.adapter` rejecting
missing, unknown, or inert adapters before mutation.
(Previously: Chat daily, Voice daily, and Voice PCT were executable while MT remained inert.)

#### Scenario: Full catalog promotion
- GIVEN the catalog
- WHEN readiness is inspected
- THEN all four entries are executable and none is inert

### Requirement: Output postconditions

MT MUST produce exactly one new or changed today-dated (`YYMMDD`)
`NARANJAX_MT_ROMAN_*.csv` and `NARANJAX_MT_E1KIA_*.csv`. Missing, unchanged,
wrong-date, duplicate, or ambiguous matches MUST fail the run. Existing MA
output sets remain unchanged.
(Previously: Only the MA output sets were specified.)

#### Scenario: Exact MT output set
- GIVEN exit zero and one qualifying MT ROMAN and E1KIA
- WHEN inventory differences are checked
- THEN both are evidenced with their roles and the run may succeed

#### Scenario: Invalid MT result
- GIVEN a missing, unchanged, wrong-date, or ambiguous MT result
- WHEN postconditions run
- THEN the run fails with preserved sandbox evidence

### Requirement: Test and scope boundary

Verification MUST use strict path-scoped TDD and generated synthetic fixtures,
including CLI MT E2E through the stateless lifecycle. Delivery MUST use two
autonomous sub-400-line slices. The change MUST reuse core, avoid legacy
edits/execution, real data, secrets, and builds, and MUST NOT claim
production/UAT acceptance.
(Previously: Verification covered the MA entries while MT remained non-executable.)

#### Scenario: Synthetic implementation evidence
- GIVEN two slices and focused adapter, wrapper, catalog, and CLI E2E tests
- WHEN scope and evidence are audited
- THEN synthetic tests pass, the catalog has no inert entries, MA behavior is unchanged, and only implementation readiness is claimed
