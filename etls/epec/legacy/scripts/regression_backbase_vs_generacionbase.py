from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEFAULT_CANONICAL_INPUT = Path("back-base/base-recibida/input_1_luz_16_04_26 (2).xlsx")
BASE_FILE_LABEL = "base_epec"
PHONES_FILE_LABEL = "telefonos_epec"


@dataclass
class ProcessingOutputs:
    base_csv: Path
    phones_csv: Path
    source_input: Path | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compara outputs de back-base vs generacionBase-exe para el mismo input canonico."
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Raiz del workspace (default: carpeta raiz del repo).",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_CANONICAL_INPUT,
        help="Input canonico a usar cuando se ejecuta el procesamiento.",
    )
    parser.add_argument(
        "--back-base-base-csv",
        type=Path,
        help="Ruta a base_epec de back-base para reutilizar output existente.",
    )
    parser.add_argument(
        "--back-base-phones-csv",
        type=Path,
        help="Ruta a telefonos_epec de back-base para reutilizar output existente.",
    )
    parser.add_argument(
        "--gen-base-csv",
        type=Path,
        help="Ruta a base_epec de generacionBase-exe para reutilizar output existente.",
    )
    parser.add_argument(
        "--gen-phones-csv",
        type=Path,
        help="Ruta a telefonos_epec de generacionBase-exe para reutilizar output existente.",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="No borrar carpeta temporal de ejecucion (debug).",
    )
    return parser.parse_args()


def _resolve_path(base: Path, value: Path | None) -> Path | None:
    if value is None:
        return None
    return value if value.is_absolute() else (base / value)


def _normalize_column_name(value: object) -> str:
    return str(value).replace("\ufeff", "").strip()


def _normalize_cell(value: object) -> str:
    normalized = str(value)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()


def _load_and_normalize_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        sep=";",
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        encoding="utf-8-sig",
    )

    normalized_columns = [_normalize_column_name(col) for col in df.columns]
    if len(normalized_columns) != len(set(normalized_columns)):
        raise ValueError(f"Columnas duplicadas tras normalizar en {path}")

    df.columns = normalized_columns
    for col in df.columns:
        df[col] = df[col].map(_normalize_cell)
    return df


def _counter_from_df(df: pd.DataFrame, columns: list[str]) -> Counter[tuple[str, ...]]:
    ordered = df[columns]
    return Counter(ordered.itertuples(index=False, name=None))


def _row_preview(columns: list[str], row: tuple[str, ...], limit: int = 4) -> str:
    parts = []
    for col, value in zip(columns, row):
        if value:
            parts.append(f"{col}={value}")
        if len(parts) >= limit:
            break
    if not parts:
        parts = [f"{columns[0]}={row[0]}" if columns else "(fila vacia)"]
    return " | ".join(parts)


def _describe_counter_delta(
    label: str,
    columns: list[str],
    delta: Counter[tuple[str, ...]],
    max_samples: int = 5,
) -> list[str]:
    if not delta:
        return []
    lines = [f"  - {label}: {sum(delta.values())} fila(s)"]
    for row, count in sorted(delta.items(), key=lambda item: item[0])[:max_samples]:
        lines.append(f"    * x{count}: {_row_preview(columns, row)}")
    return lines


def compare_csv_pair(name: str, back_csv: Path, gen_csv: Path) -> tuple[bool, list[str]]:
    notes: list[str] = []

    back_df = _load_and_normalize_csv(back_csv)
    gen_df = _load_and_normalize_csv(gen_csv)

    back_cols = list(back_df.columns)
    gen_cols = list(gen_df.columns)
    back_set = set(back_cols)
    gen_set = set(gen_cols)

    ok = True
    if back_set != gen_set:
        ok = False
        missing_in_gen = sorted(back_set - gen_set)
        missing_in_back = sorted(gen_set - back_set)
        if missing_in_gen:
            notes.append(f"- {name}: faltan en generacionBase-exe -> {missing_in_gen}")
        if missing_in_back:
            notes.append(f"- {name}: faltan en back-base -> {missing_in_back}")

    if len(back_df) != len(gen_df):
        ok = False
        notes.append(f"- {name}: cantidad de filas distinta (back-base={len(back_df)}, generacionBase-exe={len(gen_df)})")

    if back_set == gen_set:
        canonical_columns = sorted(back_set)
        only_back = _counter_from_df(back_df, canonical_columns) - _counter_from_df(gen_df, canonical_columns)
        only_gen = _counter_from_df(gen_df, canonical_columns) - _counter_from_df(back_df, canonical_columns)
        if only_back or only_gen:
            ok = False
            notes.append(f"- {name}: contenido distinto tras normalizacion deterministica")
            notes.extend(_describe_counter_delta("Solo en back-base", canonical_columns, only_back))
            notes.extend(_describe_counter_delta("Solo en generacionBase-exe", canonical_columns, only_gen))

    if ok:
        notes.append(f"- {name}: OK (columnas={len(back_set)}, filas={len(back_df)}, contenido equivalente)")

    return ok, notes


