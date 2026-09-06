# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es este proyecto

ETL de cobranzas de Álvarez Maquinarias. Lee cuatro reportes de Autologica
(`.xls`, `.xlsx`, `.pdf`) y produce dos CSV: `ALVAREZ_MAQUINARIAS_ROMAN_YYMMDD.csv`
(gestión, una fila por cliente) y `ALVAREZ_MAQUINARIAS_E1KIA_YYMMDD.csv`
(marcador de la plataforma de llamadas, una sola columna `TelefonoCliente`).

Código, comentarios, docs y nombres de test están en español. Mantené esa convención.

## Comandos

```bash
python -m pip install -r requirements.txt
python main.py --preparar                                      # crea inputs/<hoy>/
python main.py                                                 # procesa inputs/<hoy>/ -> outputs/<hoy>/
python -m pytest tests/ -v
python scripts/generate_sample_data.py --run-date 2026-08-04   # fixtures sintéticos en inputs/<run-date>/
```

Guía paso a paso para el operador: `docs/TUTORIAL.md`.

Un solo test: `python -m pytest tests/test_pipeline.py::test_e1kia_lista_una_sola_vez_un_telefono_compartido -v`

No hay `pyproject.toml` ni config de lint versionada — ruff/mypy se corren a mano
si hacen falta. No hay build.

## Arquitectura

Flujo lineal en `src/etl/pipeline.py`: `extract()` → `transform()` → `load()`.
La pieza clave es el **esquema canónico** (`schema.CANONICAL_COLUMNS`): cada
adapter de `extractors.py` traduce su fuente sucia a ese esquema, y nada aguas
abajo sabe que las fuentes eran reportes de Autologica.

- **`schema.py`** — único lugar donde viven los nombres de columna. Tres niveles:
  canónico (`COL_*`), detalle enriquecido (`COL_TELEFONO`, `COL_MONTO_USD`…) y
  salida de negocio (`OUT_*`). No escribas strings de columna a mano en otro archivo.
- **`extractors.py`** — un adapter por fuente. Las cuatro son reportes agrupados
  (header corrido, subtotales de pivot, celdas combinadas), no tablas planas:
  el header se **busca** con `locate_header_row`, nunca se asume fila fija.
  Repuestos se lee del PDF a propósito — el `.xlsx` equivalente tiene texto
  corrupto por celdas superpuestas.
- **`transformers.py`** — reglas de negocio. Lo no obvio es la **resolución de
  identidad**: solo Saldos trae ID de Autologica, el resto se une por nombre
  normalizado, así que un mismo deudor llega partido en varias claves.
  `normalize_client_name` reune las iniciales sueltas que deja la puntuacion
  (`S.A.` -> `SA`) y separa el sufijo societario cuando lo precede la inicial de
  un socio (`GERMAN R S.H.` -> `R` + `SH`): sin eso, la misma sociedad de hecho
  escrita con o sin puntos daba dos claves distintas.
  `resolve_duplicate_clients` fusiona con union-find y solo con evidencia
  (truncamiento contra el techo de largo medido por fuente, o teléfono
  compartido + nombre reconociblemente igual). Nunca aflojes esas condiciones
  sin leer `docs/ASSUMPTIONS.md`: fusionar de más mezcla deuda entre clientes reales.
- **`loaders.py`** — formato de intercambio (`;`, UTF-8 **sin** BOM, CRLF) definido
  una sola vez en la clase base; las subclases solo cambian el recorte de filas.
- **`config.py`** — `PipelineConfig.for_dated_run` resuelve y **sandboxea** las
  rutas: solo basenames con la extensión esperada, dentro de `inputs/<run-date>/`,
  archivo regular y legible. Toda validación de entrada vive acá, antes de extraer.
  El nombre de archivo de cada fuente se resuelve en **tres niveles**: el que pasó
  el operador (`--saldos X`) → el nombre canónico si está → descubrimiento por
  extensión. El descubrimiento solo **propone** un nombre; `_resolve_sources`
  sigue siendo el único límite de confianza y no se saltea. Si una regla no da
  exactamente un archivo, la fuente queda sin asignar y la corrida aborta
  listando la partición — nunca elige entre dos candidatos.
