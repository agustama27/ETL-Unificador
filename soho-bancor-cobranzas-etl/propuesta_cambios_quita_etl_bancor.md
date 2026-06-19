# Cambio de contrato ROMAN — Quita de Intereses

> **Rama:** `feature/pago-con-quitas`
> **Fecha:** 2026-06-11
> **Alcance:** agregar 3 columnas al ROMAN (`aplica_quita`, `monto_quita_ars`, `fecha_limite_quita`)
> que el agente Cynthia (Retell, flow v1.4.0) ya espera como variables dinámicas.

---

## 1. Qué se agregó

Tres columnas al final del `BANCOR_ROMAN_YYYYMMDD.csv` (sin-filtros):

| Columna | Tipo | Significado |
|---|---|---|
| `aplica_quita` | `si` / `no` | El cliente es elegible para la quita de intereses |
| `monto_quita_ars` | número (2 decimales fijos) o `''` | Monto final a pagar **con** el descuento aplicado |
| `fecha_limite_quita` | `YYYY-MM-DD` o `''` | Fecha límite de campaña (config); solo cuando `aplica_quita == 'si'` |

## 2. Lógica (fuente única de verdad)

`calcular_quita()` en `back-base/procesos/base_generator.py`. `aplica_quita = 'si'` ⟺ TODAS:

1. `Tipo_Mercado == TIPO_MERCADO_ELEGIBLE` (default `"MA"`)
2. `max(Dias_Mora)` del cliente cae en un rango de `RANGOS_QUITA` (61–365)
3. la quita calculada es `> 0`
4. `0 < monto_quita_ars < monto_adeudado_ars`
5. (si `EXCLUIR_SI_TIENE_OFERTA`) el cliente no tiene oferta pre-calculada

**Fórmula:** `quita = pct_comp·ΣCompensatorio + pct_punit·ΣPunitorios`
(porcentajes según el rango); `monto_quita_ars = round(MontoAdeudado_consolidado − quita, 2)`.
Reutiliza el `MontoAdeudado` ya consolidado — **nunca** un recálculo paralelo.

| Días de mora | pct_comp | pct_punit |
|---|---|---|
| 61–90 | 0.00 | 1.00 |
| 91–180 | 0.30 | 1.00 |
| 181–365 | 0.50 | 1.00 |

## 3. Archivos tocados

| Archivo | Cambio |
|---|---|
| `back-base/procesos/config_quita.py` | **Nuevo.** Módulo de datos puros con los parámetros sintonizables. |
| `back-base/procesos/base_generator.py` | `calcular_quita()`, integración en `procesar_base_completa`/`consolidar_grupo`, trampas T1/T2/T3, validación de contrato, variantes de encabezado `Tipo_Mercado`. |
| `filtrosAplicados_base_BANCOR/procesos/pipeline_wfm.py` | Mismas 3 columnas en el ROMAN del **.exe** (el desplegado); **importa `calcular_quita` de back-base** vía el loader existente para no duplicar la fórmula. Suma `Compensatorio`/`Punitorios` en `_consolidar_base`. |
| `tests/back_base/test_calcular_quita.py` | **Nuevo.** 8 grupos de casos (rangos, bordes, mercado, descuento-cero, oferta, redondeo, decimal europeo, no-regresión de naming). |
| `back-base/AGENTS.md` | Sección "Quita de Intereses" en el contrato del módulo. |

## 4. Dos pipelines, una fórmula

El ROMAN desplegado lo genera el **.exe** (`pipeline_wfm.py`), no `back-base`. Para que la feature
llegue a producción se implementó en **ambos**; el exe importa `calcular_quita` desde back-base
(loader `_load_back_base_generator_module`), garantizando una sola fuente de verdad para la lógica
financiera. (Decisión tomada con el dueño del repo el 2026-06-11.)

## 5. Decisiones abiertas (pendientes de Bancor)

| # | Decisión | Estado |
|---|---|---|
| D1 | `MA` = universo elegible | Inferida de los datos; **pendiente confirmación Bancor** |
| D3 | `EXCLUIR_SI_TIENE_OFERTA = True` | Default conservador |
| D4 | `QUITA_INCLUYE_IVA = False` (no condona IVA de intereses) | **Consultar a Bancor** |
| D5 | `FECHA_LIMITE_QUITA = '2026-06-12'` | Igualada a la oferta desplegada; cambiable en config sin tocar código |

## 6. Verificación

- **Tests:** `35 passed` (8 grupos de quita + suite del exe intacta).
- **End-to-end** sobre `GYM_Evoltis 15-05 1.xlsx`: contrato ROMAN valida OK, **451/4404 clientes elegibles**;
  montos con 2 decimales, `monto_quita < monto_adeudado`, fecha solo en filas `si`, vacíos en `no`.
- **A1 (no-regresión):** diff del ROMAN regenerado (código viejo vs nuevo, mismo input) =
  exactamente `['aplica_quita', 'monto_quita_ars', 'fecha_limite_quita']`; las **21 columnas previas byte-idénticas**.

## 7. Riesgo residual

**Whitelist de Retell:** si el componente que mapea columnas ROMAN → variables dinámicas usa lista
blanca, hay que agregar `aplica_quita`, `monto_quita_ars`, `fecha_limite_quita` allí, o `{{aplica_quita}}`
llegará vacío y el flow caerá siempre a refinanciación (falla silenciosa). Verificar con una llamada de prueba.
