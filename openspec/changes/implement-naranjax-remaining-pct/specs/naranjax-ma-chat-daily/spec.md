# Delta for Naranja X MA Chat Daily

## ADDED Requirements

### Requirement: Chat PCT and MT PCT invocation contracts

Chat PCT and MT PCT MUST accept only host-local today, reject PLANES, PAGOS,
and no-PLANES intent, and invoke active Python with their catalog entry point,
an explicitly staged `--input` CSV, and a sandbox `--output_dir` — never
allowing legacy input autodetection or cwd-relative default output
directories.

#### Scenario: Exact commands from catalog data
- GIVEN today's request for either new PCT entry
- WHEN the command is prepared
- THEN it exactly matches the entry's interpreter, entry point, staged input, and sandbox output directory

#### Scenario: Daily-only intents are rejected
- GIVEN a request for either entry carrying PLANES, PAGOS, or no-PLANES intent
- WHEN validation runs
- THEN it is evidenced and rejected before lock or subprocess mutation

## MODIFIED Requirements

### Requirement: Catalog contracts and promotion

The catalog MUST expose six executable entries — Chat daily, Voice daily,
Voice PCT, MT daily, Chat PCT, and MT PCT — with selection by
`definition.adapter` rejecting missing or unknown adapters before mutation.
(Previously: four executable entries.)

#### Scenario: Six-entry promotion
- GIVEN the catalog
- WHEN readiness is inspected
- THEN all six entries are executable and each resolves its registered adapter

### Requirement: Output postconditions

Chat PCT MUST produce exactly one new or changed today-dated
`NARANJAX_PCT_*.csv`; MT PCT exactly one today-dated
`DEELO_NAR_USUEVOLTIS_*.txt` (`YYYYMMDD`). Missing, unchanged, wrong-date, or
ambiguous matches MUST fail the run. Existing output sets remain unchanged.
(Previously: PCT postconditions covered only the MA Voice PCT artifact.)

#### Scenario: Exact new-entry outputs
- GIVEN exit zero and one qualifying artifact for the selected entry
- WHEN inventory differences are checked
- THEN it is evidenced with the `pct` role and the run may succeed

#### Scenario: Invalid new-entry result
- GIVEN a missing, unchanged, wrong-date, or ambiguous result
- WHEN postconditions run
- THEN the run fails with preserved sandbox evidence

### Requirement: Test and scope boundary

Verification MUST use generated synthetic fixtures, including parametrized CLI
E2E for both new entries through the stateless lifecycle, plus one real
fixture-driven platform run per entry. Delivery MUST stay below 400 changed
lines per slice. The change MUST NOT edit legacy code, touch the MT `--back`
job, or claim production/UAT acceptance.
(Previously: coverage ended at the four-entry catalog.)

#### Scenario: Synthetic implementation evidence
- GIVEN the implementation slice and focused catalog plus E2E tests
- WHEN scope and evidence are audited
- THEN synthetic tests pass, all prior suites stay green, and only implementation readiness is claimed
