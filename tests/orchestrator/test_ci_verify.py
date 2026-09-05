"""El guard que impide que un skip pase por verde.

Su modo de falla es el silencio: si el parseo deja de reconocer las lineas de pytest,
`ci_verify` reporta cero skips inesperados y el build queda verde con la suite rota.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from ci_verify import MOTIVOS_ESPERADOS, skips, skips_inesperados  # noqa: E402

SALIDA_CI = """\
SKIPPED [1] test/integration/uat_upstream/test_upstream_parity.py:58: repo upstream ausente: /home/x/Desktop/soho-bancor-cobranzas-etl
SKIPPED [1] test/integration/test_helm_chart.py:31: helm no esta en el PATH
401 passed, 2 skipped in 90.11s
"""

SALIDA_CON_DEPENDENCIA_FALTANTE = """\
SKIPPED [1] test/integration/uat_upstream/test_upstream_parity.py:58: repo upstream ausente: /home/x/Desktop/soho
SKIPPED [1] etls/alvarezmaquinarias/tests/test_alvarez_job.py:13: could not import 'xlwt': No module named 'xlwt'
399 passed, 2 skipped in 88.02s
"""


def test_reconoce_las_lineas_de_skip_de_pytest():
    """Si esto se rompe, el guard reporta cero y deja pasar cualquier cosa."""
    assert len(skips(SALIDA_CI)) == 2


def test_los_skips_esperados_no_rompen_el_build():
    assert skips_inesperados(SALIDA_CI) == []


def test_una_dependencia_faltante_rompe_el_build():
    """El caso real: xlwt y reportlab estaban sin declarar y Alvarez nunca corrio en limpio."""
    inesperados = skips_inesperados(SALIDA_CON_DEPENDENCIA_FALTANTE)

    assert len(inesperados) == 1
    assert "xlwt" in inesperados[0][2]


def test_una_suite_sin_skips_no_reporta_nada():
    assert skips("412 passed, 1 xfailed in 89.90s") == []


@pytest.mark.parametrize("motivo", MOTIVOS_ESPERADOS)
def test_cada_motivo_esperado_esta_documentado_en_el_codigo(motivo):
    """Un motivo agregado sin explicacion es una puerta abierta."""
    fuente = (Path(__file__).resolve().parents[2] / "scripts" / "ci_verify.py").read_text(
        encoding="utf-8")

    assert motivo in fuente
