# Plan de implementación — Quita de Intereses en `soho-bancor-cobranzas-etl`

> **Repo:** https://bitbucket.org/evoltis/soho-bancor-cobranzas-etl
> **Módulo afectado:** `back-base/` — función `procesar_base_completa()` en `back-base/procesos/base_generator.py` (pipeline "sin-filtros" que genera `BANCOR_ROMAN_YYYYMMDD.csv`)
> **Objetivo:** agregar 3 columnas al ROMAN (`aplica_quita`, `monto_quita_ars`, `fecha_limite_quita`) que el agente Cynthia (Retell, flow v1.4.0) ya espera como variables dinámicas.
> **Contexto de negocio:** `[BANCOR] COBRANZAS | QUITAS DE INTERESES | CASOS DE USO` (criterios 20–25): pago total con quita según días de mora y tipo de mercado, sujeto a autorización posterior de Bancor.
> **Estado del análisis:** ✅ Plan verificado contra el código real de `main` (commit del 11/06/2026) y contra datos reales (`GYM_Evoltis_10-06.xlsx`, `BANCOR_ROMAN_20260608.csv`).

---

## 0. Instrucciones para el agente implementador

Este repo tiene su propio sistema de guía para agentes. **Antes de codear, leé en este orden:**

1. `AGENTS.md` (raíz) — reglas generales.
2. `back-base/AGENTS.md` — convenciones del módulo.
3. Skills del repo: `skills/code-conventions.md`, `skills/data-model.md`, `skills/feature-implementation.md`, `skills/testing.md`.

Reglas que aplican sí o sí (del AGENTS.md): funciones top-level sin clases, `pathlib.Path` relativo, lectura multi-encoding, salida CSV `;` UTF-8, mínimo blast radius, generar siempre el archivo debug, y **actualizar `back-base/AGENTS.md` y `propuesta_cambios_etl_bancor.md`-style doc al cierre** (el repo documenta cada cambio de contrato).

---

## 1. Cómo funciona hoy el pipeline (verificado en código)

`main.py` → `procesar_base_completa()`:

1. Lee CSV/Excel de `back-base/base-recibida/` (`leer_archivo_entrada`, soporta el GYM xlsx).
2. `normalizar_encabezados_nuevas_columnas(df)` — normaliza variantes de headers a canónicos.
3. **Filtros a nivel operación:** excluye `EstadoDescripcion == 'Cancelada'`, excluye `SaldoCapital == 0`, mantiene `MontoAdeudado > 0`.
4. Selección de columnas: lista `columnas_seleccionadas` (29 columnas). **⚠️ `Tipo_Mercado`, `Compensatorio` y `Punitorios` NO están en la lista hoy** — el GYM las trae pero el ETL las descarta acá. Este es el primer punto de cambio.
5. `filtrar_acuerdos_vigentes(df)` — excluye operaciones con promesa/refi vigente (≤7 días).
6. Consolidación: `groupby('CUIL')` con `consolidar_grupo(grupo)`:
   - `MontoAdeudado` = `sum`
   - `Dias_Mora` = `max`
   - `oferta_importe` = `'si'` si algún `OFERTA_Importe > 0`
   - `AnticipoMinimo` = primera fila (es nivel cliente)
   - `resumen_productos` = `construir_resumen_productos(grupo)`
7. `deduplicar_por_telefonos`.
8. Drop de `columnas_redundantes` (SaldoCapital, InteresAdeudado, etc.).
9. `normalizar_valores_sin_filtros(df)` — formatea montos/fechas/teléfonos **y normaliza columnas "booleanas"** (ver trampa T2).
10. `normalizar_columnas_semanticas_sin_filtros(df)` — snake_case + prefijos semánticos vía `_nombre_columna_semantico` (ver trampa T1).
11. Reordena/selecciona por `columnas_objetivo` (21 columnas finales) + re-normaliza `oferta_importe` a si/no.
12. `validar_contrato_roman(df_salida, df_origen)` — invariantes del contrato.
13. Escribe `BANCOR_ROMAN_YYYYMMDD.csv` (`;`, utf-8).

### ⚠️ Discrepancia detectada (resolver en discovery)

El ROMAN **desplegado** (08/06) tiene **22 columnas** — incluye `fecha_limite_oferta` al final — pero `columnas_objetivo` en `main` tiene **21** y la cadena `fecha_limite` no aparece en `base_generator.py`. Alguien o algo agrega esa columna después (¿paso manual? ¿n8n? ¿campaign-manager?).
**Acción:** identificar dónde se agrega `fecha_limite_oferta` antes de decidir dónde inyectar `fecha_limite_quita`. Si es un post-paso externo, lo correcto es **traer ambas fechas al ETL** y eliminar el post-paso, o como mínimo agregar la nueva columna en el mismo lugar. Preguntar a Agustín (último committer) si no surge del código.