def _load_back_base_module(back_base_dir: Path):
    module_path = back_base_dir / "procesos" / "base_generator.py"
    spec = importlib.util.spec_from_file_location("back_base_generator", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"No se pudo cargar modulo back-base en {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_back_base(back_base_dir: Path, source_input: Path, temp_root: Path) -> ProcessingOutputs:
    module = _load_back_base_module(back_base_dir)
    run_root = temp_root / "back-base"
    input_dir = run_root / "base-recibida"
    input_dir.mkdir(parents=True, exist_ok=True)

    copied_input = input_dir / source_input.name
    shutil.copy2(source_input, copied_input)

    dataframe = module.combinar_archivos(run_root)
    base_csv = module.guardar_csv_consolidado(dataframe, run_root)
    phones_csv = module.generar_csv_telefonos(dataframe, run_root)

    return ProcessingOutputs(base_csv=Path(base_csv), phones_csv=Path(phones_csv), source_input=copied_input)


def run_generacion_base_exe(gen_dir: Path, source_input: Path, temp_root: Path) -> ProcessingOutputs:
    if str(gen_dir) not in sys.path:
        sys.path.insert(0, str(gen_dir))

    from app.processor import process_base_file  # pylint: disable=import-outside-toplevel

    output_root = temp_root / "generacionBase-exe" / "salidas"
    result = process_base_file(source_input, output_root)
    return ProcessingOutputs(
        base_csv=result.generated_base_path,
        phones_csv=result.generated_phones_path,
        source_input=result.source_path,
    )


def main() -> int:
    args = parse_args()
    workspace_root = args.workspace_root.resolve()
    input_path = _resolve_path(workspace_root, args.input)
    if input_path is None:
        raise ValueError("Debe especificarse --input")

    back_base_dir = workspace_root / "back-base"
    gen_dir = workspace_root / "generacionBase-exe"

    if not back_base_dir.exists():
        raise FileNotFoundError(f"No existe back-base en {back_base_dir}")
    if not gen_dir.exists():
        raise FileNotFoundError(f"No existe generacionBase-exe en {gen_dir}")

    back_reuse_base = _resolve_path(workspace_root, args.back_base_base_csv)
    back_reuse_phones = _resolve_path(workspace_root, args.back_base_phones_csv)
    gen_reuse_base = _resolve_path(workspace_root, args.gen_base_csv)
    gen_reuse_phones = _resolve_path(workspace_root, args.gen_phones_csv)

    temp_dir_obj = tempfile.TemporaryDirectory(prefix="regresion_backbase_vs_genbase_")
    temp_root = Path(temp_dir_obj.name)

    try:
        if back_reuse_base and back_reuse_phones:
            back_outputs = ProcessingOutputs(base_csv=back_reuse_base, phones_csv=back_reuse_phones)
            back_mode = "reutilizado"
        else:
            if not input_path.exists():
                raise FileNotFoundError(
                    "Input canonico no encontrado. Pase --input o rutas --back-base-*-csv/--gen-*-csv para reutilizar outputs."
                )
            back_outputs = run_back_base(back_base_dir, input_path, temp_root)
            back_mode = "ejecutado"

        if gen_reuse_base and gen_reuse_phones:
            gen_outputs = ProcessingOutputs(base_csv=gen_reuse_base, phones_csv=gen_reuse_phones)
            gen_mode = "reutilizado"
        else:
            if not input_path.exists():
                raise FileNotFoundError(
                    "Input canonico no encontrado. Pase --input o rutas --back-base-*-csv/--gen-*-csv para reutilizar outputs."
                )
            gen_outputs = run_generacion_base_exe(gen_dir, input_path, temp_root)
            gen_mode = "ejecutado"

        for path in (
            back_outputs.base_csv,
            back_outputs.phones_csv,
            gen_outputs.base_csv,
            gen_outputs.phones_csv,
        ):
            if not path.exists():
                raise FileNotFoundError(f"Output no encontrado: {path}")

        print("=== Regresion back-base vs generacionBase-exe ===")
        print(f"Workspace: {workspace_root}")
        print(f"Input: {input_path if input_path.exists() else '(n/a - modo reutilizado)'}")
        print(f"back-base: {back_mode}")
        print(f"  - {BASE_FILE_LABEL}: {back_outputs.base_csv}")
        print(f"  - {PHONES_FILE_LABEL}: {back_outputs.phones_csv}")
        print(f"generacionBase-exe: {gen_mode}")
        print(f"  - {BASE_FILE_LABEL}: {gen_outputs.base_csv}")
        print(f"  - {PHONES_FILE_LABEL}: {gen_outputs.phones_csv}")

        all_ok = True
        reports: list[str] = []

        base_ok, base_notes = compare_csv_pair(BASE_FILE_LABEL, back_outputs.base_csv, gen_outputs.base_csv)
        phone_ok, phone_notes = compare_csv_pair(PHONES_FILE_LABEL, back_outputs.phones_csv, gen_outputs.phones_csv)
        all_ok = base_ok and phone_ok
        reports.extend(base_notes)
        reports.extend(phone_notes)

        print("\nResultado:")
        for line in reports:
            print(line)

        if all_ok:
            print("\n[PASS] Regresion OK: outputs equivalentes por negocio.")
            return 0

        print("\n[FAIL] Regresion con mismatches.")
        return 1
    finally:
        if args.keep_temp:
            print(f"\n[INFO] Carpeta temporal preservada en: {temp_root}")
            temp_dir_obj = None
        if temp_dir_obj is not None:
            temp_dir_obj.cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