- **`codigos_area.py`** — tabla CP → característica telefónica, para completar
  los teléfonos locales del export por página. Ampliar solo con prefijos
  verificados contra un directorio público; un CP sin verificar se deja afuera.

### Invariantes que el pipeline defiende

- **Solo USD.** Las filas ARS y de moneda desconocida se excluyen en extracción,
  antes de registrar teléfonos o identidades. Los diagnósticos son conteos
  agregados por fuente; los tests verifican que ningún warning filtre valores de fila.
- **Paridad de teléfonos.** `verify_phone_parity` corre *antes* de escribir: el
  E1KIA debe cubrir exactamente el mismo conjunto de teléfonos que el ROMAN, sin
  repetidos. Si falla, la corrida aborta sin dejar archivos parciales. La
  correspondencia es entre conjuntos, no entre filas.
- **Sin salidas parciales.** Colisión de archivos (sin `--overwrite`), CSV de
  saldos inválido o paridad rota abortan antes de escribir nada.
- **Nunca se adivina.** Ante ambigüedad —dos archivos para la misma fuente, un CP
  sin mapear, un teléfono que no reconstruye a 10 dígitos— el pipeline aborta o
  deja el dato como vino, y lo informa. Preferimos un fallo ruidoso a un dato
  inventado que pasa todas las validaciones de formato.

## Gotchas

- **`test/` (singular) contiene archivos reales de clientes** y **no** está en
  `.gitignore`. Nunca lo agregues al índice. `tests/` (plural) es la suite.
- **Los docs están contract-testeados.** `tests/test_cli.py` afirma frases
  literales de `README.md`, `docs/SPEC.md`, `docs/HARNESS.md` y
  `docs/ASSUMPTIONS.md` (política de datos, nombres de export, contrato CSV).
  Editar esos archivos rompe tests — corré la suite después de tocarlos.
- El proyecto no configura `logging`, así que solo `WARNING` o más llega al
  operador. Por eso las fusiones de cliente se loguean como warning, no info.
- `--tipo-cambio` es un no-op obsoleto que se acepta con advertencia; los saldos
  ya vienen en USD.
- `--run-date` es la partición de E/S; `--reference-date` es la fecha de cálculo
  de días de mora. Son independientes **a propósito** y así se confirmó en
  agosto 2026: reprocesar una partición vieja da `DiasMora` actualizado al día
  de hoy, no al del archivo. Para reproducir una entrega exacta hay que pasar
  `--reference-date` explícito. No propongas cambiar el default.
- **Los importes mezclan convención AR e inglesa en el mismo archivo.**
  `parse_currency_amount` desambigua por la **forma** del valor, no por la
  fuente: con ambos separadores manda el de más a la derecha (`17.264,70` →
  17264.70, `17,264.70` → 17264.70); con uno solo, agrupa miles solo si los
  grupos son de tres dígitos exactos. Asumir coma decimal dividía por mil todo
  importe en convención inglesa — USD 140.310 subestimados sobre 41 clientes en
  la corrida del 12/08/2026. La marca de moneda se saca pegada o separada
  (`USD1.149,20`): la frontera de palabra que se exigía
  antes no existe entre la `D` y el `1`.
- **Las fuentes mezclan tipos de celda dentro de la misma hoja.** Remitos de
  Servicios trae el importe como número nativo de Excel en casi todas las filas
  y como texto (`USD1.149,20`) en unas pocas. Ningún adapter debe decidir por
  `isinstance`: pasá la celda por `parse_currency_amount` y quedate con lo que
  resuelva. Exigir número nativo costó USD 3.184 en la corrida del 01/09/2026.
