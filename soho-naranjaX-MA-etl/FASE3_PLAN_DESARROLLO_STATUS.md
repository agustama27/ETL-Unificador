# Fase 3 - Status actualizado

Fuente: `FASE3_PLAN_DESARROLLO.md` + estado real de codigo/tests del repo.

## 1) Resumen ejecutivo

- **Semaforo general: AMARILLO.** Fase 3 quedo tecnicamente estable en `back-base` y `back-resultados`; el unico pendiente bloqueante funcional sigue siendo D4 (negocio).
- **Implementado y validado:** estado mensual + snapshot diario, exclusion persistente por `RECUPERO=SI`, filtro de scope M90 para ROMAN, logs diarios, movimiento de insumos a procesados, normalizacion telefonos con sufijo Excel `.0`, y salida ROMAN sin `recupero/tipo_pago` (D3 aplicado tecnicamente de forma temporal).
- **Pendiente principal:** cierre de negocio D4 (mapa completo de tipificaciones en `back-resultados`) y confirmaciones funcionales finales (D2/D3).
- **Riesgo tecnico de colision `etl`: RESUELTO (definitivo).** Se elimino la colision de imports con separacion estructural de namespaces (`back_base_etl` y `back_resultados_etl`) y ya se valida corrida conjunta.

## 2) Checklist del plan original

### Tareas del plan

- [x] **TAREA 1 - Filtros de negocio (implementacion tecnica):** existe `aplicar_filtros()` con scope por cajon y exclusion `RECUPERO=SI` en `update_estado()`.
- [x] **TAREA 2 - Estado persistente diario:** `inicializar_estado()`, `cargar_estado()`, `guardar_estado()` con snapshot inmutable.
- [x] **TAREA 3 - Orquestador diario simplificado:** `back-base/ejecutar_dia.py` operativo y `ejecutar_dia.bat` para uso diario.
- [ ] **TAREA 4 - Schema final ROMAN (D3):** aplicado temporalmente excluyendo `recupero/tipo_pago` del ROMAN; falta confirmacion final de negocio para cierre definitivo.
- [ ] **TAREA 5 - Mapa tipificaciones completo (D4):** aun incompleto (siguen codigos placeholder en `back-resultados`).

### Criterios de aceptacion Fase 3

- [x] `python ejecutar_dia.py` sin argumentos soportado por defaults del script.
- [x] Movimiento automatico a `diarios/procesados/YYYYMMDD/` implementado.
- [x] Estado mensual acumulado en `estados/estado_YYYYMM.csv` implementado.
- [x] Snapshot diario inmutable `estados/estado_YYYYMMDD.csv` implementado.
- [x] `RECUPERO=SI` excluido del estado persistente y de ROMAN posteriores.
- [x] Filtro de cajon en ROMAN aplicado (scope actual: `M90`).
- [ ] Mapa tipificaciones completo para todos los resultados IA (pendiente D4).
- [x] `pytest back-base/tests/ back-resultados/tests/` en una sola corrida (30 passed) tras resolver colision de imports.
- [x] Log diario con deteccion, resumen de filas/exclusiones y paths de salida.

## 3) Cambios y mejoras implementadas

- **Estado persistente:** se incorporo almacenamiento de estado vigente mensual y snapshots diarios inmutables para rollback manual.
- **Filtro M90:** se filtra el ROMAN por cajones en scope (default actual `("M90",)`), excluyendo cajones fuera de mora avanzada.
- **Ejecucion diaria:** se agrego orquestador diario con deteccion de archivos, carga de estado, update, filtro, salida ROMAN y guardado de estado.
- **Logs diarios:** se registra un log por fecha (`YYYYMMDD.log`) con inicio, archivos detectados, resumen y estado final.
- **Movimiento a procesados:** al finalizar exitosamente mueve insumos diarios a carpeta particionada por fecha; en fallo no los mueve.
- **Normalizacion telefonos `.0`:** se corrige el caso de valores exportados por Excel con sufijo `.0` para conservar telefono valido.
- **D3 aplicado (temporal):** el ROMAN excluye `recupero` y `tipo_pago` del CSV final, manteniendolos para logica interna/estado.
- **Limpieza `back-update-base`:** no existe directorio `back-update-base/`; la operacion quedo consolidada en `back-base/`.
- **Resolucion estructural de imports:** se desambiguaron namespaces Python para evitar colision historica de `etl` entre modulos.
- **Namespaces nuevos:** `back_base_etl` (base) y `back_resultados_etl` (resultados) reemplazan la dependencia implicita de `from etl...`.
- **Compatibilidad/transicion:** `from etl...` pasa a considerarse breaking change para consumidores externos; se requiere migracion explicita de imports al nuevo namespace segun modulo.
- **Validacion post-cambio:** `pytest back-base/tests -q` (21 passed), `pytest back-resultados/tests -q` (9 passed), `pytest back-base/tests back-resultados/tests -q` (30 passed), y smoke de CLI `--help` en ambos modulos OK.

