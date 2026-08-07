"""Rastrea en que etapa aparecen los 'nan' residuales."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from filtrosAplicados_base_BANCOR.procesos import pipeline_wfm as P

INPUT = Path(r"C:\Users\agustin.tamagusuku\Desktop\soho-bancor-cobranzas-etl\filtrosAplicados_base_BANCOR\dist\20-04-2026\entrada\GYM_Evoltis 16-04_162108.xlsx")


def count_nan(df, etapa):
    col = "NumeroCelular"
    if col not in df.columns:
        return
    serie = df[col]
    # Contar NaN reales y strings "nan"
    nan_real = serie.isna().sum()
    serie_str = serie.astype(str)
    nan_str = (serie_str == "nan").sum()
    vacio = (serie_str == "").sum()
    print(f"[{etapa:<15}] filas={len(df)}  NaN_real={nan_real}  str_'nan'={nan_str}  vacio=''={vacio}")


df, _ = P.leer_archivo_entrada(INPUT)
df = P._limpiar_nombres_columnas(df)
count_nan(df, "lectura")

df = P._normalizar_columnas_numericas(df)
count_nan(df, "num")

df = P._normalizar_columnas_texto(df)
count_nan(df, "texto")

df = P._normalizar_columnas_telefono(df)
count_nan(df, "telefono")

df["EstadoDescripcion"] = df["EstadoDescripcion"].astype(str).str.strip()
df = df[df["EstadoDescripcion"] != "Cancelada"].copy()
df = df[df["MontoAdeudado"].notna() & (df["MontoAdeudado"] > 0)].copy()
count_nan(df, "filtros1")

df, _ = P.filtrar_fecha_entrega_por_meses(df, [2, 3])
count_nan(df, "fecha")

df, _ = P.filtrar_acuerdos_vigentes(df)
count_nan(df, "acuerdos")

df_consolidado = (
    df.groupby("Cliente_BT", sort=False)
      .apply(P.consolidar_grupo, include_groups=False)
      .reset_index()
)
count_nan(df_consolidado, "consolidado")

df_unicos, _ = P.deduplicar_por_telefonos(df_consolidado)
count_nan(df_unicos, "dedup")

df_unicos, _ = P.filtrar_filas_sin_telefono(df_unicos)
count_nan(df_unicos, "filtrar_sin_tel")
