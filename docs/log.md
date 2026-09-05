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
