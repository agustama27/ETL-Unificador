"""CLI del ETL de cobranzas — Álvarez Maquinaria.

Corrida diaria, dos pasos:

    python main.py --preparar     # crea inputs/<hoy>/ para dejar los exports
    python main.py                # procesa esa partición

Los cuatro exports se identifican por su extensión, así que no hace falta
renombrarlos. `--saldos`, `--maquinarias`, `--repuestos` y `--servicios`
siguen disponibles para fijar un archivo puntual.
"""

from __future__ import annotations

import argparse
import math
from datetime import date
from pathlib import Path
from typing import Sequence

from src.etl.config import PipelineConfig
from src.etl.pipeline import run_pipeline


def _parse_iso_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("usar fecha AAAA-MM-DD válida") from error
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("usar fecha canónica AAAA-MM-DD")
    return parsed


def _parse_bare_filename(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or path.name != value or value in {".", ".."}:
        raise argparse.ArgumentTypeError(
            "usar solo un nombre de archivo dentro de inputs/<run-date>/"
        )
    return value


def _reject_output_override(value: str) -> str:
    raise argparse.ArgumentTypeError(
        "--output fue eliminado; usar --run-date para seleccionar outputs/<run-date>/"
    )


def _parse_legacy_exchange_rate(value: str) -> float:
    try:
        rate = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("usar un número finito mayor a 0") from error
    if not math.isfinite(rate) or rate <= 0:
        raise argparse.ArgumentTypeError("usar un número finito mayor a 0")
    return rate


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--saldos",
        type=_parse_bare_filename,
        default="saldos.xls",
        help="Saldos: saldos.xls por defecto o un basename saldos.csv compatible",
    )
    parser.add_argument("--maquinarias", type=_parse_bare_filename, default="maquinarias.xlsx")
    parser.add_argument("--repuestos", type=_parse_bare_filename, default="repuestos.pdf")
    parser.add_argument("--servicios", type=_parse_bare_filename, default="servicios.xlsx")
    parser.add_argument("--output", type=_reject_output_override, help=argparse.SUPPRESS)
    parser.add_argument(
        "--tipo-cambio",
        type=_parse_legacy_exchange_rate,
        default=None,
        help="Obsoleto: se acepta temporalmente, no afecta los saldos USD",
    )
    parser.add_argument(
        "--reference-date",
        type=_parse_iso_date,
        default=None,
        help="Fecha de corte para dias de mora, formato AAAA-MM-DD (default: hoy)",
    )
    parser.add_argument(
        "--run-date",
        type=_parse_iso_date,
        default=None,
        help="Partición de entrada y salida, formato AAAA-MM-DD (default: hoy)",
    )
    parser.add_argument(
        "--input-date",
        type=_parse_iso_date,
        default=None,
        help="Partición de inputs, formato AAAA-MM-DD (usar junto con --output-date)",
    )
    parser.add_argument(
        "--output-date",
        type=_parse_iso_date,
        default=None,
        help="Partición y sufijo de outputs, formato AAAA-MM-DD (usar junto con --input-date)",
    )
    parser.add_argument(
        "--preparar",
        action="store_true",
        help="Crea inputs/<run-date>/ para dejar los exports del día y termina",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Permite reemplazar las salidas fijas de la partición seleccionada",
    )
    return parser.parse_args(argv)


def _preparar_particion(project_root: Path, run_date: date) -> None:
    """Crea la partición del día y dice qué dejar adentro.

    Separado del procesamiento a propósito: crear la carpeta y procesarla son
    dos momentos distintos del día, y mezclarlos haría que una corrida sobre
    una fecha equivocada cree la carpeta en vez de fallar.
    """
    input_dir = project_root / "inputs" / run_date.isoformat()
    ya_existia = input_dir.is_dir()
    input_dir.mkdir(parents=True, exist_ok=True)
    print(f"Partición de entrada: {input_dir}" + (" (ya existía)" if ya_existia else ""))

    presentes = sorted(path.name for path in input_dir.iterdir() if path.is_file())
    if presentes:
        print("Archivos presentes:")
        for nombre in presentes:
            print(f"  - {nombre}")
    else:
        print("Dejá ahí los cuatro exports de Autologica (el nombre no importa):")
        print("  - saldos de clientes      .csv o .xls")
        print("  - maquinarias             .xlsx")
        print("  - remitos de servicios    .xlsx  (con 'servicio' en el nombre)")
        print("  - remitos de repuestos    .pdf")
    print(f"Después: python main.py --run-date {run_date.isoformat()}")


def main() -> None:
    args = _parse_args()
    reference_date = args.reference_date or date.today()
    if args.run_date is not None and (args.input_date is not None or args.output_date is not None):
        raise ValueError("usar --run-date o --input-date junto con --output-date, no ambos")
    if (args.input_date is None) != (args.output_date is None):
        raise ValueError("--input-date y --output-date deben indicarse juntos")
    input_date = args.input_date or args.run_date or date.today()
    output_date = args.output_date or args.run_date or date.today()
    if args.tipo_cambio is not None:
        print("Advertencia: --tipo-cambio está obsoleto y no tiene efecto.")
    project_root = Path(__file__).resolve().parent
    if args.preparar:
        _preparar_particion(project_root, input_date)
        return
    config = PipelineConfig.for_dated_run(
        project_root=project_root,
        input_date=input_date,
        output_date=output_date,
        source_names={
            "saldos": args.saldos,
            "maquinarias": args.maquinarias,
            "repuestos": args.repuestos,
            "servicios": args.servicios,
        },
        reference_date=reference_date,
        overwrite=args.overwrite,
    )

    # Antes de procesar: con el descubrimiento por extensión, qué archivo
    # entró como qué fuente deja de ser evidente. Si la corrida aborta, el
    # operador igual vio la asignación.
    print("Fuentes de la corrida:")
    for etiqueta, ruta in (
        ("saldos     ", config.saldos_generales_path),
        ("maquinarias", config.maquinarias_path),
        ("repuestos  ", config.remitos_repuestos_path),
        ("servicios  ", config.remitos_servicios_path),
    ):
        print(f"  {etiqueta}  {ruta.name}")

    result = run_pipeline(config)
    print(f"Roman (gestion):    {result.roman_path}")
    print(f"Approach (llamadas): {result.approach_path}")
    print(result.diagnostics.summary())


if __name__ == "__main__":
    main()
