# Exploration: implement-naranjax-ma-chat-mvp

## Current State

### Outcome

Implementation is ready to start on `feat/naranjax-contracts-catalog` as four
`stacked-to-main` slices. The archived plan remains accurate against the current
Chat source: the direct daily entry point is the correct subprocess boundary,
all mutable paths can be redirected, output dates come from `date.today()`,
PLANES is auto-detected from `diarios_dir`, snapshot collision is checked before
legacy state writes, and CHAT is written before later validation.

No root product package, dependency manifest, or root tests exist yet. The new
code should therefore be isolated in root packages and tests, without importing
or changing any legacy package.

### Exact root structure

```text
pyproject.toml
registry/
└── naranjax.yaml
orchestrator/
├── __init__.py
├── models.py
├── catalog.py
├── file_manager.py
├── run_store.py
├── runner.py
├── logging_utils.py
├── service.py
└── run.py
adapters/
├── __init__.py
└── naranjax/
    ├── __init__.py
    └── ma_chat.py
tests/
├── orchestrator/
│   ├── test_catalog.py
│   ├── test_file_manager.py
│   ├── test_run_store.py
│   ├── test_runner.py
│   └── test_logging_utils.py
├── adapters/naranjax/test_ma_chat.py
├── e2e/test_naranjax_ma_chat.py
└── support/
    ├── fake_jobs.py
    └── synthetic_naranjax.py
```

`tests/support` generates scripts, CSVs, and XLSX files only under `tmp_path`;
no data fixture is committed. A root `conftest.py` is unnecessary when commands
run from the repository root.

### Dependencies

Use `pyproject.toml` as the single root declaration with Python `>=3.12` and:

- runtime: `PyYAML>=6.0,<7.0` for the required YAML catalog;
- test extra: `pytest>=8.4,<9.0`;
- Naranja X integration extra: `pandas>=2.2,<3.0` and
  `openpyxl>=3.1,<4.0`.

The current environment satisfies these versions. Do not add `customtkinter`:
the selected legacy entry point does not import the UI. Use the standard library
for hashing, atomic replace, locking, subprocesses, and JSON; no lock/process
library is required for this pilot.

### Guarded defaults verified for implementation

| Concern | Safe MVP default |
|---|---|
| Business date | Parse a real `YYYYMMDD` date, require equality with host-local `date.today()`, and derive `YYYYMM`; never accept an independent month. Persist business and artifact dates separately. |
| State ownership | Unifier-only lineage under `var/state/<etl_id>/<YYYYMM>/`; never point the legacy process at manual or legacy state. Seed only the run's staged `state/`. |
| Promotion | Under the month lock, prepare same-volume temp files after all postconditions. Replace the immutable snapshot first and current monthly state second. This prevents a new current without a snapshot; if the second replace fails, block the lineage for operator recovery rather than retry automatically. |
| Retry/snapshot | Reject before subprocess execution when canonical `estado_YYYYMMDD.csv` exists. No overwrite, resume, or automatic deletion. |
| Locking | Fail-fast exclusive-create `.lock`, held from canonical preflight/seed through promotion. Store schema version, run ID, PID, hostname, and UTC start. Never auto-break a stale lock; recovery is manual after process/run evidence inspection. |
| PLANES omitted | Require explicit `--sin-planes-hoy`; omit `--planes`, pass `--sin_planes_hoy`, and provide an empty per-run `input/diarios/`. Absence without intent is `blocked`. |
| PAGOS omitted | Omit `--pagos`; Chat direct mode disables PAGOS. Do not generalize this policy to Voice. |
| Timeout | Catalog default 900 seconds, with 10-second terminate grace then kill. Capture both streams concurrently and finalize evidence as `timed_out`. The selected legacy job does not spawn child jobs; process-tree support is deferred and must be revisited before other adapters. |
| Output detection | Inventory relative path, size, mtime, and SHA-256 before/after. Because output is run-isolated and initially empty, require exactly one new/changed match for each role: ROMAN, CHAT, E1KIA. Parse dates from names, require the three dates to agree with host-local today, and fail on missing or ambiguous matches even with exit 0. |
| Catalog readiness | PR 1 catalogs all four IDs as non-executable. PR 4 alone changes Chat to ready/executable and supplies its adapter key. Voice daily remains candidate; MA PCT and MT remain blocked by their known contract failures. |

Atomic replacement cannot provide a true multi-file transaction across snapshot
and current. Snapshot-first plus a blocked recovery state is the conservative MVP
ordering. If crash-consistent all-or-nothing promotion is mandatory, a versioned
state manifest/pointer is required and should be a separate design change rather
than hidden inside this slice.

### Synthetic test safety

- Build the 21-column monthly base in memory and write its `Asignacion` sheet to
  `tmp_path` with pandas/openpyxl. Use synthetic M90/PURO rows only.
- Generate optional PLANES (`default_1`) and PAGOS files at runtime; never reuse
  the tracked legacy CSV fixtures or any operational directory.
- Invoke the real Chat entry point only through `sys.executable`, with every
  mutable directory explicitly bound beneath the run sandbox and with today's
  local date.
- Test generic process behavior with tiny Python scripts generated under
  `tmp_path`; scripts cover success, nonzero, large interleaved streams, partial
  output, and timeout without shell commands.
