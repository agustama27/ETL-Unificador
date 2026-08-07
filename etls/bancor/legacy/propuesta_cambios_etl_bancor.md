# Propuesta de cambios — ETL BANCOR cobranzas (GYM → ROMAN)

**Fecha:** 15/05/2026
**Cliente:** BANCOR (Banco de Córdoba)
**Implementación:** Agente de voz IA para gestión de cobranza en mora
**Input analizado:** `GYM_Evoltis_15-05_1.xlsx` (9.830 operaciones / 4.865 clientes)
**Output analizado:** `BANCOR_ROMAN_20260505.csv` (1.514 filas)

---

## 1. Resumen ejecutivo

El ROMAN actual presenta tres problemas que impiden al agente IA gestionar correctamente clientes con múltiples productos en mora:

1. **`monto_oferta_importe` llega siempre como `"false"` (1.514/1.514 filas).** El agente nunca ve el importe de oferta, ni siquiera puede evaluar la condición `> 0` para ramificar a "presentación con oferta" o "presentación sin oferta".
2. **`monto_adeudado_ars` no coincide ni con la suma ni con el máximo de la deuda real del cliente** (0.1% de coincidencia sobre 1.512 filas).
3. **El detalle por producto se pierde**: agrupadores y números de operación se concatenan con coma sin asociación entre ellos. El agente no puede decirle al cliente qué producto tiene oferta y cuál no.

La propuesta consiste en:
- **Reemplazar** `monto_oferta_importe` (con bug) por `oferta_importe` (`si`/`no`, a nivel cliente).
- **Corregir** `monto_adeudado_ars` para que sea `SUM(MontoVencido)` por CUIL.
- **Agregar** `monto_entrega_ars` (anticipo mínimo del cliente).
- **Agregar** `resumen_productos` (string con detalle por operación, formato pre-armado para el prompt del agente).
- **Eliminar** las columnas que quedan redundantes con `resumen_productos`.

---

## 2. Bugs detectados en el ROMAN actual

### 2.1 Bug crítico — `monto_oferta_importe = "false"` en todas las filas

| Valor de `monto_oferta_importe` | Filas |
|---|---:|
| `"false"` (string) | 1.514 |
| Numérico | 0 |
| Vacío | 0 |

Cruce con `tipo_campana_ref`:

| Campaña | Filas con `"false"` |
|---|---:|
| CAMPAÑA35% | 920 |
| CAMPAÑA45% | 547 |
| CAMPAÑA30% | 30 |
| CAMPAÑA20% | 4 |
| NO APLICA | 13 |

Incluso clientes con ofertas reales en el GYM llegan al ROMAN con `"false"`. El bug afecta al 100% del output.

### 2.2 Bug — `monto_adeudado_ars` no es trazable contra el GYM

Cruzando los 1.512 CUILs comparables:

| Comparación | Coincidencia |
|---|---:|
| `monto_adeudado_ars` = `SUM(MontoAdeudado)` por CUIL | 1 caso (0,1%) |
| `monto_adeudado_ars` = `MAX(MontoAdeudado)` por CUIL | 1 caso (0,1%) |
| `monto_adeudado_ars` = `SUM(MontoVencido)` por CUIL | a validar |

**Ejemplo CUIL 20100505607** (5 productos en GYM):
- ROMAN: `monto_adeudado_ars = 2.038.703,18`
- GYM `SUM(MontoAdeudado)` = 2.102.629
- GYM `SUM(MontoVencido)` = a verificar contra el código del ETL

### 2.3 Bug — Concatenación con coma rompe la asociación producto-deuda

**Ejemplo real** del ROMAN actual (CUIL 20108260174):

```
tipo_agrupador_producto: "Préstamos Personales,Cuenta Corriente"
id_nro_operacion:        "502544036,502421016,...,501839473"   ← 20 IDs
monto_adeudado_ars:      2.255.197                              ← uno solo
monto_oferta_importe:    false                                   ← bug
```

