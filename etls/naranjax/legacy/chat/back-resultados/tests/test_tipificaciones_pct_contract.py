"""Integration and contract tests for tipificaciones PCT ETL."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import uuid
import csv
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACK_RESULTADOS_DIR = REPO_ROOT / "back-resultados"
ENTRYPOINT = BACK_RESULTADOS_DIR / "etl_tipificaciones_ia_voz_pct.py"
FIXTURES_DIR = Path(__file__).parent / "fixtures"

sys.path.insert(0, str(BACK_RESULTADOS_DIR))

from back_resultados_etl.constants import OBSERVACIONES_MAX_CHARS  # noqa: E402


class TipificacionesPCTContractTests(unittest.TestCase):
    """Validate output contract and failure behavior."""

    def test_output_tiene_header_y_7_columnas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run = subprocess.run(
                [
                    sys.executable,
                    str(ENTRYPOINT),
                    "--input",
                    str(FIXTURES_DIR / "historial_todos_tipos.csv"),
                    "--output_dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=f"stderr:\n{run.stderr}\nstdout:\n{run.stdout}")

            generated_files = sorted(Path(tmpdir).glob("NARANJAX_PCT_*.csv"))
            self.assertEqual(len(generated_files), 1)
            self.assertRegex(generated_files[0].name, r"^NARANJAX_PCT_\d{8}\.csv$")

            payload = generated_files[0].read_bytes()
            self.assertFalse(payload.startswith(b"\xef\xbb\xbf"))
            self.assertNotIn(b"\r\n", payload)
            self.assertIn(b"|", payload)

            lines = generated_files[0].read_text(encoding="cp1252").splitlines()
            self.assertEqual(
                lines[0],
                "DNI|TIPIFICACION|NROPRODUCTO|FECHA_PROMESA|MONTO_PROMESA|CALL_REFID|OBSERVACIONES",
            )
            for line in lines[1:]:
                self.assertEqual(len(line.split("|")), 7)
                self.assertNotIn('"', line)

    def test_dni_call_refid_y_fecha_reformateada(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run = subprocess.run(
                [
                    sys.executable,
                    str(ENTRYPOINT),
                    "--input",
                    str(FIXTURES_DIR / "historial_minimo.csv"),
                    "--output_dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0)
            generated_file = sorted(Path(tmpdir).glob("NARANJAX_PCT_*.csv"))[0]
            lines = generated_file.read_text(encoding="cp1252").splitlines()
            row = lines[1].split("|")
            self.assertEqual(row[0], "DU32204249")
            self.assertEqual(row[3], "20260502")
            self.assertEqual(row[5], "call_108c246ea49501d60a04a6ff9e9")

    def test_missing_required_columns_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run = subprocess.run(
                [
                    sys.executable,
                    str(ENTRYPOINT),
                    "--input",
                    str(FIXTURES_DIR / "historial_missing_cols.csv"),
                    "--output_dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(run.returncode, 0)
            self.assertRegex(run.stderr, r"Missing required source columns")
            self.assertEqual(list(Path(tmpdir).glob("NARANJAX_PCT_*.csv")), [])

    def test_input_con_id_dni_como_alias_id_cliente(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run = subprocess.run(
                [
                    sys.executable,
                    str(ENTRYPOINT),
                    "--input",
                    str(FIXTURES_DIR / "historial_id_dni_alias.csv"),
                    "--output_dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=f"stderr:\n{run.stderr}\nstdout:\n{run.stdout}")
            generated_file = sorted(Path(tmpdir).glob("NARANJAX_PCT_*.csv"))[0]
            lines = generated_file.read_text(encoding="cp1252").splitlines()
            row = lines[1].split("|")
            self.assertEqual(row[0], "22057826")
            self.assertEqual(row[1], "12")

    def test_dni_preserva_representacion_exacta_desde_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run = subprocess.run(
                [
                    sys.executable,
                    str(ENTRYPOINT),
                    "--input",
                    str(FIXTURES_DIR / "historial_dni_preserve_exact.csv"),
                    "--output_dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=f"stderr:\n{run.stderr}\nstdout:\n{run.stdout}")

            generated_file = sorted(Path(tmpdir).glob("NARANJAX_PCT_*.csv"))[0]
            with generated_file.open("r", encoding="cp1252", newline="") as fh:
                reader = csv.DictReader(fh, delimiter="|")
                first_row = next(reader)

            self.assertEqual(first_row["DNI"], "  DU 32.204.249  ")

    def test_observaciones_truncadas_y_omitidos(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run = subprocess.run(
                [
                    sys.executable,
                    str(ENTRYPOINT),
                    "--input",
                    str(FIXTURES_DIR / "historial_observability.csv"),
                    "--output_dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=f"stderr:\n{run.stderr}\nstdout:\n{run.stdout}")

            generated_files = sorted(Path(tmpdir).glob("NARANJAX_PCT_*.csv"))
            self.assertEqual(len(generated_files), 1)

            lines = generated_files[0].read_text(encoding="cp1252").splitlines()
            self.assertEqual(len(lines), 2)
            self.assertLessEqual(len(lines[1].split("|", 6)[6]), OBSERVACIONES_MAX_CHARS)

            self.assertRegex(run.stderr, r"total_input_rows=3")
            self.assertRegex(run.stderr, r"total_output_rows=1")
            self.assertRegex(run.stderr, r"omitted_rows_total=2")
            self.assertRegex(run.stderr, r"warning_count=2")
            self.assertRegex(run.stderr, r"'missing_dni': 1")
            self.assertRegex(run.stderr, r"'unmapped_tipificacion': 1")

    def test_prioriza_columnas_roman23_para_dni_y_observaciones(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            run = subprocess.run(
                [
                    sys.executable,
                    str(ENTRYPOINT),
                    "--input",
                    str(FIXTURES_DIR / "historial_roman23_priority.csv"),
                    "--output_dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=f"stderr:\n{run.stderr}\nstdout:\n{run.stdout}")

            generated_file = sorted(Path(tmpdir).glob("NARANJAX_PCT_*.csv"))[0]
            with generated_file.open("r", encoding="cp1252", newline="") as fh:
                reader = csv.DictReader(fh, delimiter="|")
                row = next(reader)

            self.assertEqual(row["DNI"], "DU00020240118")
            self.assertEqual(row["TIPIFICACION"], "11")
            self.assertEqual(row["NROPRODUCTO"], "DU00020240118")
            self.assertEqual(row["CALL_REFID"], "call_434f431c28a9544d5f2c5dc6bc6")
            self.assertEqual(
                row["OBSERVACIONES"],
                "Observacion desde columna lowercase Roman 23",
            )

    def test_observaciones_reemplaza_pipe_backslash_y_doble_comilla_doble(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "input_obs_sanitize.csv"
            input_path.write_text(
                "\n".join(
                    [
                        "[Salida] Tipificaciones,[Entrada] id_cliente,[Entrada] id_nro_producto,[Salida] fecha_compromiso_tc,[Salida] monto_compromiso,[Entrada] call_id,call_refid,[Salida] observaciones",
                        'Promesa de pago,22057826,22057826,02/05/26,1234,call_test,call_test_ref,"texto|con\\barra""""doble"',
                    ]
                ),
                encoding="utf-8",
            )

            run = subprocess.run(
                [
                    sys.executable,
                    str(ENTRYPOINT),
                    "--input",
                    str(input_path),
                    "--output_dir",
                    tmpdir,
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(run.returncode, 0, msg=f"stderr:\n{run.stderr}\nstdout:\n{run.stdout}")

            generated_file = sorted(Path(tmpdir).glob("NARANJAX_PCT_*.csv"))[0]
            with generated_file.open("r", encoding="cp1252", newline="") as fh:
                reader = csv.DictReader(fh, delimiter="|")
                row = next(reader)

            self.assertNotIn("|", row["OBSERVACIONES"])
            self.assertNotIn("\\", row["OBSERVACIONES"])
            self.assertNotIn('""', row["OBSERVACIONES"])
            self.assertEqual(row["OBSERVACIONES"], "texto con barra doble")
            self.assertLessEqual(len(row["OBSERVACIONES"]), OBSERVACIONES_MAX_CHARS)

    def test_default_input_desde_roman_si_no_hay_input_explicito(self) -> None:
        roman_dir = BACK_RESULTADOS_DIR / "roman"
        roman_dir.mkdir(parents=True, exist_ok=True)
        source_fixture = FIXTURES_DIR / "historial_minimo.csv"
        temp_input = roman_dir / f"test_default_input_{uuid.uuid4().hex}.csv"

        try:
            temp_input.write_text(source_fixture.read_text(encoding="utf-8"), encoding="utf-8")

            with tempfile.TemporaryDirectory() as tmpdir:
                run = subprocess.run(
                    [
                        sys.executable,
                        str(ENTRYPOINT),
                        "--output_dir",
                        tmpdir,
                    ],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(run.returncode, 0, msg=f"stderr:\n{run.stderr}\nstdout:\n{run.stdout}")
                generated_files = sorted(Path(tmpdir).glob("NARANJAX_PCT_*.csv"))
                self.assertEqual(len(generated_files), 1)
        finally:
            if temp_input.exists():
                temp_input.unlink()


if __name__ == "__main__":
    unittest.main()
