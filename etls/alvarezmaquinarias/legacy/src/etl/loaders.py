"""Loaders: archivo Roman (gestión) y listado Approach (marcador).

Ambos consumidores pidieron el mismo formato de intercambio: CSV con `;`,
UTF-8 sin BOM y CRLF (ver `CSV_*`). Lo que los diferencia es el recorte de
filas, no el formato — por eso el formato vive una sola vez, en la clase
base.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import schema

# Formato de intercambio pedido por ambos consumidores.
# `utf-8` a secas, no `utf-8-sig`: el BOM no es ASCII y rompe a los parsers
# que leen el archivo como ASCII plano.
CSV_SEPARADOR = ";"
CSV_ENCODING = "utf-8"
CSV_TERMINADOR = "\r\n"


class CsvExportLoader:
    """Escribe el consolidado en el formato de intercambio acordado.

    Como `Productos` y `ProductosRemitos` usan `;` internamente, el writer
    entrecomilla esos campos — se leen bien con cualquier parser CSV real,
    pero NO con un `split(';')` a mano.
    """

    def rows_to_export(self, consolidado: pd.DataFrame) -> pd.DataFrame:
        return consolidado

    def save(self, consolidado: pd.DataFrame, path: Path) -> Path:
        self.rows_to_export(consolidado).to_csv(
            path,
            index=False,
            sep=CSV_SEPARADOR,
            encoding=CSV_ENCODING,
            lineterminator=CSV_TERMINADOR,
        )
        return path


class RomanCsvLoader(CsvExportLoader):
    """CSV de gestión interna: una fila por cliente, todas las filas del
    consolidado. El desglose por deuda va empaquetado en la columna
    `Productos` (array `producto:monto`)."""


class ApproachLoader(CsvExportLoader):
    """Marcador de la plataforma de llamadas: una sola columna, el teléfono.

    Es el universo llamable del Roman y nada más — mismo conjunto de
    teléfonos, en el mismo orden de prioridad. Un número que aparece en
    varias filas del Roman (dos razones sociales que comparten línea) se
    lista una sola vez: la plataforma marca números, no clientes, y
    llamar dos veces al mismo número es una llamada desperdiciada.
    """

    def rows_to_export(self, consolidado: pd.DataFrame) -> pd.DataFrame:
        con_telefono = consolidado[consolidado[schema.OUT_TELEFONO_CLIENTE].notna()]
        return con_telefono[[schema.OUT_TELEFONO_CLIENTE]].drop_duplicates(
            subset=schema.OUT_TELEFONO_CLIENTE, keep="first"
        )
