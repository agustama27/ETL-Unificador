---
name: ui-pipeline-sync-guard
description: "Trigger: cambios en UI, worker, rutas de procesamiento, back-base, back-resultados, rebuild. Garantiza que la UI ejecute exactamente los mismos pipelines oficiales que CLI/procesos."
license: Apache-2.0
metadata:
  author: gentleman-programming
  version: "1.0"
---

## Activation Contract

Usar esta skill cuando se modifique cualquier parte de UI o wiring de ejecucion (`ui/app.py`, `ui/screens/*`, `ui/worker.py`) o cuando cambie la logica en `procesos/*` para `back-base` o `back-resultados`.

## Hard Rules

1. UI y CLI deben invocar la MISMA funcion de pipeline por dominio. No duplicar logica.
2. `back-base` en UI debe ejecutar el mismo flujo que CLI principal (`procesar_base` + `extraer_telefonos` via `core/procesar_dia.py`).
3. `back-resultados` en UI debe ejecutar el mismo flujo que `python main.py --back` (funcion `procesos.back_resultados.procesar`).
4. Si hay dos implementaciones para el mismo dominio, una debe eliminarse o quedar fuera del flujo productivo.
5. Cualquier cambio de naming/formato de salida debe aplicarse en el pipeline oficial, no solo en UI.

## Decision Gates

| Situacion | Accion obligatoria |
|---|---|
| Cambio solo visual (labels, tabs, botones) | Verificar que no se rompa wiring de worker y que mantenga pipeline oficial |
| Cambio en `ui/worker.py` | Confirmar imports y funcion llamada por cada pestaña |
| Cambio en `procesos/back_resultados.py` o `core/procesar_dia.py` | Verificar UI y CLI con mismos resultados para mismo input |
| Bug report "UI difiere de CLI" | Bloquear release hasta alinear UI al pipeline oficial |

## Execution Steps

1. Mapear rutas de ejecucion por pestaña:
   - `back-base/`: `WorkerThread` -> `core.procesar_dia.procesar_dia`
   - `back-resultados/`: `BackResultadosWorkerThread` -> `procesos.back_resultados.procesar`
2. Verificar que `main.py --back` use la misma funcion que `back-resultados/` en UI.
3. Ejecutar chequeo rapido de compilacion:
   - `python -m py_compile ui/worker.py ui/screens/principal.py core/procesar_dia.py procesos/back_resultados.py`
4. Rebuild de ejecutable:
   - `packaging\build.bat`
5. Si falla por lock de `.exe`, cerrar proceso y reintentar build.

## Output Contract

- Informar funcion oficial usada por cada pestaña.
- Informar archivos tocados por la alineacion.
- Confirmar estado del rebuild y ruta del `.exe`.

## References

- `main.py`
- `ui/worker.py`
- `core/procesar_dia.py`
- `procesos/back_resultados.py`
