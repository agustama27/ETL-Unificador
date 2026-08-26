# Fixes ETL Álvarez Maquinarias — corrida 12/08/2026

Repositorio: `alvarez-maquinaria-etl` (Bitbucket, workspace `evoltis`, rama `main`)

Cuatro defectos detectados auditando las salidas `ALVAREZ_MAQUINARIAS_ROMAN_260812.csv`
y `ALVAREZ_MAQUINARIAS_E1KIA_260812.csv` contra la corrida previa del 04/08.

## Contexto: por qué aparecieron ahora

La fuente de cuenta corriente cambió de `.xls` a `.csv` entre las dos corridas. Eso
activó el camino `SaldosGeneralesExtractor._extract_csv_report` en lugar de
`_extract_xls`, y expuso defectos que el camino `.xls` no ejercitaba.

Evidencia comparativa:

| Métrica | 04/08 (`.xls`) | 12/08 (`.csv`) |
|---|---|---|
| Clientes en ROMAN | 214 | 192 |
| Con teléfono | 129 (60,3 %) | 62 (32,3 %) |
| Máximo Cuenta Corriente | USD 17.264,70 | USD 965,47 |
| Suma Cuenta Corriente | USD 189.152,07 | USD 25.145,34 |

**No modificar el comportamiento del camino `.xls`.** Los fixes deben servir a ambos.

---

## Fix 1 — Error de escala /1000 en montos (CRÍTICO)

**Archivo:** `src/etl/utils.py`
**Función:** `parse_currency_amount`

### Problema

La función no contempla el caso **punto sin coma**. En formato argentino un punto solo
es separador de miles, pero cae en el `else` implícito y `float()` lo interpreta como
separador decimal:

```python
has_dot = "." in text
has_comma = "," in text
if has_dot and has_comma:      # "17.264,70" → 17264.70   OK
    text = text.replace(".", "").replace(",", ".")
elif has_comma:                # "853,01"    → 853.01     OK
    text = text.replace(",", ".")
# FALTA el caso has_dot sin coma: "17.264" → float() = 17.264
```

Verificado contra los 41 clientes afectados, coincide exacto en todos:

| Origen | `float()` actual | ROMAN 12/08 | Real |
|---|---|---|---|
| `"17.264"` | 17.264 | 17,26 | 17.264,70 |
| `"4.072"` | 4.072 | 4,07 | 4.072,00 |
| `"2.003"` | 2.003 | 2,00 | 2.003,80 |
| `"1.020"` | 1.020 | 1,02 | 1.020,05 |

**Prueba diagnóstica:** ningún cliente supera USD 965,47 de cuenta corriente en la
salida. Un techo justo debajo de 1.000 es imposible naturalmente — es el rastro de que
todo lo de cuatro dígitos o más quedó dividido por mil.

**Impacto:** USD 140.310,81 subestimados sobre 41 clientes. La deuda total real es
~USD 987.000, no los 847.014 informados. El agente de voz está diciendo montos
incorrectos por teléfono.

**Por qué solo afecta a Cuenta Corriente:** las otras tres fuentes entregan número
nativo (xlsx) o exigen coma decimal en el regex (`_REPUESTOS_DETALLE_RE` en el PDF).
Solo la CSV de saldos produce strings dot-only.

### Cambio requerido

Agregar la rama faltante. Un punto solo es separador de miles **únicamente** si el
patrón corresponde a grupos de tres dígitos; si no, es un decimal legítimo de otra
fuente (`"17.26"` debe seguir siendo 17,26) y no se toca.

```python
_MILES_SOLO_PUNTO = re.compile(r"^\d{1,3}(?:\.\d{3})+$")

# ... dentro de parse_currency_amount, después del elif has_comma:
elif has_dot and _MILES_SOLO_PUNTO.fullmatch(text):
    text = text.replace(".", "")
```

Colocar el `elif` nuevo **después** de `elif has_comma` y antes del `try`. No alterar
las dos ramas existentes.

Un signo negativo antes del número debe seguir funcionando; contemplarlo en el regex si
las fuentes traen saldos a favor.

### Tests a agregar

En `tests/` (archivo de utils, o `test_pipeline.py` si no existe uno dedicado):

```python
# el caso que falla hoy
assert parse_currency_amount("17.264") == 17264.0
assert parse_currency_amount("4.072") == 4072.0
assert parse_currency_amount("1.020.500") == 1020500.0

# no romper lo que ya funciona
assert parse_currency_amount("17.264,70") == 17264.70
assert parse_currency_amount("853,01") == 853.01
assert parse_currency_amount("965,47") == 965.47
assert parse_currency_amount(17264.70) == 17264.70

# decimal legítimo de dos dígitos: NO es separador de miles
assert parse_currency_amount("17.26") == 17.26
assert parse_currency_amount("0.5") == 0.5
```

---

## Fix 2 — Teléfono: gana el primero en vez del válido

**Archivo:** `src/etl/transformers.py`
**Funciones:** `ClientPhoneDirectory.register`, `consolidate_by_client`

### Problema

