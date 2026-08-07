"""Unit tests for mapping and normalization behavior."""

from __future__ import annotations

import unittest
import tempfile
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
BACK_RESULTADOS_DIR = REPO_ROOT / "back-resultados"
sys.path.insert(0, str(BACK_RESULTADOS_DIR))


from back_resultados_etl.cleaners import (  # noqa: E402
    format_fecha_compromiso,
    normalize_result_key,
    resolve_fecha_promesa,
    truncate_observaciones,
)
from back_resultados_etl.constants import (  # noqa: E402
    COLUMN_ALIASES,
    OBSERVACIONES_MAX_CHARS,
    TIPIF_MAP,
)
from back_resultados_etl.io import load_input  # noqa: E402


class TipificacionesMappingTests(unittest.TestCase):
    """Validate mapping and cleaners contracts."""

    def test_todas_tipificaciones_mapeadas(self) -> None:
        expected = {
            "LOGCALL",
            "PROMESA_DE_PAGO",
            "DIFICULTAD_DE_PAGO",
            "SIN_VOLUNTAD_DE_PAGO",
            "NO_RECONOCE_DEUDA",
            "NOTIFICADO_TITULAR",
            "NOTIFICADO_FAMILIAR",
            "CONOCE_TITULAR",
            "NO_RESPONDE",
            "CONTESTADOR",
            "FALLECIDO",
            "NO_ES_TITULAR",
            "MENSAJE",
            "MENSAJE_DEUDOR",
            "MENSAJE_TERCERO",
            "YA_PAGO_TOTAL_MORA",
            "YA_PAGO_TOTAL_CUENTA",
            "YA_PAGO_PLAN_DE_PAGO",
            "YA_PAGO_PLAN_DE_CUOTAS",
            "YA_PAGO_MES_VENCIDO",
            "DIF_DE_PAGO_BOTON_DE_PAGO",
            "DIF_DE_PAGO_SIN_TRABAJO",
            "DIF_DE_PAGO_PROBLEMAS_DE_SALUD",
            "DIF_DE_PAGO_PROBLEMAS_CON_EL_COBRO",
            "DIF_DE_PAGO_GENERAL",
            "DIF_DE_PAGO_PRIORIZA_OTRAS_DEUDAS",
        }
        self.assertEqual(expected, set(TIPIF_MAP.keys()))

    def test_normalize_accentos_y_espacios(self) -> None:
        self.assertEqual(normalize_result_key("  Prómésa de   pago "), "PROMESA_DE_PAGO")

    def test_format_fecha_compromiso_valida(self) -> None:
        self.assertEqual(format_fecha_compromiso("02/05/26"), "20260502")

    def test_format_fecha_compromiso_vacia(self) -> None:
        self.assertEqual(format_fecha_compromiso(""), "")

    def test_format_fecha_compromiso_invalida(self) -> None:
        self.assertEqual(format_fecha_compromiso("2026-05-02"), "")

    def test_truncate_observaciones_largo(self) -> None:
        text = ("hola " * 500).strip()
        truncated = truncate_observaciones(text, max_chars=OBSERVACIONES_MAX_CHARS)
        self.assertLessEqual(len(truncated), OBSERVACIONES_MAX_CHARS)
        self.assertFalse(truncated.endswith(" "))
        self.assertNotEqual(truncated, text)

    def test_truncate_observaciones_corto(self) -> None:
        self.assertEqual(
            truncate_observaciones("texto corto", max_chars=OBSERVACIONES_MAX_CHARS),
            "texto corto",
        )

    def test_truncate_observaciones_sin_espacios_respeta_tope(self) -> None:
        text = "a" * (OBSERVACIONES_MAX_CHARS + 17)
        truncated = truncate_observaciones(text, max_chars=OBSERVACIONES_MAX_CHARS)
        self.assertEqual(len(truncated), OBSERVACIONES_MAX_CHARS)

    def test_truncate_observaciones_sanitiza_caracteres_bloqueados(self) -> None:
        text = 'inicio|medio\\fin""cierre'
        truncated = truncate_observaciones(text, max_chars=OBSERVACIONES_MAX_CHARS)
        self.assertNotIn("|", truncated)
        self.assertNotIn("\\", truncated)
        self.assertNotIn('""', truncated)
        self.assertEqual(truncated, "inicio medio fin cierre")

    def test_resolve_fecha_solo_tc(self) -> None:
        self.assertEqual(resolve_fecha_promesa("02/05/26", ""), "02/05/26")

    def test_resolve_fecha_solo_nd(self) -> None:
        self.assertEqual(resolve_fecha_promesa("", "03/05/26"), "03/05/26")

    def test_resolve_fecha_ambas(self) -> None:
        self.assertEqual(resolve_fecha_promesa("02/05/26", "03/05/26"), "02/05/26")

    def test_resolve_fecha_ninguna(self) -> None:
        self.assertEqual(resolve_fecha_promesa("", ""), "")

    def test_column_alias_salida_tipificaciones(self) -> None:
        self.assertIn("[Salida] Tipificaciones", COLUMN_ALIASES["tipificaciones"])

    def test_column_alias_entrada_id_cliente(self) -> None:
        self.assertIn("[Entrada] id_cliente", COLUMN_ALIASES["id_cliente"])

    def test_column_alias_entrada_id_dni(self) -> None:
        self.assertIn("[Entrada] id_dni", COLUMN_ALIASES["id_cliente"])

    def test_column_alias_entrada_user_number(self) -> None:
        self.assertIn("[Entrada] user_number", COLUMN_ALIASES["id_cliente"])

    def test_load_input_fallback_a_user_number_para_id_cliente(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input_user_number_alias.csv"
            input_path.write_text(
                "\n".join(
                    [
                        "Call ID,[Salida] Tipificaciones,[Salida] observaciones,[Entrada] user_number",
                        "call_1,Promesa de pago,ok,5493517710632",
                    ]
                ),
                encoding="utf-8",
            )

            loaded = load_input(str(input_path))
            self.assertEqual(loaded.loc[0, "id_cliente"], "5493517710632")


if __name__ == "__main__":
    unittest.main()
