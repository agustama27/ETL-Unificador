# Plan de Desarrollo — Fase 4
## ETL Naranja X Mora Avanzada — Empaquetamiento con Interfaz Visual (Windows)

---

## Contexto y estado al cierre de Fase 3

Al inicio de Fase 4 se asume que los siguientes puntos de Fase 3 están cerrados:

- **D2 → CERRADO:** Scope de cajones = `M90` con condición `ECOSISTEMA = PURO`
- **D3 → CERRADO:** `recupero` y `tipo_pago` no salen en el ROMAN (uso interno solamente)
- **D4 (pre-condición):** Mapa completo de tipificaciones validado con Naranja X y actualizado en `back-resultados/etl/constants.py`

> ⚠️ **D4 es pre-condición bloqueante de Fase 4.** Si no está cerrado al momento de arrancar, la app va a generar un PCT con códigos placeholder. No arrancar Fase 4 hasta que D4 esté resuelto.

---

## Objetivo de la Fase 4

Empaquetar el pipeline ETL existente (`back-base` + `back-resultados`) como una **aplicación de escritorio Windows** con interfaz visual, que el operador pueda descargar y usar sin instalar Python ni abrir una terminal. A su vez, el mismo ejecutable debe poder correrse desde la consola cuando así se desee, sin pasar por la UI.

---

## Decisiones de diseño confirmadas

| Variable | Decisión |
|---|---|
| Sistema operativo | Windows |
| Python en la PC del operador | No — el ejecutable debe ser autocontenido |
| Cantidad de usuarios que procesan | Uno solo |
| Archivos de estado | Viven en la PC del operador (o su OneDrive personal) |
| Archivos de entrada | Pueden venir de una carpeta de OneDrive local |
| Stack UI | customtkinter (Python nativo, aspecto moderno) |
| Empaquetado | PyInstaller → un único `.exe` autocontenido |
| Modos de ejecución | UI (default) y CLI (via argumento `--cli`) en el mismo ejecutable |

---

## Arquitectura dual: UI y CLI en un mismo ejecutable

La lógica de negocio del ETL vive en una capa central compartida. Tanto la UI como la CLI son dos "entradas" distintas a esa misma lógica — sin duplicación de código ni comportamiento divergente.

```
etl/                     ← lógica pura (sin CLI, sin UI)
    procesar_dia.py      ← función central invocable
    estado.py
    filtros.py
    ...
         │
         ├── cli.py      ← entrada por consola (argumentos, flags)
         └── app.py      ← entrada por UI (customtkinter)
```

El ejecutable detecta el modo al arrancar según los argumentos recibidos:

```
# Modo UI — doble clic o sin argumentos
naranjax_etl.exe

# Modo CLI — con argumentos explícitos
naranjax_etl.exe --cli --base base_mensual.xlsx --planes planes.txt --pagos pagos.txt
```

**Ventajas de este enfoque:**
- Un solo artefacto para distribuir y mantener
- Cualquier cambio en la lógica de negocio se refleja automáticamente en ambos modos
- El operador técnico puede automatizar ejecuciones via CLI (scripts, Task Scheduler de Windows) sin depender de la UI
- La UI y la CLI comparten validaciones, logs y manejo de errores

---

## Consideraciones técnicas clave

### OneDrive como origen de archivos

El operador puede tener los archivos de entrada (base mensual, planes, pagos) en una carpeta de OneDrive sincronizada localmente. Dos escenarios posibles:

- **OneDrive en modo "siempre disponible offline":** los archivos están en disco, la app los lee como cualquier carpeta normal. Sin problemas.
- **OneDrive en modo "bajo demanda":** los archivos pueden no estar descargados. La app debe verificar que el archivo es accesible antes de intentar procesarlo y mostrar un mensaje claro si no lo está.

**Acción:** agregar validación de accesibilidad de archivo antes de cada ejecución, con mensaje de error específico para este caso.

### Estado persistente — un solo operador

Como solo una persona procesa, el estado mensual (`estado_YYYYMM.csv`) y los snapshots diarios viven en la PC del operador. No hay riesgo de colisión. La carpeta de estado se configura una sola vez en la primera ejecución y se persiste en un archivo de configuración local.

### PyInstaller y dependencias

El `.exe` generado por PyInstaller incluye el intérprete Python y todas las dependencias. El operador descarga un archivo y lo ejecuta — sin instaladores, sin `pip`, sin terminal.

Puntos a tener en cuenta durante el empaquetado:
- Las dependencias de `back-base` y `back-resultados` deben estar declaradas explícitamente en un `requirements.txt` consolidado
- Los archivos de configuración y recursos (íconos, assets de UI) deben incluirse en el bundle de PyInstaller mediante `--add-data`
- Verificar compatibilidad de todas las dependencias con PyInstaller antes de arrancar el desarrollo de UI

---

## Flujo de la aplicación

### Primera ejecución (configuración inicial)

Al abrir la app por primera vez, el operador configura:

