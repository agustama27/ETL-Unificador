# Prompt: Crear proyecto soho-clarouy-encuestas-etl

## Contexto

Sos un agente de software especializado en ETL Python. Vas a crear un proyecto completo
llamado **soho-clarouy-encuestas-etl** siguiendo los mismos patrones arquitectónicos,
convenciones de código y estructura de directorios de un proyecto de referencia que
podés inspeccionar en: `C:\Users\agustin.tamagusuku\Desktop\soho-bancor-cobranzas-etl`

**ANTES DE ESCRIBIR UNA SOLA LÍNEA DE CÓDIGO**, leer obligatoriamente:

1. `soho-bancor-cobranzas-etl/AGENTS.md` — arquitectura general y reglas globales
2. `soho-bancor-cobranzas-etl/skills/code-conventions.md` — convenciones de código
3. `soho-bancor-cobranzas-etl/skills/data-model.md` — contratos de datos
4. `soho-bancor-cobranzas-etl/skills/feature-implementation.md` — orden de implementación
5. `soho-bancor-cobranzas-etl/back-resultados/AGENTS.md` — patrón Retell + ROMAN
6. `soho-bancor-cobranzas-etl/back-base/AGENTS.md` — patrón limpieza de base

---

## Propósito del Nuevo Proyecto

Sistema ETL Python 3.12 que automatiza el procesamiento de encuestas post-contacto para
**Claro Uruguay**. Las encuestas son ejecutadas por un agente de voz de Retell.ai. El
sistema procesa los resultados de las llamadas junto con datos de gestión humana (ROMAN),
produciendo un CSV de análisis interno.

**Dominio**: encuestas de satisfacción post-portabilidad / post-contacto (es-UY).

---

## Estructura de Directorios a Crear

```
soho-clarouy-encuestas-etl/
├── AGENTS.md                          ← Generar al final con toda la documentación
├── README.md
│
├── .claude/
│   └── settings.json                  ← Copiar permisos del proyecto de referencia
│
├── skills/                            ← COPIAR el directorio completo desde el proyecto
│   ├── bug-fix.md                       de referencia (son genéricos y reutilizables)
│   ├── code-conventions.md
│   ├── data-model.md
│   ├── feature-implementation.md
│   ├── testing.md
│   └── skill-creator.md
│
├── back-base/                         ← MÓDULO 1: Limpieza de base de clientes
│   ├── AGENTS.md
│   ├── main.py
│   ├── requirements.txt
│   ├── base-recibida/                 ← INPUT: CSV de clientes Claro Uruguay
│   ├── base-generada/
│   │   ├── con-filtros/
│   │   └── sin-filtros/
│   └── procesos/
│       ├── base_generator.py
│       └── phone_extractor.py
│
├── back-resultados/                   ← MÓDULO 2: Resultados de encuestas Retell + ROMAN
│   ├── AGENTS.md
│   ├── main.py
│   ├── requirements.txt
│   ├── .env                           ← RETELL_API_KEY (gitignored)
│   ├── .gitignore
│   ├── calls/                         ← INPUT: CSV con call_ids exportados de Retell
│   ├── roman/                         ← INPUT: CSV con gestiones humanas ROMAN
│   ├── results/                       ← OUTPUT: CSV de análisis interno (26 columnas)
│   └── procesos/
│       ├── retell_manager.py          ← Llamada paralela a API Retell (100 workers)
│       ├── tipif_generator.py         ← Generador del CSV de 26 columnas
│       ├── roman_manager.py           ← Normalización de datos ROMAN
│       ├── data_merger.py             ← Merge inteligente Retell + ROMAN
│       └── config_encuesta.py         ← Configuración de campos y enums
```

---

## Módulo 1: back-base

Adaptar la lógica de `soho-bancor-cobranzas-etl/back-base/` para el contexto de
Claro Uruguay.

### Diferencias respecto al proyecto de referencia

- **Formato del CSV de entrada**: DESCONOCIDO aún. Implementar la cadena de encoding
  multi-formato como en el proyecto de referencia (`['latin-1', 'iso-8859-1', 'cp1252',
  'utf-8', 'utf-16']`) con detección automática del separador (`,` o `;`).