`normalize_phone` acepta de 8 a 13 dígitos, pero `to_international_phone` exige
**exactamente 10** dígitos que no empiecen con `0` ni `15`. Entre ambos umbrales hay una
franja donde un teléfono "válido" para el directorio es inválido para la salida.

En `ClientPhoneDirectory.register`:

```python
if key in self._phone_by_key:
    continue                      # el primero gana y bloquea a los demás
phone = normalize_phone(row.get(schema.COL_TELEFONO_RAW), min_digits, max_digits)
if phone:
    self._phone_by_key[key] = phone
```

Un local pelado de 8 dígitos entra al directorio, bloquea un número de 10 dígitos que
viene de otra fuente, y `to_international_phone` termina devolviendo `None`. El cliente
sale sin teléfono teniendo uno bueno disponible.

Mismo patrón en `consolidate_by_client`:

```python
telefono = next((t for t in group[schema.COL_TELEFONO] if t), None)
```

Toma el primero truthy sin verificar que sirva para el formato internacional.

**Impacto:** 12 clientes identificados con teléfono recuperable presente en la fuente.

### Cambio requerido

**En `ClientPhoneDirectory`:** reemplazar la lógica *first-wins* por *best-wins*. Un
teléfono que pasa `to_international_phone` siempre debe reemplazar a uno que no pasa. Si
ya hay uno válido registrado, mantenerlo (no oscilar entre válidos).

Sugerencia de implementación: guardar el crudo normalizado como hoy, pero permitir el
reemplazo cuando el candidato es internacionalizable y el guardado no lo es.

**En `consolidate_by_client`:** elegir el primer teléfono del grupo que pase
`to_international_phone`; solo si ninguno pasa, caer al primero truthy (para no perder el
dato crudo en diagnósticos).

```python
telefono = next(
    (t for t in group[schema.COL_TELEFONO] if t and to_international_phone(t)),
    next((t for t in group[schema.COL_TELEFONO] if t), None),
)
```

No cambiar `normalize_phone` ni `to_international_phone`: sus reglas son correctas, el
problema es el orden de selección.

### Tests a agregar

- Cliente con dos filas: fuente A con teléfono de 8 dígitos, fuente B con uno de 10.
  La salida debe traer el de 10 en formato `549...`, sin importar el orden de las fuentes
  en el `concat`.
- Cliente con dos teléfonos válidos de 10 dígitos: la salida es determinística (el
  primero), no depende del orden de iteración.
- Cliente con un único teléfono de 8 dígitos: la salida queda vacía (comportamiento
  actual correcto, no debe cambiar).

---

## Fix 3 — Códigos de área: cobertura insuficiente y sin trazabilidad

**Archivos:** `src/etl/codigos_area.py`, `src/etl/extractors.py`

### Problema

El export "ficha por página" trae los teléfonos como local pelado sin característica.
`complete_national_phone` los reconstruye usando `area_code_for_locality(localidad)`,
pero `AREA_POR_CP` mapea solo **32 códigos postales**. Todo CP fuera de la tabla deja el
teléfono incompleto y el cliente sale sin número.

En `_extract_csv_report` el fallo se registra únicamente como conteo agregado:

```python
logger.warning(
    "%s: %d telefono(s) siguen incompletos (localidad sin mapear o largo invalido)",
    self.fuente, telefonos_incompletos,
)
```

No se puede saber **qué CP** faltó mapear, así que el problema no es accionable: hay que
adivinar qué agregar a la tabla.

**Impacto:** 130 de 192 clientes sin teléfono (67,7 %), USD 111.697,97 sin posibilidad
de gestión telefónica. De esos 130, **108 tienen ID de Autológica**, o sea vienen de
cuenta corriente — exactamente la fuente que usa este mecanismo.

### Cambio requerido

**Trazabilidad primero.** Acumular los CP que no resolvieron y emitir un warning con la
lista de CP distintos y su conteo. El CP no es dato personal (identifica una localidad,
no un cliente), así que puede loguearse sin violar el criterio de no exponer datos de
cliente que sigue el resto del módulo.

Formato sugerido:

```
saldos_generales: 87 telefono(s) sin completar; CP sin mapear: 2300(12), 6270(9), 5988(5)
```

**Después ampliar la tabla.** Una vez que la corrida liste los CP faltantes, agregarlos a
`AREA_POR_CP` verificando cada prefijo contra un directorio público, como indica el
docstring del módulo. **No inventar códigos**: un CP sin verificar se deja fuera y el
teléfono queda incompleto, que es el comportamiento seguro actual.

No modificar `complete_national_phone`: su lógica de reconstrucción es correcta.

### Tests a agregar

- CP mapeado + local de 8 dígitos → nacional de 10 dígitos correcto.
- CP no mapeado → teléfono sin completar, y el CP aparece en el warning.
- CP mapeado + número que ya viene con característica → no se duplica el prefijo.

---

## Fix 4 — Duplicados: falta la regla por ID de Autológica

**Archivo:** `src/etl/transformers.py`
**Funciones:** `_ClienteFacts`, `_client_facts`, `_es_el_mismo_cliente`

