# Harness de desarrollo

El harness permite validar el ETL con archivos sintéticos locales. No incluye
datos, identidades ni detalles de una operación real.

**Política de documentación:** Los ejemplos son genéricos. No documente datos
de clientes ni detalles operativos específicos.

## Flujo local

```bash
python -m pip install -r requirements.txt
python scripts/generate_sample_data.py --run-date 2026-08-04
python main.py --run-date 2026-08-04
python -m pytest tests/ -v
```

`--run-date` resuelve `inputs/<run-date>/` y `outputs/<run-date>/`.
`--reference-date` es independiente. `--overwrite` permite reemplazar solo
las exportaciones fijas de la partición elegida; `--output` y rutas arbitrarias
de origen se rechazan antes de ejecutar el pipeline.

Las pruebas sintéticas incluyen una fila ARS de repuestos: se descarta antes
de registrar identidad o teléfonos. La corrida informa únicamente el conteo
agregado por fuente. `--tipo-cambio` queda aceptado de forma temporal solo
como argumento obsoleto sin efecto; debe ser finito y positivo si se provee.

## Protección de datos

- `inputs/` y `outputs/` están ignorados por Git.
- Los tests generan sus propios fixtures sintéticos.
- Antes de un commit, verificá `git status --short` para confirmar que no haya
  archivos bajo esos directorios.
- Si necesitás reproducir un problema, usá únicamente valores ficticios y
  minimizados.
