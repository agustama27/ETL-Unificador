# Bitácora

Append-only, cronológico, lo más nuevo abajo. Cada línea linkea al cuadrante donde quedó el
hecho vigente: el log dice qué pasó, la documentación dice qué es.

Formato: `## [YYYY-MM-DD] <op> | <tema>`. Grepeable con `grep '^## \[' docs/log.md`.

## [2026-09-05] update | adopción de ADR-ARC-022

- La documentación pasa a cuadrantes Diátaxis. Se movieron nueve archivos con `git mv`, sin
  reescribir contenido → [index.md](index.md)
- Los dos documentos de planificación que vivían en la raíz del repo
  (`01_objetivo_proyecto_etl_unificador.md`, `02_primer_paso_planificacion_agente_codigo.md`)
  pasan a `reports/`: son constancia fechada, no documentación vigente →
  [reports/01-objetivo-proyecto.md](reports/01-objetivo-proyecto.md)
- Se actualizaron los links entrantes en `README.md`, `AGENTS.md`, los `README` de `etls/` y un
  docstring de test, en vez de dejar stubs. El repositorio es autocontenido y no hay links
  entrantes externos que preservar → [index.md](index.md)
- `openspec/` queda deliberadamente sin tocar y sin catalogar: sus referencias a las rutas
  viejas son parte de un registro histórico → [index.md](index.md)

## [2026-09-05] update | adopción de uv (ADR-ARC-003)

- Las dependencias pasan a `uv` con `uv.lock` versionado como fuente de verdad. El entorno
  pip queda reemplazado → [reference/comandos.md](reference/comandos.md)
- Las dependencias del camino de datos pasan de rango a versión exacta. Motivo: la paridad
  byte a byte no cubre el drift de dependencias, porque corre los dos lados con el mismo
  intérprete → [explanation/paridad-upstream.md](explanation/paridad-upstream.md)
- `numpy` sube de 2.4.0 a 2.4.6: la 2.4.0 que estaba instalada está *yanked* en PyPI por un
  bug de compatibilidad hacia atrás. Verificado con sha256 de los 9 artefactos de Bancor y
  CartaSur: idénticos → [explanation/paridad-upstream.md](explanation/paridad-upstream.md)
- `xlwt` y `reportlab` estaban instalados pero sin declarar: los tests de Alvarez, incluida
  su paridad, se salteaban en un entorno limpio. Ahora están en el extra `test` →
  [explanation/paridad-upstream.md](explanation/paridad-upstream.md)
- Entran `Taskfile.yml`, `ruff`, `.coveragerc` y `sonar-project.properties`. El ruleset de
  ruff es el default; `DTZ` queda afuera a propósito → [reference/comandos.md](reference/comandos.md)
