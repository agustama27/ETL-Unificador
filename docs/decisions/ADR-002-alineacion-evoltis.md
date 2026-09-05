# ADR-002 — Alineación con el scaffolding de Evoltis y modelo de ejecución en Kubernetes

- **Estado:** aceptado
- **Fecha:** 2026-09-05
- **Ámbito:** estructura del repositorio, empaquetado, y cómo corre un ETL en el cluster
- **Gobierna:** ADR-ARC-002 (scaffolding), ADR-ARC-003 (uv), ADR-ARC-022 (documentación),
  ADR-DEV-001 (branching)

## Contexto

El ETL Unificador se despliega en el cluster de Evoltis. Eso obliga a adoptar el scaffolding
corporativo, y obliga a decidir algo que el scaffolding no cubre: **este repositorio no es un
microservicio**, es una capa de ejecución sobre 25 ETLs legacy de clientes que corren como
subprocesos.

Los ADRs corporativos asumen un servicio que atiende requests. Acá hay un servicio que atiende
requests **y además lanza procesos de hasta una hora** que escriben archivos.

Al momento de escribir esto, ARC-002, ARC-003 y ARC-022 están en estado **Draft**, sin
aprobación formal de Arquitectura. Se adoptan igual porque los dos repositorios de referencia
—`pandape-scraper-api` y `bcra-scraper-api`— ya los implementan en `develop`: son el estándar
de hecho.

## Decisión 1 — `etls/` es una carpeta de primer nivel, fuera de `apps/`

`apps/` es, según ARC-002, la raíz de los **procesos desplegables en Kubernetes**. Los ETLs de
`etls/<cliente>/` no lo son: no tienen imagen, no tienen puerto, y el orquestador los invoca
como subprocesos. Tampoco son `apps/commons/`, que ARC-002 define como código compartido
**nuestro**: son árboles vendorizados de los clientes, con su propia historia y su propio
upstream.

ARC-002 admite carpetas especializadas mientras no dupliquen un rol ya definido. `etls/` no
duplica ninguno.

**Alternativa descartada:** `apps/etl-<cliente>/`, una carpeta por cliente. Daría 25 entradas
en `apps/` que ningún pipeline construye, y sugeriría que cada una es desplegable. La
estructura mentiría sobre lo que hace el sistema.

## Decisión 2 — Los paquetes conservan su nombre de import de primer nivel

Los paquetes bajaron a `apps/commons/` y `apps/etl-platform-api/`, pero siguen importándose
como `etl_core`, `orchestrator` y `platform_api`. Los directorios se declaran como raíces de
código, igual que hace `bcra-scraper-api` con `apps/commons`.

No es comodidad: los 25 `manifest.yaml` declaran su adapter como **string** resuelto en
runtime —`adapter: etl_core.contracts:SubprocessAdapter`—. El nombre del paquete es parte del
contrato de catálogo. Renombrarlo obligaría a reescribir los 25 manifiestos de clientes en
producción a cambio de una convención de nombres.

## Decisión 3 — La raíz del workspace se resuelve por marcador, no contando niveles

`orchestrator.workspace.workspace_root()` sube hasta el primer ancestro que tiene
`pyproject.toml` **y** `etls/`.

Antes se resolvía con `Path(__file__).resolve().parents[1]` en dos lugares. Mover los paquetes
un nivel hacia abajo hizo que apuntaran a `apps/commons`, y **103 tests fallaron de una vez**.
Contar niveles ata el código a su profundidad en el árbol; el marcador no.

Falla rápido si no encuentra la raíz: un workspace mal resuelto escribe la evidencia de
corridas en el lugar equivocado, y eso se descubre tarde y mal.

## Decisión 4 — El servidor MCP vive en `tools/`, no en `apps/`

`platform_mcp` es un servidor **stdio**: se registra en el cliente MCP del desarrollador y
habla con la API por HTTP. No se despliega en Kubernetes. `apps/` queda reservado a lo que sí.

## Decisión 5 — Los ETLs siguen corriendo como subprocesos dentro del pod de la API

Es la decisión con más consecuencias, y la que más conviene revisar más adelante.

**Se mantiene el modelo actual:** la API lanza cada ETL con `subprocess.Popen` dentro de su
propio pod, con réplica única y un volumen persistente para `var/`.