- **Columna de teléfono**: usar el campo `msisdn` (formato `5989XXXXXXXX`) como
  identificador principal en lugar de CUIT.
- **Columna de identificador único**: usar `customer_id` (formato `CLAROUY-00123456`).
- **Deduplicación**: misma lógica — un `customer_id` puede tener múltiples `msisdn`;
  generar archivo `telefonos_x_cliente_DDMMAAAA.csv`.

### Output de back-base

Dos archivos en `base-generada/`:

- `base_clarouy_DDMMAAAA.csv`: base consolidada (un registro por cliente)
- `telefonos_x_cliente_DDMMAAAA.csv`: teléfonos únicos para cargar en Retell

---

## Módulo 2: back-resultados

Este es el módulo central. Replicar exactamente el patrón de
`soho-bancor-cobranzas-etl/back-resultados/` con las siguientes adaptaciones.

### Variables dinámicas de entrada (inyectadas por Retell antes de la llamada)

Estas variables llegan en `retell_llm_dynamic_variables` del endpoint de la API:

| Variable                 | Tipo    | Descripción                                         |
|--------------------------|---------|-----------------------------------------------------|
| msisdn                   | string  | Número de teléfono del cliente                      |
| customer_id              | string  | ID interno de cliente                               |
| nombre_cliente           | string? | Nombre del cliente (nullable)                       |
| campaign_id              | string  | Campaña que disparó la encuesta                     |
| canal                    | enum    | VOICE / WHATSAPP                                    |
| idioma                   | enum    | Locale (ej: es-UY)                                  |
| max_reintentos_principal | int     | Reintentos para pregunta principal                  |
| max_reintentos_domicilio | int     | Reintentos para validar domicilio                   |
| skill_derivacion         | int     | Skill de destino para derivación a asesor           |

### Variables de análisis post-llamada (en `custom_analysis_data`)

Estas variables las genera el agente Retell en `custom_analysis_data`:

| Variable                | Tipo    | Descripción                                                   |
|-------------------------|---------|---------------------------------------------------------------|
| encuesta_completada     | bool    | ¿Se completó el flujo de la encuesta?                         |
| motivo_cierre           | enum    | OK_RECHAZO_CLIENTE / DERIVADO_ASESOR / FALLIDA_NULL_REC       |
| fecha_hora              | text?   | Fecha/hora para volver a contactar (nullable)                 |
| global_experience       | enum    | MUY_BUENA / PODRIA_MEJORAR / TUVO_INCONVENIENTES / NO_ENTENDIA|
| descripcion_inicial     | text    | Primera explicación libre del cliente                         |
| comentario_mejora       | text    | Comentario de mejoras (cuando experiencia no fue buena)       |
| sin_comentarios         | bool    | true cuando cliente indica que no tiene comentarios           |
| detalle_experiencia     | text    | Detalle adicional ("No me trates de experiencia")             |
| tipo_experiencia        | enum    | MEJORA / INCONVENIENTE                                        |
| categoria               | enum    | COBERTURA_SERVICIO / PORTABILIDAD / FACTURACION / ACTIVACION / ATENCION_CLIENTES / OTROS |
| subcategoria            | enum?   | Subcategoría (configurable, nullable)                         |
| es_cobertura            | bool    | true cuando categoría = COBERTURA_SERVICIO                    |
| texto_domicilio_cliente | text    | Domicilio tal como lo dijo el cliente                         |
| domicilio_validado      | bool    | Resultado de validación del domicilio (proviene de Retell/ROMAN) |
| domicilio_normalizado   | text    | Dirección normalizada en texto libre (proviene de Retell/ROMAN) |
| domicilio_intentos      | int     | Cantidad de intentos de captura/validación                    |
| inconveniente_continua  | bool    | true si el problema sigue vigente                             |
| pudiste_solucionarlo    | bool    | ¿Pudiste solucionarlo?                                        |
| derivar_a_asesor        | bool    | true si acepta hablar con asesor                              |
| skill_destino           | int     | Skill al que se deriva                                        |
| id_caso_reclamo         | string? | ID del caso/reclamo en CRM (nullable)                         |

