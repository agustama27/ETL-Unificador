# Encuesta CX

## ETLs

| ID | Estado | Descripción |
|---|---|---|
| `encuestacx.base.daily` | ✅ operativo | Base de encuestas para n8n/Retell desde export XLSX |

## Contrato

- Entrada `base` (`.xlsx`, requerida) → salidas `survey_base` (`base_encuesta.csv`) y
  `survey_base_e164` (`base_encuesta_e164.csv`, teléfonos normalizados E.164).
- Adapter: `SubprocessAdapter` genérico (`etl_core`). Sin estado mensual.

## Estructura

`manifest.yaml` · `job.py` (CLI puente, valida emails vía `email-validator`) ·
`legacy/` (no tocar) · `tests/` (e2e sintético + job test contra el legacy real).

## Contacto

Equipo de operaciones Evoltis (canal Encuesta CX). Sin deadline formal declarado.
