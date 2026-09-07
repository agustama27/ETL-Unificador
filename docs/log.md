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

## [2026-09-05] update | scaffolding de monorepo (ADR-ARC-002)

- Los paquetes bajan a `apps/commons/` (etl_core, orchestrator), `apps/etl-platform-api/`
  y `tools/etl-platform-mcp/`. El frontend pasa a `apps/etl-console/`. Los nombres de
  import de primer nivel se conservan: los 25 `manifest.yaml` resuelven el adapter por
  string en runtime → [reference/ARQUITECTURA.md](reference/ARQUITECTURA.md)
- La raíz del workspace pasa a resolverse por marcador y no contando niveles con
  `parents[n]`. El conteo se rompió con la mudanza y se llevó 103 tests de una vez →
  [reference/ARQUITECTURA.md](reference/ARQUITECTURA.md)
- La API gana `/health` y `/ready`, fuera del prefijo `/api` para que no pasen por el
  token. Antes no había ninguna: un probe de Kubernetes habría recibido 401 →
  [reference/ARQUITECTURA.md](reference/ARQUITECTURA.md)
- Entran `config/{local,local-compose,dev}.json` con un loader que siembra defaults sin
  pisar el entorno, y `test/{integration,assets}` + `test/docker-compose.yaml`. La suite
  de paridad pasa a `test/integration/` → [reference/comandos.md](reference/comandos.md)
- El `Dockerfile` pasa a `apps/etl-platform-api/` y fija `TZ=America/Argentina/Buenos_Aires`.
  No es cosmético: los wrappers nombran su salida con la fecha local →
  [decisions/ADR-002-alineacion-evoltis.md](decisions/ADR-002-alineacion-evoltis.md)

## [2026-09-05] update | chart de Helm y despliegue

- Entra `deploy/package/` con el chart: ConfigMap, Deployment, Service y PVC. Los helpers,
  el ConfigMap y el Service se toman del chart de referencia de Evoltis sin cambios →
  [how-to/desplegar-en-kubernetes.md](how-to/desplegar-en-kubernetes.md)
- El volumen de `var/` es `ReadWriteOnce` con `resource-policy: keep`, y la estrategia es
  `Recreate`: consecuencia del locking por lock files, no una preferencia →
  [decisions/ADR-002-alineacion-evoltis.md](decisions/ADR-002-alineacion-evoltis.md)
- `terminationGracePeriodSeconds: 3900` cubre el ETL más largo del catálogo (3600 s de
  `petersen.base.daily`). Hay un test que lo verifica contra el catálogo real, para que no
  se separen → [how-to/desplegar-en-kubernetes.md](how-to/desplegar-en-kubernetes.md)
- El Taskfile gana las tareas de docker, helm y ECR, y `task check` ahora incluye
  `helm:lint` → [reference/comandos.md](reference/comandos.md)

## [2026-09-05] update | pipeline de CI/CD (ADR-DEV-001)

- `bitbucket-pipelines.yml` pasa de 11 líneas a la estructura corporativa: versionado por
  rama (`develop` → `-dev.N`, `release/*` → `-rc.N`, `main` → base), publicación a ECR con
  OIDC, push del chart al registro OCI y actualización del repo de ops por GitOps →
  [reference/comandos.md](reference/comandos.md)
- CI corre en Python 3.12 y no 3.13: el `uv.lock` está resuelto para 3.12 y las
  dependencias del camino de datos van pineadas →
  [explanation/paridad-upstream.md](explanation/paridad-upstream.md)
- Entra `task ci:verify`, que falla ante cualquier skip inesperado. La paridad se saltea en
  CI por diseño —los repos upstream no están en el runner— y ese skip legítimo volvía
  invisibles a los demás → [reference/comandos.md](reference/comandos.md)

## [2026-09-05] update | stack de Docker Compose para la VM STAGE

- Entran `compose.yaml`, el `Dockerfile` del frontend con nginx y `.env.example`. Son los
  prerrequisitos que pide la guía de deploy de SRV-APP-STAGE, que despliega con Compose y
  no con Kubernetes: el chart de `deploy/package/` no aplica a ese destino →
  [how-to/desplegar-en-vm-stage.md](how-to/desplegar-en-vm-stage.md)
- Solo el frontend publica puerto; el backend queda en la red interna y nginx le proxea
  `/api` con timeouts de 3900 s, porque una corrida puede tardar una hora →
  [how-to/desplegar-en-vm-stage.md](how-to/desplegar-en-vm-stage.md)
- `.gitignore` tenía `.env.*`, que también excluía `.env.example`. Se agregó la negación:
  la plantilla lleva nombres de variables, nunca valores → [index.md](index.md)

## [2026-09-05] deploy | primer despliegue en SRV-APP-STAGE

- Stack `etl-unificador` levantado en `/opt/stacks/etl-unificador`, frontend en el puerto
  **8082** (elegido tras inspeccionar: 8000, 8081, 8088 y 9443 estaban ocupados por
  `cupones-bancor`, `cora`, `axis` y `portainer`) →
  [how-to/desplegar-en-vm-stage.md](how-to/desplegar-en-vm-stage.md)
- `ai-agent` no está en el grupo `docker`: todos los comandos van con `sudo docker`. No se
  corrigió con `usermod` porque es un cambio permanente a una VM compartida →
  [how-to/desplegar-en-vm-stage.md](how-to/desplegar-en-vm-stage.md)
