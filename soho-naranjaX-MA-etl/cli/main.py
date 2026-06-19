from __future__ import annotations

import argparse
import logging
from datetime import date
from pathlib import Path

from core.config_store import load_config
from core.modelos import ArchivosDia, ConfigDia
from core.procesar_dia import procesar_dia
from core.runtime_paths import resolve_estado_dir, resolve_output_dir
from core.validators_archivos import aggregate_messages, validar_archivo, validar_csv_basico, validar_estado_mensual


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NaranjaX ETL CLI")
    parser.add_argument("--base", required=True, help="Path base mensual")
    parser.add_argument("--planes", required=False, default=None, help="Path archivo PLANES mensual")
    parser.add_argument("--pagos", required=False, default=None, help="Path archivo PAGOS (opcional, ignorado)")
    parser.add_argument(
        "--inicio-mes-sin-diarios",
        action="store_true",
        help="Permite ejecutar inicializacion mensual y generar ROMAN sin PLANES/PAGOS diarios",
    )
    parser.add_argument("--salida", default=None, help="Carpeta de salida")
    parser.add_argument("--estado", default=None, help="Carpeta de estado")
    parser.add_argument("--fecha", default=date.today().strftime("%Y%m%d"), help="Fecha YYYYMMDD")
    return parser


def run_cli(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv[1:] if argv else None)
    cfg = load_config()
    estado_dir = resolve_estado_dir(cfg.get("carpeta_estado"), explicit_estado_dir=args.estado)
    salida_dir = resolve_output_dir(cfg.get("carpeta_salida"), explicit_output_dir=args.salida)

    if estado_dir is None:
        print("Error: carpeta de estado no configurada. Use --estado o configure NARANJAX_ESTADO_DIR.")
        return 1
    if salida_dir is None:
        print("Error: carpeta de salida no configurada. Use --salida o configure NARANJAX_OUTPUT_DIR.")
        return 1

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    fecha = str(args.fecha)
    config = ConfigDia(
        estado_dir=estado_dir,
        output_dir=salida_dir,
        logs_dir=salida_dir / "logs",
        procesados_dir=salida_dir / "procesados",
    )
    diarios_dir = Path(args.planes).parent if args.planes else Path(args.base).parent
    archivos = ArchivosDia(
        fecha=fecha,
        mes=fecha[:6],
        input_base=Path(args.base),
        diarios_dir=diarios_dir,
        planes=Path(args.planes) if args.planes else None,
        pagos=Path(args.pagos) if args.pagos else None,
        usar_pagos=bool(args.pagos),
        autodetect_planes=False,
        autodetect_pagos=False,
        modo_sin_diarios=bool(args.inicio_mes_sin_diarios),
    )

    issues = []
    if archivos.planes is None and not archivos.modo_sin_diarios:
        print("Falta path de input requerido (--planes).")
        return 1
    validations = [
        ("base", archivos.input_base, (".xlsx",)),
    ]
    if archivos.planes is not None:
        validations.append(("planes", archivos.planes, (".xlsx", ".csv")))
    if archivos.pagos is not None:
        validations.append(("pagos", archivos.pagos, (".csv", ".txt")))
    for alias, path, extensiones in validations:
        alias_issues = []
        for issue in validar_archivo(path, extensiones):
            if issue.code == "MISSING":
                issue = issue.__class__(
                    code=issue.code,
                    message=f"{issue.message}: input '{alias}' -> {path}",
                )
            alias_issues.append(issue)
        issues.extend(alias_issues)
        if alias == "pagos" and all(issue.code != "MISSING" for issue in alias_issues):
            issues.extend(validar_csv_basico(path))
    state_issues = validar_estado_mensual(config.estado_dir, archivos.mes)
    if state_issues:
        print(f"No hay estado mensual para {archivos.mes[:4]}-{archivos.mes[4:6]}. Se inicializara desde base en esta ejecucion.")
    issues.extend([issue for issue in state_issues if issue.code != "STATE_MISSING"])
    messages = aggregate_messages(issues)
    if messages:
        for message in messages:
            print(message)
        return 1

    if archivos.pagos is not None:
        print("Aviso: se proceso archivo de pagos para esta corrida.")
    if archivos.modo_sin_diarios:
        print("Modo especial: inicio de mes sin diarios (PLANES/PAGOS intencionalmente ausentes).")

    resultado = procesar_dia(config, archivos, log_cb=lambda line: print(line))
    return 0 if resultado.status == "success" else 1