- **`FlagPrioridad` sale siempre `False`.** `COL_PRIORIDAD_RAW` está fijo en
  `None` en los seis puntos de extracción y ninguna fuente trae el dato, así que
  la primera clave del orden de `consolidate_by_client` es inerte y el ROMAN
  queda ordenado solo por saldo. Es una columna muerta pendiente de definición
  del negocio: no inventes el criterio de prioridad.
- **El export `.csv` de Saldos trae la mitad de los teléfonos que el `.xls`**
  (43,8 % vs 91,3 % de cobertura, medido en agosto 2026). Si la cobertura
  telefónica baja, revisá con qué formato vino Saldos antes de buscar el bug en
  el código: el techo está en la fuente.

## Ruflo — Claude Code Configuration

Sección autogenerada por `ruflo init`. Aplica al tooling de agentes, no al ETL.

## Rules

- Do what has been asked; nothing more, nothing less
- NEVER create files unless absolutely necessary — prefer editing existing files
- NEVER create documentation files unless explicitly requested
- NEVER save working files or tests to root — use `/src`, `/tests`, `/docs`, `/config`, `/scripts`
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files
- NEVER add a `Co-Authored-By` trailer to user commits unless this project's `.claude/settings.json` has `attribution.commit` set (#2078). The Claude Code Bash tool may suggest one in its default commit-message template — ignore it. `Co-Authored-By` is semantic authorship attribution under git/GitHub convention; the tool is the facilitator, not a co-author.
- Keep files under 500 lines
- Validate input at system boundaries

## Agent Comms (SendMessage-First Coordination)

Named agents coordinate via `SendMessage`, not polling or shared state.

```
Lead (you) ←→ architect ←→ developer ←→ tester ←→ reviewer
              (named agents message each other directly)
```

### Spawning a Coordinated Team

```javascript
// ALL agents in ONE message, each knows WHO to message next
Agent({ prompt: "Research the codebase. SendMessage findings to 'architect'.",
  subagent_type: "researcher", name: "researcher", run_in_background: true })
Agent({ prompt: "Wait for 'researcher'. Design solution. SendMessage to 'coder'.",
  subagent_type: "system-architect", name: "architect", run_in_background: true })
Agent({ prompt: "Wait for 'architect'. Implement it. SendMessage to 'tester'.",
  subagent_type: "coder", name: "coder", run_in_background: true })
Agent({ prompt: "Wait for 'coder'. Write tests. SendMessage results to 'reviewer'.",
  subagent_type: "tester", name: "tester", run_in_background: true })
Agent({ prompt: "Wait for 'tester'. Review code quality and security.",
  subagent_type: "reviewer", name: "reviewer", run_in_background: true })

// Kick off the pipeline
SendMessage({ to: "researcher", summary: "Start", message: "[task context]" })
```

### Patterns

| Pattern | Flow | Use When |
|---------|------|----------|
| **Pipeline** | A → B → C → D | Sequential dependencies (feature dev) |
| **Fan-out** | Lead → A, B, C → Lead | Independent parallel work (research) |
| **Supervisor** | Lead ↔ workers | Ongoing coordination (complex refactor) |

### Rules

- ALWAYS name agents — `name: "role"` makes them addressable
- ALWAYS include comms instructions in prompts — who to message, what to send
- Spawn ALL agents in ONE message with `run_in_background: true`
- After spawning: STOP, tell user what's running, wait for results
- NEVER poll status — agents message back or complete automatically

## Swarm & Routing

### Config
- **Topology**: hierarchical-mesh (anti-drift)
- **Max Agents**: 15
- **Memory**: hybrid
- **HNSW**: Enabled
- **Neural**: Enabled

```bash
npx @claude-flow/cli@latest swarm init --topology hierarchical --max-agents 8 --strategy specialized
```

### Agent Routing

| Task | Agents | Topology |
|------|--------|----------|
| Bug Fix | researcher, coder, tester | hierarchical |
| Feature | architect, coder, tester, reviewer | hierarchical |
| Refactor | architect, coder, reviewer | hierarchical |
| Performance | perf-engineer, coder | hierarchical |
| Security | security-architect, auditor | hierarchical |

