# Fase 2 - Estado de Implementacion

Fuente: `FASE2_PLAN_DESARROLLO.md` + revision de codigo/tests en repo.

## Acta de Avance - Semaforo

- Estado general del proyecto: **AMARILLO**. La implementacion tecnica de Fase 2 esta mayormente completada y validada por tests, pero quedan 3 definiciones funcionales de cliente que impactan reglas finales de salida.
- Bloques en **VERDE** (completado): carga de diarios (`planes`/`pagos`), pivot de planes con columnas dinamicas, merge `update_estado()`, orquestacion CLI, contrato de salida actualizado y suite de tests en verde.
- Bloques en **AMARILLO** (pendiente de definicion o riesgo): regla de exclusion por `RECUPERO=SI`, precedencia final de `CAJON_ACTUAL_PROD` vs `CAJON`, y confirmacion de si `recupero`/`tipo_pago` quedan en schema final.
- Bloques en **ROJO**: sin bloqueantes rojos actuales.

## Proximas decisiones (cliente/negocio)

1. Definir regla de negocio para `RECUPERO=SI` (exclusion vs inclusion en ROMAN).
2. Confirmar precedencia funcional final para `CAJON_ACTUAL_PROD` (pagos) frente a `CAJON` (planes).
3. Confirmar alcance de campos `recupero` y `tipo_pago` en salida final (schema publico vs uso interno).

## Checklist de tareas del plan

### TAREA 1 - `io.py`: carga de archivos diarios
- [x] `load_planes()` implementado (hoja `default_1`, normalizacion lowercase, validacion de columnas requeridas, log de filas).
  - Evidencia: `back-base/etl/io.py`, `back-base/etl/validators.py`.
- [x] `load_pagos()` implementado (CSV `;`, normalizacion lowercase, validacion de columnas requeridas, log de filas).
  - Evidencia: `back-base/etl/io.py`, `back-base/etl/validators.py`.

### TAREA 2 - Pivot de planes
- [x] Modulo `pivot_planes()` implementado con una fila por `nroproducto` y columnas dinamicas `plan_N_*`.
  - Evidencia: `back-base/etl/planes_pivot.py`.
- [x] Orden de planes por menor cantidad de cuotas implementado.
  - Evidencia: `back-base/etl/planes_pivot.py`, `back-base/tests/test_planes_pivot.py`.
- [x] Exclusion de `CAJON=CAN` implementada.
  - Evidencia: `back-base/etl/planes_pivot.py`, `back-base/tests/test_planes_pivot.py`.
- [x] Generacion dinamica de columnas de plan implementada via helper.
  - Evidencia: `back-base/etl/constants.py:get_plan_column_names`, `back-base/etl/planes_pivot.py`.

### TAREA 3 - `update_estado()`: merge de base + planes + pagos
- [x] `update_estado()` implementado con precedencia de montos/cajon desde planes y campos `recupero`/`tipo_pago` desde pagos.
  - Evidencia: `back-base/etl/update_estado.py`, `back-base/tests/test_update_estado.py`.
- [x] Warning para filas base sin match en planes implementado.
  - Evidencia: `back-base/etl/update_estado.py`, `back-base/tests/test_update_estado.py`.

### TAREA 4 - `constants.py`: columnas nuevas
- [x] `OUTPUT_COLUMNS_PHASE2_FIXED`, `PLAN_COLUMN_PATTERN`, `PLAN_FIELDS`, `OUTPUT_FILENAME_ROMAN`, `PLANES_REQUIRED_COLUMNS`, `PAGOS_REQUIRED_COLUMNS` implementadas.
  - Evidencia: `back-base/etl/constants.py`.

### TAREA 5 - `transformers.py`: adaptacion de transform
- [x] `transform()` adaptado para recibir `plan_columns` y emitir columnas `recupero`, `tipo_pago` y planes dinamicos.
  - Evidencia: `back-base/etl/transformers.py`.

### TAREA 6 - `etl_naranjax.py`: orquestador actualizado
- [x] CLI actualizado con `--planes` y `--pagos` opcionales.
  - Evidencia: `back-base/etl_naranjax.py`.
- [x] Flujo completo implementado: carga -> pivot -> update_estado -> transform -> save.
  - Evidencia: `back-base/etl_naranjax.py`, `back-base/tests/test_cli_phase2_integration.py`.
