# Exploration: implement-naranjax-ma-voice-daily

## Current State

### Verified daily boundary

The safe subprocess boundary is the direct daily entry point, not the UI facade:

```text
cwd: soho-naranjaX-MA-etl
command:
  <active Python> back-base/ejecutar_dia.py
    --fecha YYYYMMDD --mes YYYYMM
    --input <run>/input/base.xlsx
    --diarios_dir <run>/input/diarios
    --estado_dir <run>/state
    --output_dir <run>/output
    --logs_dir <run>/logs
    --procesados_dir <run>/processed
    [--planes <run>/input/diarios/planes.xlsx]
    [--pagos <run>/input/diarios/pagos.csv]
```

Use `sys.executable`, as Chat does, rather than the catalog's literal `python`.
`--mes` must always be derived from `--fecha`; allowing an independently supplied
month can load one month while state saving derives another month from the date.
Voice has no `--chat` or `--sin_planes_hoy` legacy flags. Evidence:
`soho-naranjaX-MA-etl/back-base/ejecutar_dia.py:51-99` and
`adapters/naranjax/ma_chat.py:31-58`.

`naranjax_etl.py --cli` is unsuitable: it has a different public contract,
requires `--base`, effectively requires PLANES unless
`--inicio-mes-sin-diarios`, derives `diarios_dir` from an input parent, and does
not create the direct entry point's daily file log. Evidence:
`soho-naranjaX-MA-etl/naranjax_etl.py:6-15`,
`soho-naranjaX-MA-etl/cli/main.py:15-105`.

### Inputs and discovery

- **BASE** is XLSX. It is operationally required when staged monthly state is
  absent or empty. The workbook accepts `Asignacion`, `Asignación`,
  `ASIGNACION`, a matching `Asignacion M90 - *`, or a sole sheet; required
  columns are alias-mapped. Initial state retains only `cajon=M90` and
  `ecosistema=PURO`. Evidence: `back-base/back_base_etl/io.py:252-384` and
  `back-base/back_base_etl/estado_persistente.py:36-85` under the Voice tree.
- **PLANES** is XLSX and must contain sheet `default_1`. An explicit `--planes`
  wins; otherwise the core scans sorted files in `diarios_dir` and the last
  recognized `.xlsx` whose name contains `planes` or `cartera` wins. The
  existing root input declaration must therefore remain `.xlsx` only, despite
  the facade validator accepting CSV. Evidence: `core/procesar_dia.py:34-50,
  171-215`; `back-base/back_base_etl/io.py:395-442`.
- **PAGOS** is CSV (`;`/`,` detection and legacy aliases). The direct Voice
  entry sets `usar_pagos=True`; if `--pagos` is omitted, residual recognized
  PAGOS in `diarios_dir` may be auto-detected and processed. This differs from
  Chat and makes the run-local daily directory mandatory. Evidence:
  `back-base/ejecutar_dia.py:89-97`, `core/procesar_dia.py:171-223`, and
  `tests/core/test_optional_pagos_handling.py:61-125`.
- **No PLANES** is valid legacy behavior: omit `--planes` and provide an
  isolated daily directory containing only the explicitly staged PAGOS, if
  any. State keeps monthly/deferred values and the job still writes ROMAN and
  E1KIA. The unified `no_planes_today` flag should remain required as explicit
  operator intent, but it is an adapter guard only; Voice must not translate it
  to a nonexistent legacy flag. Evidence: `core/procesar_dia.py:177-215` and
  `back-base/tests/test_ejecutar_dia_integration.py:217-255`.

### Flow, outputs, dates, logs, and exits

The core loads or initializes monthly state, discovers/selects daily files,
applies PLANES then PAGOS, filters Voice scope, writes ROMAN then E1KIA, writes
state, and finally copies used daily inputs. PLANES coverage defaults to 1% and
can be changed only by allowlisted `NARANJAX_PLANES_MIN_COVERAGE`; insufficient
coverage fails. Evidence: `core/procesar_dia.py:133-332`.

Daily Voice has exactly two output classes:

| Role | Pattern | Date |
|---|---|---|
| ROMAN | `NARANJAX_MA_ROMAN_YYYYMMDD.csv` | host-local `date.today()` |
| E1KIA | `NARANJAX_MA_E1KIA_YYMMDD_sinestrategia.csv` | host-local `date.today()` |

There is no daily PCT output. `ResultadoDia.output_pct` is unused; PCT is a
separate job (`back-resultados/etl_tipificaciones_ia_voz_pct.py`) producing
`NARANJAX_PCT_YYYYMMDD.csv` from a separate input contract. PCT remains blocked
and non-executable in this change. Evidence: `core/modelos.py:29-46`,
`core/procesar_dia.py:286-329`, `back-base/back_base_etl/io.py:547-568`, and
`back-resultados/back_resultados_etl/io.py:126-152`.

