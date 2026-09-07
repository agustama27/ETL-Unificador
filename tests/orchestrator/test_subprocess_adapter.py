"""El adapter genérico y la extensión del archivo de entrada.

`SubprocessAdapter` lo comparten 10 ETLs de 6 clientes (AGENTS.md). Construía la
ruta del input con la **primera extensión declarada** en el manifiesto, mientras
que el staging guarda el archivo con su **extensión real**. Con un solo formato
declarado las dos coinciden y nadie lo notaba; en cuanto un ETL declaraba varios,
el subproceso recibía una ruta inexistente. Es la razón por la que Alvarez,
CartaSur y Petersen tienen adapter propio.
"""

from datetime import date
from pathlib import Path

import pytest

from etl_core.contracts import SubprocessAdapter, ValidationError
from orchestrator.models import (ETLDefinition, InputSpec, Readiness,
                                 RepositoryStatus, RunRequest)

HOY = date(2026, 7, 21)


def _definicion(*extensiones: str) -> ETLDefinition:
    return ETLDefinition(
        id="cliente.base.daily", name="Cliente base",
        repository_status=RepositoryStatus.PRESENT, readiness=Readiness.READY,
        executable=True, project_path=Path("etls/cliente/legacy"),
        working_dir=Path("etls/cliente/legacy"),
        entrypoint=Path("etls/cliente/job.py"),
        command=("python", "../job.py"),
        inputs=(InputSpec(role="base", extensions=tuple(extensiones), required=True),),
        adapter="etl_core.contracts:SubprocessAdapter",
    )


def _pedido(nombre: str) -> RunRequest:
    return RunRequest(etl_id="cliente.base.daily", business_date=HOY,
                      inputs={"base": Path("/subido") / nombre})


def _ruta_de_input(comando: tuple[str, ...]) -> str:
    return comando[comando.index("--input") + 1]


@pytest.mark.parametrize("nombre", ["base.csv", "base.xlsx", "base.xls"])
def test_usa_la_extension_del_archivo_subido(nombre: str) -> None:
    """Lo que el staging escribió es `input/base<sufijo real>`, no `extensions[0]`."""
    comando = SubprocessAdapter(today=lambda: HOY).command(
        _definicion(".csv", ".xlsx", ".xls"), _pedido(nombre), Path("/run"))

    assert _ruta_de_input(comando).endswith(f"base{Path(nombre).suffix}")


def test_con_una_sola_extension_el_resultado_no_cambia() -> None:
    """Garantía para los 10 ETLs que ya usan el adapter: cero cambio de comportamiento."""
    comando = SubprocessAdapter(today=lambda: HOY).command(
        _definicion(".csv"), _pedido("base.csv"), Path("/run"))

    assert _ruta_de_input(comando).endswith("base.csv")


def test_la_extension_se_normaliza_a_minusculas() -> None:
    """El staging usa `casefold()`: si el adapter no, en Linux no encuentra el archivo."""
    comando = SubprocessAdapter(today=lambda: HOY).command(
        _definicion(".csv", ".xlsx"), _pedido("BASE.XLSX"), Path("/run"))

    assert _ruta_de_input(comando).endswith("base.xlsx")


def test_el_orden_declarado_ya_no_decide_nada() -> None:
    """Antes, declarar `[.csv, .xlsx]` y subir un xlsx pedía `base.csv`: inexistente."""
    adapter = SubprocessAdapter(today=lambda: HOY)

    primero_csv = adapter.command(_definicion(".csv", ".xlsx"), _pedido("base.xlsx"), Path("/run"))
    primero_xlsx = adapter.command(_definicion(".xlsx", ".csv"), _pedido("base.xlsx"), Path("/run"))

    assert _ruta_de_input(primero_csv) == _ruta_de_input(primero_xlsx)


def test_sigue_rechazando_una_fecha_que_no_sea_hoy() -> None:
    """El fix no aflojó la guarda de ADR-001 decisión 7."""
    pedido = RunRequest(etl_id="cliente.base.daily", business_date=date(2026, 7, 20),
                        inputs={"base": Path("/subido/base.csv")})

    with pytest.raises(ValidationError, match="today"):
        SubprocessAdapter(today=lambda: HOY).command(_definicion(".csv"), pedido, Path("/run"))
