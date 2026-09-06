# Supuestos operativos

Este documento conserva únicamente supuestos generales que permiten operar y
probar el ETL sin registrar datos, identidades ni detalles de una operación
real.

**Política de documentación:** Los ejemplos son genéricos. No documente datos
de clientes ni detalles operativos específicos.

## Supuestos vigentes

- Las cuatro entradas requeridas se ubican en `inputs/<run-date>/` y se
  seleccionan con `--run-date`.
- `--reference-date` controla los cálculos de fecha de forma independiente.
- Los nombres de entrada deben ser basenames seguros con la extensión esperada.
- Cuando el nombre canónico no está en la partición, cada fuente se identifica
  por su extensión; el descubrimiento propone el archivo y las validaciones de
  entrada se aplican igual. Si dos archivos compiten por la misma fuente, la
  corrida aborta en vez de elegir uno.
- `--preparar` crea `inputs/<run-date>/` y termina, sin procesar nada.
- Las dos exportaciones fijas se escriben en `outputs/<run-date>/`.
- `--overwrite` reemplaza solo esas exportaciones y solo en la partición
  seleccionada.
- `inputs/` y `outputs/` nunca se versionan; los ejemplos y fixtures deben ser
  sintéticos.
- Solo las filas USD ingresan al esquema canónico. ARS y monedas desconocidas
  se excluyen antes de registrar teléfonos, unir identidades o calcular saldos.
- Las exclusiones se comunican mediante conteos agregados por fuente, sin
  identidades, teléfonos, remitos, importes ni valores crudos.
- `--tipo-cambio` es opcional y transitorio: si se indica un valor finito y
  positivo, se advierte que está obsoleto y no produce conversión alguna.

## Saldos CSV

El valor predeterminado de `--saldos` sigue siendo `saldos.xls`; un operador
puede indicar `--saldos saldos.csv` para un export CP1252 separado por coma en
uno de dos layouts: el reporte seccionado estructurado, o el export "ficha por
página" de Saldos de clientes, del que se toma únicamente el Saldo DOLARES.
No se admiten otros encodings ni delimitadores. En el export por página, una
cola final truncada sin bloque de cliente se descarta con warning; si trae un
bloque de cliente, la corrida aborta para no perder deuda en silencio. El CSV
inválido se rechaza antes de generar transformaciones, sin salidas parciales.

**Separadores de importe.** Ese export mezcla convención argentina
(`1.234,56`) e inglesa (`1,234.56`) dentro del mismo archivo, así que la
convención no se puede deducir del origen: se deduce de la forma del valor.
Cuando aparecen los dos separadores, el que está más a la derecha es el
decimal y el otro agrupa miles. Cuando aparece uno solo, es separador de miles
únicamente si agrupa de a tres dígitos exactos (`1.234`, `1,234`); en
cualquier otro caso es decimal (`965.47`, `853,01`). Asumir siempre coma
decimal dividía por mil todo importe escrito en convención inglesa.

La marca de moneda se saca esté separada (`USD 850,00`) o pegada al número
(`USD1.149,20`, `U$S1.149,20`, `US$…`). Exigir frontera de palabra dejaba el
prefijo puesto cuando venía pegado, y el importe entero quedaba sin parsear.

Los Remitos de Servicios mezclan números nativos de Excel con celdas de texto
en la misma hoja, así que el `Total` de cada fila se toma como el último valor
que resuelva a un importe, no como el último valor numérico: exigir número
nativo descartaba filas completas con deuda real.

## Identidad del cliente

Solo una de las cuatro fuentes trae el ID de Autologica. Las demás se unen por
nombre normalizado (`normalize_client_name`), así que cualquier variación de
grafía parte al mismo deudor en dos registros. Dos causas observadas:

1. **Ancho de columna.** Las fuentes son reportes con columnas fijas: un nombre
   que llega al largo máximo de su fuente está cortado, a veces en mitad de una
   palabra. La sigla societaria escrita con puntos (`S.A.`) también rompía la
   clave, porque al sacar la puntuación quedaban tokens de una letra que el
   stripper de sufijos no reconocía; `normalize_client_name` los vuelve a unir.
   Cuando la sigla viene precedida por la inicial de un socio —el patrón de las
   sociedades de hecho, `... GERMAN R S.H.`— la corrida de letras se corta por
   el sufijo más largo del final, así `S.H.` y `SH` siguen dando la misma clave.
2. **Erratas de carga.** Una letra de más o de menos en el nombre.

`resolve_duplicate_clients` fusiona dos claves solo con evidencia:

- **Mismo ID de Autologica** — se evalúa primero y tiene precedencia sobre las
  heurísticas de nombre. No es una heurística: dos filas con el mismo ID son la
  misma cuenta en el sistema de registro. Cubre los casos que las reglas de
  nombre no pueden ver, como dos grafías que divergen a mitad de palabra
  (ninguna es prefijo de la otra) en clientes sin teléfono, donde la regla de
  errata nunca llega a evaluarse.
- **Truncamiento** — una clave es prefijo de la otra **y** alguna llegó al
  techo de largo de su fuente. La condición de techo es la que hace segura la
  regla: sin ella se fusionarían entidades legítimamente distintas cuyo nombre
  arranca igual, como una sociedad y una de sus personas integrantes.
- **Teléfono** — comparten línea **y** el nombre es reconociblemente el mismo
  (prefijo, o similitud ≥ 0,90). Compartir teléfono por sí solo no alcanza: un
  titular y su razón social pueden usar el mismo número siendo deudores
  distintos.

Gana la variante con ID de Autologica (es el sistema de registro); si ninguna
lo tiene, la que no está truncada. Cada fusión se emite como `warning` de la
corrida para poder auditarla.

## Teléfonos del export por página

Los teléfonos de ese export suelen venir como número local sin característica.
El adapter los completa de forma determinista: quita prefijos `549`/`54`, el
`0` de larga distancia y el `15` de celular local, y antepone la
característica de la **localidad declarada del cliente** (columna `CP -
NOMBRE` del mismo reporte), según la tabla versionada en
`src/etl/codigos_area.py`, construida desde directorios públicos de prefijos.

Supuesto de negocio: el teléfono del cliente pertenece a la característica de
su localidad. Si el resultado no da un nacional de 10 dígitos exactos, o la
localidad no está mapeada, el número queda como vino — nunca se inventan
dígitos. Cada corrida informa como `warning` los conteos agregados de
teléfonos completados y de los que siguen incompletos, sin números ni
identidades. El warning de incompletos además lista los códigos postales que
no están en la tabla, ordenados por frecuencia: sin ese detalle, ampliar la
tabla es adivinar qué localidad faltó. El CP identifica una localidad, no a un
cliente, así que informarlo no expone datos personales. Un nacional de 10
dígitos que empiece con `0` o `15` se considera falso válido y no llega a las
exportaciones.

Cuando un cliente llega con teléfono desde varias fuentes gana el que sirve
para la salida (un nacional de 10 dígitos), no el primero que apareció: un
local sin característica es válido para el maestro pero inútil para llamar, y
con *first-wins* bloqueaba al número bueno de otra fuente. Entre dos números
igual de válidos gana el primero, para que la corrida no dependa del orden de
las fuentes.

## Límites de seguridad

No se documentan muestras operativas ni se copian valores desde archivos de
entrada. Para investigar errores, usá fixtures minimizados con valores
ficticios y ejecutá:

```bash
python -m pytest tests/ -v
```