El agente recibe un solo monto agregado y un string con 20 IDs sin saber a cuál corresponde la oferta de la Cuenta Corriente.

---

## 3. Validación de granularidad de cada campo en el GYM

Análisis de qué campos son constantes dentro de un mismo CUIL (== nivel cliente) vs varían por operación (== nivel producto):

| Campo del GYM | % CUILs con un solo valor | Granularidad |
|---|---:|---|
| `Cod_Estudio` | 100,0% | CLIENTE |
| `Tipo_Asignacion` | 99,9% | CLIENTE |
| `PRIORIDAD` | 100,0% | CLIENTE |
| `Sucursal_Cuenta` | 100,0% | CLIENTE |
| `Nro Cuenta` | 100,0% | CLIENTE |
| `Tipo de Cuenta` | 100,0% | CLIENTE |
| `Estado Cuenta` | 100,0% | CLIENTE |
| `Fecha_Gestion` | 100,0% | CLIENTE |
| `GestionDescripción` | 100,0% | CLIENTE |
| `Campaña_REF` | 100,0% | CLIENTE |
| `Deuda_vencida_Clte` | 100,0% | CLIENTE (== `SUM(MontoVencido)`) |
| **`AnticipoMinimo`** | **100,0%** | **CLIENTE — no sumar** |
| **`CapitalClte`** | **100,0%** | **CLIENTE** |
| `Fecha_Entrega` | 98,4% | PRODUCTO |
| `ModuloCodigo` | 74,3% | PRODUCTO |
| **`AgrupadorProducto`** | varía | **PRODUCTO** |
| **`NumeroOperacion`** | único global | **PRODUCTO** |
| **`MontoAdeudado`** | 68,0% | **PRODUCTO** |
| **`MontoVencido`** | 68,0% | **PRODUCTO** |
| **`OFERTA_Importe`** | varía | **PRODUCTO** |
| `Dias_Mora` | varía | PRODUCTO |
| `TipoOperacionDescripcion` | varía | PRODUCTO |

---

## 4. Patrón de ofertas en el GYM

Confirmado que las ofertas (`OFERTA_Importe > 0`) aplican exclusivamente a Tarjeta de Crédito y Cuenta Corriente. Préstamos nunca traen oferta en este corte.

| AgrupadorProducto | Filas | Con oferta | % con oferta |
|---|---:|---:|---:|
| Tarjeta de Crédito | 4.426 | 4.259 | **96 %** |
| Cuenta Corriente | 389 | 368 | **95 %** |
| Préstamos Personales | 4.919 | 0 | 0 % |
| Préstamos Consolidados | 70 | 0 | 0 % |
| Préstamos Refinanciados | 26 | 0 | 0 % |

Segmentación de clientes (sobre 4.865 CUILs en el GYM):

| Segmento | Clientes | % |
|---|---:|---:|
| Todos sus productos tienen oferta | 2.915 | 60 % |
| Productos mixtos (algunos con oferta, otros no) | **1.150** | **24 %** |
| Ningún producto tiene oferta | 800 | 16 % |

---

## 5. Variables definidas (4 cambios principales)

### 5.1 `oferta_importe` (nueva — reemplaza `monto_oferta_importe`)

| Atributo | Valor |
|---|---|
| **Tipo** | string |
| **Valores válidos** | `"si"` / `"no"` |
| **Granularidad** | Cliente |
| **Cálculo** | `"si"` si **al menos un** producto del cliente tiene `OFERTA_Importe > 0`, sino `"no"` |
| **Para qué** | Permite al agente evaluar el nodo condicional de ramificación: ¿presenta oferta o no? |

**Reemplaza:** `monto_oferta_importe` (campo con bug, eliminado).

### 5.2 `monto_adeudado_ars` (modificada — corrección de cálculo)

| Atributo | Valor |
|---|---|
| **Tipo** | decimal |
| **Granularidad** | Cliente |
| **Cálculo** | `SUM(MontoVencido)` agrupado por `CUIL` |
| **Alternativa equivalente** | `first(Deuda_vencida_Clte)` por CUIL (el GYM ya trae el total pre-calculado) |
| **Para qué** | Deuda vencida total del cliente, sumando todos sus productos |

