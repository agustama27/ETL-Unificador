# Exploration: Remaining Tipificaciones PCT Jobs (Chat PCT, MT PCT)

## Question

Which legacy jobs remain outside the four-entry catalog, and can they be
promoted without new adapter code?

## Inventory of Remaining Jobs

| Job | Entry point | Suite | Status |
|---|---|---|---|
| Chat PCT | `SOHO-Chat-NX_MA-ETL/back-resultados/etl_tipificaciones_ia_voz_pct.py` | **25 passed** | Ready |
| MT PCT | `soho-naranjaX-MT-etl/back-resultados/etl_tipificaciones_ia_voz_pct.py` | **7 passed** (incl. the USUEVOLTIS save_output contract fixed in #44) | Ready |
| MT `--back` | `soho-naranjaX-MT-etl/main.py --back` (`procesos/back_resultados.py`) | **No dedicated contract suite** | Out of this change — needs its own exploration, legacy contract tests, and multi-input core support |

## Chat PCT — a byte-identical clone

The Chat PCT entry point is **byte-identical** to the already-promoted MA Voice
PCT entry point (verified by file comparison). Same package layout
(`back_resultados_etl`), same `NARANJAX_PCT_` prefix, same `|`/cp1252/7-column
contract, same `--input`/`--output_dir`/`--log_level` CLI, same 0/1 exits.
Only the project root differs.

## MT PCT — same shape, different output contract

```text
python back-resultados/etl_tipificaciones_ia_voz_pct.py
  [--input FILE] [--output_dir DIR] [--log_level LEVEL]
```

- `--input` optional with legacy autodetection
  (`resolve_tipificaciones_input_path`) — the adapter MUST always pass it.
- `--output_dir` defaults to a **cwd-relative** `back-resultados/base-generada`
  — the adapter MUST redirect it to the sandbox.
- Exits: `SystemExit(main())` returning 0 on success, 1 on any error.
- Output: `DEELO_NAR_USUEVOLTIS_YYYYMMDD.txt` — system date `%Y%m%d`,
  `|`-separated, cp1252, LF, 40 fixed columns (col 1 run timestamp, col 3
  `NARANJA`, col 8 `USUEVOLTIS`, col 10 `MAKE CALL`, col 11 event-mapped
  tipification), covered by the 7-passed suite.

## Key Insight: the PCT adapter is already generic

`MaVoicePctAdapter` contains no MA-specific knowledge:

- `command()` builds `<python> <definition.command[1]> --input <staged base.csv>
  --output_dir <run>/output` — entry point comes from the catalog.
- `outputs()` delegates to the shared role classifier — globs and date formats
  come from the catalog.
- Validation (today-only, no PLANES/PAGOS/no-PLANES) applies to all three
  tipificaciones jobs equally; all are stateless.

Both remaining jobs stage a `.csv` tipificaciones export as `input/base.csv`
and emit one system-dated artifact. Promoting them requires **zero new adapter
code**: two catalog entries reusing the class under new adapter keys
(`naranjax.ma.chat.pct`, `naranjax.mt.voice.pct`).

## Catalog Deltas

| Field | `naranjax.ma.chat.pct` | `naranjax.mt.voice.pct` |
|---|---|---|
| project/working dir | `SOHO-Chat-NX_MA-ETL` | `soho-naranjaX-MT-etl` |
| output | `{role: pct, glob: NARANJAX_PCT_*.csv, date_format: YYYYMMDD}` | `{role: pct, glob: DEELO_NAR_USUEVOLTIS_*.txt, date_format: YYYYMMDD}` |
| everything else | identical to `naranjax.ma.voice.pct` | identical to `naranjax.ma.voice.pct` |

## Options Considered

| Option | Verdict |
|---|---|
| Reuse `MaVoicePctAdapter` under new keys | **Chosen** — zero new behavior, zero new code paths |
| Rename the class to a generic `TipificacionesPctAdapter` | Deferred — pure churn across imports/tests; note left for a future refactor |
| One shared adapter instance across keys | Rejected — per-entry instances keep injection/test seams identical to the existing pattern |
