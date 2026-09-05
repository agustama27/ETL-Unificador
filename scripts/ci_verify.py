"""Corre la suite en CI y falla si aparece un skip que no esperabamos.

Por que existe: en CI la suite de paridad contra los upstream se saltea, porque los
repositorios de los clientes viven en un Escritorio y no en el runner. Ese skip es
legitimo. El problema es que un skip legitimo hace que el resto se vuelva invisible:
si manana falta una dependencia opcional, pytest dice "passed" y suma un skip mas
que nadie mira.

Eso ya paso. Hasta la adopcion de uv, `xlwt` y `reportlab` estaban instalados en el
entorno de desarrollo pero no declarados: en una maquina limpia, la paridad de
Alvarez se salteaba en silencio y nunca habia corrido ahi.

Este script permite exactamente los skips esperados y falla con cualquier otro.
"""

from __future__ import annotations

import re
import subprocess
import sys

# Unico motivo de skip aceptable en CI: el runner no tiene los repos upstream.
# Cualquier otro es entorno roto y tiene que romper el build.
MOTIVOS_ESPERADOS = (
    "repo upstream ausente",
    "helm no esta en el PATH",
)

LINEA_SKIP = re.compile(r"^SKIPPED \[(\d+)\] (.+?): (.+)$", re.MULTILINE)


def skips(salida: str) -> list[tuple[str, str, str]]:
    """Los skips que reporta pytest con `-rs`, como (cantidad, ubicacion, motivo)."""
    return LINEA_SKIP.findall(salida)


def skips_inesperados(salida: str) -> list[tuple[str, str, str]]:
    """Los que no coinciden con ningun motivo esperado. Si hay alguno, el build rompe."""
    return [s for s in skips(salida)
            if not any(esperado in s[2] for esperado in MOTIVOS_ESPERADOS)]


def main() -> int:
    proceso = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-rs"],
        capture_output=True, text=True, check=False)
    salida = proceso.stdout + proceso.stderr
    print(salida)

    if proceso.returncode != 0:
        print("ci:verify — la suite fallo.", file=sys.stderr)
        return proceso.returncode

    inesperados = skips_inesperados(salida)
    if inesperados:
        print("\nci:verify — SKIPS INESPERADOS. Un skip no es un pase.", file=sys.stderr)
        for cantidad, ubicacion, motivo in inesperados:
            print(f"  [{cantidad}] {ubicacion}: {motivo}", file=sys.stderr)
        print("\nSi falta una dependencia, declarala en pyproject.toml y corre `task sync`.\n"
              "Si el skip es legitimo y permanente, agregalo a MOTIVOS_ESPERADOS con el "
              "motivo escrito.", file=sys.stderr)
        return 1

    esperados = skips(salida)
    print(f"\nci:verify — OK. Skips esperados: {len(esperados)}.")
    for cantidad, ubicacion, motivo in esperados:
        print(f"  [{cantidad}] {ubicacion}: {motivo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