Output filenames and ROMAN `fecha_limite_sistema` use machine date, not
`--fecha`. Therefore the existing today-only machine-date gate remains
required; otherwise requested business date, state snapshot date, filename,
and row content diverge. Evidence: `back-base/back_base_etl/io.py:547-568` and
`back-base/back_base_etl/transformers.py:79,202`.

The direct entry writes console output (logging's stream handler uses stderr)
and UTF-8 `<logs_dir>/<fecha>.log`. Success falls through with exit 0; a core
exception is caught into `ResultadoDia(status="error")`, logged with traceback,
and mapped to exit 1; argparse errors exit 2. Evidence:
`back-base/ejecutar_dia.py:30-49,99-103` and `core/procesar_dia.py:330-332`.

Failures are non-transactional inside the sandbox: ROMAN can remain if E1KIA
fails; both outputs can remain if state persistence fails; current state is
written before its snapshot after a pre-existing-snapshot check. The unifier
must continue treating exit 0 as insufficient and promote nothing until both
output postconditions and staged-current-state availability pass. Evidence:
`core/procesar_dia.py:286-299` and
`back-base/back_base_etl/estado_persistente.py:103-123`.

### State, retry, and concurrency

Legacy staged state is `estado_YYYYMM.csv` plus immutable
`estado_YYYYMMDD.csv`. The existing root service already stages only canonical
current state, preflights recovery/snapshot collision, locks per ETL/month,
runs in an isolated sandbox, and promotes the staged current through
snapshot-first/current-second durable copies. The extra legacy snapshot remains
run-local evidence; canonical promotion recreates both files from staged
current. Evidence: `orchestrator/service.py:37-99,118-143` and
`orchestrator/state_store.py:159-179`.

Reuse those policies unchanged:

- same-date retry is blocked before subprocess when canonical snapshot exists;
- concurrent Voice dates in one month fail fast on the Voice ETL/month lock;
- stale locks and partial promotion require manual recovery;
- no automatic retry, snapshot overwrite, or state rollback;
- failed run sandboxes and logs remain evidence.

The lock scope is ETL ID/month, so Voice and Chat deliberately use independent
unifier-owned lineages and do not lock each other. This is safe only while they
remain separate repositories/lineages; do not bind either adapter to manual
legacy state.

### Catalog accuracy and reusable platform

The existing Voice catalog entry is accurate only for identity, repository
presence, candidate readiness, inertness, and `project_path`. It is not an
executable contract yet. Promotion requires:

```yaml
working_dir: soho-naranjaX-MA-etl
entrypoint: soho-naranjaX-MA-etl/back-base/ejecutar_dia.py
command: [python, back-base/ejecutar_dia.py]
fixed_arguments: []
arguments:
  business_date: --fecha
  base: --input
  planes: --planes
  pagos: --pagos
inputs:
  - {role: base, extensions: [.xlsx], required: true}
  - {role: planes, extensions: [.xlsx], required: false}
  - {role: pagos, extensions: [.csv], required: false}
outputs:
  - {role: roman, glob: 'NARANJAX_MA_ROMAN_*.csv', date_format: YYYYMMDD}
  - {role: e1kia, glob: 'NARANJAX_MA_E1KIA_*_sinestrategia.csv', date_format: YYMMDD}
allowed_exits: [0]
timeout_seconds: 900
request_date_format: YYYYMMDD
output_date_source: system_date
adapter: naranjax.ma.voice
environment_allowlist: [NARANJAX_PLANES_MIN_COVERAGE]
```

No catalog mapping should claim a Voice `--sin_planes_hoy` argument. The root
`RunRequest`, `ArtifactRole`, staging destinations, runner, evidence/redaction,
run store, state store, timeout, service lifecycle, and CLI arguments can be
reused unchanged. The two required extension points are:

1. a `MaVoiceAdapter` that builds the Voice command and reuses the existing
   today/no-PLANES validation and role-driven output classifier; composition
   with the unchanged `MaChatAdapter` is the smallest safe implementation for
   two variants, avoiding duplicated date/postcondition logic;
2. `orchestrator/run.py` adapter registration/selection by
   `definition.adapter` instead of its current hard-coded Chat instance.

`RunService` currently imports shared adapter exceptions from `ma_chat.py`.
Voice composition can deliberately raise those same exceptions and leave the
service unchanged. Extract a neutral MA-daily base only if a later third
variant makes this coupling costly; doing it now increases Chat regression and
review surface without changing behavior.

## Affected Areas

- `registry/naranjax.yaml` — complete the Voice contract, then promote only
  Voice daily; keep PCT/MT inert.
- `adapters/naranjax/ma_voice.py` — Voice translation and reuse of shared
  validation/output postconditions.
- `orchestrator/run.py` — register/select Chat or Voice adapter while retaining
  one typed CLI pipeline.
- `tests/adapters/naranjax/test_ma_voice.py` — exact command, no-PLANES/PAGOS
  isolation, today gate, and two-role output classifications.
- `tests/orchestrator/test_catalog.py` — assert Chat and Voice daily executable,
  with PCT/MT still inert.
- `tests/e2e/test_naranjax_ma_voice.py` — synthetic runner/service/CLI lifecycle;
  never invoke the legacy tree.
- `tests/support/synthetic_naranjax.py` — parameterize synthetic output/state
  writing by adapter/date without committing CSV/XLSX fixtures.
- `openspec/specs/naranjax-ma-chat-daily/spec.md` — requires a later Voice delta
  because its current source-of-truth says only Chat is executable; do not edit
  it during exploration.

No file under `soho-naranjaX-MA-etl/` or other legacy/product tree should change.

## Approaches

1. **Thin Voice adapter by composition over the existing Chat guard helpers** —
   own command construction; delegate common today validation and role-driven
   output classification.
   - Pros: smallest behavior surface; Chat and generic core remain unchanged;
     exact shared safeguards; comfortably reviewable.
   - Cons: temporary naming/coupling to `MaChatAdapter` until another MA daily
     adapter justifies neutral extraction.
   - Effort: Low/Medium.

2. **Extract a neutral MA-daily base adapter now** — move exceptions,
   validation, output classification, and command prefix into a shared module.
   - Pros: cleaner long-term domain structure.
   - Cons: modifies proven Chat code/tests, increases regression and 400-line
     risk for only two variants, and adds no operator capability.
   - Effort: Medium.

## Recommendation

Use Approach 1 and keep the legacy process fully isolated. Preserve the
today-only gate, explicit no-PLANES intent, empty/staged-only daily directory,
900-second timeout, strict exactly-one-new-or-changed ROMAN/E1KIA
postconditions, unifier-owned state, same-date retry rejection, and manual
recovery semantics. Do not execute or promote PCT.

Conservative stacked-to-main delivery, with no functional size exception:

1. **PR Voice adapter + inert complete catalog contract** — add adapter and unit
   tests; complete Voice metadata but keep `candidate/executable:false` until
   CLI wiring exists. Target under 300 changed lines.
2. **PR CLI wiring + promotion + synthetic E2E** — select adapters by catalog
   key, promote Voice daily, update catalog tests, and add synthetic lifecycle
   coverage. Target under 250 changed lines.

Each PR starts and finishes autonomously, is independently revertible, and must
remain below 400 additions plus deletions. If PR 1 approaches 400, keep output
classification cases table-driven rather than extracting shared product code.

Focused test commands:

```text
python -m pytest tests/adapters/naranjax/test_ma_voice.py -q
python -m pytest tests/orchestrator/test_catalog.py -q
python -m pytest tests/e2e/test_naranjax_ma_voice.py -q
python -m pytest tests/adapters/naranjax/test_ma_chat.py tests/e2e/test_naranjax_ma_chat.py -q
python -m pytest tests/orchestrator/test_service.py -q
python -m orchestrator.run --help
git diff --check
```

Do not run root-wide pytest or any test under `soho-naranjaX-MA-etl/` for this
change. Current safe baseline verification used only synthetic/root tests:
`39 passed` for catalog+service and `24 passed` for Chat adapter+synthetic E2E.

Synthetic tests should create placeholder external inputs under `tmp_path`, let
the existing `FileManager` stage them, and use a fake `Runner` to emit run-local
ROMAN/E1KIA plus staged monthly state. Parameterize missing, ambiguous,
unchanged, wrong-date, nonzero, timeout, and spawn-failure modes. This verifies
the adapter/service boundary without importing or running legacy code and
without committing data files.

## Risks

- Machine-date naming/content makes today-only validation non-negotiable while
  legacy code remains unchanged.
- Voice omission of PAGOS can still consume a residual file unless the adapter
  uses the isolated run-local daily directory; this differs from Chat.
- Exit 0 can coexist with wrong/missing/ambiguous outputs; output diff
  postconditions must remain mandatory.
- Legacy writes are non-transactional inside failed sandboxes; canonical state
  must be promoted only after all postconditions.
- `NARANJAX_PLANES_MIN_COVERAGE` materially changes failure behavior and must
  remain allowlisted/redacted/evidenced.
- `RunService` exception imports remain Chat-named technical debt; extracting
  them now is unnecessary scope, but a later third MA adapter should revisit it.
- Real MA Chat UAT is still pending. Passing Chat regression tests or reusing its
  core MUST NOT be reported as production acceptance for Chat or Voice.
- MA PCT is a separate pending boundary and MUST remain non-executable.

## Ready for Proposal

Yes. Requirements are concrete enough for proposal/spec/design: promote only
`naranjax.ma.voice.daily`, preserve all existing core safety policies, implement
the exact direct Voice command, require explicit no-PLANES intent without a
legacy flag, require ROMAN+E1KIA only, use synthetic tests only, and retain PCT
as blocked/non-executable.
