from pathlib import Path
from typing import Callable

from core.modelos import ArchivosDia, ConfigDia, ResultadoDia
from procesos.base_generator import procesar_base
from procesos.phone_extractor import extraer_telefonos


def procesar_dia(
    config: ConfigDia,
    archivos: ArchivosDia,
    log_cb: Callable[[str], None] | None = None,
    modo_ejecucion: str = "ui",
) -> ResultadoDia:
    def log(line: str) -> None:
        if log_cb:
            log_cb(line)

    try:
        config.output_dir.mkdir(parents=True, exist_ok=True)
        config.logs_dir.mkdir(parents=True, exist_ok=True)
        config.procesados_dir.mkdir(parents=True, exist_ok=True)

        log("Paso 1/2: Generando base procesada...")
        if archivos.usar_base_reciente:
            base_path = procesar_base(output_dir=config.output_dir)
        else:
            if archivos.base_entrada is None:
                raise ValueError("Debe indicar archivo base de entrada para modo manual")
            base_path = procesar_base(archivos.base_entrada, output_dir=config.output_dir)
        log(f"Base generada: {base_path}")

        log("Paso 2/2: Extrayendo telefonos...")
        tel_path = extraer_telefonos(base_path, output_dir=config.output_dir)
        log(f"Telefonos generados: {tel_path}")

        return ResultadoDia(
            status="ok",
            output_base=Path(base_path),
            output_telefonos=Path(tel_path),
            rows_entrada=0,
            rows_salida=0,
            modo_ejecucion=modo_ejecucion,
        )
    except Exception as exc:
        log(f"Error: {exc}")
        return ResultadoDia(status="error", errores=[str(exc)], modo_ejecucion=modo_ejecucion)