### When to Swarm
- **YES**: 3+ files, new features, cross-module refactoring, API changes, security, performance
- **NO**: single file edits, 1-2 line fixes, docs updates, config changes, questions

### 3-Tier Model Routing

| Tier | Handler | Use Cases |
|------|---------|-----------|
| 1 | Agent Booster (WASM) | Simple transforms — skip LLM, use Edit directly |
| 2 | Haiku | Simple tasks, low complexity |
| 3 | Sonnet/Opus | Architecture, security, complex reasoning |

## Memory & Learning

### Before Any Task
```bash
npx @claude-flow/cli@latest memory search --query "[task keywords]" --namespace patterns
npx @claude-flow/cli@latest hooks route --task "[task description]"
```

### After Success
```bash
npx @claude-flow/cli@latest memory store --namespace patterns --key "[name]" --value "[what worked]"
npx @claude-flow/cli@latest hooks post-task --task-id "[id]" --success true --store-results true
```

### MCP Tools (use `ToolSearch("keyword")` to discover)

| Category | Key Tools |
|----------|-----------|
| **Memory** | `memory_store`, `memory_search`, `memory_search_unified` |
| **Bridge** | `memory_import_claude`, `memory_bridge_status` |
| **Swarm** | `swarm_init`, `swarm_status`, `swarm_health` |
| **Agents** | `agent_spawn`, `agent_list`, `agent_status` |
| **Hooks** | `hooks_route`, `hooks_post-task`, `hooks_worker-dispatch` |
| **Security** | `aidefence_scan`, `aidefence_is_safe`, `aidefence_has_pii` |
| **Hive-Mind** | `hive-mind_init`, `hive-mind_consensus`, `hive-mind_spawn` |

### Background Workers

| Worker | When |
|--------|------|
| `audit` | After security changes |
| `optimize` | After performance work |
| `testgaps` | After adding features |
| `map` | Every 5+ file changes |
| `document` | After API changes |

```bash
npx @claude-flow/cli@latest hooks worker dispatch --trigger audit
```

## Agents

**Core**: `coder`, `reviewer`, `tester`, `planner`, `researcher`
**Architecture**: `system-architect`, `backend-dev`, `mobile-dev`
**Security**: `security-architect`, `security-auditor`
**Performance**: `performance-engineer`, `perf-analyzer`
**Coordination**: `hierarchical-coordinator`, `mesh-coordinator`, `adaptive-coordinator`
**GitHub**: `pr-manager`, `code-review-swarm`, `issue-tracker`, `release-manager`

Any string works as a custom agent type.

## Build & Test

- ALWAYS run tests after code changes
- ALWAYS verify build succeeds before committing

```bash
npm run build && npm test
```

## CLI Quick Reference

```bash
npx @claude-flow/cli@latest init --wizard           # Setup
npx @claude-flow/cli@latest swarm init --v3-mode     # Start swarm
npx @claude-flow/cli@latest memory search --query "" # Vector search
npx @claude-flow/cli@latest hooks route --task ""    # Route to agent
npx @claude-flow/cli@latest doctor --fix             # Diagnostics
npx @claude-flow/cli@latest security scan            # Security scan
npx @claude-flow/cli@latest performance benchmark    # Benchmarks
```

26 commands, 140+ subcommands. Use `--help` on any command for details.

## Setup

```bash
claude mcp add claude-flow -- npx -y ruflo@latest mcp start
npx ruflo@latest doctor --fix
```

> The background `daemon` is optional. It runs interval workers that each spawn
> a headless `claude` session, so it consumes tokens continuously. Start it only
> if you want those sweeps: `npx ruflo@latest daemon start` (self-stops after 12h
> by default; `--ttl 0` to disable, `daemon status --all` to audit running daemons).

**Agent tool** handles execution (agents, files, code, git). **MCP tools** handle coordination (swarm, memory, hooks). **CLI** is the same via Bash.