- Verificado en la VM: frontend 200, `/ready` con 25 ETLs, 401 sin token y 200 con token,
  `date` en `-03`, `var/` escribible sobre el volumen. Los ocho contenedores de los otros
  equipos conservan su uptime → [how-to/desplegar-en-vm-stage.md](how-to/desplegar-en-vm-stage.md)

## [2026-09-06] fix | pantalla de acceso en la consola

- La consola mostraba "No se pudo cargar el tablero" cuando el backend devolvía 401 por
  falta de token, que es indistinguible de un servidor caído. Entra `screens/Acceso.tsx`
  con un campo para pegar el token → [reference/comandos.md](reference/comandos.md)
- Hasta ahora la única forma de cargar el token era abrir DevTools y escribir en
  `localStorage` a mano: no era un flujo que se le pudiera pedir a operaciones →
  [how-to/desplegar-en-vm-stage.md](how-to/desplegar-en-vm-stage.md)
- `api.ts` gana `ApiError` con el status. Un 401 y una caída de red ya no se ven igual.
  El 503 (backend sin `ETL_CONSOLE_TOKEN`) muestra un mensaje distinto: no se arregla
  desde el navegador → [reference/comandos.md](reference/comandos.md)

## [2026-09-06] update | sincronización de lógica con los ETLs individuales

- Bancor carga masiva, Alvarez y Naranja X MA quedan alineados con sus repos upstream:
  37 archivos. La paridad byte a byte estaba verde y aun así el código difería, porque
  compara la salida sobre un fixture sintético, no el código →
  [explanation/paridad-upstream.md](explanation/paridad-upstream.md)
- Naranja X MA cambia una regla de negocio: `DEFAULT_CAJONES_SCOPE` pasa de
  `("M60","M90")` a `("M90",)`. Cambia qué clientes entran al proceso →
  [reference/ARQUITECTURA.md](reference/ARQUITECTURA.md)
- La sincronización de `io.py` de MA pisó la tolerancia de hoja autorizada por
  operaciones y rompió 3 tests. Se rehízo fusionando: se conserva la tolerancia y se porta
  el fallback `nroproducto`→`dni` del upstream →
  [decisions/tolerancia-hoja-asignacion.md](decisions/tolerancia-hoja-asignacion.md)
- CartaSur y Naranja X MT ya estaban al día. El único archivo que MT parecía tener
  desactualizado es un test **sin trackear** del upstream que contradice su propio código
  de producción y falla al correrlo → [explanation/paridad-upstream.md](explanation/paridad-upstream.md)

## [2026-09-06] update | EPEC a la rama CXI y baja del ETL de Chat

- EPEC se sincroniza contra `feature/cxi-luz-salientes-v1.1`, por decisión explícita.
  **Cambia el contrato de salida: de 33 a 24 columnas**, y suma
  `[Salida] Utilidad Informacion`. Entra además el test del consolidador →
  [reference/ARQUITECTURA.md](reference/ARQUITECTURA.md)
- Se dan de baja `naranjax.ma.chat.daily` y `naranjax.ma.chat.pct` y se borra
  `legacy/chat`. El catálogo pasa de 25 entradas / 18 ejecutables a **23 / 16** →
  [../etls/naranjax/README.md](../etls/naranjax/README.md)
- `ma_chat.py` **no** se borró: `MaVoiceAdapter`, `MtVoiceAdapter` y `MtVoiceBackAdapter`
  lo componen (`self._shared = MaChatAdapter(...)`). Quedó como implementación compartida
  de Naranja X sin ETL propio; el nombre engaña y conviene renombrarlo →
  [reference/ARQUITECTURA.md](reference/ARQUITECTURA.md)
- `test_both_copies_share_the_exact_resolution_code` se queda sin segunda copia y se
  reemplaza por un guard que verifica que la tolerancia autorizada siga en el legacy.
  No es equivalente: es mejor. Cubre el modo de falla real, que es una resincronización
  que la pise → [decisions/tolerancia-hoja-asignacion.md](decisions/tolerancia-hoja-asignacion.md)
- Los ADR-001 y de tolerancia quedan sin editar: son registros de decisión y ARC-022 pide
  superseder, no reescribir. Sus menciones a las dos copias describen lo que era cierto
  cuando se escribieron → [index.md](index.md)

## [2026-09-06] fix | la base de Bancor puede llegar en Excel

- El manifiesto de `bancor.base.daily` declaraba solo `.csv`, pero el legacy lee CSV y
  Excel y la UI del repo individual ofrece los tres formatos. Ahora declara
  `[.csv, .xlsx, .xls]` → [../etls/bancor/README.md](../etls/bancor/README.md)
- `SubprocessAdapter` construía la ruta del input con la **primera extensión declarada**
  mientras el staging usa la **real**. Con un solo formato coincidían y nadie lo notaba;
  con varios, el subproceso recibía una ruta inexistente. Es la razón por la que Alvarez,
  CartaSur y Petersen tienen adapter propio → [reference/ARQUITECTURA.md](reference/ARQUITECTURA.md)
- El `job.py` de Bancor copiaba el input con el nombre fijo `base.csv`. El legacy elige
  el lector **por la extensión**, así que un `.xlsx` renombrado iba al parser de CSV →
  [../etls/bancor/README.md](../etls/bancor/README.md)