## 4) Evidencia tecnica por punto

- **Estado persistente:** `back-base/etl/estado_persistente.py`, `back-base/tests/test_estado_persistente.py`.
- **Exclusion RECUPERO=SI en estado:** `back-base/etl/update_estado.py`, `back-base/tests/test_update_estado.py`.
- **Filtro M90 en ROMAN:** `back-base/etl/filtros.py`, `back-base/tests/test_ejecutar_dia_integration.py`.
- **Ejecucion diaria y orquestacion:** `back-base/ejecutar_dia.py`, `ejecutar_dia.bat`, `back-base/tests/test_ejecutar_dia_integration.py`.
- **Logs diarios:** `back-base/ejecutar_dia.py` (configuracion y summary), `back-base/tests/test_ejecutar_dia_integration.py`.
- **Movimiento a procesados:** `back-base/ejecutar_dia.py`, `back-base/tests/test_ejecutar_dia_integration.py`.
- **Normalizacion telefonos `.0`:** `back-base/etl/cleaners.py`, `back-base/tests/test_phone_cleaning.py`.
- **D3 temporal (schema ROMAN):** `back-base/etl/constants.py`, `back-base/tests/test_ejecutar_dia_integration.py`, `README_ETL.md`.
- **Tipificaciones pendientes D4:** `back-resultados/etl/constants.py`, `back-resultados/tests/test_tipificaciones_mapping.py`.
- **Limpieza `back-update-base`:** `README_ETL.md` (estructura consolidada en `back-base/`) + verificacion de estructura actual del repo (sin `back-update-base/`).
- **Resolucion de colision de imports / namespaces:** migracion estructural a `back_base_etl` y `back_resultados_etl` + validacion de ejecucion conjunta de tests y smoke de CLI help.

## 5) Pendientes

### Pendientes tecnicos opcionales

- Agregar test unitario explicito de `aplicar_filtros()` con resumen de exclusiones por motivo.
- Evaluar exponer scope de cajones como config (env/flag) para evitar hardcode operativo de `M90`.
- Completar transicion de consumidores que aun usen `from etl...` hacia `back_base_etl` o `back_resultados_etl` segun corresponda.

### Pendientes de negocio (D4 y confirmaciones finales)

- **D4 (bloqueante funcional):** validar con cliente el mapa completo de tipificaciones y actualizar `back-resultados/etl/constants.py`.
- **D2:** confirmar scope final de mora avanzada (`M90` solo vs `M90/M120/M150`) para fijar filtro definitivo.
- **D3:** confirmar si exclusion de `recupero/tipo_pago` en ROMAN queda definitiva o vuelve al schema publico.

## 6) Semaforo y proximos pasos recomendados

- **Semaforo:** **AMARILLO**.
  - **Verde:** core operativo Fase 3 en `back-base` + `back-resultados` funcionando y probado; colision tecnica de imports `etl` resuelta en forma definitiva.
  - **Amarillo:** decisiones de negocio abiertas (D2/D3/D4), con D4 aun bloqueante funcional.
  - **Rojo:** no se observan bloqueantes tecnicos severos para operacion diaria actual.

**Proximos pasos recomendados (orden):**
1. Cerrar D4 con negocio y actualizar mapa de tipificaciones + tests de `back-resultados`.
2. Confirmar D2/D3 y ajustar filtro/salida ROMAN si corresponde.
3. Completar migracion/comunicacion de compatibilidad para imports legacy `from etl...` en integraciones externas.