**Alternativa descartada por ahora:** un `Job` de Kubernetes por corrida, disparado por NATS
con envelope CloudEvents (ADR-ARC-018 y ADR-ARC-019). Es el modelo correcto a mediano plazo —
aislamiento por corrida, límites de recursos por ETL, y un rolling update que no mata un
proceso de una hora a la mitad.

Se descarta hoy por una razón concreta: reescribir el orquestador para lanzar Jobs no se puede
verificar sin un cluster. La red que protege este sistema es la paridad byte a byte, y esa red
no cubre un cambio en el mecanismo de ejecución. Entregar esa reescritura sin poder correrla
sería entregar código no verificado en el camino crítico de 10 ETLs de 6 clientes.

**Riesgos aceptados, explícitos:**

| Riesgo | Consecuencia | Mitigación aplicada |
|---|---|---|
| Un rolling update mata una corrida en curso | La corrida queda huérfana | `recover_orphans()` ya la marca al arrancar. `terminationGracePeriodSeconds` alto en el chart |
| No hay límite de recursos por ETL | Un ETL pesado afecta a la API | `ETL_MAX_CONCURRENT_RUNS` acota la concurrencia |
| Réplica única | No hay alta disponibilidad | Es el modelo del chart de referencia (`replicas: 1`). El sistema es batch diario, no OLTP |
| `var/` en un volumen `ReadWriteOnce` | No escala horizontalmente | Es consecuencia, no causa: el locking de estado ya usa lock files de filesystem |

## Decisión 6 — La zona horaria del contenedor es parte del contrato, no una preferencia

El pod fija `TZ=America/Argentina/Buenos_Aires`.

Los wrappers de `etls/` nombran sus archivos de salida con la fecha **local** (`date.today()`),
y los manifiestos declaran `output_date_source: system_date`. Un pod en UTC a las 21:00 de
Argentina ya está en el día siguiente: escribiría los artefactos con la fecha de mañana y los
globs del manifiesto no los encontrarían.

**Alternativa descartada:** normalizar los wrappers a UTC. Rompería la paridad byte a byte
contra los repositorios upstream, que es el criterio de aceptación de cada ETL. La zona horaria
se fija en el entorno, no en el código.

Por eso `DTZ` queda fuera del ruleset de ruff: sus hallazgos en `etls/` son correctos como
observación y equivocados como acción.

## Decisión 7 — `tests/` y `test/` conviven

`tests/` es el árbol unitario que descubre pytest. `test/integration/` es el que pide ARC-002,
y ahí vive la suite de paridad contra los upstream, que es genuinamente de integración: levanta
subprocesos reales contra repositorios reales.

**Alternativa descartada:** unificar bajo `test/`. Rompería los imports `tests.support.*` a
cambio de uniformidad de nombre.

## Consecuencias

**Positivas.** La estructura es reconocible para cualquiera que venga de otro repo de Evoltis.
El `uv.lock` hace reproducible un entorno que hasta ahora dependía de lo que cada máquina
tuviera instalado —y que estaba corriendo una versión de numpy retirada de PyPI—. Las sondas
`/health` y `/ready` existen, que es requisito para que el cluster pueda operar el servicio.

**Negativas.** El repositorio queda con tres raíces de código (`apps/`, `tools/`, `etls/`) en
vez de una. La decisión 5 deja deuda conocida: el día que un ETL necesite límites de recursos
propios o que la ventana de despliegue no pueda esperar a que termine una corrida, hay que ir a
Jobs, y eso es un cambio de arquitectura, no un ajuste.

## Referencias

- [ADR-ARC-002 — Scaffolding para soluciones sobre monorepo](https://evoltis.atlassian.net/wiki/spaces/AEP/pages/2219900931)
- [ADR-ARC-003 — Package manager para aplicaciones python](https://evoltis.atlassian.net/wiki/spaces/AEP/pages/2219442195)
- [ADR-ARC-022 — Estructura de documentación en repositorios](https://evoltis.atlassian.net/wiki/spaces/AEP/pages/3160375300)
- [ADR-ARC-018 — NATS como plataforma estándar de mensajería](https://evoltis.atlassian.net/wiki/spaces/AEP/pages/3125411849)
- [ADR-DEV-001 — Estrategia de branching, releases y promoción por ambientes](https://evoltis.atlassian.net/wiki/spaces/AEP/pages/2258042885)
- `docs/decisions/ADR-001-nucleo-hexagonal.md` — el núcleo que esta alineación reubica sin tocar
- `docs/explanation/paridad-upstream.md` — por qué la paridad no cubre el drift de dependencias
