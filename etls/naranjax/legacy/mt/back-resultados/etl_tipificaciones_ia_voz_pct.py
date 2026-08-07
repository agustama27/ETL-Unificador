from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.modelos import ConfigTipificaciones  # noqa: E402
from core.procesar_tipificaciones import procesar_tipificaciones, resolve_tipificaciones_input_path  # noqa: E402


LOGGER = logging.getLogger("back_resultados_cli")


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL Tipificaciones IA Voz a formato PCT")
    parser.add_argument("--input", type=Path, default=None)
    parser.add_argument("--output_dir", type=Path, default=Path("back-resultados/base-generada"))
    parser.add_argument("--log_level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, str(args.log_level).upper(), logging.INFO))

    try:
        resolved = resolve_tipificaciones_input_path(args.input)
        result = procesar_tipificaciones(resolved, ConfigTipificaciones(output_dir=args.output_dir))
        if result.status != "success":
            LOGGER.error("Proceso con error: %s", "; ".join(result.errores))
            return 1
        LOGGER.info("Output generado: %s", result.output_path)
        return 0
    except Exception:
        LOGGER.exception("Fallo en ejecución de back-resultados")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