---

## 2. Las tres trampas del código actual (T1–T3)

Estas son reales y romperían el cambio si se ignoran:

**T1 — El normalizador semántico renombraría `aplica_quita` a `txt_aplica_quita`.**
`_nombre_columna_semantico()` no reconoce el token "aplica" y cae al default `txt_`. El agente espera `{{aplica_quita}}` exacto.
✅ Fix: agregar `'aplica_quita': 'aplica_quita'` al dict `mapeo_explicito` (mismo patrón que ya usa `'oferta_importe': 'oferta_importe'`). `monto_quita_ars` y `fecha_limite_quita` están a salvo (prefijos `monto_`/`fecha_` pasan intactos).

**T2 — `normalizar_valores_sin_filtros` convierte `si`/`no` → `true`/`false`.**
El loop de detección booleana toma cualquier columna object cuyos valores estén todos en `{si, no, ...}` y los pasa por `_normalizar_booleano_texto` → `'si'` se convierte en `'true'`. Por eso el código ya tiene el contra-hack para `oferta_importe`: `replace({'true': 'si', 'false': 'no', '': 'no'})` DESPUÉS de la normalización.
✅ Fix: replicar exactamente ese mismo replace para `aplica_quita` en el mismo punto del pipeline (post `columnas_objetivo`).

**T3 — `Compensatorio`/`Punitorios` llegan como texto con decimal europeo cuando el input es CSV.**
El GYM puede entrar como xlsx (floats nativos) o como CSV `;` con decimal `,`.
✅ Fix: convertir con el patrón existente `astype(str).str.replace(',', '.')` + `pd.to_numeric(errors='coerce')` o reutilizar `_parsear_decimal()`, igual que hace el código con `MontoAdeudado`.

---

Para llevar a cabo la implementación, crea una nueva rama llamada feature/pago-con-quitas

## 3. Especificación funcional de las 3 columnas

Se agregan **al final** de `columnas_objetivo` (después de `cnt_dias_mora_max` y de `fecha_limite_oferta` si se incorpora al ETL):

### 3.1 `aplica_quita` (string: `si` / `no`)

```
aplica_quita = "si"  ⟺  TODAS:
  (a) Tipo_Mercado del cliente == "MA"                  # decisión D1, constante config
  (b) 61 <= Dias_Mora_max_cliente <= 365                # decisión D2
  (c) quita_calculada > 0                               # descuento real (ver 3.2)
  (d) monto_quita_ars < monto_adeudado_ars              # sanity
  (e) [flag EXCLUIR_SI_TIENE_OFERTA=true] oferta_importe == "no"   # decisión D3
caso contrario → "no"
```

Hechos verificados en datos (snapshot GYM 10-06, 8.841 ops / 4.351 CUILs):
- `Tipo_Mercado` ∈ {MA: 8.684, MC: 157} y es **100 % uniforme por CUIL**. Si a futuro un cliente viniera mixto → NO elegible + warning en log.
- 142 clientes elegibles por mercado+mora tienen Comp y Punit en 0 → la condición (c) los excluye (sin ella, Cynthia ofrecería "pagar lo mismo con descuento").

### 3.2 `monto_quita_ars` (number, 2 decimales fijos)

Precalculado — el agente solo lo verbaliza (su prompt prohíbe calcular/redondear montos).

```
# Dentro de consolidar_grupo (todas las operaciones sobrevivientes del cliente):
comp_total  = Σ Compensatorio
punit_total = Σ Punitorios

(pct_comp, pct_punit) según Dias_Mora max del cliente:
   61–90   → (0.00, 1.00)
   91–180  → (0.30, 1.00)
   181–365 → (0.50, 1.00)

quita           = pct_comp * comp_total + pct_punit * punit_total
monto_quita_ars = round(MontoAdeudado_consolidado - quita, 2)
```

`MontoAdeudado_consolidado` es **el mismo** `grupo['MontoAdeudado'].sum(min_count=1)` que ya calcula `consolidar_grupo` — usar esa variable, no recalcular, para que el contraste "en lugar de X pagás Y" sea coherente al teléfono.

Formato de salida: usar `_formatear_decimal_fijo_2()` (ya existe en el módulo). NO incluirla en la lista `columnas_monto` de `normalizar_valores_sin_filtros` (ese formateador borra los `.00` y acá queremos 2 decimales fijos como en `resumen_productos`).

Edge cases:
- Comp/Punit nulos → tratar como 0 (`_parsear_decimal` devuelve None → 0).
- `quita <= 0` → `aplica_quita='no'`, `monto_quita_ars=''` (vacío; un valor presente siempre significa oferta real).
- `monto_quita_ars <= 0` (anómalo) → `aplica_quita='no'` + warning con CUIL.
- Cliente no elegible → `aplica_quita='no'`, `monto_quita_ars=''`, `fecha_limite_quita=''`.

