import sys


def main() -> int:
    if "--cli" in sys.argv[1:]:
        argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a != "--cli"]
        from cli.main import run_cli

        return run_cli(argv)

    from ui.app import run_ui

    return run_ui()


if __name__ == "__main__":
    raise SystemExit(main())
