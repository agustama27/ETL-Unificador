# ETL Social Learning

Script de procesamiento de deuda de alumnos para Social Learning.

El proyecto toma un archivo CSV desde `base_recibida`, aplica reglas de transformación y deduplicación por cliente, y genera un nuevo CSV en `base_generada`.

## Qué hace el proceso

- Detecta automáticamente el separador del archivo de entrada (`;` o `,`).
- Toma el CSV más reciente dentro de `base_recibida`.
- Normaliza `CELULAR` a formato E.164.
- Unifica `NOMBRE` + `APELLIDO` en la columna `customer_name`.
- Deduplica por `DOCUMENTO` (una fila final por cliente).
- Calcula:
  - `monto_deuda`: suma de `Monto Cuota`/`MONTO` por cliente.
  - `cantidad_cuotas`: cantidad de filas (cuotas) por cliente.
  - `monto_deuda_descuento`: `monto_deuda` con el porcentaje de `% Descuento`.
- Para `Dias Mora`/`DIAS_VENCIDO`, conserva el valor máximo por cliente.
- Normaliza `MONTO` para dejarlo numérico sin símbolo `$` ni separadores de miles.
- Genera salida en UTF-8 y valida la consistencia estructural del CSV.

## Estructura del proyecto

- `main.py`: punto de entrada para ejecutar el procesamiento.
- `procesos/base_generator.py`: lógica de lectura, transformación y generación.
- `base_recibida/`: carpeta para archivos de entrada (CSV ignorados por Git).
- `base_generada/`: carpeta de salida (CSV ignorados por Git).

## Ejecución

Desde la raíz del proyecto:

```bash
python main.py
```

Al finalizar, se crea un archivo con nombre:

`base_social_learning_DDMMAAAA.csv`

en la carpeta `base_generada`.

## Versionado

El repositorio ignora los CSV de `base_recibida` y `base_generada` mediante `.gitignore`, pero mantiene ambas carpetas en Git usando `.gitkeep`.
