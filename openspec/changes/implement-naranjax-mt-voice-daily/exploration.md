# Exploration: Naranja X MT Voice Daily

## Question

Can `naranjax.mt.voice.daily` become executable through the unified platform,
given that MT uses a different architecture than the MA projects?

## Contract Blocker Resolved

The catalog kept MT `blocked` partly because its back-resultados suite reported
`1 failed, 6 passed`: the save_output contract test expected `USUOLOS` in
column 8. Evidence showed the test was stale, not the implementation:

- `plan_correccion_etl.md` documents Bug #2 (13/05/2026 client feedback):
  column 8 changed `USUOLOS -> USUEVOLTIS`; the client-validated reference file
  has all rows with `USUEVOLTIS` and none with `USUOLOS`.
- `CLAUDE.md` fixes column 8 as `USUEVOLTIS`.
- Implementation (`procesos/back_resultados.py`, `back_resultados_etl/io.py`)
  emits `USUEVOLTIS`.

PR #44 aligned the expectation. The suite now reports **7 passed**. Note the
failing test belonged to the `--back` job (USUEVOLTIS), which is NOT the daily
pipeline being promoted here — but the readiness gate required a green suite.

## Exact Legacy Daily Contract

### Entry points

| Entry | Behavior |
|---|---|
| `python main.py` | Autodetects newest `.txt` in `back-base/base_recibida/` by mtime, writes both outputs to `back-base/base_procesada/` — **no input/output arguments** |
| `python -m procesos.base_generator <input.txt>` | Explicit input, but output dir still fixed to the repo |
| `python -m procesos.phone_extractor <roman.csv>` | Same limitation |

Neither CLI can redirect outputs to a sandbox. However, the underlying core
functions CAN:

```python
procesar_base(archivo_entrada: Path | None, output_dir: Path | None) -> Path
extraer_telefonos(archivo_entrada: Path | None, output_dir: Path | None) -> Path
```

`main.py` chains them: `procesar_base()` then `extraer_telefonos(roman_path)`.
Both raise `FileNotFoundError`/`ValueError` on bad input; `main.py` maps those
to stderr + exit `1`; success is exit `0`.

### Input

One pipe-delimited TXT with exactly **33 columns** (validated on the first
line; `ValueError` otherwise). Empty file also raises `ValueError`.

### Outputs (system date, `%y%m%d`)

| Artefact | Pattern | Contract |
|---|---|---|
| ROMAN | `NARANJAX_MT_ROMAN_YYMMDD.csv` | `;`, UTF-8, header + one row per input line, TEL 1-6 normalized (549/54) |
| E1KIA | `NARANJAX_MT_E1KIA_YYMMDD.csv` | `;`, UTF-8, phones + customer_id sorted by populated-phone count |

### State

None. MT daily has no monthly estado, no snapshot, no PLANES/PAGOS — the
second stateless consumer of the platform contract introduced for PCT.

## The Sandbox Gap and Options

| Option | Verdict |
|---|---|
| Invoke `main.py` with sandbox cwd | Rejected — paths are `__file__`-anchored, cwd changes nothing; outputs land in the legacy repo and autodetection reads residual TXTs |
| Modify legacy `main.py` to accept `--input`/`--output_dir` | Rejected for this change — legacy edits are out of scope and need their own regression suite |
| Unifier-owned wrapper job invoked as a subprocess that imports `procesos` and passes explicit sandbox paths | **Chosen** — no legacy edits, no autodetection, sandboxed outputs; the subprocess boundary is preserved (the orchestrator never imports legacy code; the spawned job does, exactly like `main.py` itself) |

The wrapper (`adapters/naranjax/mt_voice_job.py`) mirrors `main.py`'s exact
chain — `procesar_base(input, output_dir)` then
`extraer_telefonos(roman, output_dir)` — and its exact failure mapping
(`FileNotFoundError`/`ValueError` -> stderr + exit 1).

## Readiness

- Back-resultados suite green (7 passed) after PR #44.
- Daily core functions already accept explicit paths; no legacy change needed.
- Roles `roman`/`e1kia` and `YYMMDD` date format already exist in the model.
- Stateless contract, suffix-preserving staging (`.txt`), and catalog-driven
  CLI selection are already in place from the PCT chain.
