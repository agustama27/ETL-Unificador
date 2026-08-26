"""UAT de paridad contra los repos upstream del Desktop.

Ejecuta cada wrapper unificado DOS veces con el mismo input sintético: una con
``cwd`` en el legacy vendorizado (``etls/<cliente>/legacy``) y otra con ``cwd``
en el repo upstream del Desktop. Como los wrappers importan el código legacy
relativo al ``cwd``, cada corrida ejecuta una copia distinta del mismo proceso;
después se comparan los artefactos byte a byte (los ZIP, por miembro, porque su
metadata embebe mtimes).

Estos tests son UAT locales: se saltean solos cuando el repo upstream no está
en el Desktop (CI incluido). No cubren:

- Naranja X MA (voice/chat daily y PCT): el vendorizado está ADELANTE del
  upstream (hotfixes M60/cajon_asig_prod/header-guard nunca commiteados en el
  desktop), así que la paridad byte a byte no es el objetivo ahí.
- Claro UY y Encuesta CX: sin repo upstream en el Desktop.
- Naranja X MT back: upstream y vendorizado son hash-idénticos en todo el
  código fuente; la paridad queda garantizada por identidad.
"""

import re
import subprocess
import sys
import zipfile
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("pandas")

from etls.bancor.tests.test_bancor_base_job import _write_input as bancor_input
from etls.cartasur.tests.test_cartasur_job import _write_input as cartasur_input
from etls.epec.tests.test_epec_base_job import _write_input as epec_input
from etls.naranjax.tests.test_mt_voice_job import _write_input as mt_input
from etls.petersen.tests.test_petersen_base_job import _write_inputs as petersen_base_inputs
from etls.petersen.tests.test_gestiones_job import _write_input as petersen_input

WORKSPACE = Path(__file__).resolve().parents[2]
DESKTOP = Path.home() / "Desktop"

UPSTREAM = {
    "bancor": DESKTOP / "soho-bancor-cobranzas-etl",
    "epec": DESKTOP / "soho-EPEC",
    "fravega": DESKTOP / "SOHO-Fravega-Cobranzas-Resultados",
    "social": DESKTOP / "soho-socialLearning",
    "petersen": DESKTOP / "soho-petersen-cobranzas-resultados",
    "mt": DESKTOP / "soho-naranjaX-MT-etl",
    "alvarez": DESKTOP / "soho-Alvarez-Maquinarias-ETL",
    "cartasur": DESKTOP / "Soho-CartaSur",
    "petersen_base": DESKTOP / "soho-petersen-etl2",
}


def _needs(client: str) -> Path:
    upstream = UPSTREAM[client]
    if not upstream.is_dir():
        pytest.skip(f"repo upstream ausente: {upstream}")
    return upstream


def _run_wrapper(wrapper: Path, cwd: Path, arguments: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(wrapper), *arguments],
        cwd=cwd, capture_output=True, text=True, timeout=600, check=False,
    )


def _snapshot(output_dir: Path, normalize=None) -> dict[str, bytes]:
    """Contenido por ruta relativa; los ZIP se expanden por miembro."""
    result: dict[str, bytes] = {}
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(output_dir).as_posix()
        if normalize is not None:
            relative = normalize(relative)
            if relative is None:
                continue
        if path.suffix.casefold() == ".zip":
            with zipfile.ZipFile(path) as archive:
                for name in sorted(archive.namelist()):
                    result[f"{relative}::{name}"] = archive.read(name)
        else:
            result[relative] = path.read_bytes()
    return result


def _assert_parity(client: str, wrapper: Path, vendored_cwd: Path, upstream_cwd: Path,
                   arguments_for: "callable", tmp_path: Path, normalize=None) -> None:
    sides = {}
    for side, cwd in (("unificador", vendored_cwd), ("upstream", upstream_cwd)):
        output_dir = tmp_path / side / "run" / "output"
        output_dir.mkdir(parents=True)
        result = _run_wrapper(wrapper, cwd, arguments_for(output_dir))
        assert result.returncode == 0, (
            f"[{client}/{side}] exit {result.returncode}\n{result.stderr or result.stdout}")
        sides[side] = _snapshot(output_dir, normalize)

    unificador, upstream = sides["unificador"], sides["upstream"]
    assert sorted(unificador) == sorted(upstream), (
        f"[{client}] conjuntos de artefactos distintos:\n"
        f"  unificador: {sorted(unificador)}\n  upstream:   {sorted(upstream)}")
    different = [name for name in unificador if unificador[name] != upstream[name]]
    assert not different, f"[{client}] difieren byte a byte: {different}"


def test_bancor_base_parity(tmp_path: Path) -> None:
    upstream = _needs("bancor")
    source = bancor_input(tmp_path)
    _assert_parity(
        "bancor", WORKSPACE / "etls/bancor/job.py",
        WORKSPACE / "etls/bancor/legacy", upstream,
        lambda output: ["--input", str(source), "--output_dir", str(output)],
        tmp_path)


def test_epec_base_parity(tmp_path: Path) -> None:
    upstream = _needs("epec")
    source = epec_input(tmp_path)
    _assert_parity(
        "epec", WORKSPACE / "etls/epec/job.py",
        WORKSPACE / "etls/epec/legacy", upstream,
        lambda output: ["--input", str(source), "--output_dir", str(output)],
        tmp_path)


