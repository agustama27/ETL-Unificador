from __future__ import annotations

import pandas as pd

from back_base_etl.filtros import DEFAULT_CAJONES_SCOPE, aplicar_filtros


def test_default_scope_includes_m60_and_m90() -> None:
    assert DEFAULT_CAJONES_SCOPE == ("M60", "M90")


def test_aplicar_filtros_keeps_m60_and_m90() -> None:
    df = pd.DataFrame(
        [
            {"nroproducto": "1", "cajon": "M60"},
            {"nroproducto": "2", "cajon": "M90"},
            {"nroproducto": "3", "cajon": "M30"},
        ]
    )

    filtrado, resumen = aplicar_filtros(df)

    assert set(filtrado["nroproducto"]) == {"1", "2"}
    assert resumen["total_incluidos"] == 2
    assert resumen["cajon_fuera_scope"] == 1