### Output: CSV de análisis interno (26 columnas)

Archivo: `results/encuestas_clarouy_DDMMAAAA.csv`

- Separador: `;`
- Encoding: `utf-8`
- Decimal: `,`
- Sin índice

**Columnas del output (exactamente en este orden)**:

```
call_id, msisdn, customer_id, nombre_cliente, campaign_id,
encuesta_completada, motivo_cierre, fecha_hora, global_experience,
descripcion_inicial, comentario_mejora, sin_comentarios, detalle_experiencia,
tipo_experiencia, categoria, subcategoria, es_cobertura,
texto_domicilio_cliente, domicilio_validado, domicilio_normalizado,
domicilio_intentos, inconveniente_continua, pudiste_solucionarlo,
derivar_a_asesor, skill_destino, id_caso_reclamo
```

> Nota: `canal`, `idioma`, `max_reintentos_principal`, `max_reintentos_domicilio` y
> `skill_derivacion` son variables operativas de la llamada y NO van al output final.

### config_encuesta.py

Crear este archivo (puro-datos, sin clases ni I/O) con los siguientes contenidos:

```python
# Columnas del output final (orden exacto)
COLUMNAS_SALIDA: list[str] = [
    'call_id', 'msisdn', 'customer_id', 'nombre_cliente', 'campaign_id',
    'encuesta_completada', 'motivo_cierre', 'fecha_hora', 'global_experience',
    'descripcion_inicial', 'comentario_mejora', 'sin_comentarios', 'detalle_experiencia',
    'tipo_experiencia', 'categoria', 'subcategoria', 'es_cobertura',
    'texto_domicilio_cliente', 'domicilio_validado', 'domicilio_normalizado',
    'domicilio_intentos', 'inconveniente_continua', 'pudiste_solucionarlo',
    'derivar_a_asesor', 'skill_destino', 'id_caso_reclamo',
]

# Alias para compatibilidad con tipif_generator (mismo patrón que el proyecto de referencia)
COLUMNAS_FIJAS = COLUMNAS_SALIDA

# Mapeo de nombres de columnas ROMAN → nombres internos
# Agregar variantes conocidas de exportación de ROMAN
MAPEO_COLUMNAS_ROMAN: dict[str, str] = {
    'ID de Llamada': 'call_id',
    'Call ID':       'call_id',
    'call_id':       'call_id',
    'CallID':        'call_id',
    'callId':        'call_id',
    # Añadir resto de mapeos según formato real del CSV ROMAN cuando esté disponible
}

# Grupos de campos por categoría semántica
CAMPOS_TIPIFICACION:  list[str] = ['motivo_cierre', 'global_experience', 'tipo_experiencia', 'categoria', 'subcategoria']
CAMPOS_EXPERIENCIA:   list[str] = ['descripcion_inicial', 'comentario_mejora', 'detalle_experiencia']
CAMPOS_DOMICILIO:     list[str] = ['texto_domicilio_cliente', 'domicilio_validado', 'domicilio_normalizado', 'domicilio_intentos']
CAMPOS_CIERRE:        list[str] = ['encuesta_completada', 'fecha_hora', 'sin_comentarios', 'es_cobertura',
                                    'inconveniente_continua', 'pudiste_solucionarlo', 'derivar_a_asesor',
                                    'skill_destino', 'id_caso_reclamo']

# Campos que ROMAN puede sobrescribir sobre Retell
CAMPOS_SOBRESCRIBIBLES: list[str] = CAMPOS_TIPIFICACION + CAMPOS_EXPERIENCIA + CAMPOS_DOMICILIO + CAMPOS_CIERRE

# Campos que NUNCA se modifican por ROMAN (identidad del registro)
CAMPOS_PROTEGIDOS: list[str] = ['call_id', 'msisdn', 'customer_id', 'campaign_id', 'canal', 'idioma']

# Valores considerados vacíos/nulos en cualquier fuente
VALORES_VACIOS: list = [None, '', 'null', 'NULL', 'n/a', 'N/A', '-', 'nan', 'NaN', 'None']

# Enums válidos por campo
ENUMS_GLOBAL_EXPERIENCE: list[str] = ['MUY_BUENA', 'PODRIA_MEJORAR', 'TUVO_INCONVENIENTES', 'NO_ENTENDIA']
ENUMS_MOTIVO_CIERRE:     list[str] = ['OK_RECHAZO_CLIENTE', 'DERIVADO_ASESOR', 'FALLIDA_NULL_REC']
ENUMS_TIPO_EXPERIENCIA:  list[str] = ['MEJORA', 'INCONVENIENTE']
ENUMS_CATEGORIA:         list[str] = ['COBERTURA_SERVICIO', 'PORTABILIDAD', 'FACTURACION',
                                       'ACTIVACION', 'ATENCION_CLIENTES', 'OTROS']

def es_valor_valido(valor) -> bool:
    """Retorna True si el valor no es considerado vacío/nulo."""
    return valor not in VALORES_VACIOS and str(valor).strip() not in VALORES_VACIOS

def normalizar_booleano(valor) -> bool:
    """Convierte strings y enteros a bool. Retorna False para valores vacíos."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return bool(valor)
    if isinstance(valor, str):
        return valor.strip().lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
    return False
```