1. **Carpeta de estado:** dónde se guardan `estado_YYYYMM.csv` y los snapshots diarios
2. **Carpeta de salida:** dónde se depositan el ROMAN y el PCT generados

Estos valores se guardan en `config.json` local y no se vuelven a pedir.

### Ejecución diaria (flujo normal)

```
[Pantalla principal]
        │
        ├── Seleccionar base mensual (Excel)
        ├── Seleccionar archivo de planes del día
        └── Seleccionar archivo de pagos del día
                │
                ▼
        [Validación de archivos]
        ├── ¿Existe y es accesible? ✓ / ✗
        ├── ¿Formato correcto? ✓ / ✗
        └── ¿Estado mensual cargado? ✓ / ✗
                │
                ▼
        [Botón "Procesar"]
                │
                ▼
        [Barra de progreso + log en tiempo real]
                │
                ▼
        [Pantalla de resultado]
        ├── Registros procesados
        ├── Registros excluidos (con motivo)
        ├── Path del ROMAN generado
        ├── Path del PCT generado
        └── Botón "Abrir carpeta de salida"
```

---

## Tareas

### T1 — Refactorizar ETL como librería invocable con soporte dual UI/CLI

**Objetivo:** desacoplar la lógica de negocio en una capa central compartida, y construir sobre ella dos entradas independientes: una CLI y una UI.

**Descripción:**
- Extraer la lógica central de `back-base/ejecutar_dia.py` a una función `procesar_dia(config, archivos) → resultado`
- Hacer lo mismo con `back-resultados`
- La función debe retornar un objeto con: registros procesados, exclusiones por motivo, paths de salida, errores
- El log debe poder redirigirse a un callback configurable (para mostrarlo en tiempo real en la UI o en stdout en CLI)
- Construir `cli.py` como wrapper de `procesar_dia()` que acepta argumentos por línea de comandos:
  - `--base`, `--planes`, `--pagos` para los archivos de entrada
  - `--salida` para carpeta de salida (opcional, usa config si no se pasa)
  - `--estado` para carpeta de estado (opcional, usa config si no se pasa)
- El ejecutable detecta el modo al arrancar: si recibe `--cli` corre sin UI; si no recibe argumentos abre la UI

**Criterios de aceptación:**
- `procesar_dia()` invocable desde Python sin CLI ni UI
- El log fluye a un callback configurable (stdout en CLI, widget en UI)
- `naranjax_etl.exe --cli --base X --planes Y --pagos Z` corre sin abrir ventana y devuelve exit code 0 si éxito, 1 si error
- `naranjax_etl.exe` sin argumentos abre la UI normalmente
- Los tests existentes (`pytest back-base/tests back-resultados/tests`) siguen pasando sin modificación
- No hay efectos secundarios: la refactorización no cambia comportamiento del pipeline

**Dependencias:** ninguna (puede arrancar ya)

---

### T2 — Diseño y construcción de la UI

**Objetivo:** construir la interfaz visual con customtkinter.

**Descripción:**

*Pantalla de configuración inicial (solo primera vez):*
- Selector de carpeta de estado (con botón de explorador)
- Selector de carpeta de salida
- Botón "Guardar configuración"
- Validación: ambas carpetas deben existir y ser escribibles

*Pantalla principal:*
- Tres selectores de archivo (base mensual, planes, pagos) con botón de explorador y validación visual inmediata (✓ / ✗)
- Panel de estado: muestra si el estado mensual está cargado y para qué período
- Botón "Procesar" (habilitado solo si los tres archivos están validados)
- Área de log en tiempo real (scrollable)
- Barra de progreso

*Pantalla de resultado:*
- Resumen: registros procesados, excluidos totales, desglose de exclusiones por motivo (RECUPERO=SI, ECOSISTEMA ≠ PURO, cajon fuera de scope, teléfono inválido)
- Paths de los archivos generados (ROMAN y PCT)
- Botón "Abrir carpeta de salida"
- Botón "Nueva ejecución" (vuelve a pantalla principal)

**Criterios de aceptación:**
- La UI corre sin errores en Windows con Python instalado (previo al empaquetado)
- El botón "Procesar" no se puede presionar si algún archivo no está validado
- Si un archivo de OneDrive no está disponible offline, muestra mensaje específico: "El archivo no está disponible localmente. Abrí OneDrive y asegurate de que esté descargado antes de continuar."
- El log se actualiza en tiempo real durante el procesamiento (no al finalizar)
- La pantalla no se congela durante el procesamiento (uso de threading)

**Dependencias:** T1

---

### T3 — Validación de archivos de entrada

**Objetivo:** detectar problemas en los archivos antes de procesar, con mensajes claros para el operador.

**Descripción:**

Validaciones a implementar antes de habilitar el botón "Procesar":

