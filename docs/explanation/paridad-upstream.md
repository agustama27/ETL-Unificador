# Qué cubre la paridad byte a byte, y qué no

`test/integration/uat_upstream/test_upstream_parity.py` es el criterio de aceptación de cada ETL
vendorizado: corre el mismo `job.py` contra el legacy del repositorio y contra el repo
upstream del Escritorio, y compara los artefactos **byte a byte**.

Es una red muy fuerte para lo que cubre. El problema es que su cobertura tiene una forma que
no es obvia, y confundirla con "el ETL está protegido" lleva a decisiones equivocadas.

## Lo que cubre

Que el legacy vendorizado en `etls/<cliente>/legacy/` produzca **exactamente** lo mismo que el
repo del cliente. Detecta un port incompleto, un archivo que no se copió, una diferencia de
configuración entre los dos árboles.

Ese es su trabajo, y lo hace bien: es lo que atrapó el port a medias de la campaña
OFERTA_PREVENTA de Bancor antes de que se mergeara.

## Lo que NO cubre: el drift de dependencias

El test ejecuta los dos lados así:

```python
subprocess.run([sys.executable, str(wrapper), ...], cwd=cwd, ...)
```

**El mismo intérprete para los dos lados.** O sea: las mismas versiones de pandas, numpy,
openpyxl y holidays.

Si mañana pandas cambia cómo formatea un decimal, los dos lados cambian **juntos**. La
comparación sigue dando verde mientras el CSV que recibe el cliente cambió. La paridad es
invariante ante el drift de dependencias, por construcción.

Esto no es un defecto del test: comparar dos entornos distintos mediría otra cosa, y sería
frágil por razones que no tienen que ver con el código. Pero significa que **la paridad no es
la red que protege al cliente de una actualización de pandas**. Esa red es otra.

## La red que sí protege: el pin y el lock

Por eso las dependencias del camino de datos van pineadas a versión exacta en `pyproject.toml`
y congeladas en `uv.lock`, en vez de a rango. Las versiones y el motivo de cada una están en
[../reference/comandos.md](../reference/comandos.md).

El procedimiento para subir una de ellas no es `uv lock --upgrade`. Es:

1. Cambiar el pin.
2. Correr los ETLs sensibles antes y después, y comparar el **sha256 de cada artefacto**.
3. Si algún hash cambia, entender por qué antes de seguir. Un cambio de formato numérico no
   es un detalle: es el archivo que la operación carga en el discador.

Ese fue exactamente el chequeo que reveló que `numpy 2.4.0` —la versión que estaba instalada
en el entorno de desarrollo— está *yanked* en PyPI por un bug de compatibilidad hacia atrás.
Se subió a `2.4.6` con los nueve artefactos de Bancor y CartaSur idénticos.

## El otro hueco: el skip

El test hace `pytest.skip` si el repo upstream no está en el Escritorio. Un skip se ve verde
en la salida de pytest si no se mira con `-rs`, y **un skip no es un pase**: significa que
nadie comparó nada.

Corré `task test:parity`, que ya pasa `-rs`, y confirmá que dice `PASSED` y no `SKIPPED`.

El mismo cuidado vale para `pytest.importorskip`: hasta la adopción de uv, los tests de
Alvarez se salteaban cuando faltaba `xlwt` o `reportlab`, que estaban instalados en el
entorno de desarrollo pero **no declarados en** `pyproject.toml`. En una máquina limpia, la
paridad de Alvarez nunca corrió. El lock cierra ese hueco.
