"""Unifier-owned CLI for the Petersen gestiones ETL.

The legacy ``main()`` anchors every folder to ``get_project_root()`` (the
``procesos.paths`` module ``__file__``). This wrapper repoints that seam at a
sandbox work root, stages the ROMAN CSV plus the optional approach/base/
excluidos inputs into the legacy folder layout, runs the exact legacy
``main()`` fail-fast, and publishes the final ZIP into ``output/``.
"""

import argparse
import shutil
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Petersen gestiones (unified)")
    parser.add_argument("--input", required=True, help="ROMAN export CSV")
    parser.add_argument("--output_dir", required=True, help="Sandbox output directory")
    parser.add_argument("--approach", default=None, help="Optional approach CSV")
    parser.add_argument("--clientes", default=None, help="Optional client base CSV")
    parser.add_argument("--excluidos", default=None, help="Optional excluded clients CSV")
    arguments = parser.parse_args()

    sys.path.insert(0, str(Path.cwd()))
    import procesos.paths as paths

    output_dir = Path(arguments.output_dir)
    work = output_dir.parent / "legacy"
    (work / "procesos").mkdir(parents=True, exist_ok=True)
    (work / "roman").mkdir(parents=True, exist_ok=True)
    shutil.copy2(arguments.input, work / "roman" / "roman.csv")
    for value, folder, name in (
        (arguments.approach, "approach", "approach.csv"),
        (arguments.clientes, "base", "base.csv"),
        (arguments.excluidos, "datos-excluidos", "excluidos.csv"),
    ):
        if value is not None:
            (work / folder).mkdir(parents=True, exist_ok=True)
            shutil.copy2(value, work / folder / name)

    paths.__file__ = str(work / "procesos" / "paths.py")
    import main as legacy

    try:
        legacy.main()
    except Exception as error:  # noqa: BLE001 - fail-fast boundary
        print(f"Error: {error}", file=sys.stderr)
        return 1

    zips = sorted(work.glob("Gestiones_Petersen_*.zip"))
    if not zips:
        print("Error: no se genero el ZIP de gestiones", file=sys.stderr)
        return 1
    shutil.copy2(zips[-1], output_dir / zips[-1].name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
