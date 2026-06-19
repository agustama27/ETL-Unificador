"""Verifica si la normalizacion de telefonos se aplico correctamente en el output del exe."""

import sys
from pathlib import Path

import pandas as pd

OUTPUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Users\agustin.tamagusuku\Desktop\soho-bancor-cobranzas-etl\filtrosAplicados_base_BANCOR\dist\20-04-2026\salida\base_recibida_BANCOR_conFiltros_20042026_162108.xlsx")

df = pd.read_excel(OUTPUT, dtype={"NumeroTelefono": str, "NumeroTrabajo": str, "NumeroCelular": str})
print(f"Archivo: {OUTPUT.name}")
print(f"Filas: {len(df)}")
print(f"Columnas de telefono presentes: {[c for c in ('NumeroTelefono','NumeroTrabajo','NumeroCelular') if c in df.columns]}")
print()

RANGOS = {"NumeroTelefono": (10, 12), "NumeroTrabajo": (10, 12), "NumeroCelular": (12, 13)}
PREFIJOS = {"NumeroTelefono": "54", "NumeroTrabajo": "54", "NumeroCelular": "549"}

for col in ("NumeroTelefono", "NumeroTrabajo", "NumeroCelular"):
    if col not in df.columns:
        continue
    serie = df[col].astype(str).replace({"nan": "", "NaN": "", "None": "", "NaT": ""})
    con_dato = serie[(serie != "") & (serie.str.len() >= 4)]
    min_l, max_l = RANGOS[col]
    prefijo = PREFIJOS[col]

    total = len(con_dato)
    bien_prefijo = con_dato.str.startswith(prefijo).sum()
    # Celular exige 549 estricto; fijo exige 54 pero NO 549
    if col == "NumeroCelular":
        solo_digitos = con_dato.str.fullmatch(r"\d+").sum()
        ok_prefijo = con_dato.str.startswith("549").sum()
    else:
        solo_digitos = con_dato.str.fullmatch(r"\d+").sum()
        ok_prefijo = (con_dato.str.startswith("54") & ~con_dato.str.startswith("549")).sum()

    longitudes_ok = ((con_dato.str.len() >= min_l) & (con_dato.str.len() <= max_l)).sum()

    # Sospechosos: fuera de prefijo, fuera de rango, o con '15' en posicion sospechosa
    mal_prefijo = con_dato[~con_dato.str.startswith(prefijo)].head(10).tolist()
    mal_longitud = con_dato[(con_dato.str.len() < min_l) | (con_dato.str.len() > max_l)].head(10).tolist()
    con_no_digitos = con_dato[~con_dato.str.fullmatch(r"\d+")].head(10).tolist()

    print(f"=== {col} ===")
    print(f"  Total con dato : {total}")
    print(f"  Solo digitos   : {solo_digitos} / {total}")
    print(f"  Prefijo ok     : {ok_prefijo} / {total}  (esperado: {prefijo}{' estricto' if col=='NumeroCelular' else ' sin 549'})")
    print(f"  Longitud ok    : {longitudes_ok} / {total}  (rango {min_l}-{max_l})")
    if mal_prefijo:
        print(f"  [X] Prefijo mal (muestra): {mal_prefijo}")
    if mal_longitud:
        print(f"  [X] Longitud mal (muestra): {mal_longitud}")
    if con_no_digitos:
        print(f"  [X] No digitos (muestra): {con_no_digitos}")
    if not (mal_prefijo or mal_longitud or con_no_digitos):
        print(f"  [OK] Todos los numeros pasan todas las validaciones")

    # Muestra aleatoria de valores normalizados
    print(f"  Muestra: {con_dato.sample(min(5, total), random_state=1).tolist()}")
    print()

# Cross-check: contar numeros que empiezan con 15 (señal de que no se removio)
print("=== Verificacion prefijo '15' residual ===")
for col in ("NumeroTelefono", "NumeroTrabajo", "NumeroCelular"):
    if col not in df.columns:
        continue
    serie = df[col].astype(str)
    # Buscar '15' inmediatamente despues del prefijo 54/549
    if col == "NumeroCelular":
        # en celular '549' + X → si X empieza con area y luego '15' sería raro
        patron = serie.str.match(r"549\d{2,4}15\d+")
    else:
        patron = serie.str.match(r"54\d{2,4}15\d+")
    sospechosos = serie[patron.fillna(False)].head(5).tolist()
    print(f"  {col}: {patron.sum()} numeros con posible '15' residual embebido")
    if sospechosos:
        print(f"    Muestra: {sospechosos}")
