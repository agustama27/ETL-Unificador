"""
Tests de la quita de intereses (back-base / procesar_base_completa).

Cubre la funcion pura `calcular_quita` (spec 3.1/3.2) y el no-regression de naming
de las trampas T1 (renombrado semantico) y T2 (deteccion booleana si/no -> true/false).
"""
import sys
from pathlib import Path

import pytest

# Importa el modulo de back-base por path, robusto ante el rootdir de pytest.
_PROCESOS = Path(__file__).resolve().parents[2] / "back-base" / "procesos"
if str(_PROCESOS) not in sys.path:
    sys.path.insert(0, str(_PROCESOS))

import base_generator  # noqa: E402
from base_generator import calcular_quita  # noqa: E402


# ── 1. Porcentajes por rango ────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "dias_mora, esperado_monto",
    [
        (75, 800.0),   # rango 61-90  -> (0.00, 1.00): quita = 200
        (150, 770.0),  # rango 91-180 -> (0.30, 1.00): quita = 0.3*100 + 200 = 230
        (300, 750.0),  # rango 181-365-> (0.50, 1.00): quita = 0.5*100 + 200 = 250
    ],
)
def test_porcentajes_por_rango(dias_mora, esperado_monto):
    aplica, monto = calcular_quita("MA", dias_mora, comp_total=100, punit_total=200,
                                   monto_adeudado=1000, tiene_oferta=False)
    assert aplica == "si"
    assert monto == esperado_monto


# ── 2. Bordes exactos de los rangos ─────────────────────────────────────────────

@pytest.mark.parametrize(
    "dias_mora, aplica_esperado",
    [
        (60, "no"),
        (61, "si"),
        (90, "si"),
        (91, "si"),
        (180, "si"),
        (181, "si"),
        (365, "si"),
        (366, "no"),
    ],
)
def test_bordes_de_rango(dias_mora, aplica_esperado):
    aplica, _ = calcular_quita("MA", dias_mora, comp_total=100, punit_total=100,
                               monto_adeudado=1000, tiene_oferta=False)
    assert aplica == aplica_esperado


# ── 3. Tipo de mercado ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("tipo", ["MC", "", None, "__MIXTO__"])
def test_mercado_no_elegible(tipo):
    aplica, monto = calcular_quita(tipo, 150, comp_total=100, punit_total=200,
                                   monto_adeudado=1000, tiene_oferta=False)
    assert (aplica, monto) == ("no", None)


def test_mercado_ma_case_insensitive():
    aplica, _ = calcular_quita(" ma ", 150, comp_total=100, punit_total=200,
                               monto_adeudado=1000, tiene_oferta=False)
    assert aplica == "si"


# ── 4. Sin descuento real ───────────────────────────────────────────────────────

def test_comp_y_punit_cero_no_aplica():
    aplica, monto = calcular_quita("MA", 150, comp_total=0, punit_total=0,
                                   monto_adeudado=1000, tiene_oferta=False)
    assert (aplica, monto) == ("no", None)


def test_comp_y_punit_nulos_se_tratan_como_cero():
    aplica, monto = calcular_quita("MA", 150, comp_total=None, punit_total=None,
                                   monto_adeudado=1000, tiene_oferta=False)
    assert (aplica, monto) == ("no", None)


# ── 5. Exclusividad con oferta ──────────────────────────────────────────────────

def test_con_oferta_excluye_por_default():
    aplica, _ = calcular_quita("MA", 150, comp_total=100, punit_total=200,
                               monto_adeudado=1000, tiene_oferta=True)
    assert aplica == "no"


def test_flag_excluir_oferta_desactivado(monkeypatch):
    monkeypatch.setattr(base_generator, "EXCLUIR_SI_TIENE_OFERTA", False)
    aplica, _ = calcular_quita("MA", 150, comp_total=100, punit_total=200,
                               monto_adeudado=1000, tiene_oferta=True)
    assert aplica == "si"


# ── 6. Redondeo y sanity (d) ────────────────────────────────────────────────────

def test_redondeo_dos_decimales():
    # rango 75 -> (0, 1): quita = 66.66 ; monto_quita = 1000 - 66.66 = 933.34
    aplica, monto = calcular_quita("MA", 75, comp_total=33.33, punit_total=66.66,
                                   monto_adeudado=1000, tiene_oferta=False)
    assert aplica == "si"
    assert monto == 933.34


def test_quita_que_deja_monto_no_positivo_no_aplica():
    # rango 150 -> (0.3, 1): quita = 2000 > monto -> monto_quita negativo -> no
    aplica, monto = calcular_quita("MA", 150, comp_total=0, punit_total=2000,
                                   monto_adeudado=1000, tiene_oferta=False)
    assert (aplica, monto) == ("no", None)


def test_monto_quita_siempre_menor_al_adeudado():
    aplica, monto = calcular_quita("MA", 150, comp_total=100, punit_total=200,
                                   monto_adeudado=1000, tiene_oferta=False)
    assert aplica == "si"
    assert 0 < monto < 1000


# ── 7. Decimal europeo (T3) ─────────────────────────────────────────────────────

def test_decimal_europeo_en_entradas():
    # comp=1000.50, punit=2000.50, monto=100000.00, rango 150 -> (0.3, 1)
    # quita = 0.3*1000.50 + 2000.50 = 300.15 + 2000.50 = 2300.65
    aplica, monto = calcular_quita("MA", 150, comp_total="1000,50", punit_total="2000,50",
                                   monto_adeudado="100000,00", tiene_oferta=False)
    assert aplica == "si"
    assert monto == 97699.35


# ── 8. No-regression de naming (T1 / T2) ────────────────────────────────────────

def test_naming_semantico_no_renombra_columnas_quita():
    """T1: el normalizador semantico debe dejar los nombres exactos."""
    assert base_generator._nombre_columna_semantico("aplica_quita") == "aplica_quita"
    assert base_generator._nombre_columna_semantico("monto_quita_ars") == "monto_quita_ars"
    assert base_generator._nombre_columna_semantico("fecha_limite_quita") == "fecha_limite_quita"
