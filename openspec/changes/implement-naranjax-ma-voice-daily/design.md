# Design: Implement Naranja X MA Voice Daily

## Technical Approach

Add a thin Voice subprocess adapter and replace `orchestrator.run`'s Chat instance with a catalog-keyed adapter registry. Keep `RunService`, sandbox staging, runner, evidence/redaction, monthly locks, state promotion, request model, timeout, and legacy trees unchanged. Strict TDD uses generated inputs and a fake runner only.

## Architecture Decisions

| Concern | Choice / rationale | Rejected / tradeoff |
|---|---|---|
| Voice reuse | `MaVoiceAdapter` composes `MaChatAdapter` for `validate()` and `outputs()`, preserving today/no-PLANES guards, shared exceptions, and role-driven classification. Voice owns command/isolation because its legacy flags and PAGOS discovery differ. | Extracting a neutral base edits proven Chat code and enlarges regression/review scope. |
| Selection/DI | Build one `Mapping[str, adapter]` keyed by catalog `definition.adapter`; pass it to `Catalog.load`, select after ETL lookup, then inject the selected object into `_service`. Allow `main(..., adapters=..., service_factory=...)` so CLI tests replace infrastructure without legacy execution. | ETL-ID conditionals or a hard-coded Chat adapter duplicate catalog authority. |
| Isolation | Before command creation, require `input/diarios` files to equal exactly the staged `planes.xlsx`/`pagos.csv` implied by the request. Thus either omission cannot trigger residual autodiscovery, while no-PLANES plus PAGOS remains valid. | Requiring an empty directory would incorrectly reject supplied PAGOS. |
| Promotion | PR1 records the complete Voice contract but keeps `candidate/executable:false`; PR2 registers selection and atomically changes only Voice daily to `ready/executable:true`. PCT and MT remain blocked/inert. | Enabling metadata before dispatch exists makes the catalog unloadable/unsafe. |

## Data Flow

```text
CLI -> RunRequest -> Catalog -> adapter key -> RunService -> isolated sandbox
                                                     -> Runner -> output diff
                                                     -> state check/promotion -> run.json
```

## Interfaces / Contracts

Voice command is exactly:

```text
sys.executable back-base/ejecutar_dia.py --fecha YYYYMMDD --mes YYYYMM
 --input <run>/input/base.xlsx --diarios_dir <run>/input/diarios
 --estado_dir <run>/state --output_dir <run>/output --logs_dir <run>/logs
 --procesados_dir <run>/processed [--planes <run>/input/diarios/planes.xlsx]
 [--pagos <run>/input/diarios/pagos.csv]
```

`YYYYMM` is derived from the validated date. Never emit `--chat` or `--sin_planes_hoy`; unified `no_planes_today` remains required when PLANES is absent. Catalog inputs are BASE `.xlsx` required, PLANES `.xlsx` optional, PAGOS `.csv` optional; exit `[0]`, timeout `900`, and allowlist `NARANJAX_PLANES_MIN_COVERAGE` remain.

Success requires exactly one new/changed `NARANJAX_MA_ROMAN_YYYYMMDD.csv` and `NARANJAX_MA_E1KIA_YYMMDD_sinestrategia.csv`, both host-today dated, then an available staged `estado_YYYYMM.csv` promoted by the existing snapshot-first/current-second policy. Exit 0 alone never succeeds; partial sandbox outputs remain evidence and nothing canonical is promoted. No PCT role/output exists.

CLI flags and terminal output remain `--etl --fecha --base [--planes] [--pagos] [--sin-planes-hoy]` and `run=<id> status=<status>`; exits stay 0 succeeded, 2 blocked/validation, 1 execution failure. Unknown ETL or unregistered executable adapter remains a catalog error before service execution.

## File Changes and Strict TDD Slices

| Slice | Product files | RED then GREEN tests / regression |
|---|---|---|
| PR1 adapter + inert contract, target <300 lines | Create `adapters/naranjax/ma_voice.py`; modify `registry/naranjax.yaml` without promotion | Create `tests/adapters/naranjax/test_ma_voice.py`: exact order, derived month, both optional combinations, exact-directory isolation, today/intent conflicts, ROMAN/E1KIA missing/ambiguous/unchanged/wrong-date. Run this path, then `test_ma_chat.py`. |
| PR2 registry selection + promotion, target <250 lines | Modify `orchestrator/run.py`, `registry/naranjax.yaml`, `tests/support/synthetic_naranjax.py` | Modify `tests/orchestrator/test_catalog.py`; create `tests/e2e/test_naranjax_ma_voice.py`: catalog dispatch, CLI mapping/statuses, success state/artifacts, historical block-before-run, nonzero/timeout/spawn and invalid-output no-promotion. Run each path, then Chat E2E and `tests/orchestrator/test_service.py`. |

Each stacked-to-main PR is autonomous, revertible, and MUST remain below 400 additions plus deletions; no size exception. No root-wide pytest, legacy test, real fixture, build, or legacy edit.

## Migration / Rollout and Rollback

No data migration. Revert PR2 first to remove Voice executability/dispatch while preserving evidence and canonical state; revert PR1 only to remove inert metadata/adapter. Never overwrite snapshots, auto-break locks, or auto-rollback state. Chat stays executable but not UAT-accepted; PCT stays inert.

## Open Questions

None.