### 3.3 `fecha_limite_quita` (date `YYYY-MM-DD`)

No existe en el GYM → parámetro de configuración con precedencia:
1. Config/env `FECHA_LIMITE_QUITA` (fecha fija de campaña) si está definida.
2. Fallback: mismo valor que `fecha_limite_oferta` del cliente (cuando se resuelva la discrepancia de la sección 1).

🔴 Pendiente de negocio: Bancor no definió la fecha. Dejar el parámetro cambiable sin tocar código.

---

## 4. Decisiones de diseño

| # | Decisión | Estado |
|---|---|---|
| D1 | `MA` = "Mercado Abierto" (universo elegible del PDF). Constante `TIPO_MERCADO_ELEGIBLE = "MA"` en config. | ⚠️ Inferida de los datos; **pendiente confirmación Bancor** |
| D2 | Rango de mora a nivel cliente con `max(Dias_Mora)` (= el `cnt_dias_mora_max` que el agente ya verbaliza). Alternativa por operación documentada pero no implementada. | ✅ Tomada, flag de revisión con Bancor |
| D3 | Exclusividad con oferta pre-calculada: flag `EXCLUIR_SI_TIENE_OFERTA` default `true`. La exclusión vive en el ETL a propósito: el flow v1.4.0 enruta todos los rechazos por el branch de elegibilidad, cambiar la regla no requiere tocar el agente. | ⚠️ Abierta, default conservador |
| D4 | IVA de los intereses: el GYM trae `IVACompensatorio`, `PercepIVACompensatorio`, `IVAPunitorios`, `PercepIVAPunitorios`. Fórmula default NO los condona; flag `QUITA_INCLUYE_IVA` default `false` que, si se activa, suma `pct_comp*(IVAComp+PercepIVAComp) + pct_punit*(IVAPunit+PercepIVAPunit)` a la quita. | ⚠️ **Consultar a Bancor** |
| D5 | Columnas nuevas al final del CSV; `si`/`no` minúscula; fechas `YYYY-MM-DD`; montos punto decimal 2 fijos. | ✅ Consistente con formato existente |

---

## 5. Cambios concretos en el código (Fase por fase)

### Fase 0 — Discovery residual (corto)
- Resolver el misterio `fecha_limite_oferta` (sección 1). Decide dónde nace `fecha_limite_quita`.
- Localizar el componente que mapea columnas ROMAN → variables dinámicas de Retell (probablemente repo `campaign-manager` o flujo n8n). Si usa whitelist, anotar el cambio necesario allí (`aplica_quita`, `monto_quita_ars`, `fecha_limite_quita`). **Falla silenciosa si se omite:** el branch de elegibilidad del flow caería siempre a refinanciación.

### Fase 1 — Config (`back-base/procesos/config_quita.py`, nuevo)
Seguir el patrón del repo "pure-data config modules" (solo dicts/listas/funciones simples):

```python
TIPO_MERCADO_ELEGIBLE = 'MA'
EXCLUIR_SI_TIENE_OFERTA = True
QUITA_INCLUYE_IVA = False
FECHA_LIMITE_QUITA = None  # 'YYYY-MM-DD' fijo de campaña, o None → fallback

RANGOS_QUITA = [
    {'mora_min': 61,  'mora_max': 90,  'pct_comp': 0.00, 'pct_punit': 1.00},
    {'mora_min': 91,  'mora_max': 180, 'pct_comp': 0.30, 'pct_punit': 1.00},
    {'mora_min': 181, 'mora_max': 365, 'pct_comp': 0.50, 'pct_punit': 1.00},
]
```

### Fase 2 — `base_generator.py`, función pura + integración
1. Nueva función top-level `calcular_quita(tipo_mercado, dias_mora_max, comp_total, punit_total, monto_adeudado, tiene_oferta, iva_totales=None) -> tuple[str, float|None]` — testeable en aislamiento, implementa la spec 3.1/3.2.
2. `columnas_seleccionadas` (en `procesar_base_completa`): agregar `'Tipo_Mercado'`, `'Compensatorio'`, `'Punitorios'` (+ las 4 de IVA solo si `QUITA_INCLUYE_IVA`).
3. Conversión numérica de `Compensatorio`/`Punitorios` con el patrón europeo existente (trampa T3), junto a la conversión de `MontoAdeudado`.
4. En `consolidar_grupo`: sumar comp/punit del grupo, tomar `Tipo_Mercado` de la primera fila (uniforme por cliente), invocar `calcular_quita` usando el MontoAdeudado ya consolidado y el `Dias_Mora` max ya calculado. Setear `resultado['aplica_quita']`, `resultado['monto_quita_ars']`, `resultado['fecha_limite_quita']`.
5. `columnas_redundantes`: agregar `'Tipo_Mercado'`, `'Compensatorio'`, `'Punitorios'` (las crudas se descartan tras el cálculo; no salen al ROMAN).
6. `mapeo_explicito` en `_nombre_columna_semantico`: agregar `'aplica_quita': 'aplica_quita'` (trampa T1).
7. Post-`columnas_objetivo`: replicar para `aplica_quita` el replace `{'true': 'si', 'false': 'no', '': 'no'}` que ya existe para `oferta_importe` (trampa T2).
8. `columnas_objetivo`: append `'aplica_quita', 'monto_quita_ars', 'fecha_limite_quita'` al final.
9. Encabezados: agregar variantes de `Tipo_Mercado` (`'Tipo Mercado'`, `'tipo_mercado'`, `'TipoMercado'`) a `normalizar_encabezados_nuevas_columnas` por robustez.

