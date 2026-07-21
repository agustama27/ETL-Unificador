# Objetivo del proyecto — ETL Unificador

## 1. Contexto

Actualmente existen múltiples proyectos ETL separados, cada uno con su propia estructura, comandos, carpetas de entrada/salida, reglas de negocio, logs y forma de ejecución.

El objetivo no es simplemente juntar carpetas dentro de un monorepo, sino construir una **plataforma unificada de ejecución, administración y observabilidad de ETLs**.

El primer dominio funcional elegido para iniciar el proyecto es **Naranja X**, utilizando como base estos proyectos:

```text
SOHO-Chat-NX_MA-ETL/
soho-naranjaX-MA-etl/
soho-naranjaX-MT-etl/
```

> Nota: si alguno de estos proyectos no está presente en el repositorio remoto al momento de trabajar, el agente debe reportarlo explícitamente y no asumir su existencia.

## 2. Objetivo principal

Construir un sistema unificador que permita ejecutar distintos ETLs desde una capa común, sin que el usuario tenga que conocer la estructura interna de cada proyecto.

El sistema debe permitir, en etapas futuras:

```text
Seleccionar cliente / proceso / fecha / archivos de entrada
↓
Ejecutar el ETL correspondiente
↓
Registrar estado, logs, errores y outputs
↓
Descargar archivos generados
↓
Auditar ejecuciones anteriores
↓
Exponer la funcionalidad mediante API y luego una UI
```

La primera versión debe enfocarse en la **ejecución controlada por backend/CLI**, no en la UI final.

## 3. Enfoque arquitectónico esperado

La arquitectura deseada es una plataforma con adapters, no una reescritura inmediata de todos los ETLs.

Arquitectura conceptual:

```text
ETL Unificador
├── Catálogo de ETLs
├── Runner común
├── Adapters por proyecto/proceso
├── Registro de ejecuciones
├── Captura de logs
├── Gestión de inputs/outputs
└── Metadata de auditoría
```

Arquitectura objetivo inicial:

```text
etl-unificador/
├── registry/
│   └── naranjax.yaml
│
├── orchestrator/
│   ├── models.py
│   ├── runner.py
│   ├── run_store.py
│   ├── file_manager.py
│   └── logging_utils.py
│
├── adapters/
│   └── naranjax/
│       ├── ma_voice.py
│       ├── ma_chat.py
│       └── mt_voice.py
│
├── runs/
│   └── .gitkeep
│
└── docs/
    └── .gitkeep
```

El sistema debería dividirse en tres capas:
┌──────────────────────────────────────────┐
│ Plataforma ETL                           │
│ API, UI, cola, ejecución, logs, estados  │
└────────────────────┬─────────────────────┘
                     │ Contrato común
┌────────────────────▼─────────────────────┐
│ Adapter del ETL                          │
│ Traduce inputs del sistema al ETL real   │
└────────────────────┬─────────────────────┘
                     │
┌────────────────────▼─────────────────────┐
│ Lógica específica del cliente            │
│ Bancor / Naranja X / EPEC / Frávega      │
└──────────────────────────────────────────┘

Una estructura razonable sería:
ETL-Unificador/
├── platform/
│   ├── api/
│   ├── orchestrator/
│   ├── workers/
│   ├── storage/
│   └── database/
│
├── etl_core/
│   ├── contracts.py
│   ├── execution.py
│   ├── artifacts.py
│   ├── logging.py
│   └── validation.py
│
├── etls/
│   ├── bancor/
│   │   ├── manifest.yaml
│   │   ├── adapter.py
│   │   ├── pipelines/
│   │   │   ├── back_base/
│   │   │   ├── back_resultados/
│   │   │   ├── carga_masiva/
│   │   │   └── cupones/
│   │   ├── tests/
│   │   ├── fixtures/
│   │   ├── CHANGELOG.md
│   │   └── README.md
│   │
│   ├── naranjax/
│   │   ├── ma_voice/
│   │   ├── ma_chat/
│   │   └── mt_voice/
│   │
│   ├── epec/
│   └── fravega/
│
└── shared/
    ├── csv_readers/
    ├── phone_normalization/
    └── file_validation/


## 4. Principio central de diseño

Los ETLs existentes deben tratarse inicialmente como **legacy jobs invocables**, no como código a refactorizar de inmediato.

El unificador debe poder ejecutar un ETL existente mediante subprocess, capturar sus logs, detectar sus outputs y devolver un resultado estructurado.

Ejemplo conceptual:

```text
Unificador
  ↓
Adapter NaranjaX MA Chat
  ↓
python back-base/ejecutar_dia.py --chat ...
  ↓
Outputs + logs + metadata
```
Código que debe permanecer por cliente:
reglas de quita de Bancor
filtros de módulos de Bancor
códigos PCT
scope de cajones de Naranja X
consolidación por DNI del chat
prioridad de deuda planes > pagos > API
estructura CRM de cada cliente
reglas de exclusión de cada operación


## 5. Primer dominio: Naranja X