**Cambio:** la lógica actual no es trazable; debe migrarse a la fórmula explícita.

### 5.3 `monto_entrega_ars` (nueva)

| Atributo | Valor |
|---|---|
| **Tipo** | decimal |
| **Granularidad** | Cliente |
| **Cálculo** | `first(AnticipoMinimo)` por `CUIL` — ⚠️ **NO sumar** |
| **Origen GYM** | columna `AnticipoMinimo` |
| **Para qué** | Anticipo mínimo que el cliente debe entregar para aplicar a refinanciación |

⚠️ **Nota crítica:** `AnticipoMinimo` viene repetido en cada fila del cliente (es a nivel cliente). Si el ETL hace una agregación por defecto del tipo `SUM`, el valor se multiplica por la cantidad de productos. **Usar `first()`, `min()` o `max()` indistintamente** — todas dan el mismo resultado porque el valor es constante por CUIL.

### 5.4 `resumen_productos` (nueva)

| Atributo | Valor |
|---|---|
| **Tipo** | string |
| **Granularidad** | Cliente (consolidado, una entrada por operación dentro del string) |
| **Formato** | `[Producto DeudaVencida:{monto} OfertaImporte:{monto} ; Producto DeudaVencida:{monto} OfertaImporte:NO ; ...]` |
| **Separador de productos** | ` ; ` (espacio-punto y coma-espacio) |
| **Delimitadores** | corchetes `[ ]` al inicio y fin |
| **Sin oferta** | literal `OfertaImporte:NO` (no `0`, no vacío) |
| **Con oferta** | número con 2 decimales: `OfertaImporte:1586266.21` |
| **Una entrada por** | `NumeroOperacion` (no se agrupa por AgrupadorProducto: si un cliente tiene dos tarjetas, aparecen las dos como entradas separadas) |
| **Orden sugerido** | por `AgrupadorProducto` luego `NumeroOperacion` |
| **Sin límite de caracteres** | confirmado por negocio |

**Campos del GYM usados:**
- `AgrupadorProducto` → texto del producto
- `MontoVencido` → valor de `DeudaVencida`
- `OFERTA_Importe` → valor de `OfertaImporte` (o `"NO"` si vacío o ≤ 0)

---

## 6. Columnas a eliminar del ROMAN

Estas columnas pierden sentido porque su contenido queda dentro de `resumen_productos` o estaban afectadas por bugs:

| Columna actual | Motivo de eliminación |
|---|---|
| `tipo_agrupador_producto` | Ya aparece dentro de `resumen_productos` para cada producto |
| `monto_vencido_ars` | Ya aparece como `DeudaVencida` por producto dentro de `resumen_productos` |
| `monto_oferta_importe` | Reemplazada por `oferta_importe` (si/no, cliente); el importe por producto está dentro de `resumen_productos` |

---

## 7. Columnas a evaluar (por producto, no incluidas en `resumen_productos`)

Quedan en el ROMAN actual con criterio poco claro de cuál operación toman. Sugiero eliminarlas o definirles un criterio explícito:

| Columna actual | Granularidad | Recomendación |
|---|---|---|
| `id_nro_operacion` | producto | **Eliminar.** El detalle queda implícito en `resumen_productos`. Si el dialer/CRM lo necesita, agregarlo al formato del resumen. |
| `cnt_dias_mora` | producto | **Cambiar a `cnt_dias_mora_max`** (máximo por CUIL). Es el indicador más útil para segmentación. |
| `id_modulo_codigo` | producto (74%) | **Eliminar.** Si negocio lo necesita, definir qué módulo se toma (el del producto con mayor deuda, por ejemplo). |
| `monto_saldo_capital_ars` | producto | **Eliminar** o cambiar a `SUM` si negocio lo pide. |
| `monto_interes_adeudado_ars` | producto | **Eliminar** o cambiar a `SUM`. |
| `monto_impuesto_valor_agregado_interes_adeudado_ars` | producto | **Eliminar** o cambiar a `SUM`. |