- [x] Compatibilidad hacia atras sin diarios implementada.
  - Evidencia: `back-base/etl_naranjax.py`, `back-base/tests/test_cli_phase2_integration.py`.

### TAREA 7 - Tests
- [x] `test_planes_pivot.py` creado y validando orden/exclusion/dinamica de columnas.
  - Evidencia: `back-base/tests/test_planes_pivot.py`.
- [x] `test_update_estado.py` creado y validando precedencia/warnings.
  - Evidencia: `back-base/tests/test_update_estado.py`.
- [x] Contrato de salida actualizado (`golden_output_header.txt` incluye `recupero` y `tipo_pago`).
  - Evidencia: `back-base/tests/golden_output_header.txt`, `back-base/tests/test_relocation_contract.py`.
- [x] Prueba de integracion Fase 2 con diarios agregada.
  - Evidencia: `back-base/tests/test_cli_phase2_integration.py`.
- [ ] Fixtures solicitados en el plan con nombre exacto (`planes_sample.xlsx`, `pagos_sample.csv`) no existen con esa nomenclatura.
  - Evidencia: existen equivalentes `back-base/tests/fixtures/diario_planes_phase2.*` y `back-base/tests/fixtures/diario_pagos_phase2.csv`.

## Checklist de criterios de aceptacion

- [x] ROMAN generado con una fila por cliente en flujo con diarios.
  - Evidencia: diseño de `pivot_planes()` + `update_estado()` y validaciones en `back-base/tests/test_cli_phase2_integration.py`.
- [x] Montos `monto_deuda_total_ars` y `monto_total_vencido_ars` vienen de planes cuando hay match.
  - Evidencia: `back-base/tests/test_cli_phase2_integration.py`, `back-base/tests/test_update_estado.py`.
- [x] Cantidad de columnas de plan dinamica (no hardcodeada).
  - Evidencia: `back-base/etl/constants.py:get_plan_column_names`, `back-base/etl/planes_pivot.py`, `back-base/tests/test_planes_pivot.py`.
- [x] Planes ordenados de menor a mayor cuotas.
  - Evidencia: `back-base/etl/planes_pivot.py`, `back-base/tests/test_planes_pivot.py`.
- [x] Clientes con `CAJON=CAN` excluidos.
  - Evidencia: `back-base/etl/planes_pivot.py`, `back-base/etl/update_estado.py`, `back-base/tests/test_planes_pivot.py`, `back-base/tests/test_cli_phase2_integration.py`.
- [x] Sin archivos diarios mantiene compatibilidad hacia atras.
  - Evidencia: `back-base/tests/test_cli_phase2_integration.py::test_cli_phase2_without_diarios_keeps_monthly_contract`.
- [x] Todos los tests pasan en `pytest back-base/tests/`.
  - Evidencia: corrida local realizada (8 passed).
- [x] Golden header actualizado con columnas nuevas fijas de Fase 2.
  - Evidencia: `back-base/tests/golden_output_header.txt`.

## Preguntas pendientes con cliente (siguen abiertas)

- [ ] Definir si `RECUPERO=SI` excluye o no del ROMAN.
  - Evidencia: no hay regla de exclusion en `back-base/etl/update_estado.py`.
- [ ] Confirmar precedencia final de `CAJON_ACTUAL_PROD` (pagos) vs `CAJON` (planes).
  - Evidencia: implementado actualmente con prioridad de planes en `back-base/etl/update_estado.py`.
- [ ] Confirmar si `recupero` y `tipo_pago` deben quedar en schema final ROMAN o solo uso interno.
  - Evidencia: hoy se incluyen en salida via `back-base/etl/constants.py` y `back-base/etl/transformers.py`.

## Pendientes criticos para cierre de Fase 2

1. Cerrar definiciones funcionales con cliente sobre `RECUPERO`, precedencia de cajon y schema final (impacta reglas de negocio definitivas).
2. Alinear nomenclatura de fixtures con el plan (o actualizar plan para reflejar nombres reales usados en tests).
3. (Opcional de robustez) agregar test explicito de "sin duplicados" por `id_nro_producto` en salida para reforzar criterio de aceptacion.
