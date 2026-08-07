# Skill: phone-csv-compare

> Load this skill when you need to compare phone numbers between two CSV files and detect numbers present in source but missing in target.

---

## Purpose and Scope

Use this skill to validate phone coverage between two datasets (for example, two Bancor exports) while handling Argentine prefixes.

Apply it when you need to:
- Detect numbers present in file A and missing in file B
- Compare phone numbers despite formatting differences
- Treat `549` (mobile) and `54` (landline/international prefix) as equivalent to local variants

---

## Execution Pattern

Run the reusable utility:

```bash
python back-base/procesos/phone_csv_compare.py \
  --source "<path/source.csv>" \
  --target "<path/target.csv>" \
  --output "<path/faltantes.csv>"
```

Optional explicit columns:

```bash
python back-base/procesos/phone_csv_compare.py \
  --source "<path/source.csv>" \
  --target "<path/target.csv>" \
  --source-column "NumeroCelular" \
  --target-column "NumeroCelular"
```

If columns are not provided, the script auto-detects candidate phone columns by name (`telefono`, `celular`, `phone`, `tel`, `movil`, `móvil`, etc.) and uses all candidates.

---

## Matching Rules

For each phone value:
1. Keep digits only
2. Build equivalence set:
   - If starts with `549`, also include the same number without `549`
   - Else if starts with `54`, also include the same number without `54`
3. Compare source vs target using normalized equivalence sets

A source number is considered missing only if none of its normalized equivalents exists in target.

---

## Input/Output and Validation

- Read CSV with separator `;`
- Use project encoding fallback chain for reading:

```python
['latin-1', 'iso-8859-1', 'cp1252', 'utf-8', 'utf-16']
```

- If all fail, fallback to `errors='replace'`
- Print clear console summary:
  - total source values
  - total target values
  - total missing values (unique + occurrences)
  - example missing numbers
- If `--output` is provided, write missing results as `;`-separated UTF-8 CSV
