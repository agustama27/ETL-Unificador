"""Corre el pipeline paso a paso para detectar donde se reinserta el '.0'."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd

from filtrosAplicados_base_BANCOR.procesos import pipeline_wfm as P

INPUT = Path(r"C:\Users\agustin.tamagusuku\Desktop\soho-bancor-cobranzas-etl\filtrosAplicados_base_BANCOR\dist\20-04-2026\entrada\GYM_Evoltis 16-04_162108.xlsx")


def muestra(df, etapa):
    col = "NumeroCelular"
    if col not in df.columns:
        return
    serie = df[col].astype(str)
    sample = serie[serie != ""].head(3).tolist()
    con_punto = serie.str.contains(r"\.", regex=True, na=False).sum()
    print(f"[{etapa}] dtype={df[col].dtype} muestra={sample} con_punto={con_punto}")


df, det = P.leer_archivo_entrada(INPUT)
df = P._limpiar_nombres_columnas(df)
muestra(df, "lectura")

df = P._normalizar_columnas_numericas(df)
muestra(df, "num")

df = P._normalizar_columnas_texto(df)
muestra(df, "texto")

df = P._normalizar_columnas_telefono(df)
muestra(df, "telefono")

# Filtros
df["EstadoDescripcion"] = df["EstadoDescripcion"].astype(str).str.strip()
df = df[df["EstadoDescripcion"] != "Cancelada"].copy()
df = df[df["MontoAdeudado"].notna() & (df["MontoAdeudado"] > 0)].copy()
muestra(df, "filtros1")

df, _ = P.filtrar_fecha_entrega_por_meses(df, [2, 3])
muestra(df, "fecha")

df, _ = P.filtrar_acuerdos_vigentes(df)
muestra(df, "acuerdos")

df_consolidado = (
    df.groupby("Cliente_BT", sort=False)
      .apply(P.consolidar_grupo)
      .reset_index(drop=True)
)
muestra(df_consolidado, "consolidado")

df_unicos, _ = P.deduplicar_por_telefonos(df_consolidado)
muestra(df_unicos, "dedup")
