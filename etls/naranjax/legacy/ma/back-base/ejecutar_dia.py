#!/usr/bin/env python3
"""Execute daily Mora Avanzada flow with persistent state."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.modelos import ArchivosDia, ConfigDia
from core.procesar_dia import procesar_dia


LOGGER = logging.getLogger("ejecutar_dia")
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = SCRIPT_DIR / "archivo-recibido" / "NARANJAX_MA_BaseMensual.xlsx"
DEFAULT_DIARIOS_DIR = SCRIPT_DIR / "diarios" / "entrada"
DEFAULT_ESTADOS_DIR = SCRIPT_DIR / "estados"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "base-generada"
DEFAULT_LOGS_DIR = SCRIPT_DIR / "logs"
DEFAULT_PROCESADOS_DIR = SCRIPT_DIR / "diarios" / "procesados"


def configurar_logging(fecha: str, logs_dir: str) -> Path:
    """Configure console + daily file logging for current execution."""
    logs_path = Path(logs_dir)
    logs_path.mkdir(parents=True, exist_ok=True)
    log_file = logs_path / f"{fecha}.log"

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
    logger_root = logging.getLogger()
    logger_root.setLevel(logging.INFO)
    logger_root.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger_root.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger_root.addHandler(file_handler)

    return log_file

def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta el flujo diario con estado persistente")
    parser.add_argument("--fecha", default=date.today().strftime("%Y%m%d"), help="Fecha de corrida YYYYMMDD")
    parser.add_argument("--mes", default=None, help="Mes de estado YYYYMM (default: fecha[:6])")
    parser.add_argument("--input", default=str(DEFAULT_INPUT_PATH), help="Base mensual (Excel Asignacion)")
    parser.add_argument("--diarios_dir", default=str(DEFAULT_DIARIOS_DIR), help="Carpeta de diarios de entrada")
    parser.add_argument("--estado_dir", default=str(DEFAULT_ESTADOS_DIR), help="Carpeta de estados persistentes")
    parser.add_argument("--output_dir", default=str(DEFAULT_OUTPUT_DIR), help="Carpeta destino ROMAN")
    parser.add_argument("--logs_dir", default=str(DEFAULT_LOGS_DIR), help="Carpeta de logs diarios")
    parser.add_argument(
        "--procesados_dir",
        default=str(DEFAULT_PROCESADOS_DIR),
        help="Carpeta base para diarios procesados",
    )
    parser.add_argument("--planes", default=None, help="Path explicito de PLANES diario (.xlsx)")
    parser.add_argument("--pagos", default=None, help="Path explicito de PAGOS diario (.csv)")
    args = parser.parse_args()

    fecha = str(args.fecha).strip()
    mes = str(args.mes).strip() if args.mes else fecha[:6]
    log_path = configurar_logging(fecha=fecha, logs_dir=args.logs_dir)
    LOGGER.info("Starting daily execution fecha=%s mes=%s", fecha, mes)
    LOGGER.info(
        "Run paths input=%s diarios_dir=%s estado_dir=%s output_dir=%s logs_file=%s procesados_dir=%s",
        args.input,
        args.diarios_dir,
        args.estado_dir,
        args.output_dir,
        log_path,
        args.procesados_dir,
    )

    config = ConfigDia(
        estado_dir=Path(args.estado_dir),
        output_dir=Path(args.output_dir),
        logs_dir=Path(args.logs_dir),
        procesados_dir=Path(args.procesados_dir),
    )
    archivos = ArchivosDia(
        fecha=fecha,
        mes=mes,
        input_base=Path(args.input),
        diarios_dir=Path(args.diarios_dir),
        planes=Path(args.planes) if args.planes else None,
        pagos=Path(args.pagos) if args.pagos else None,
        usar_pagos=True,
    )

    resultado = procesar_dia(config=config, archivos=archivos, log_cb=None)
    if resultado.status != "success":
        LOGGER.error("Daily execution failed: %s", "; ".join(resultado.errores))
        sys.exit(1)
    LOGGER.info("Finished daily execution fecha=%s status=success", fecha)


if __name__ == "__main__":
    main()
