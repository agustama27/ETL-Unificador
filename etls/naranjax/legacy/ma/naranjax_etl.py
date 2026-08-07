from __future__ import annotations

import sys


def main() -> int:
    if "--cli" in sys.argv[1:]:
        argv = [sys.argv[0]] + [arg for arg in sys.argv[1:] if arg != "--cli"]
        from cli.main import run_cli

        return run_cli(argv)

    from ui.app import run_ui

    return run_ui()


if __name__ == "__main__":
    raise SystemExit(main())