---

## 8. Esquema completo del ROMAN propuesto

Orden sugerido y mapeo desde el GYM:

| # | Columna ROMAN | Origen / Cálculo | Granularidad |
|---|---|---|---|
| 1 | `id_cliente_bt` | `Cliente_BT` | Cliente |
| 2 | `id_cuil` | `CUIL` | Cliente |
| 3 | `id_nro_documento` | `NumeroDocumento` | Cliente |
| 4 | `customer_name` | `ClienteNombre` | Cliente |
| 5 | `tel_fijo` | `NumeroTelefono` | Cliente |
| 6 | `tel_laboral` | `NumeroTrabajo` | Cliente |
| 7 | `tel_celular` | `NumeroCelular` | Cliente |
| 8 | `txt_mail` | `Mail` | Cliente |
| 9 | `id_nro_cuenta` | `Nro Cuenta` | Cliente |
| 10 | `tipo_cuenta` | `Tipo de Cuenta` | Cliente |
| 11 | `id_sucursal_cuenta` | `Sucursal_Cuenta` | Cliente |
| 12 | `tipo_campana_ref` | `Campaña_REF` | Cliente |
| 13 | `tipo_asignacion` | `Tipo_Asignacion` | Cliente |
| 14 | `txt_gestion_descripcion` | `GestionDescripción` | Cliente |
| 15 | `tipo_estado_cuenta` | `Estado Cuenta` | Cliente |
| 16 | `fecha_gestion` | `Fecha_Gestion` | Cliente |
| 17 | **`monto_adeudado_ars`** | `SUM(MontoVencido)` por CUIL | Cliente (calculada) |
| 18 | **`monto_entrega_ars`** | `first(AnticipoMinimo)` por CUIL | Cliente (calculada) |
| 19 | **`oferta_importe`** | `"si"` si `any(OFERTA_Importe > 0)`, sino `"no"` | Cliente (calculada) |
| 20 | **`resumen_productos`** | string concatenado por operación | Cliente (calculada) |
| 21 | `cnt_dias_mora_max` | `MAX(Dias_Mora)` por CUIL | Cliente (calculada) |

**Total: 21 columnas** (vs. 27 actuales). Cambio neto:
- Agregadas: 4 (`oferta_importe`, `monto_entrega_ars`, `resumen_productos`, `cnt_dias_mora_max`)
- Eliminadas: 9 (`tipo_agrupador_producto`, `id_modulo_codigo`, `id_nro_operacion`, `cnt_dias_mora`, `monto_vencido_ars`, `monto_saldo_capital_ars`, `monto_interes_adeudado_ars`, `monto_impuesto_valor_agregado_interes_adeudado_ars`, `monto_oferta_importe`)
- Modificada: 1 (`monto_adeudado_ars`)
- Sin cambio: 16
- `tipo_tasa_40`: pendiente confirmar si se mantiene (en el corte actual está vacío en todas las filas)

---

## 9. Ejemplos concretos con datos reales del GYM

### Caso A — Cliente MIXTO (préstamo sin oferta + tarjeta con oferta)

```
id_cuil:              20084733564
customer_name:        MARTINEZ ALDO ALBERTO
monto_adeudado_ars:   7238602.00
monto_entrega_ars:    564442.27
oferta_importe:       si
tipo_campana_ref:     CAMPAÑA30%
cnt_dias_mora_max:    430
resumen_productos:    [Préstamos Personales DeudaVencida:2592157.00 OfertaImporte:NO ;
                       Tarjeta de Crédito DeudaVencida:4646445.00 OfertaImporte:1586266.21]
```

### Caso B — Cliente con TODOS sus productos en oferta