### Merge ROMAN

El CSV de ROMAN puede contener cualquier subconjunto de las columnas de `CAMPOS_SOBRESCRIBIBLES`.
Las reglas de merge son idénticas al proyecto de referencia:

- ROMAN siempre actualiza (no reemplaza) sobre Retell
- Solo sobrescribe si el valor ROMAN no está en `VALORES_VACIOS`
- Solo sobrescribe si el valor ROMAN difiere del valor Retell actual
- Campos en `CAMPOS_PROTEGIDOS` nunca se modifican
- El join key es `call_id`
- Retell es el conjunto canónico (no se pierden registros de Retell)
- Registros solo en ROMAN (sin `call_id` en Retell) se descartan con advertencia

---

## Patrones Obligatorios

Copiar e implementar exactamente desde el proyecto de referencia.

### 1. Multi-encoding CSV reader

```python
ENCODINGS = ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252', 'utf-16']

def leer_csv_con_codificacion(path: Path, separador: str = ';') -> tuple[pd.DataFrame, str]:
    for encoding in ENCODINGS:
        try:
            df = pd.read_csv(path, sep=separador, encoding=encoding, low_memory=False)
            return df, encoding
        except UnicodeDecodeError:
            continue
    df = pd.read_csv(path, sep=separador, encoding='latin-1',
                     on_bad_lines='skip', encoding_errors='replace')
    return df, 'latin-1 (errors replaced)'
```

Agregar autodetección de separador: intentar con `,` primero, si el DataFrame tiene
una sola columna reintentar con `;`.

### 2. Llamadas Retell paralelas

- `ThreadPoolExecutor(max_workers=100)` + `as_completed()` + `tqdm`
- Timeout 10s por request
- Errores individuales logueados con `print()`, no se propagan
- DNS caching: monkey-patch de `socket.getaddrinfo` con wrapper cacheante
- Session singleton: `requests.Session` con `HTTPAdapter(pool_connections=100, pool_maxsize=100)`
  y 2 reintentos en errores 5xx

### 3. Búsqueda recursiva de campos en JSON

```python
def buscar_campo_recursivo(objeto, nombre_campo: str, visitados=None):
    """Navega dicts/lists/objetos anidados con protección contra referencias circulares."""
```

Prioridades de búsqueda en la respuesta Retell:
- Dinámicas: `retell_llm_dynamic_variables` → `collected_dynamic_variables` → `dynamic_variables`
- Postcall: `custom_analysis_data` → `postcall` → `post_call`

### 4. Rutas relativas con pathlib

```python
BASE_DIR = Path(__file__).parent.parent  # → raíz del módulo
```

Nunca rutas absolutas. Siempre `BASE_DIR / "subcarpeta"`.

### 5. Bloque `__main__` en cada archivo

Cada archivo en `procesos/` debe cerrar con su bloque `if __name__ == "__main__"` de
prueba aislada. El bloque debe ser funcional (no solo `pass`).

