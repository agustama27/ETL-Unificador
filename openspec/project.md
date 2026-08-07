# Project Context

## Purpose

Plataforma unificada de ejecución, administración y observabilidad de los ETLs de cobranza
de Evoltis. Envuelve ETLs legacy como procesos invocables con sandbox aislado por corrida,
evidencia forense (hash de inputs, stdout/stderr, exit code, artefactos), locking por
período y promoción durable del estado persistente. La lógica de negocio del cliente nunca
vive en el núcleo: queda dentro del proyecto legacy (`SOHO-*`, `soho-*`), que no se modifica.

## Tech Stack

- Python 3.12+ (núcleo `orchestrator/`, adapters, API)
- FastAPI + Uvicorn (`platform_api/`)
- React + Vite + TypeScript (`frontend/`)
- PyYAML para el catálogo declarativo (`registry/*.yaml`)
- pandas + openpyxl sólo en los ETLs legacy (extra `etl`; `naranjax` es alias legado)
- pytest (unit por capa + 13 e2e por ETL)
- Docker / docker-compose; CI en Bitbucket Pipelines (Linux, Python 3.12)

## Project Conventions

Extraídas de `docs/ARQUITECTURA.md` §8. Respetarlas al agregar código.

### Code Style

- Python 3.12+: `StrEnum`, `Self`, `X | None`, `is_relative_to`.
- Inmutabilidad: modelos `@dataclass(frozen=True)`; mapas envueltos en `MappingProxyType`
  en `__post_init__`.
- Sin comentarios decorativos; docstring de una línea cuando el nombre no alcanza.
- Nombres del dominio en inglés en el código; mensajes de usuario en español (la API la
  consume el equipo de operaciones).

### Architecture Patterns

- Cuatro capas: interfaces (CLI/API/UI) → núcleo orquestador → adapters por cliente →
  legacy por subprocess. El núcleo sólo conoce archivos, procesos, estados y evidencia.
- Inyección de dependencias por constructor con default (`Runner(popen=...)`,
  `StateStore(replace=...)`): el núcleo se testea sin tocar disco.
- Excepciones con atributo `code` (`RunBlockedError`, `StatePromotionError`); los códigos
  terminan en `run.json` y se documentan en `docs/ARQUITECTURA.md` §3.
- Nada de `except Exception` genérico en el núcleo; sólo tipos concretos. Única excepción
  documentada: la frontera fail-fast de los `*_job.py`.
- Arquitectura objetivo: hexagonal con adapters descubribles (`docs/ADR-001-nucleo-hexagonal.md`).

### Testing Strategy

- `tests/orchestrator`, `tests/adapters`, `tests/api`: unit por capa.
- `tests/e2e`: 13 tests, uno por ETL, de punta a punta. Son la red de seguridad ante
  refactors: deben pasar **sin modificarse**. Si un refactor obliga a tocar un e2e, se
  cambió comportamiento observable.

### Git Workflow

- Ramas `feature/*` sobre `main`; conventional commits.
- Nunca commitear datos reales: `.csv`, `.xlsx`, `.xls`, `.env`, outputs ni `var/`
  (contienen PII).

## Domain Context

ETLs diarios/mensuales de cobranza por cliente (Naranja X, Bancor, Petersen, EPEC,
Frávega, Claro UY, Encuesta CX, Social Learning). Los ETLs con estado leen/escriben un
acumulado mensual; la promoción publica snapshot del día + estado corriente del mes de
forma durable, y ante una promoción a medias el ETL/mes queda bloqueado (`recovery.json`)
hasta intervención humana.

## Important Constraints

- **`SubprocessAdapter` (etl_core) es compartido por 10 ETLs de seis clientes** (bases de
  Bancor, EPEC, Frávega, Claro UY, Encuesta CX, Social Learning AR/CL y los PCT de
  Naranja X). Tocarlo exige correr los 13 e2e. Ver ADR-001, decisión 2.
- Los legacy (`etls/*/legacy/`) no se modifican; se invocan por subprocess.
- Sólo se acepta `business_date == hoy` (los legacy estampan la fecha del sistema).
- La API no está endurecida: sin autenticación ni recuperación ante reinicio (Fase 4).

## External Dependencies

- Retell.ai: varios ETLs (`executable: false`) esperan credenciales de su API; los motivos
  legibles están en `platform_api/catalog_meta.py` (`INERT_REASONS`).