- Snapshot-collision tests create only a synthetic canonical sentinel, assert the
  legacy subprocess was not called, and compare canonical hashes before/after.
- Missing-output tests use a fake adapter job, not mutation/deletion inside the
  legacy tree. No test runs root-wide pytest collection.

## Affected Areas

### PR 1 — contracts/catalog (`feat/naranjax-contracts-catalog`)

Start: approved planning branch. Finish: importable contracts and a validated,
non-executable four-entry catalog.

- `pyproject.toml`
- `orchestrator/__init__.py`
- `orchestrator/models.py`
- `orchestrator/catalog.py`
- `registry/naranjax.yaml`
- `tests/orchestrator/test_catalog.py`

Rollback: revert only the root package/declaration/catalog/tests. No runtime
directories or legacy code exist after rollback.

### PR 2 — sandbox/state

Start: stable definitions. Finish: auditable run creation, containment, input
evidence, inventory diff, lock, staged state, collision preflight, and guarded
promotion; no subprocess integration.

- `orchestrator/file_manager.py`
- `orchestrator/run_store.py`
- `tests/orchestrator/test_file_manager.py`
- `tests/orchestrator/test_run_store.py`

Rollback: remove sandbox/state services; catalog remains non-executable.

### PR 3 — process evidence

Start: sandbox contracts. Finish: generic subprocess execution with concurrent
streams, allowed exits, timeout escalation, stable errors, legacy-log capture,
and partial evidence preservation.

- `orchestrator/runner.py`
- `orchestrator/logging_utils.py`
- `tests/support/fake_jobs.py`
- `tests/orchestrator/test_runner.py`
- `tests/orchestrator/test_logging_utils.py`

Rollback: remove process execution; state/catalog slices remain inert.

### PR 4 — Chat adapter/CLI

Start: inert generic core. Finish: Chat-only adapter, orchestration service, thin
CLI, synthetic legacy E2E, and Chat catalog promotion to executable.

- `adapters/__init__.py`
- `adapters/naranjax/__init__.py`
- `adapters/naranjax/ma_chat.py`
- `orchestrator/service.py`
- `orchestrator/run.py`
- `registry/naranjax.yaml` (Chat readiness only)
- `tests/support/synthetic_naranjax.py`
- `tests/adapters/naranjax/test_ma_chat.py`
- `tests/e2e/test_naranjax_ma_chat.py`
- `docs/PLAN_MVP_ETL_UNIFICADOR_NARANJAX.md` (behavior/verification status only)

Rollback: revert Chat wiring/readiness; generic core remains present but no
catalog entry is executable.

Each PR is one work unit with tests and behavior documentation. Measure
`additions + deletions` before opening each PR; target 300–380 lines. If a slice
crosses 400, stop and split it rather than requesting an implicit exception.

## Approaches

1. **Root packages plus subprocess adapter** — implement the planned narrow core
   and invoke the real Chat daily entry point only in the final slice.
   - Pros: preserves legacy behavior, isolates dependencies/state, supports future adapters.
   - Cons: filesystem transaction and Windows process limitations remain explicit.
   - Effort: High across four bounded PRs.

2. **Import Chat core in-process** — call `procesar_dia()` directly.
   - Pros: structured result and simpler output references.
   - Cons: couples paths, globals, imports, timeout, and dependencies; bypasses the verified executable contract.
   - Effort: Medium code, high operational risk.

## Recommendation

Proceed with Approach 1 and the four slices above. Treat the safe defaults as
MVP policy, not configurable operator choices: today-only dates, unifier-owned
state, snapshot rejection, fail-fast/manual-recovery locks, explicit no-PLANES,
900/10-second timeout, and strict three-output evidence. Keep every catalog entry
non-executable until its adapter slice proves its complete postconditions.

### Focused test commands

```text
python -m pytest tests/orchestrator/test_catalog.py -q
python -m pytest tests/orchestrator/test_file_manager.py tests/orchestrator/test_run_store.py -q
python -m pytest tests/orchestrator/test_runner.py tests/orchestrator/test_logging_utils.py -q
python -m pytest tests/adapters/naranjax/test_ma_chat.py -q
python -m pytest tests/e2e/test_naranjax_ma_chat.py -q
python -m orchestrator.run --help
git diff --check
```

Do not run `python -m pytest` without paths.

## Risks

- Snapshot-first/current-second promotion needs explicit blocked recovery if the
  second replace or host crashes; it is not a multi-file atomic transaction.
- Exclusive-create locks can survive interpreter/host crashes; automatic stale
  lock deletion is intentionally forbidden in the MVP.
- Parent terminate/kill is sufficient for the verified Chat entry point, but not
  a general process-tree guarantee for future adapters.
- The final Chat slice has the greatest 400-line risk because it contains the
  service, CLI, adapter, synthetic factory, and E2E.
- Global `.gitignore` excludes CSV/XLSX; synthetic fixtures must stay generated
  in `tmp_path`, not force-added.
- Output patterns must be role-specific and reject ambiguity; broad globs can
  accidentally treat partial or stale output as success.

## Ready for Proposal

Yes. The implementation boundary and conservative defaults are concrete enough
for a new proposal/spec/design/tasks cycle. The next phase should make the above
defaults normative and preserve the four-PR `stacked-to-main` chain.