El proyecto debe comenzar con Naranja X porque permite trabajar con variantes relacionadas:

```text
Naranja X MA Voz
  → soho-naranjaX-MA-etl/
  → proceso diario base / ROMAN / E1KIA / PCT

Naranja X MA Chat
  → SOHO-Chat-NX_MA-ETL/
  → proceso diario base / ROMAN / CHAT_ROMAN / E1KIA

Naranja X MT
  → soho-naranjaX-MT-etl/
  → pendiente de relevar en detalle
```

El primer piloto recomendado es **SOHO-Chat-NX_MA-ETL**, porque ya tiene una variante clara de ejecución con `--chat` y genera un output diferenciado por DNI.

## 6. Qué debe resolver el unificador

El sistema debe abstraer diferencias como:

```text
- Nombre del proyecto/carpeta
- Comando de ejecución
- Argumentos CLI
- Archivos requeridos
- Archivos opcionales
- Carpeta de estado persistente
- Carpeta de logs
- Carpeta de outputs
- Patrones de nombre de salida
- Formato de fecha usado por cada output
- Exit code del proceso
- stdout/stderr
- Validación mínima post-ejecución
```

## 7. Contrato mínimo de un ETL unificado

Cada ETL debe poder declararse con un contrato similar a este:

```yaml
id: naranjax.ma.chat.daily
name: Naranja X MA Chat - Proceso diario
project_path: SOHO-Chat-NX_MA-ETL
command:
  - python
  - back-base/ejecutar_dia.py
  - --chat
inputs:
  required:
    - base_mensual
  optional:
    - planes
    - pagos
outputs:
  - pattern: NARANJAX_MA_ROMAN_*.csv
  - pattern: NARANJAX_MA_CHAT_ROMAN_*.csv
  - pattern: NARANJAX_MA_E1KIA_*.csv
stateful: true
```

## 8. Resultado esperado del runner

Cada ejecución debe producir un resultado estructurado como:

```json
{
  "run_id": "run_20260619_083000",
  "etl_id": "naranjax.ma.chat.daily",
  "status": "success",
  "started_at": "2026-06-19T08:30:00-03:00",
  "finished_at": "2026-06-19T08:32:10-03:00",
  "exit_code": 0,
  "inputs": {
    "base_mensual": "...",
    "planes": "...",
    "pagos": "..."
  },
  "outputs": [
    "NARANJAX_MA_ROMAN_20260619.csv",
    "NARANJAX_MA_CHAT_ROMAN_260619.csv",
    "NARANJAX_MA_E1KIA_260619_sinestrategia.csv"
  ],
  "log_file": "runs/naranjax.ma.chat.daily/20260619_083000/logs/run.log",
  "error_message": null
}
```

## 9. Sandbox por ejecución

Cada corrida debe aislarse en una carpeta propia:

```text
runs/
└── naranjax.ma.chat.daily/
    └── 20260619_083000/
        ├── input/
        ├── output/
        ├── logs/
        ├── state/
        ├── processed/
        └── run.json
```

Esto permite reproducibilidad, auditoría y futura migración a cloud storage.

## 10. Principios de diseño

El proyecto debe alinearse con principios de sistemas data-intensive:

### Confiabilidad

El sistema debe poder detectar fallos, registrar errores, conservar logs y permitir auditar qué pasó en cada ejecución.

### Mantenibilidad

No debe duplicarse lógica innecesariamente. Las diferencias entre ETLs deben declararse en configuración o adapters pequeños.

### Evolvabilidad

Debe ser fácil agregar nuevos ETLs sin modificar el core del orquestador.

### Operabilidad

Cada ejecución debe dejar evidencia: metadata, logs, inputs usados, outputs generados y estado final.

## 11. Restricciones importantes

El agente de código debe respetar estas restricciones:

```text
- No reescribir los ETLs existentes en la primera fase.
- No modificar reglas de negocio de Naranja X sin justificación explícita.
- No subir archivos de datos reales, temporales, builds ni secretos.
- No commitear .env, .csv, .xlsx, .xls, .exe ni outputs generados.
- Mantener compatibilidad con ejecución local existente.
- Implementar cambios con mínimo blast radius.
- Preferir adapters/configuración antes que condicionales hardcodeados.
- Documentar supuestos y dudas.
```

## 12. Alcance del MVP

El MVP no necesita API ni UI. Debe lograr:

```text
1. Registrar los ETLs Naranja X en un catálogo.
2. Ejecutar al menos un ETL desde el runner común.
3. Capturar stdout/stderr/logs.
4. Detectar archivos generados.
5. Crear un run.json con metadata.
6. Aislar cada ejecución en runs/.
7. Dejar preparado el diseño para sumar FastAPI posteriormente.
```

## 13. Primer entregable esperado

El primer entregable técnico debe ser una planificación validada para implementar el runner unificado, partiendo por:

```text
SOHO-Chat-NX_MA-ETL/
```

y luego extendiendo hacia:

```text
soho-naranjaX-MA-etl/
soho-naranjaX-MT-etl/
```
