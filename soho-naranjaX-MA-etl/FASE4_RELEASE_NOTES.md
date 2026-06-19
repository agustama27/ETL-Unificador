# Fase 4 - Release Notes (estado actual)

Fecha de actualizacion: 2026-05-04
Proyecto: soho-naranjaX-MA-etl

## 1) Cambios funcionales implementados desde la version original de Fase 4

- `id_dni` ahora preserva el valor crudo de origen (por ejemplo `DU26373245`), sin recortar prefijos.
- Se agrega `id_producto` en salida ROMAN inmediatamente despues de `id_dni` (contrato de columnas mantenido).
- Se incorporo soporte de formato PLANES tipo `Planes 29-04.xlsx` (mapeo por alias de columnas).
- Se incorporo soporte de formato PAGOS tipo `evoltis_avanzada_pagos_detalle_20260428.csv` (auto-deteccion de delimitador y alias).
- Se restauro la logica de PAGOS (hotfix A): aplica descuento por `importe_pago` y exclusion persistente de clientes con `RECUPERO=SI`.
- Se agrego fail-fast de cobertura de PLANES: si hay archivo PLANES pero la cobertura de `plan_*` en ROMAN queda por debajo del minimo, la corrida falla con mensaje accionable.
- Se ordena ROMAN de forma deterministica por `tel_3`, `id_dni`, `id_producto` (con `tel_3` vacio al final).

## 2) Comportamiento operativo actual

- Corrida normal (UI): requiere `Base mensual` + `Planes` validos y `estado_YYYYMM.csv` existente para habilitar `Procesar`; `PAGOS` es opcional.
- Corrida normal (core/CLI): puede procesar sin diarios; si faltan PLANES y PAGOS, usa el estado vigente y mantiene valores mensuales/diferidos.
- Primer dia habil con solo base cruda y sin diarios: si no existe `estado_YYYYMM.csv`, se inicializa desde base; la corrida puede continuar sin diarios, pero no aplica actualizaciones diarias de PLANES/PAGOS.
- Recomendacion OneDrive: separar carpeta de entrada diaria (archivos nuevos) de carpeta de procesados (`...\\procesados\\YYYYMMDD`) para evitar reprocesos; mantener ambas disponibles localmente (tilde verde) antes de correr.

## 3) Checklist de validacion post-run

- Verificar `status=success` y ausencia de errores en log diario.
- Confirmar generacion de `NARANJAX_MA_ROMAN_YYYYMMDD.csv` en carpeta de salida.
- Validar en header ROMAN que `id_producto` exista y quede justo despues de `id_dni`.
- Tomar una muestra de filas y confirmar que `id_dni` conserve formato crudo (incluyendo prefijo `DU` cuando aplique).
- Si hubo PLANES, validar que existan columnas `plan_*` con cobertura razonable (no todo vacio).
- Si hubo PAGOS, validar impacto esperado: deuda ajustada por `importe_pago` y exclusion de `RECUPERO=SI` del estado persistente.
- Confirmar actualizacion de `estado_YYYYMM.csv` y snapshot `estado_YYYYMMDD.csv`.
- Confirmar movimiento de diarios usados a `procesados\\YYYYMMDD`.

## 4) Riesgos / pendientes conocidos

- Si se selecciona un PLANES con estructura valida pero bajo cruce efectivo, el fail-fast corta la corrida (comportamiento esperado, requiere correccion de insumo/llaves).
- Persisten riesgos operativos de OneDrive placeholder o archivos bloqueados por Excel; la validacion avisa, pero depende de accion del operador.

## 5) Comandos utiles (CLI)

```powershell
python "C:\Users\agustin.tamagusuku\Desktop\soho-naranjaX-MA-etl\cli\main.py" --base "C:\RUTA\NARANJAX_MA_BaseMensual.xlsx" --planes "C:\RUTA\Planes 29-04.xlsx" --pagos "C:\RUTA\evoltis_avanzada_pagos_detalle_20260428.csv" --estado "C:\RUTA\estado" --salida "C:\RUTA\salida"
```

```powershell
python "C:\Users\agustin.tamagusuku\Desktop\soho-naranjaX-MA-etl\back-base\ejecutar_dia.py" --input "C:\RUTA\NARANJAX_MA_BaseMensual.xlsx" --diarios_dir "C:\RUTA\entrada" --estado_dir "C:\RUTA\estado" --output_dir "C:\RUTA\salida" --procesados_dir "C:\RUTA\procesados" --fecha 20260504
```
