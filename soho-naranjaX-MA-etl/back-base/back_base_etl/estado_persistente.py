"""Persistent monthly state helpers with immutable daily snapshots."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def _validar_mes(mes: str) -> str:
    mes_normalizado = str(mes).strip()
    if len(mes_normalizado) != 6 or not mes_normalizado.isdigit():
        raise ValueError(
            f"Mes invalido '{mes}'. Formato esperado: YYYYMM (ej: 202604)."
        )
    return mes_normalizado


def _validar_fecha(fecha: str) -> str:
    fecha_normalizada = str(fecha).strip()
    if len(fecha_normalizada) != 8 or not fecha_normalizada.isdigit():
        raise ValueError(
            f"Fecha invalida '{fecha}'. Formato esperado: YYYYMMDD (ej: 20260418)."
        )
    return fecha_normalizada


def _path_estado_vigente(estado_dir: str, mes: str) -> Path:
    return Path(estado_dir) / f"estado_{mes}.csv"


def _path_snapshot_diario(estado_dir: str, fecha: str) -> Path:
    return Path(estado_dir) / f"estado_{fecha}.csv"


def _filtrar_base_inicial_m90_puro(df_base: pd.DataFrame) -> pd.DataFrame:
    """Keep only monthly base rows with cajon=M90 and ecosistema=PURO."""
    required_columns = {"cajon", "ecosistema"}
    if not required_columns.issubset(df_base.columns):
        return df_base.copy()

    cajon = df_base["cajon"].fillna("").astype(str).str.strip().str.casefold()
    ecosistema = df_base["ecosistema"].fillna("").astype(str).str.strip().str.casefold()
    include_mask = (cajon == "m90") & (ecosistema == "puro")
    return df_base[include_mask].copy()


def _resumen_valores_unicos(serie: pd.Series, limit: int = 10) -> str:
    """Return a comma-separated, truncated list of distinct values for diagnostics."""
    valores = (
        serie.fillna("").astype(str).str.strip().replace("", "<vacio>").unique().tolist()
    )
    truncados = valores[:limit]
    sufijo = "" if len(valores) <= limit else f", ... (+{len(valores) - limit} mas)"
    return ", ".join(repr(valor) for valor in truncados) + sufijo


def inicializar_estado(df_base: pd.DataFrame, output_dir: str, mes: str) -> str:
    """Create monthly current state from base dataframe once per month."""
    mes_normalizado = _validar_mes(mes)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    path_vigente = _path_estado_vigente(str(output_path), mes_normalizado)
    df_filtrado = _filtrar_base_inicial_m90_puro(df_base)

    # Zero-row guard: catches the silent-failure case where the schema is
    # right (cajon/ecosistema columns present) but the values do not match
    # M90+PURO. This typically means upstream column shift or a value
    # convention change (e.g., M90 -> M90B), and the operator needs an
    # explicit error rather than a 0-row CSV.
    tiene_columnas_filtro = {"cajon", "ecosistema"}.issubset(df_base.columns)
    if tiene_columnas_filtro and len(df_base) > 0 and len(df_filtrado) == 0:
        cajon_unicos = _resumen_valores_unicos(df_base["cajon"])
        ecosistema_unicos = _resumen_valores_unicos(df_base["ecosistema"])
        raise ValueError(
            "inicializar_estado: el filtro M90+PURO no encontro filas en una "
            f"base de {len(df_base)} registros. Revisar mapeo de columnas y "
            "valores. Columnas examinadas: cajon, ecosistema. "
            f"Valores unicos vistos en cajon: {cajon_unicos}. "
            f"Valores unicos vistos en ecosistema: {ecosistema_unicos}."
        )

    df_filtrado.to_csv(path_vigente, sep=";", encoding="utf-8", index=False, lineterminator="\n")
    return str(path_vigente)


def cargar_estado(estado_dir: str, mes: str) -> pd.DataFrame:
    """Load current monthly state or fail with an operator-friendly message."""
    mes_normalizado = _validar_mes(mes)
    path_vigente = _path_estado_vigente(estado_dir, mes_normalizado)

    if not path_vigente.exists():
        raise FileNotFoundError(
            "No existe estado vigente para el mes "
            f"{mes_normalizado}. Archivo esperado: {path_vigente}. "
            "Inicializa el mes con inicializar_estado(...) antes de ejecutar el update diario."
        )

    return pd.read_csv(path_vigente, sep=";", dtype=str, keep_default_na=False)


def guardar_estado(df: pd.DataFrame, estado_dir: str, fecha: str) -> tuple[str, str]:
    """Save current monthly state and immutable daily snapshot."""
    fecha_normalizada = _validar_fecha(fecha)
    mes_normalizado = fecha_normalizada[:6]

    base_dir = Path(estado_dir)
    base_dir.mkdir(parents=True, exist_ok=True)

    path_vigente = _path_estado_vigente(str(base_dir), mes_normalizado)
    path_snapshot = _path_snapshot_diario(str(base_dir), fecha_normalizada)

    if path_snapshot.exists():
        raise FileExistsError(
            "Snapshot diario inmutable ya existe para "
            f"{fecha_normalizada}: {path_snapshot}. "
            "No se sobreescribe para proteger rollback manual."
        )

    df.to_csv(path_vigente, sep=";", encoding="utf-8", index=False, lineterminator="\n")
    df.to_csv(path_snapshot, sep=";", encoding="utf-8", index=False, lineterminator="\n")

    return str(path_vigente), str(path_snapshot)
