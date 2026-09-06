from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

import pandas as pd


BACK_RESULTADOS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACK_RESULTADOS))

from procesos.logcall_consolidator import (  # noqa: E402
    OUTPUT_COLUMNS,
    OUTPUT_EXPORT_COLUMNS,
    _build_no_connected_rows,
    _normalize_canonical_fields,
    generate_consolidated_dataframe,
)


class LuzOutputLayoutTest(unittest.TestCase):
    def test_layout_has_exactly_the_sixteen_required_columns(self):
        self.assertEqual(len(OUTPUT_COLUMNS), 16)
        self.assertEqual(OUTPUT_EXPORT_COLUMNS[-1], "Utilidad Informacion")
        self.assertNotIn("[Entrada] Direccion", OUTPUT_COLUMNS)
        self.assertNotIn("[Salida] Speech Completo", OUTPUT_COLUMNS)

    def test_utilidad_preserves_agent_value_and_defaults_empty_values(self):
        dataframe = pd.DataFrame(
            {
                "[Salida] Utilidad Informacion": ["MUY_UTIL", "", None],
            }
        )

        normalized = _normalize_canonical_fields(dataframe)

        self.assertEqual(
            normalized["[Salida] Utilidad Informacion"].tolist(),
            ["MUY_UTIL", "No informado", "No informado"],
        )

    def test_non_connected_rows_keep_default_utilidad(self):
        logcall = pd.DataFrame(
            {
                "RESULT": [8],
                "LOGDATE": [20260901],
                "LOGTIME": [101500],
                "PHONE": [5493511234567],
                "LENGTHCALL": [10],
            }
        )

        rows = _build_no_connected_rows(logcall)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.iloc[0]["[Salida] Utilidad Informacion"], "No informado")
        self.assertEqual(rows.iloc[0]["[Salida] Resultado Efectivamente Informado"], "No")

    def test_roman_export_maps_real_utilidad_value_and_name_fallback(self):
        with TemporaryDirectory() as temporary_directory:
            roman_folder = Path(temporary_directory) / "roman"
            logcall_folder = Path(temporary_directory) / "logcall"
            roman_folder.mkdir()
            logcall_folder.mkdir()

            pd.DataFrame(
                {
                    "Fecha": ["01/09/26 10:15", "01/09/26 10:16"],
                    "Desde": ["5493511234567", "5493511234568"],
                    "[Entrada] nombre_cliente": ["Cliente prioritario", ""],
                    "[Entrada] customer_name": ["Cliente de respaldo", "Cliente de respaldo"],
                    "[Salida] utilidad_informacion": ["MUY_UTIL", "UTIL"],
                }
            ).to_csv(roman_folder / "roman_v14.csv", index=False)

            output = generate_consolidated_dataframe(roman_folder, logcall_folder)

        self.assertEqual(list(output.columns), OUTPUT_COLUMNS)
        self.assertEqual(output.columns[-1], "[Salida] Utilidad Informacion")
        self.assertEqual(output.iloc[0]["[Salida] Utilidad Informacion"], "MUY_UTIL")
        self.assertEqual(output.iloc[0]["[Entrada] Razón social"], "Cliente prioritario")
        self.assertEqual(output.iloc[1]["[Salida] Utilidad Informacion"], "UTIL")
        self.assertEqual(output.iloc[1]["[Entrada] Razón social"], "Cliente de respaldo")


if __name__ == "__main__":
    unittest.main()