### Fase 3 — `validar_contrato_roman` (extender)
Nuevos invariantes (warning en consola, mismo estilo):
- `aplica_quita` ∈ {`si`, `no`} en todas las filas.
- `aplica_quita == 'si'` ⇒ `monto_quita_ars` numérico, `0 < monto_quita_ars < monto_adeudado_ars`, `fecha_limite_quita` con formato `YYYY-MM-DD`.
- `aplica_quita == 'no'` ⇒ `monto_quita_ars == ''` y `fecha_limite_quita == ''`.
- Log resumen por corrida: total clientes / elegibles / excluidos por mercado / por mora / por descuento-cero / por oferta-existente.

### Fase 4 — Tests (`tests/back_base/test_calcular_quita.py`, pytest, skill `testing`)
1. Porcentajes por rango: mora 75 → (0, 1.00); 150 → (0.30, 1.00); 300 → (0.50, 1.00).
2. Bordes exactos: 60→no; 61→sí; 90/91 cambia rango; 180/181 cambia; 365→sí; 366→no.
3. MC en cualquier rango → no. Tipo_Mercado vacío/None → no.
4. Comp=0 y Punit=0 → ('no', None).
5. `tiene_oferta=True` con flag default → no; con flag en False → sí.
6. Redondeo 2 decimales; `monto_quita < monto_adeudado` siempre que aplique.
7. Decimal europeo: `'12943845,00'` parsea bien (T3).
8. Test de no-regresión de naming: tras el pipeline completo, las columnas se llaman exactamente `aplica_quita`, `monto_quita_ars`, `fecha_limite_quita` (cubre T1) y los valores son `si`/`no` (cubre T2).

### Fase 5 — Validación end-to-end + documentación
- Correr `python back-base/main.py` con `GYM_Evoltis_10-06.xlsx` en `base-recibida/`.
- Números de referencia (orden de magnitud; los filtros del ETL pueden moverlos): ~2.425 CUILs elegibles por mercado+mora de 4.351; ~142 caen por descuento-cero; distribución de ops MA por rango 61–90: ~12 / 91–180: ~693 / 181–365: ~4.255.
- **A1 (crítico):** diff del ROMAN regenerado vs versión previa del código = exactamente las 3 columnas nuevas; las 21/22 existentes byte-idénticas.
- Actualizar `back-base/AGENTS.md` (Data Model + Filters) y crear doc de cambio estilo `propuesta_cambios_etl_bancor.md` con la spec final.

---

## 6. Riesgos

1. **D1 sin confirmar (MA):** universo equivocado si la interpretación falla. Mitigación: constante config + log resumen.
2. **Whitelist Retell no actualizada:** `{{aplica_quita}}` vacío → el flow cae siempre a refi, sin error visible. Mitigación: Fase 0 + llamada de prueba verificando variables inyectadas.
3. **Doble agregación incoherente:** la quita DEBE usar el MontoAdeudado consolidado existente (Fase 2.4), nunca un recálculo paralelo.
4. **Trampas T1/T2:** cubiertas con el test de no-regresión de naming (Fase 4.8). Sin ese test, un refactor futuro del normalizador puede romper el contrato silenciosamente.
5. **Fecha límite indefinida:** parámetro configurable + pendiente explícito con Bancor.
6. **`fecha_limite_oferta` fantasma:** mientras no se sepa quién la agrega, el contrato del ROMAN desplegado ≠ repo. Resolver en Fase 0 antes de mergear.

---

## 7. Fuera de alcance

- El flow del agente (v1.4.0 ya espera estas columnas; no tocar).
- El workflow n8n + SQS del mail a `cobranzasbancor@evoltis.com` (dispara por la variable post-call `quita_voluntad_acuerdo`).
- Las tipificaciones post-call (congeladas por pedido del cliente interno).
- Los módulos `back-resultados`, `back-cargaMasiva`, `back-cupones` y el pipeline `con-filtros` (`procesar_base()`): este cambio toca únicamente `procesar_base_completa()` y soporte.