def test_fravega_base_parity(tmp_path: Path) -> None:
    upstream = _needs("fravega")
    source = tmp_path / "base.csv"
    source.write_text(
        "DNI;Credito;Importe;Cuotas;Ultima cuota;Tipo de Cartera;Dias atraso;Cel;Nombre\n"
        "12345678;CR1;1000,50;3;05/2026;PROPIA;30;3517710632;CLIENTE SINTETICO\n"
        "12345678;CR2;500,25;2;06/2026;PROPIA;45;3517710632;CLIENTE SINTETICO\n"
        "20111222;CR3;800,00;1;07/2026;TERCEROS;10;3514400185;OTRO CLIENTE\n",
        encoding="utf-8")
    _assert_parity(
        "fravega", WORKSPACE / "etls/fravega/job.py",
        WORKSPACE / "etls/fravega/legacy", upstream,
        lambda output: ["--input", str(source), "--output_dir", str(output)],
        tmp_path)


@pytest.mark.parametrize("country", ("argentina", "chile"))
def test_sociallearning_base_parity(tmp_path: Path, country: str) -> None:
    upstream = _needs("social")
    source = tmp_path / "cartera.csv"
    source.write_text(
        "APELLIDO,NOMBRE,DOCUMENTO,CELULAR,MONTO,Monto Cuota,% Descuento,"
        "PORCENTAJE_BECA,Dias Mora,DIAS_VENCIDO\n"
        "AGUIRRE,CAROLINA,12345678,3517710632,1500.00,1500.00,10,10,30,30\n"
        "AGUIRRE,CAROLINA,12345678,3517710632,1500.00,1500.00,10,10,45,45\n"
        "PEREZ,JUAN,20111222,3514400185,2000.00,2000.00,0,0,15,15\n",
        encoding="utf-8")
    _assert_parity(
        f"social-{country}", WORKSPACE / "etls/sociallearning/job.py",
        WORKSPACE / "etls/sociallearning/legacy", upstream,
        lambda output: ["--country", country, "--input", str(source),
                        "--output_dir", str(output)],
        tmp_path)


def test_petersen_gestiones_parity(tmp_path: Path) -> None:
    upstream = _needs("petersen")
    source = petersen_input(tmp_path, banks=["Santa Fe", "Entre Ríos", "Santa Cruz", "San Juan"])
    _assert_parity(
        "petersen", WORKSPACE / "etls/petersen/job.py",
        WORKSPACE / "etls/petersen/legacy", upstream,
        lambda output: ["--input", str(source), "--output_dir", str(output)],
        tmp_path)


def test_naranjax_mt_daily_parity(tmp_path: Path) -> None:
    upstream = _needs("mt")
    source = mt_input(tmp_path, 33)
    _assert_parity(
        "naranjax-mt", WORKSPACE / "etls/naranjax/mt_voice_job.py",
        WORKSPACE / "etls/naranjax/legacy/mt", upstream,
        lambda output: ["--input", str(source), "--output_dir", str(output)],
        tmp_path)


def test_cartasur_base_parity(tmp_path: Path) -> None:
    upstream = _needs("cartasur")
    pytest.importorskip("holidays")
    source = cartasur_input(tmp_path)
    _assert_parity(
        "cartasur", WORKSPACE / "etls/cartasur/job.py",
        WORKSPACE / "etls/cartasur/legacy", upstream,
        lambda output: ["--input", str(source), "--output_dir", str(output)],
        tmp_path,
        # Los logs internos (.logs/) llevan timestamps: no son artefactos.
        normalize=lambda name: None if name.startswith(".logs/") else name)


def test_petersen_base_tabla_integradora_parity(tmp_path: Path) -> None:
    upstream = _needs("petersen_base")
    incoming = petersen_base_inputs(tmp_path)
    _assert_parity(
        "petersen-base", WORKSPACE / "etls/petersen/job_base.py",
        WORKSPACE / "etls/petersen/legacy_base", upstream,
        lambda output: ["--input", str(incoming), "--output_dir", str(output)],
        tmp_path,
        # Los nombres llevan _HHMMSS del reloj: se normaliza para comparar
        # contenido; la fecha YYYYMMDD (del input) se preserva.
        normalize=lambda name: re.sub(r"_\d{6}(?=\.(?:csv|txt)$)", "", name))


def test_alvarez_cobranzas_parity(tmp_path: Path) -> None:
    upstream = _needs("alvarez")
    pytest.importorskip("pypdf")
    pytest.importorskip("xlrd")
    pytest.importorskip("xlwt")
    pytest.importorskip("reportlab")
    legacy = WORKSPACE / "etls/alvarezmaquinarias/legacy"
    sys.path.insert(0, str(legacy))
    try:
        from scripts.generate_sample_data import generate_sample_data
        inputs = generate_sample_data(tmp_path, date.today())
    finally:
        sys.path.remove(str(legacy))
    _assert_parity(
        "alvarez", WORKSPACE / "etls/alvarezmaquinarias/job.py",
        legacy, upstream,
        lambda output: ["--input", str(inputs / "saldos.xls"),
                        "--maquinarias", str(inputs / "maquinarias.xlsx"),
                        "--servicios", str(inputs / "servicios.xlsx"),
                        "--repuestos", str(inputs / "repuestos.pdf"),
                        "--output_dir", str(output)],
        tmp_path)
