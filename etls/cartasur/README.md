# CartaSur

## ETLs

| ID | Estado | Descripción |
|---|---|---|
| `cartasur.base.daily` | ✅ operativo | Base de cobranzas diaria (ROMAN + E1KIA) |

## Contrato

- Entrada `base` (requerida): `.xlsx`, `.xlsm` o `.csv` (CSV con `;`, encoding
  `utf-8-sig` con fallback `cp1252`). 11 columnas obligatorias validadas fail-fast
  contra `src/cartasur_etl/config/default_mapping.yaml`.
- Salidas (fecha del sistema, `YYMMDD`):
  - `roman` — `CARTA_SUR_ROMAN_YYMMDD.csv` (UTF-8, coma)
  - `e1kia` — `CARTA_SUR_E1KIA_YYMMDD.csv` (UTF-8, `;`, header `tel_fijo;tel_celular`)
  - Además escribe `validation_report.{csv,json}` en `output/` (no declarados como
    artefactos; quedan en la evidencia del run).
- Adapter propio (`CartaSurAdapter`): la base acepta tres extensiones y el
  `SubprocessAdapter` genérico hardcodea la primera declarada — con un `.csv`
  el subproceso recibiría una ruta inexistente. Sin estado mensual.
- Reglas de negocio (README del legacy): mora 1–10 `PRE_MORA`, 11–30
  `MORA_TEMPRANA` (+3 días hábiles), **mora >30 se excluye y se reporta `NO_CALL`**;
  el seguro nunca suma a `monto_total_ars`. Usa `holidays` (feriados AR, offline).

## Dependencias

Extra `cartasur` en `pyproject.toml`: suma `holidays` al conjunto `etl`.

## Estructura

`manifest.yaml` · `adapter.py` · `job.py` · `legacy/` (no tocar; upstream
`Desktop/Soho-CartaSur`, **sin git** — vendorizado del working tree 2026-08-26,
excluyendo `in/`, `out/`, builds y el fixture `.xlsx` de sus tests) · `tests/`.

El `job.py` no usa la CLI legacy (sin `--cli` abre la GUI customtkinter y su flag
es `--output-dir` con guion): importa la API pública
`cartasur_etl.procesar_dia:procesar_paths` con rutas explícitas del sandbox.

## Contacto

Equipo de operaciones Evoltis (canal CartaSur). Deadline formal: pendiente de
definir con negocio. El README del legacy lista "Riesgos pendientes de validar
con CartaSur".
