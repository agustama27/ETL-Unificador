# AGENTS.md — back-cupones

> **Module**: Payment coupon generation (MODULE 4) — **IN PROGRESS / NOT IMPLEMENTED**
> **Read this before**: Starting any implementation work in `back-cupones/`.

---

## Module Purpose

Generate individual payment-coupon files for Bancor clients by filling a VBA-macro Excel template (`.xlsm`). Each coupon is a populated copy of the Bancor-provided template.

**Status**: The core generator (`cupon_generator.py`) is **empty**. The template structure has been analysed and documented. Implementation is pending.

---

## Directory Layout

```
back-cupones/
├── AGENTS.md                          ← You are here
├── template/
│   └── CUPON BANCOR - Template.xlsm  ← VBA-macro template provided by Bancor (read-only)
└── procesos/
    ├── cupon_generator.py             ← EMPTY — core logic to be implemented
    ├── analizar_template.py           ← Utility: inspects .xlsm structure (154 lines)
    └── resumen_campos_template.md     ← Documented field mapping for the template
```

> There is no `main.py`, `requirements.txt`, or `.env` yet — these must be created when implementing.

---

## Template Structure (analysed)

The template `CUPON BANCOR - Template.xlsm` has **4 sheets**:

| Sheet | Purpose |
|-------|---------|
| `CARGA INICIAL` | **Data entry sheet** — write values here |
| `Cobranzas` | Formatted coupon view — auto-populated via Excel formulas (read-only for us) |
| `LETRAS` | Lookup table: numbers → words (used by formulas in `Cobranzas`) |
| `Hoja1` | Branch lookup table (sucursales) |

### Fields to populate in `CARGA INICIAL`

| Field name | Cell | Notes |
|---|---|---|
| `CID` | `D4` | Client ID — currently empty in template |
| `SUCURSAL` | `G4` | Branch number |
| `FECHA_PAGO` | `N9` | Payment date — template has `=TODAY()` formula |
| `CUENTA_CLIENTE` | `T9` | Client account number — currently empty |
| `MODULO` | `B12` | Fixed: `"201- GESTION Y MORA"` |
| `MONEDA` | `N12` | Fixed: `"80 - Pesos"` |
| `NRO_OPERACION` | `B15` | Operation number — currently empty |
| `TIPO_OPERACION` | `J15` | Placeholder: `"Ingresar TIPOOPER"` |
| `PAPEL` | `Q15` | Placeholder: `"Ingresar PAPEL"` |
| `TIPO_DOC` | `B18` | Fixed: `"CUIT"` |
| `CUIL_CUIT` | `G18` | 11-digit CUIT — currently empty |
| `NOMBRE_CLIENTE` | `L18` | Client full name — currently empty |

**Amount fields** (columns `AE`+): Contain formulas; may require numeric input values in rows 8-13.

### Key implementation constraint
- Must use `openpyxl` with `keep_vba=True` to preserve VBA macros when saving
- Writing to a `.xlsm` file requires `openpyxl >= 3.1.0`
- Do NOT overwrite the original template — always copy it first, then populate the copy

---

## Implementation Plan (pending)

When implementing `cupon_generator.py`, follow this approach:

1. **Copy template**: `shutil.copy(template_path, output_path)` — never modify the original
2. **Open copy with VBA**: `load_workbook(output_path, keep_vba=True)`
3. **Write to `CARGA INICIAL` sheet**: Use documented cell addresses from `resumen_campos_template.md`
4. **Handle `TIPO_OPERACION` and `PAPEL`**: Research correct values from Bancor — placeholders currently in template
5. **Save as `.xlsm`**: `wb.save(output_path)` — file extension must be `.xlsm` (not `.xlsx`)
6. **One coupon per client**: Generate a separate file per `NRO_OPERACION`

### Suggested function signature

```python
def generar_cupon(datos_cliente: dict, output_dir: Path) -> Path:
    """
    Generates a payment coupon from the template for a single client.

    Args:
        datos_cliente: dict with keys matching CAMPOS_TEMPLATE (see below)
        output_dir: directory where the generated .xlsm will be saved

    Returns:
        Path to the generated file
    """
```

### Expected `datos_cliente` keys

```python
{
    "CID": str,            # Client ID
    "SUCURSAL": str,       # Branch number
    "CUENTA_CLIENTE": str, # Account number
    "NRO_OPERACION": str,  # Operation number
    "TIPO_OPERACION": str, # TBD — research with Bancor
    "PAPEL": str,          # TBD — research with Bancor
    "CUIL_CUIT": str,      # 11-digit CUIT (no hyphens)
    "NOMBRE_CLIENTE": str, # Full name / company name
    "FECHA_PAGO": str,     # Payment date (YYYY-MM-DD or None to keep =TODAY())
}
```

---

## Utility: `analizar_template.py`

Run this script to inspect the template structure whenever the template changes:

```bash
python back-cupones/procesos/analizar_template.py
```

Output: field names, cell addresses, current values, and formula status for all cells in `CARGA INICIAL`.

---

## Coding Rules (module-specific)

1. **Never overwrite template**: Always copy first with `shutil.copy()`.
2. **Keep VBA**: Open and save with `keep_vba=True` — never use regular `.xlsx` format.
3. **Use documented cell addresses**: Reference `resumen_campos_template.md` for cell coordinates — do not re-derive them.
4. **Output naming**: Suggest `CUPON_{CUIT}_{NRO_OPERACION}_{DATE}.xlsm`.
5. **No classes**: Top-level functions only (consistent with all other modules).
6. **Paths**: `Path(__file__).parent.parent / "template"` — never hardcode absolute paths.
7. **Standalone execution**: `cupon_generator.py` must have its own `if __name__ == "__main__"` block for isolated testing.
8. **Create `main.py`**: When implementing, add a `main.py` at `back-cupones/main.py` following the pattern of the other modules.
9. **Create `requirements.txt`**: At minimum `openpyxl>=3.1.0`. Add more as needed.

---

## Required Skills

Load these skills before implementing this module:

- `feature-implementation` — TDD order, file skeleton, registration steps
- `code-conventions` — naming, imports, formatting
- `data-model` — field contracts, validation rules

---

## Questions Pending (before implementation)

1. What are the valid values for `TIPO_OPERACION` (cell `J15`)? The template shows placeholder `"Ingresar TIPOOPER"`.
2. What are the valid values for `PAPEL` (cell `Q15`)? The template shows placeholder `"Ingresar PAPEL"`.
3. Are the amount fields (`AE8`, `AE9`, etc.) calculated entirely by formulas, or do they need numeric inputs?
4. Should coupons be generated per client or per operation (a client can have multiple `NumeroOperacion`)?
5. What is the output delivery method — email attachment, shared folder, or printed PDF?

> **Before starting implementation**: Clarify these questions with the business owner to avoid rework.

---

## How to Test (once implemented)

```bash
# 1. Run the utility to understand the template
python back-cupones/procesos/analizar_template.py

# 2. After implementing cupon_generator.py, run it standalone:
python back-cupones/procesos/cupon_generator.py

# 3. Verify:
# - Output .xlsm file opens in Excel without errors
# - VBA macros are preserved (enable macros prompt appears)
# - "Cobranzas" sheet shows correctly rendered coupon
# - All data fields are populated with correct values
```
