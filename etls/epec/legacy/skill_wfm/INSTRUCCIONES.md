# Skill WFM - Uso de `base_generator.py`

## 1) Proposito del script

`base_generator.py` consolida archivos de entrada con datos de clientes y telefonos, normaliza telefonia argentina, elimina telefonos invalidos, deduplica por clave compuesta de telefonos y genera archivos listos para consumo operativo.

Flujo principal:
- Lee todos los `.csv`, `.xlsx` y `.xls` desde `base-recibida/`.
- Homologa columnas y consolida en un unico DataFrame.
- Normaliza `TELEFONO` y `TELEFONO_CELULAR`.
- Excluye telefonos invalidos (vaciando la celda, no borrando fila).
- Deduplica por PK compuesta `TELEFONO;TELEFONO_CELULAR`.
- Genera salida consolidada y salida especifica de telefonos.

## 2) Estructura esperada de carpetas

El script calcula la carpeta base como `Path(__file__).parent.parent`. Si usas esta copia en `skill_wfm/base_generator.py`, el layout esperado es:

```text
<proyecto>/
  base-recibida/
    archivo1.csv
    archivo2.xlsx
    ...
  base-generada/            (se crea automaticamente)
  skill_wfm/
    base_generator.py
    INSTRUCCIONES.md
```

## 3) Formato esperado de entrada

### Archivos admitidos
- CSV (`.csv`)
- Excel (`.xlsx`, `.xls`)

### Delimitador y encoding (CSV)
- Intenta `;` y `,` como separador.
- Intenta encodings: `utf-8`, `latin-1`, `cp1252`, `iso-8859-1`.

### Columnas relevantes
- Recomendadas/prioritarias: `RAZON_SOCIAL`, `TELEFONO`, `TELEFONO_CELULAR`.
- Puede procesar archivos con columnas distintas; unifica el set total de columnas.
- `TELEFONO` y `TELEFONO_CELULAR` se leen como texto para preservar formato.

### Tipos de datos
- Telefonos: texto (se limpian a solo digitos durante normalizacion).
- Resto: segun inferencia de pandas.

## 4) Salidas generadas

En `base-generada/`:
- `base_epec_DDMMYYYY.csv`: consolidado final (separador `;`, UTF-8).
- `telefonos_epec_DDMMYYYY.csv`: una linea por registro con telefonos combinados (`celular,telefono` o solo uno).

Salida opcional de debug:
- `base-generada/debug/duplicados_telefono_excluidos_YYYYMMDD_HHMMSS.csv` cuando existen grupos duplicados por PK de telefonos.

## 5) Regla de telefonos (foco en lineas solicitadas)

### Linea 17 - `quitar_15_local_argentino(cuerpo)`
- Busca el patron argentino local: `<caracteristica(2-4)> + 15 + <numero(6-8)>`.
- Si el patron es valido, elimina ese `15` local intermedio.
- Solo aplica si el cuerpo tiene longitud razonable (10-12 antes de remover).

### Linea 47 - `normalizar_numero_telefono(valor, tipo)`
- Limpia todo excepto digitos.
- Quita ceros iniciales.
- Detecta y separa prefijos `54` o `549` ya presentes.
- Elimina prefijos duplicados residuales (`54`/`549`) al inicio del cuerpo.
- Define prefijo final por tipo:
  - `fijo` -> `54`
  - `celular` -> `549`

### Linea 83 - Aplicacion de la regla
- Ejecuta `cuerpo, _ = quitar_15_local_argentino(cuerpo)`.
- Este es el punto exacto donde se remueve el `15` local antes de reconstruir el numero final normalizado.

## 6) Ejecucion (pasos concretos)

Desde la raiz del proyecto:

```bash
python "skill_wfm/base_generator.py"
```

Dependencias minimas:
- `pandas`
- Para Excel: `openpyxl` (o `xlrd` para `.xls` antiguos)

Si falta dependencia de Excel:

```bash
pip install openpyxl
```

## 7) Recomendaciones de validacion

- Confirmar que se generaron ambos archivos en `base-generada/`.
- Revisar en consola metricas de validacion de telefonos (`validos_incluidos` / `invalidos_excluidos`).
- Revisar que `TELEFONO` empiece con `54` y `TELEFONO_CELULAR` con `549`.
- Si aparece archivo debug de duplicados, auditar esos registros excluidos.
- Verificar que el archivo de telefonos no incluya lineas vacias.

## 8) Riesgos / casos borde

- Entradas con columnas de telefono ausentes: el proceso sigue, pero sin normalizacion de esa columna.
- Numeros con formatos atipicos (internacionales, extensiones, texto mixto) pueden terminar vacios si no cumplen reglas.
- El patron del `15` se elimina solo cuando el match es claro; casos ambiguos se conservan.
- Archivos CSV con delimitadores/encodings no contemplados pueden fallar lectura.
- Duplicados por PK de telefonos excluyen todo el grupo, incluida clave vacia repetida (`;`).

## 9) Regla de saneamiento de texto (mojibake)

- El pipeline aplica saneamiento conservador sobre columnas tipo `DESCRIPCION` y `MOTIVO` (incluye variantes de nombre, con/sin tilde).
- Busca patrones tipicos de mojibake UTF-8/Latin-1 (`Ã`, `Â`, `â`, `Ð`, `�`) y solo corrige si la transformacion reduce esos patrones.
- Si el texto ya esta bien, no se modifica.
- Ejemplos esperados: `BuzÃ³n` -> `Buzón`, `colgÃ³` -> `colgó`, `ConexiÃ³n` -> `Conexión`.