```
id_cuil:              20397353843
customer_name:        GELVEZ GASTON GABRIEL
monto_adeudado_ars:   37669800.00
monto_entrega_ars:    3207618.99
oferta_importe:       si
tipo_campana_ref:     CAMPAÑA35%
cnt_dias_mora_max:    (calculado)
resumen_productos:    [Cuenta Corriente DeudaVencida:34892030.00 OfertaImporte:14913205.15 ;
                       Tarjeta de Crédito DeudaVencida:2777770.00 OfertaImporte:1183196.58]
```

### Caso C — Cliente SIN OFERTA en ningún producto (10 préstamos)

```
id_cuil:              20232785994
customer_name:        AGUILERA CESAR OMAR
monto_adeudado_ars:   2032804.17
monto_entrega_ars:    264098.20
oferta_importe:       no
tipo_campana_ref:     CAMPAÑA45%
cnt_dias_mora_max:    (calculado)
resumen_productos:    [Préstamos Personales DeudaVencida:105136.00 OfertaImporte:NO ;
                       Préstamos Personales DeudaVencida:12206.00 OfertaImporte:NO ;
                       Préstamos Personales DeudaVencida:73479.00 OfertaImporte:NO ;
                       Préstamos Personales DeudaVencida:61915.00 OfertaImporte:NO ;
                       Préstamos Personales DeudaVencida:2832.00 OfertaImporte:NO ;
                       Préstamos Personales DeudaVencida:8337.00 OfertaImporte:NO ;
                       Préstamos Personales DeudaVencida:1638.00 OfertaImporte:NO ;
                       Préstamos Personales DeudaVencida:11821.00 OfertaImporte:NO ;
                       Préstamos Personales DeudaVencida:6218.00 OfertaImporte:NO ;
                       Préstamos Personales DeudaVencida:517451.00 OfertaImporte:NO]
```

---

## 10. Lógica de transformación GYM → ROMAN (pseudocódigo)

```python
def transformar(gym_df, filtros=None):
    # 1. Filtrar (mantener lógica actual: Tipo_Asignacion = PREJUDICIAL principalmente)
    df = aplicar_filtros(gym_df, filtros)

    # 2. Agrupar por CUIL
    salida = []
    for cuil, grupo in df.groupby('CUIL'):
        # campos a nivel cliente: tomar el primero
        row = {
            'id_cliente_bt':           grupo['Cliente_BT'].iloc[0],
            'id_cuil':                 cuil,
            'id_nro_documento':        grupo['NumeroDocumento'].iloc[0],
            'customer_name':           grupo['ClienteNombre'].iloc[0],
            'tel_fijo':                grupo['NumeroTelefono'].iloc[0],
            'tel_laboral':             grupo['NumeroTrabajo'].iloc[0],
            'tel_celular':             grupo['NumeroCelular'].iloc[0],
            'txt_mail':                grupo['Mail'].iloc[0],
            'id_nro_cuenta':           grupo['Nro Cuenta'].iloc[0],
            'tipo_cuenta':             grupo['Tipo de Cuenta'].iloc[0],
            'id_sucursal_cuenta':      grupo['Sucursal_Cuenta'].iloc[0],
            'tipo_campana_ref':        grupo['Campaña_REF'].iloc[0],
            'tipo_asignacion':         grupo['Tipo_Asignacion'].iloc[0],
            'txt_gestion_descripcion': grupo['GestionDescripción'].iloc[0],
            'tipo_estado_cuenta':      grupo['Estado Cuenta'].iloc[0],
            'fecha_gestion':           grupo['Fecha_Gestion'].iloc[0],

            # campos calculados
            'monto_adeudado_ars':      grupo['MontoVencido'].sum(),
            'monto_entrega_ars':       grupo['AnticipoMinimo'].iloc[0],  # NO SUMAR
            'oferta_importe':          'si' if (grupo['OFERTA_Importe'] > 0).any() else 'no',
            'cnt_dias_mora_max':       grupo['Dias_Mora'].max(),
            'resumen_productos':       construir_resumen(grupo),
        }
        salida.append(row)
    return pd.DataFrame(salida)


def construir_resumen(grupo):
    grupo_ord = grupo.sort_values(['AgrupadorProducto', 'NumeroOperacion'])
    items = []
    for _, r in grupo_ord.iterrows():
        oferta = r['OFERTA_Importe']
        oferta_txt = 'NO' if pd.isna(oferta) or oferta <= 0 else f"{oferta:.2f}"
        items.append(
            f"{r['AgrupadorProducto']} "
            f"DeudaVencida:{r['MontoVencido']:.2f} "
            f"OfertaImporte:{oferta_txt}"
        )
    return '[' + ' ; '.join(items) + ']'
```

