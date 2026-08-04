# Exploration: Naranja X MA Voice PCT

## Question

Can `naranjax.ma.voice.pct` become executable through the unified platform now that
its contract suite is green, and what does its contract require from the core?

## Contract Blocker Resolved

The catalog kept PCT `blocked` because its contract suite reported `1 failed, 26
passed`: the roman23 priority test expected `TIPIFICACION=11` for `No responde`.
Evidence showed the test was stale, not the implementation:

- `skill-backResultados.md` (current contract) maps `NO_RESPONDE -> "7"`.
- `back_resultados_etl/constants.py` (implementation) agrees: `"NO_RESPONDE": "7"`.
- `PLAN_BACK_RESULTADOS_V2.md` maps `11`, but that same document still uses the
  obsolete output schema (`ID_PRODUCTO`/`PRODUCTO`); the failing test already used
  the current schema (`TIPIFICACION`/`NROPRODUCTO`) — it was left mid-migration.

PR #36 aligned the expectation to `7`. The suite now reports **27 passed**.

## Exact Legacy Contract

### Entry point

```text
python back-resultados/etl_tipificaciones_ia_voz_pct.py
  [--input FILE] [--output_dir DIR] [--log_level LEVEL]
```

| Argument | Behavior |
|---|---|
| `--input` | Optional. When omitted, autodetects the newest `.csv/.xlsx/.xls` under `back-resultados/roman/` — the adapter MUST always pass it explicitly. |
| `--output_dir` | Defaults to `back-resultados/base-generada/` — the adapter MUST redirect it to the sandbox. |
| `--log_level` | Defaults to `INFO`; not exposed by the unifier. |

The script prepends the subproject root to `sys.path` itself, so any cwd works;
the runner still uses the catalog `working_dir` for consistency.

### Output

| Artefact | Pattern | Contract |
|---|---|---|
| PCT | `NARANJAX_PCT_YYYYMMDD.csv` | `\|`-separated, cp1252, 7 columns (`DNI`, `TIPIFICACION`, `NROPRODUCTO`, `FECHA_PROMESA`, `MONTO_PROMESA`, `CALL_REFID`, `OBSERVACIONES`) |

The filename date comes from the system date, like the daily ETLs
(`output_date_source: system_date`).

### Exits and failure

- Success: exit `0` with a summary line on stderr (`total_input_rows=…`).
- Any exception (missing input, unparseable source, core failure): logged and
  exit `1`. No partial-output transactional guarantees, so the sandbox diff and
  postconditions remain necessary.

## Key Difference From the Daily ETLs: Stateless

PCT reads one historial CSV and emits one CSV. It has **no monthly state**, no
`estado_YYYYMM.csv`, no snapshot, no PLANES/PAGOS, and no retry-collision
semantics. The current `RunService` unconditionally:

1. Runs `_state_preflight` (harmless — lineage never exists),
2. Copies canonical current state into the sandbox (no-op — nothing exists),
3. Promotes `run/state/estado_YYYYMM.csv` after postconditions — **this breaks**:
   the staged file never exists, `promote` raises `promotion_failed`, and every
   PCT run would end `failed` after producing a valid output.

So promoting PCT requires the first stateless run contract in the core: the
service must skip state preflight/staging/promotion when the adapter declares
itself stateless, while keeping the ETL/month lock and all evidence guarantees.

## Input Staging Gap

`RunService._stage_inputs` hardcodes the `base` destination as
`input/base.xlsx`. PCT's required input is a CSV; staging it under an `.xlsx`
name would lie in evidence and confuse the legacy reader selection (the core
selects reader by suffix). The destination must follow the validated source
suffix (`input/base.csv` for PCT, unchanged `input/base.xlsx` for Chat/Voice).

## Options Considered

| Option | Verdict |
|---|---|
| Catalog field `stateful: false` + service branch | Truthful but widens catalog schema and validation for one consumer; defer until a second stateless ETL appears |
| Adapter attribute `stateful = False` (like `requires_state_change`) | **Chosen** — same precedent, no schema change, service reads one flag |
| Fake an empty staged state file for PCT | Rejected — fabricates state evidence for a stateless job |
| Separate PCT-only service | Rejected — duplicates the verified lifecycle |

## Readiness

- Contract suite green (27 passed) after PR #36.
- Adapter shape mirrors `MaVoiceAdapter` composition; output classification is
  reusable as-is via `MaChatAdapter._classify` semantics with a new `pct` role.
- No environment variables, no state, no optional inputs: the smallest adapter
  in the catalog.
