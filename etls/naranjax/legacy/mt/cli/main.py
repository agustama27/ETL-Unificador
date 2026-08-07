import argparse
from pathlib import Path

from core.modelos import ArchivosDia
from core.procesar_dia import procesar_dia
from core.runtime_paths import build_config


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ETL NaranjaX MT")
    parser.add_argument("--base", help="Ruta al TXT de entrada")
    parser.add_argument("--estado", help="Directorio de estado")
    parser.add_argument("--salida", help="Directorio de salida")
    return parser


def run_cli(argv: list[str]) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv[1:])

    config = build_config(estado_cli=args.estado, salida_cli=args.salida)
    archivos = ArchivosDia(
        base_entrada=Path(args.base) if args.base else None,
        usar_base_reciente=not bool(args.base),
    )

    result = procesar_dia(config, archivos, log_cb=lambda line: print(line), modo_ejecucion="cli")
    if result.status != "ok":
        for err in result.errores:
            print(f"Error: {err}")
        return 1
    return 0
