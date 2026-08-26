# Alvarez Maquinarias

## ETLs

| ID | Estado | Descripción |
|---|---|---|
| `alvarez.cobranzas.daily` | ✅ operativo | Cobranzas diaria: deuda USD consolidada por cliente (ROMAN + E1KIA) |

## Contrato

- Entradas (las 4 requeridas, exports de Autologica):
  - `base` — saldos generales (`.xls` o `.csv`; el `.xls` trae ~91% de cobertura telefónica vs ~44% del `.csv`)
  - `maquinarias` — maquinarias vendidas (`.xlsx`)
  - `servicios` — remitos de servicios (`.xlsx`)
  - `repuestos` — remitos de repuestos (`.pdf`)
- Salidas (fecha del sistema, `YYMMDD`):
  - `roman` — `ALVAREZ_MAQUINARIAS_ROMAN_YYMMDD.csv` (gestión; `;`, UTF-8 sin BOM, CRLF)
  - `e1kia` — `ALVAREZ_MAQUINARIAS_E1KIA_YYMMDD.csv` (marcador; única columna `TelefonoCliente`)
- Adapter propio (`AlvarezMaquinariasAdapter`): multi-input requerido y doble extensión
  en saldos, cosas que el `SubprocessAdapter` genérico no admite. Sin estado mensual.
- Invariantes del legacy: solo deuda USD, paridad de teléfonos ROMAN↔E1KIA verificada
  antes de escribir, sin salidas parciales.

## Dependencias

Extra `alvarezmaquinarias` en `pyproject.toml`: suma `xlrd` (saldos `.xls`) y `pypdf`
(remitos de repuestos) al conjunto `etl`.

## Estructura

`manifest.yaml` · `adapter.py` · `job.py` · `legacy/` (no tocar; upstream
`soho-Alvarez-Maquinarias-ETL`, vendorizado desde `main@e5a0e2d` 2026-08-21) ·
`tests/` (e2e sintético + contrato de adapter + job real).

El `job.py` no invoca `main.py` del legacy (ancla particiones `inputs/<fecha>/` a su
propio `__file__`): construye el `PipelineConfig` público con las rutas staged del
sandbox y corre `run_pipeline` fail-fast.

## Contacto

Equipo de operaciones Evoltis (canal Alvarez Maquinarias). Deadline formal: pendiente
de definir con negocio.
