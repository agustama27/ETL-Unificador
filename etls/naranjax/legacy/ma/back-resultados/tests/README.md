# Tipificaciones IA Voz PCT tests

## Automated validation

- `python -m pytest back-resultados/tests -q`
- `python -m unittest discover -s back-resultados/tests -p "test_*.py"`

Pass criteria:
- all tests green;
- output contract validated (`NARANJAX_PCT_YYYYMMDD.csv`, pipe-separated, header with 7 columns, ANSI cp1252, LF);
- output header is `DNI|TIPIFICACION|NROPRODUCTO|FECHA_PROMESA|MONTO_PROMESA|CALL_REFID|OBSERVACIONES`;
- output rows do not use quote wrapping;
- `OBSERVACIONES` is hard-capped to `1500` chars in output rows;
- `OBSERVACIONES` replaces `|`, `\\`, and `""` with spaces before applying the 1500-char cap;
- cardinality rules for PURO and ECOSISTEMICO verified;
- hard-fail behavior for missing required source columns verified.

## Manual smoke command

```bash
python back-resultados/etl_tipificaciones_ia_voz_pct.py --output_dir back-resultados/base-generada
```

Default input behavior:
- if `--input` is omitted, the process creates/uses `back-resultados/roman/`;
- it picks the most recently modified file with extension `.csv`, `.xlsx`, or `.xls` from that folder;
- if no file exists in `roman/`, execution fails with a clear error.

Explicit input still works:

```bash
python back-resultados/etl_tipificaciones_ia_voz_pct.py --input back-resultados/tests/fixtures/historial_todos_tipos.csv --output_dir back-resultados/base-generada
```

Expected artifact path pattern:
- `back-resultados/base-generada/NARANJAX_PCT_YYYYMMDD.csv`
