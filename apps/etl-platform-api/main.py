"""Entrypoint del servicio etl-platform-api.

Inserta las raíces de ``apps/`` y del workspace en ``sys.path`` antes de importar,
para que los paquetes conserven su nombre de import de primer nivel: los 25
``manifest.yaml`` declaran el adapter como string (``etl_core.contracts:...``) y se
resuelve en runtime, así que el nombre del paquete es contrato de cliente.

Uso:
    python main.py --config ../../config/local.json
"""

import argparse
import sys
from pathlib import Path

_AQUI = Path(__file__).resolve().parent
_RAIZ = _AQUI.parent.parent
for _root in (_AQUI, _RAIZ / "apps" / "commons", _RAIZ):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from config_loader import cargar, sembrar_entorno  # noqa: E402 - despues del sys.path


def main() -> int:
    parser = argparse.ArgumentParser(description="ETL Unificador — API de consola")
    parser.add_argument("--config", type=Path, default=None,
                        help="JSON de configuración (ver config/). El entorno tiene prioridad.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    argumentos = parser.parse_args()

    if argumentos.config is not None:
        sembradas = sembrar_entorno(cargar(argumentos.config))
        print(f"[config] {argumentos.config}: {len(sembradas)} variables sembradas "
              f"({', '.join(sembradas) or 'ninguna'}); el resto vino del entorno")

    import uvicorn  # noqa: PLC0415 - despues de sembrar el entorno

    uvicorn.run("platform_api.main:create_app", factory=True,
                host=argumentos.host, port=argumentos.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
