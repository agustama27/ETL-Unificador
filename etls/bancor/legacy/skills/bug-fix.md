# Skill: bug-fix

> Load this skill when investigating and fixing bugs in this project.

---

## Investigation Sequence

Follow these steps in order. Do not skip steps.

### Step 1 — Reproduce the bug
Before writing any code, confirm you can reproduce the error:
```bash
python back-<module>/main.py
# Or run the specific procesos/ file:
python back-<module>/procesos/<file>.py
```
Note the exact error message, line number, and stack trace.

### Step 2 — Read the relevant `AGENTS.md`
- Root `AGENTS.md` for cross-module issues
- Module `AGENTS.md` for module-specific issues
- Note the "Common Issues" section — the bug may already be documented there

### Step 3 — Load relevant skills
- Always load `code-conventions` for style compliance
- Load `data-model` if the bug involves CSV columns, field types, or encoding
- Do not refactor unrelated code while fixing

### Step 4 — Read the source files
Use the Read tool to read the exact file and line mentioned in the traceback. Do not guess — evidence only.

### Step 5 — Find the minimal fix
Apply the smallest possible change that fixes the bug without:
- Refactoring unrelated functions
- Changing output formats or column names
- Altering the encoding chain
- Modifying config files unless the bug is in config

### Step 6 — Verify the fix
```bash
python back-<module>/main.py
```
Confirm the error is gone and the output files are generated correctly.

---

## Common Bug Patterns in This Project

### Encoding errors
**Symptom**: `UnicodeDecodeError` when reading Bancor CSVs
**Fix**: Ensure the encoding chain is `['latin-1', 'iso-8859-1', 'cp1252', 'utf-8', 'utf-16']` in that order. See `leer_csv_con_codificacion()` pattern in `code-conventions.md`.

### European decimal parsing
**Symptom**: `OFERTA_Importe` or `MontoAdeudado` filter removes all rows
**Fix**: Before `pd.to_numeric()`, replace `,` with `.`:
```python
df['MontoAdeudado'] = pd.to_numeric(
    df['MontoAdeudado'].astype(str).str.replace(',', '.', regex=False),
    errors='coerce'
)
```

### Retell API field not found
**Symptom**: Column in output CSV is always empty
**Fix**: Check if field name changed in Retell API. Run `buscar_campo_recursivo(payload, 'field_name')` on a raw API response to confirm the field exists.

### ROMAN merge matches nothing
**Symptom**: `MergeStats.matched == 0` despite having ROMAN data
**Fix**: Compare `call_id` values between Retell and ROMAN CSVs. Common cause: `call_id` in ROMAN has `"call_"` prefix stripped, or whitespace differences. Normalize with `.str.strip()` before merging.

### CRM state validation failures
**Symptom**: All records discarded by `validador.py`
**Fix**: Check if `ESTADO` values from Retell match keys in `MAPEO_ESTADOS_RETELL_A_CRM`. Add new mappings to `config_catalogos.py` if Retell introduced new state names.

### Path not found errors
**Symptom**: `FileNotFoundError` for `calls/`, `roman/`, or `base-recibida/`
**Fix**: Check that the working directory when running is the repo root (`soho-bancor-cobranzas-etl/`). Always run as `python back-<module>/main.py` from repo root, not from inside the module directory.

### `Sub- Estado` KeyError
**Symptom**: KeyError on `"Sub- Estado"` when building CRM DataFrame
**Fix**: The column has a space before "Estado". This is intentional — `"Sub- Estado"` not `"Sub-Estado"`. Do not rename it.

---

## Minimal-Change Discipline

When fixing a bug:

| DO | DON'T |
|----|-------|
| Fix the single failing function | Refactor the whole file |
| Add only the missing dict key in config | Restructure config_catalogos.py |
| Fix the encoding in one function | Change encoding across all modules |
| Correct the column name in one place | Rename columns across the pipeline |

---

## Testing the Fix

Since there is no automated test suite, manual verification is required:

1. Run the affected module's `main.py`
2. Check that output files exist and have the correct row count
3. Open the output CSV/XLSX and verify the previously failing column now has values
4. Check the console output for error counts (should be 0 or reduced)

If the bug is in a `procesos/` file, test it standalone first:
```bash
python back-cargaMasiva/procesos/mapeador.py
# Output from its __main__ block should show correct mapping
```
