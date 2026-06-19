from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox


WINDOW_TITLE = "Flujo Luz"


def _configure_back_resultados_path() -> None:
    source_root = Path(__file__).resolve().parent.parent
    back_resultados = source_root / "back-resultados"

    if back_resultados.exists():
        back_resultados_str = str(back_resultados)
        if back_resultados_str not in sys.path:
            sys.path.insert(0, back_resultados_str)


_configure_back_resultados_path()

from app.processor import LuzProcessResult, process_luz_files


def resolve_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def run_ui(smoke_mode: bool = False) -> None:
    project_root = resolve_base_dir()
    output_root = project_root / "salidas"

    selected_roman: list[str] = []
    selected_logcall: list[str] = []

    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.geometry("660x390")
    root.resizable(False, False)

    frame = tk.Frame(root, padx=18, pady=18)
    frame.pack(fill="both", expand=True)

    title = tk.Label(frame, text="Consolidador Luz", font=("Segoe UI", 14, "bold"))
    title.pack(anchor="w", pady=(0, 8))

    description = tk.Label(
        frame,
        text=(
            "Selecciona uno o varios CSV Roman y Logcall. "
            "La salida se guarda junto al ejecutable en salidas/DD-MM-YYYY/corrida_..."
        ),
        justify="left",
        wraplength=620,
    )
    description.pack(anchor="w", pady=(0, 12))

    roman_var = tk.StringVar(value="Roman: 0 archivos seleccionados")
    logcall_var = tk.StringVar(value="Logcall: 0 archivos seleccionados")
    status_var = tk.StringVar(value="Listo para procesar.")

    def refresh_labels() -> None:
        roman_var.set(f"Roman: {len(selected_roman)} archivos seleccionados")
        logcall_var.set(f"Logcall: {len(selected_logcall)} archivos seleccionados")
        process_button.configure(state=tk.NORMAL if selected_roman and selected_logcall else tk.DISABLED)

    def select_roman_files() -> None:
        files = filedialog.askopenfilenames(
            title="Seleccionar CSV Roman",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if files:
            selected_roman.clear()
            selected_roman.extend(files)
            refresh_labels()

    def select_logcall_files() -> None:
        files = filedialog.askopenfilenames(
            title="Seleccionar CSV Logcall",
            filetypes=[("Archivos CSV", "*.csv"), ("Todos los archivos", "*.*")],
        )
        if files:
            selected_logcall.clear()
            selected_logcall.extend(files)
            refresh_labels()

    def process_selection() -> None:
        try:
            result = process_luz_files(selected_roman, selected_logcall, output_root)
            status_var.set("Procesamiento finalizado correctamente.")
            messagebox.showinfo("Proceso finalizado", _build_success_message(result))
        except Exception as error:
            status_var.set("Error en el procesamiento.")
            messagebox.showerror("Error", str(error))

    roman_button = tk.Button(
        frame,
        text="Seleccionar CSV Roman",
        command=select_roman_files,
        width=28,
        height=2,
    )
    roman_button.pack(anchor="w")

    roman_label = tk.Label(frame, textvariable=roman_var)
    roman_label.pack(anchor="w", pady=(6, 12))

    logcall_button = tk.Button(
        frame,
        text="Seleccionar CSV Logcall",
        command=select_logcall_files,
        width=28,
        height=2,
    )
    logcall_button.pack(anchor="w")

    logcall_label = tk.Label(frame, textvariable=logcall_var)
    logcall_label.pack(anchor="w", pady=(6, 12))

    process_button = tk.Button(
        frame,
        text="Procesar",
        command=process_selection,
        width=28,
        height=2,
        state=tk.DISABLED,
    )
    process_button.pack(anchor="w")

    status_label = tk.Label(frame, textvariable=status_var, fg="#1f3b4d")
    status_label.pack(anchor="w", pady=(12, 0))

    if smoke_mode:
        root.after(300, root.destroy)

    root.mainloop()


def _build_success_message(result: LuzProcessResult) -> str:
    summary = result.summary
    return (
        "Consolidacion completada correctamente.\n\n"
        f"Corrida: {result.run_root}\n"
        f"Excel: {result.output_excel_path}\n"
        f"Log: {result.log_file_path}\n"
        f"Roman (conectados): {summary.get('roman_rows', 0)}\n"
        f"Logcall total: {summary.get('logcall_rows', 0)}\n"
        f"Logcall RESULT=10: {summary.get('logcall_connected_result_10', 0)}\n"
        f"Logcall RESULT!=10: {summary.get('logcall_non_connected_rows', 0)}\n"
        f"Total output Excel: {result.total_output_rows}"
    )


def run_cli(roman_files: list[str], logcall_files: list[str]) -> int:
    project_root = resolve_base_dir()
    output_root = project_root / "salidas"

    result = process_luz_files(roman_files, logcall_files, output_root)

    print("[OK] Flujo luz procesado")
    print(f"- Corrida: {result.run_root}")
    print(f"- Excel: {result.output_excel_path}")
    print(f"- Log: {result.log_file_path}")
    print(f"- Roman seleccionados: {len(result.roman_copied_files)}")
    print(f"- Logcall seleccionados: {len(result.logcall_copied_files)}")
    print(f"- Filas output: {result.total_output_rows}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="UI y CLI para flujo luz")
    parser.add_argument(
        "--roman-files",
        nargs="+",
        help="Lista de archivos CSV Roman para procesar por CLI",
    )
    parser.add_argument(
        "--logcall-files",
        nargs="+",
        help="Lista de archivos CSV Logcall para procesar por CLI",
    )
    parser.add_argument(
        "--smoke-ui",
        action="store_true",
        help="Abre y cierra la UI automaticamente para smoke test",
    )

    args = parser.parse_args()

    if args.roman_files or args.logcall_files:
        if not args.roman_files or not args.logcall_files:
            raise ValueError("Para modo CLI se requieren ambos argumentos: --roman-files y --logcall-files")
        return run_cli(args.roman_files, args.logcall_files)

    run_ui(smoke_mode=args.smoke_ui)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
