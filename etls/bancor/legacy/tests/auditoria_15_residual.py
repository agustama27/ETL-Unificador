"""Auditoria: verifica que los casos con '15' residual tengan longitud 13 correcta
y cruza contra el input original para demostrar la trazabilidad.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from filtrosAplicados_base_BANCOR.procesos.pipeline_wfm import normalizar_telefono

OUTPUT = Path(r"C:\Users\agustin.tamagusuku\Desktop\soho-bancor-cobranzas-etl\filtrosAplicados_base_BANCOR\dist\20-04-2026\salida\base_recibida_BANCOR_conFiltros_20042026_162108.xlsx")
INPUT = Path(r"C:\Users\agustin.tamagusuku\Desktop\soho-bancor-cobranzas-etl\filtrosAplicados_base_BANCOR\dist\20-04-2026\entrada\GYM_Evoltis 16-04_162108.xlsx")

df_out = pd.read_excel(OUTPUT, dtype=str)
df_in = pd.read_excel(INPUT)

print("=" * 70)
print("AUDITORIA 1: Todos los celulares salida tienen longitud correcta")
print("=" * 70)
cel = df_out["NumeroCelular"].astype(str)
cel = cel[cel != ""]
longitudes = cel.str.len().value_counts().sort_index()
print(f"Distribucion de longitudes del NumeroCelular de salida:")
for long, cant in longitudes.items():
    estado = "OK" if 12 <= long <= 13 else "FUERA DE RANGO"
    print(f"  longitud {long}: {cant} numeros  [{estado}]")
print()

print("=" * 70)
print("AUDITORIA 2: Trazabilidad input -> output con casos '15' residual")
print("=" * 70)
# Tomar los casos que tienen '15' despues de '549XXX'
patron = cel.str.match(r"549\d{2,4}15\d+").fillna(False)
residuales = cel[patron].head(15).tolist()
print(f"Muestra de 15 celulares de salida con '15' despues del area:")
print()
print(f"{'OUTPUT (final)':<18} {'long':<5} {'INPUT (crudo)':<25} {'re-normalizado':<18} {'match?'}")
print("-" * 90)

# Crear mapa input celular -> para cruzar
df_in_cel = df_in["NumeroCelular"].astype(str).str.strip()

for numero_final in residuales:
    # Buscar el input original que al normalizarse da este numero
    match_input = None
    for raw in df_in_cel.unique():
        if normalizar_telefono(raw, "celular") == numero_final:
            match_input = raw
            break
    if match_input:
        renorm = normalizar_telefono(match_input, "celular")
        ok = "SI" if renorm == numero_final else "NO"
        print(f"{numero_final:<18} {len(numero_final):<5} {match_input:<25} {renorm:<18} {ok}")
    else:
        print(f"{numero_final:<18} {len(numero_final):<5} {'(no encontrado en input)':<25}")
print()

print("=" * 70)
print("AUDITORIA 3: Casos donde SI se removio el '15' (trazabilidad inversa)")
print("=" * 70)
# Buscar inputs crudos que contengan '15' en posicion sospechosa y ver si el output los limpio
casos_con_15_en_input = df_in_cel.dropna().astype(str)
ejemplos_removidos = 0
ejemplos_conservados = 0
for raw in casos_con_15_en_input.unique()[:2000]:
    if not raw or raw.lower() in {"nan", "none"}:
        continue
    # Quitar no digitos
    import re
    digits = re.sub(r"\D", "", raw)
    if not digits.startswith("0") or len(digits) < 13:
        continue
    sin_0 = digits[1:]
    if len(sin_0) != 12:
        continue
    # Comprobar si hay '15' en pos 2, 3 o 4
    tiene_15 = any(sin_0[p:p+2] == "15" for p in (2, 3, 4))
    if not tiene_15:
        continue
    out = normalizar_telefono(raw, "celular")
    if out and len(out) == 13:
        if ejemplos_removidos < 5:
            print(f"  input crudo {raw!r:<25} -> {out}  (15 REMOVIDO)")
            ejemplos_removidos += 1

print()
print(f"Total casos con longitud 13 en output: {(cel.str.len() == 13).sum()}")
print(f"Total casos con longitud 12 en output: {(cel.str.len() == 12).sum()}")
print(f"Total casos FUERA de 12-13: {((cel.str.len() < 12) | (cel.str.len() > 13)).sum()}")