### 6. Output CSV europeo

```python
df.to_csv(path, sep=';', decimal=',', encoding='utf-8', index=False, na_rep='')
```

### 7. Variables de entorno

`.env` en `back-resultados/` con:

```
RETELL_API_KEY=key_...
USE_ROMAN=true
```

Cargar con `python-dotenv`. Si falta `RETELL_API_KEY`, lanzar `ValueError` descriptivo.

Valores aceptados para `USE_ROMAN`: `true`, `1`, `yes`, `sí`, `si` (case-insensitive).

### 8. Columnas aceptadas para call_id en el CSV de Retell

```python
COLUMNAS_CALL_ID = ['Call ID', 'ID de Llamada', 'call_id', 'CallID', 'callId']
```

---

## Archivos de Configuración Obligatorios

### `.gitignore` (en `back-resultados/`)

```
.env
__pycache__/
*.pyc
*.pyo
.DS_Store
```

### `requirements.txt` de back-resultados

```
pandas>=2.0
requests>=2.31
python-dotenv>=1.0
tqdm>=4.66
openpyxl>=3.1
```

### `requirements.txt` de back-base

```
pandas>=2.0
python-dotenv>=1.0
tqdm>=4.66
```

---

## AGENTS.md a Generar

Al finalizar la implementación, generar:

### `AGENTS.md` raíz del nuevo proyecto

Estructura (adaptar al nuevo dominio):

1. Header: nombre del proyecto, propósito, stack
2. Repository Layout (árbol ASCII con conteos de líneas aproximados)
3. End-to-End Data Flow (diagrama ASCII del pipeline)
4. Component Map (tabla módulos → AGENTS.md locales)
5. AI Skills Registry (tabla idéntica al proyecto de referencia)
6. Coding Agent General Rules (mismas 8 reglas del proyecto de referencia)
7. Key Shared Patterns (misma tabla del proyecto de referencia)
8. Environment Variables (tabla actualizada al nuevo proyecto)
9. Running the Modules (comandos exactos para cada módulo)

### `AGENTS.md` por módulo

Cada `back-*/AGENTS.md` debe contener:

1. Propósito + nombre del archivo de output con formato de fecha
2. Árbol de directorios del módulo
3. Key Files: por cada `.py`, listar funciones principales + comportamiento
4. Data Model: spec de input + spec de output con tabla de columnas
5. Environment Variables (solo las relevantes al módulo)
6. Coding Rules (específicas del módulo, 6–8 reglas)
7. Required Skills (cuáles archivos de `skills/` cargar antes de modificar)
8. How to Test: pasos manuales + salida esperada en consola
9. Common Issues: tabla síntoma → causa probable → fix

---

## Verificación Final

Antes de declarar la tarea completada, verificar cada punto:

- [ ] Todos los archivos en `procesos/` tienen bloque `__main__` funcional
- [ ] `config_encuesta.py` contiene todos los enums, grupos de campos y funciones definidos arriba
- [ ] La cadena multi-encoding está implementada en `retell_manager.py`
- [ ] El merge ROMAN respeta `CAMPOS_PROTEGIDOS` y `VALORES_VACIOS`
- [ ] Ninguna ruta absoluta en el código (verificar con grep)
- [ ] Todos los `AGENTS.md` están generados y completos
- [ ] `.gitignore` presente en `back-resultados/`
- [ ] `requirements.txt` presente en cada módulo
- [ ] El directorio `skills/` fue copiado desde el proyecto de referencia

```bash
# Verificar que config_encuesta importa correctamente
python -c "
import sys
sys.path.insert(0, 'soho-clarouy-encuestas-etl/back-resultados/procesos')
import config_encuesta
assert len(config_encuesta.COLUMNAS_SALIDA) == 26, f'Esperadas 26 columnas, encontradas {len(config_encuesta.COLUMNAS_SALIDA)}'
assert 'call_id' in config_encuesta.COLUMNAS_SALIDA
assert 'call_id' in config_encuesta.CAMPOS_PROTEGIDOS
print('OK: config_encuesta validado')
"
```
