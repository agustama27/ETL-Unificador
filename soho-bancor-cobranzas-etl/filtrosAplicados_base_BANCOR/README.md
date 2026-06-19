# filtrosAplicados_base_BANCOR

Mini-proyecto para distribuir un ejecutable Windows que procese una base Bancor con filtros aplicados y guarde historial diario.

## Funcionalidad

- UI en Tkinter con dos pestanas:
  - `Filtros base`: procesamiento historico de base Bancor (flujo original).
  - `Verificacion telefonos`: comparacion entre telefonos de BANCOR_E1KIA (source) y BANCOR_ROMAN (target).
- Pipeline basado en la logica de `back-base/procesos/base_wfm_generator.py`.
- Excluye de la salida filas sin telefono util (`NumeroCelular` y `NumeroTelefono` vacios/nulos).
- Salida principal en XLSX + exportes auxiliares ROMAN y E1KIA.
- Historial diario con estructura:
  - `DD-MM-YYYY/entrada/`
  - `DD-MM-YYYY/salida/`
- Evita pisado en el mismo dia con timestamp en entrada y salida.

## Ejecucion local

Desde esta carpeta:

```bash
python -m pip install -r requirements.txt
python main.py
```

## Build EXE (Windows)

```bat
build_exe.bat
```

Genera el ejecutable en `dist/filtrosAplicados_base_BANCOR.exe`.

## Flujo de procesamiento

1. Seleccionar archivo fuente.
2. Elegir meses de `Fecha_Entrega`.
3. Procesar.
4. La app copia la entrada al historial del dia y guarda el resultado en `salida`.

Nombres de salida por corrida:
- `base_recibida_BANCOR_conFiltros_DDMMAAAA_HHMMSS.xlsx`
- `BANCOR_ROMAN_YYYYMMDD.csv`
- `BANCOR_E1KIA_YYYYMMDD_sinestrategia.csv`

Los tres archivos se generan en la misma carpeta diaria `DD-MM-YYYY/salida/`.

## Resultado de corrida y fallas parciales

- `success`: se generaron correctamente los 3 artefactos.
- `partial_failure`: se genero el XLSX principal, pero fallo ROMAN y/o E1KIA.
- `failed`: fallo fatal del pipeline antes de completar la salida principal.

En `partial_failure` la app mantiene visibles las rutas exitosas y muestra el motivo del artefacto fallido en la UI/log.

## Rollback operativo (release safety)

Si se requiere volver al comportamiento anterior (solo XLSX):

1. Revertir la etapa de exportes auxiliares en `procesos/pipeline_wfm.py`.
2. Revertir el render de artefactos auxiliares en `ui/app.py`.
3. Recompilar con `build_exe.bat`.

No se requieren migraciones ni cambios de datos para este rollback.

## Flujo de verificacion de telefonos

1. Ir a la pestana `Verificacion telefonos`.
2. Seleccionar archivo source (BANCOR_E1KIA).
3. Seleccionar archivo target (BANCOR_ROMAN).
4. (Opcional) Especificar columnas candidatas separadas por coma para source y target.
5. (Opcional) Activar `Generar reporte CSV de faltantes` para exportar detalle.
6. Ejecutar `Verificar telefonos`.

Resultado esperado en pantalla:
- Si no hay faltantes: mensaje `SIN_ANOMALIAS`.
- Si hay faltantes en BANCOR_ROMAN: mensaje `CON_ANOMALIAS`, conteos y ejemplos de telefonos faltantes.
- Si se activa el reporte: se genera un CSV con los faltantes detectados.

La verificacion normaliza numeros para mejorar coincidencia entre BANCOR_E1KIA y BANCOR_ROMAN (equivalencias con prefijos `549`, `54` y variantes locales) antes de calcular faltantes.
