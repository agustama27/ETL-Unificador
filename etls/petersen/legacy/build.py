from __future__ import annotations

import subprocess
import sys


def main() -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",
            "--console",
            "--name",
            "petersen_resultados",
            "main.py",
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
