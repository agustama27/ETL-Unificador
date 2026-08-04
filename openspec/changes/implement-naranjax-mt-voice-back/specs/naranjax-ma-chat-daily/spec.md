# Delta for Naranja X MA Chat Daily

## ADDED Requirements

### Requirement: Multi-input run contract

`RunRequest` MUST accept a role-keyed mapping of extra input paths. The
service MUST stage each extra declared by the catalog as
`input/<role><suffix>` with its validated source suffix, record it in
evidence, and reject undeclared or missing required extras before subprocess
mutation. The CLI MUST accept repeatable `--input ROLE=PATH` arguments.

#### Scenario: Extras stage truthfully
- GIVEN a back request with logcall and historial extras
- WHEN inputs are staged
- THEN the sandbox holds `input/logcall.csv` and `input/historial.csv` with hashes in evidence

#### Scenario: Daily adapters reject extras
- GIVEN a Chat, Voice, PCT, or MT daily request carrying any extra input
- WHEN validation runs
- THEN it is evidenced and rejected before lock or subprocess mutation

### Requirement: Back request and invocation contract

Back MUST accept only host-local today, reject PLANES/PAGOS/no-PLANES
intents, require exactly the `logcall` and `historial` extras, and invoke
active Python with `main.py --back`, all three staged inputs, and the sandbox
`--back-output-dir` — never allowing mtime autodiscovery.

#### Scenario: Exact back command
- GIVEN today's back request with staged M30, LOGCALL, and historial
- WHEN the command is prepared
- THEN it exactly matches the interpreter, entry point, `--back`, staged input paths, and sandbox output directory

#### Scenario: Incomplete extras are rejected
- GIVEN a back request missing logcall or historial
- WHEN validation runs
- THEN it is evidenced and rejected before lock or subprocess mutation

## MODIFIED Requirements

### Requirement: Catalog contracts and promotion

The catalog MUST expose seven executable entries, adding
`naranjax.mt.voice.back` with base `.txt` plus required `logcall`/`historial`
extras and USUEVOLTIS plus anomalies outputs.
(Previously: six executable entries without extra-input declarations.)

#### Scenario: Seven-entry promotion
- GIVEN the catalog
- WHEN readiness is inspected
- THEN all seven entries are executable and each resolves its registered adapter

### Requirement: Output postconditions

Back MUST produce exactly one new today-dated `DEELO_NAR_USUEVOLTIS_*.txt`
(`anomalies` role: one `_anomalias_*.txt`), both `YYYYMMDD` system-dated.
Missing, unchanged, wrong-date, or ambiguous matches MUST fail the run.
(Previously: no anomalies role existed.)

#### Scenario: Exact back output set
- GIVEN exit zero and one qualifying USUEVOLTIS and anomalies artifact
- WHEN inventory differences are checked
- THEN both are evidenced with their roles and the run may succeed

### Requirement: Test and scope boundary

Verification MUST use generated synthetic fixtures, including core extras
tests, adapter tests, CLI E2E through the stateless lifecycle, and one real
fixture-driven platform run. Delivery MUST use two sub-400-line slices. The
change MUST NOT edit legacy code or claim production/UAT acceptance.
(Previously: coverage ended at the six-entry catalog.)

#### Scenario: Synthetic implementation evidence
- GIVEN both slices and focused core, adapter, catalog, and E2E tests
- WHEN scope and evidence are audited
- THEN synthetic tests pass, all prior suites stay green, and only implementation readiness is claimed