| Validación | Mensaje si falla |
|---|---|
| Archivo existe en disco | "El archivo no fue encontrado" |
| Archivo accesible (no solo placeholder de OneDrive) | "El archivo está en la nube y no se puede leer todavía. Para descargarlo: abrí el Explorador de Windows → navegá hasta el archivo → hacé clic derecho → seleccioná 'Mantener siempre en este dispositivo'. Esperá a que aparezca el tilde verde y volvé a intentarlo. Para evitar este problema en el futuro, podés hacer lo mismo sobre toda la carpeta donde recibís los archivos." |
| Extensión correcta (`.xlsx`, `.txt`, `.csv` según corresponda) | "El formato del archivo no es el esperado" |
| Archivo no está abierto en Excel u otro programa | "El archivo está siendo usado por otro programa. Cerralo e intentá de nuevo" |
| Estado mensual existe para el período actual | "No hay estado mensual para [MES]. ¿Es la primera ejecución del mes?" |

**Criterios de aceptación:**
- Cada validación muestra su mensaje específico, no un error genérico
- Las validaciones se ejecutan al seleccionar cada archivo (no solo al presionar "Procesar")
- Si hay múltiples problemas, se muestran todos juntos, no de a uno

**Dependencias:** T1, T2

---

### T4 — Empaquetado con PyInstaller

**Objetivo:** generar un `.exe` autocontenido que corra en Windows sin Python instalado.

**Descripción:**
- Consolidar `requirements.txt` con todas las dependencias de `back-base`, `back-resultados` y la UI
- Crear el archivo `.spec` de PyInstaller con:
  - Inclusión de assets (íconos, fuentes si aplica)
  - Inclusión de archivos de configuración default
  - Modo `--onefile` o `--onedir` según tamaño resultante
- Probar el `.exe` en una máquina Windows limpia (sin Python instalado)
- Documentar el proceso de build para poder regenerar el ejecutable ante cambios

**Criterios de aceptación:**
- El `.exe` corre en Windows sin Python ni dependencias instaladas
- El tamaño del ejecutable es razonable (< 150 MB)
- El tiempo de inicio de la app es menor a 10 segundos
- La app no dispara falsos positivos en Windows Defender (validar con firma o exclusión documentada)
- El proceso de build está documentado y es reproducible

**Dependencias:** T2, T3

---

### T5 — Documentación de usuario

**Objetivo:** un documento claro que cubra ambos modos de uso — UI para el operador no técnico, CLI para quien necesite automatizar.

**Descripción:**
- Instrucciones de instalación (descargar, ejecutar por primera vez, configurar carpetas)
- Flujo de uso diario en modo UI, paso a paso con capturas de pantalla
- Referencia de uso en modo CLI: argumentos disponibles, ejemplos de comandos, integración con Task Scheduler de Windows
- Sección de errores frecuentes y cómo resolverlos (especialmente el caso OneDrive)
- Formato: PDF

**Criterios de aceptación:**
- Cualquier persona sin conocimiento técnico puede instalar y usar la app en modo UI siguiendo el documento
- Un operador técnico puede configurar una ejecución automática via CLI leyendo la sección correspondiente
- Cubre el caso de error de OneDrive explícitamente en ambos modos
- Incluye capturas de pantalla reales de la app terminada

**Dependencias:** T4

---

## Criterios de aceptación de la Fase 4

- El `.exe` corre en una PC con Windows sin Python instalado
- El operador puede completar el procesamiento diario completo sin abrir una terminal (modo UI)
- El mismo `.exe` puede correrse desde consola pasando `--cli` y los archivos como argumentos (modo CLI)
- En modo CLI, el ejecutable devuelve exit code 0 si éxito y 1 si error — apto para automatización con Task Scheduler u otros scripts
- Si un archivo de OneDrive no está disponible offline, ambos modos informan el problema con mensaje claro y accionable
- El estado persistente se puede apuntar a cualquier carpeta local o de OneDrive personal
- El resultado del procesamiento queda visible en pantalla (UI) o en stdout (CLI) con desglose de exclusiones por motivo
- Los tests existentes de `back-base` y `back-resultados` siguen pasando sin cambios
- Existe documentación de usuario en PDF que cubre ambos modos de uso

---

## Orden de ejecución recomendado

```
Pre-condición: Cerrar D4 con Naranja X
        │
        ▼
T1 — Refactorizar ETL como librería   ←── puede arrancar ya
        │
        ├──────────────────────┐
        ▼                      ▼
T2 — UI               T3 — Validaciones
        │                      │
        └──────────┬───────────┘
                   ▼
          T4 — Empaquetado PyInstaller
                   │
                   ▼
          T5 — Documentación de usuario
```

---

## Semáforo al inicio de Fase 4

| Item | Estado |
|---|---|
| D2 — Scope cajones | ✅ CERRADO (M90 + ECOSISTEMA=PURO) |
| D3 — Schema ROMAN | ✅ CERRADO (recupero/tipo_pago solo uso interno) |
| D4 — Mapa tipificaciones | ⚠️ PENDIENTE — bloqueante para arrancar |
| Core ETL Fase 3 | ✅ Operativo y testeado (30 tests passed) |
| Colisión imports `etl` | ✅ Resuelta (namespaces separados) |
