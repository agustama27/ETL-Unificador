"""CLI puente al legacy — completar sólo si el legacy no tiene CLI usable.

Contrato: recibe ``--input`` y ``--output_dir`` apuntando al sandbox, importa las
funciones del legacy (cwd = ``legacy/``), las ejecuta en cadena **fail-fast** y copia
los productos a ``output/``. Referencia limpia: ``etls/petersen/job.py``. No copiar el
monkeypatch de ``__file__`` de ``etls/bancor/job.py``.
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Cliente proceso (unified)")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output_dir", required=True)
    arguments = parser.parse_args()

    sys.path.insert(0, str(Path.cwd()))
    # from procesos.mi_modulo import procesar   # importa el legacy acá

    try:
        raise NotImplementedError("completar la cadena del legacy")
    except Exception as error:  # noqa: BLE001 - frontera fail-fast documentada
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