---

## 11. Validaciones recomendadas para el ETL

Tests automáticos que sugiero agregar al pipeline (para que el bug del `"false"` no vuelva a colarse):

1. **Test de tipos de datos**:
   - `monto_adeudado_ars` debe ser numérico (`float`), no string.
   - `monto_entrega_ars` debe ser numérico, no string.
   - `oferta_importe` debe ser exactamente `"si"` o `"no"`.

2. **Test de coherencia**:
   - Si en el GYM hay al menos una `OFERTA_Importe > 0` para el CUIL, entonces `oferta_importe == "si"`.
   - `monto_entrega_ars` debe coincidir con `AnticipoMinimo` de cualquier fila del CUIL en el GYM (no debe ser una suma).
   - `monto_adeudado_ars` debe coincidir con `SUM(MontoVencido)` del CUIL, o equivalentemente con `Deuda_vencida_Clte`.

3. **Test de granularidad**:
   - Cada `id_cuil` aparece exactamente una vez en el ROMAN.

4. **Test de formato del resumen**:
   - `resumen_productos` empieza con `[` y termina con `]`.
   - El número de bloques separados por ` ; ` coincide con el número de operaciones del CUIL en el GYM.

---

## 12. Pendientes y decisiones futuras

🟡 **Validar contra el código del ETL** la causa raíz del bug `monto_oferta_importe = "false"`. Posibles hipótesis:
- Una operación tipo `bool(oferta)` se está serializando como string.
- Mapeo erróneo de columnas entre input y output.

🟡 **Semántica de `Campaña_REF`** — los nombres `CAMPAÑA20%`, `CAMPAÑA30%`, etc. no se corresponden con el porcentaje de descuento real (mediana de pago: 25%, 37%, 54%, 76% respectivamente). Conviene aclarar con negocio cuál es la convención correcta antes de que se cuele al prompt del agente.

🟡 **`Tipo_Asignacion` `MORA TARDIA`** — hoy casi no entra al ROMAN (0,2% pasa). Confirmar con negocio si es intencional o si debería ampliarse.

🟡 **Préstamos Consolidados y Refinanciados** (96 operaciones en GYM, sin oferta) — confirmar trato igual a Préstamos Personales o flujo diferenciado.

🟢 **Política de orden dentro de `resumen_productos`** — hoy propuesto: `AgrupadorProducto, NumeroOperacion`. Alternativa: priorizar productos con oferta primero, para que el discurso comercial los mencione antes.

🟢 **`tipo_tasa_40`** — verificar si tiene contenido en otros cortes; en el corte actual está vacío.

🟢 **Próximos pasos** — abrir el ZIP del ETL (`soho-bancor-cobranzas-etl`) para localizar los puntos exactos del código donde aplicar los cambios.

---

## Anexo — Glosario rápido

| Término | Significado |
|---|---|
| GYM | Archivo input proveniente del banco con la cartera en mora a gestionar |
| ROMAN | Archivo output que consume el agente conversacional IA |
| CUIL | Identificador fiscal único del cliente |
| Operación | Unidad de deuda individual (tarjeta, préstamo, cuenta corriente) |
| Cliente multi-producto | Cliente con más de una operación en mora simultáneamente |
| Oferta | Importe especial al cual el cliente puede cancelar la deuda (suele aplicar solo a Tarjeta y Cuenta Corriente) |
| AnticipoMinimo | Monto mínimo que el cliente debe pagar de entrada para acceder a un plan de refinanciación |
