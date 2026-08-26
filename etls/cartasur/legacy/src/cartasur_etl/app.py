from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--cli" in argv:
        from cartasur_etl.cli import run_cli

        return run_cli([arg for arg in argv if arg != "--cli"])
    from cartasur_etl.ui.app import run_ui

    return run_ui()


if __name__ == "__main__":
    raise SystemExit(main())