### Problema

`_es_el_mismo_cliente` evalúa dos criterios: prefijo por truncamiento, y teléfono
compartido más nombre parecido. **Nunca compara el ID de Autológica**, que es la señal
más fuerte disponible.

`_ClienteFacts` guarda solo el booleano `tiene_id`, no el valor, así que la comparación
no es posible ni siquiera si se quisiera hacer.

Caso real en la salida del 12/08:

| ID Autológica | Nombre en ROMAN | Saldo | Productos |
|---|---|---|---|
| 1241 | FINOCCHI RICARDO HUGO E HIJOS SRL | 924,59 | Cuenta Corriente:17.26;Servicios:907.33 |
| 1241 | FINOCHI RICARDO HUGO E HIJOS SRL | 351,08 | Repuestos:351.08 |

Por qué ninguna regla actual los une:

- `FINOCCHI` y `FINOCHI` divergen en el carácter 5 — ninguno es prefijo del otro, así que
  la regla de truncamiento no aplica.
- Ambos sin teléfono, así que la regla `telefono+errata` (que sí los uniría, el ratio de
  `difflib` supera 0,90) nunca se evalúa.

La deuda del cliente quedó partida en dos filas y el agente informa un saldo incompleto.

### Cambio requerido

**1.** Agregar el campo `cliente_id: Optional[str]` a `_ClienteFacts`.

**2.** Poblarlo en `_client_facts` reutilizando `_first_cliente_id(group)`, que ya se
llama ahí para calcular `tiene_id`. Evitar la doble llamada.

**3.** Agregar la comparación como **primera regla** de `_es_el_mismo_cliente`, antes de
las heurísticas de nombre:

```python
if a.cliente_id and b.cliente_id and a.cliente_id == b.cliente_id:
    return "mismo ID Autologica"
```

Va primero porque es determinístico: dos filas con el mismo ID son el mismo cliente en el
sistema de registro, sin margen de interpretación. Las reglas heurísticas quedan como
fallback para los clientes que no traen ID.

La resolución de cuál variante gana ya la maneja `_canonico` y no requiere cambios: ante
empate de `tiene_id` desempata por truncamiento y luego por largo del nombre.

### Tests a agregar

- Dos filas con mismo `cliente_id` y nombres distintos (`FINOCCHI` / `FINOCHI`) se
  fusionan en una sola fila; el saldo resultante es la suma (1.275,67) y `Productos`
  concatena las entradas de ambas.
- Dos filas con `cliente_id` distinto y nombres parecidos **no** se fusionan.
- Dos filas sin `cliente_id` mantienen el comportamiento heurístico actual (no debe
  haber regresión en los tests existentes de truncamiento y errata).

---

## Verificación de la corrida completa

Después de aplicar los cuatro fixes, correr el pipeline sobre las mismas fuentes de
agosto y validar contra estos números:

| Chequeo | Antes | Esperado |
|---|---|---|
| Máximo Cuenta Corriente | USD 965,47 | > USD 17.000 |
| Suma Cuenta Corriente | USD 25.145,34 | ~USD 165.000 |
| Deuda total ROMAN | USD 847.014,16 | ~USD 987.000 |
| Clientes con teléfono | 62 (32,3 %) | ≥ 74, objetivo ~129 |
| Filas en E1KIA | 62 | igual al conteo de clientes con teléfono |
| IDs de Autológica duplicados | 1 (el 1241) | 0 |

Chequeo de regresión estructural, ya cubierto por el diseño actual pero conviene
confirmarlo:

- E1KIA no debe traer duplicados ni filas sin teléfono.
- Todo teléfono en ROMAN debe tener 13 dígitos y empezar con `549`.
- La suma de los montos del array `Productos` debe coincidir con `SaldoExigibleUSD` en
  cada fila.
- `ProductosRemitos` debe ser un subconjunto de `Productos`.

## Orden sugerido

1. **Fix 1** — una línea, desbloquea el error que más impacta al cliente final.
2. **Fix 2** — recupera 12 clientes de inmediato.
3. **Fix 4** — acotado y determinístico.
4. **Fix 3** — requiere una corrida intermedia para saber qué CP agregar.

## Fuera de alcance

No tocar en esta iteración, aunque aparezcan durante la implementación:

- El criterio de matching por nombre normalizado (documentado y asumido en
  `docs/ASSUMPTIONS.md`).
- La decisión de tratar todos los teléfonos como celular con prefijo `549`.
- El descarte del `.xlsx` de repuestos en favor del PDF.
- La inferencia de moneda USD en cuenta corriente (pendiente de confirmación del
  cliente, no es un bug de código).

## Documentación a actualizar

- `docs/ASSUMPTIONS.md`: dejar asentado que el punto sin coma se interpreta como
  separador de miles, y que el ID de Autológica tiene precedencia sobre las heurísticas
  de nombre al resolver duplicados.
- `docs/SPEC.md`: el encabezado se declara "implementado" mientras el cierre dice
  "pendiente de tu OK para empezar a codear". Unificar.
