from __future__ import annotations

from procesos.base_generator import generate_base


def main() -> int:
    try:
        output_file = generate_base()
        print(f"Procesamiento finalizado. Archivo generado: {output_file}")
        return 0
    except Exception as exc:
        print(f"Error al ejecutar el procesamiento: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
