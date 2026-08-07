from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

from app.processor import process_base_file


WINDOW_TITLE = "Generacion Base"
SELECT_BUTTON_TEXT = "Seleccionar base a procesar"


def resolve_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def run_ui() -> None:
    project_root = resolve_base_dir()
    output_root = project_root / "salidas"

    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.geometry("520x220")
    root.resizable(False, False)

    frame = tk.Frame(root, padx=18, pady=18)
    frame.pack(fill="both", expand=True)

    title = tk.Label(frame, text="Generador de Base", font=("Segoe UI", 14, "bold"))
    title.pack(anchor="w", pady=(0, 8))

    description = tk.Label(
        frame,
        text="Selecciona un archivo CSV o Excel para procesarlo y guardar la salida por fecha.",
        justify="left",
    )
    description.pack(anchor="w", pady=(0, 12))

    status_var = tk.StringVar(value="Listo para procesar.")

    def on_select_and_process() -> None:
        selected_path = filedialog.askopenfilename(
            title="Seleccionar base a procesar",
            filetypes=[
                ("Archivos de base", "*.csv *.xlsx *.xls"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if not selected_path:
            return

        try:
            result = process_base_file(selected_path, output_root)
            status_var.set(f"Procesado: {result.source_path.name}")
            messagebox.showinfo(
                "Proceso finalizado",
                "Base procesada correctamente.\n\n"
                f"Base Recibida: {result.copied_input_path}\n"
                f"Base Generada (EPEC_ROMAN): {result.generated_base_path}\n"
                f"Base Generada (EPEC_E1KIA): {result.generated_phones_path}",
            )
        except Exception as error:
            status_var.set("Error en el procesamiento.")
            messagebox.showerror("Error", str(error))

    process_button = tk.Button(
        frame,
        text=SELECT_BUTTON_TEXT,
        command=on_select_and_process,
        width=32,
        height=2,
    )
    process_button.pack(anchor="w")

    status_label = tk.Label(frame, textvariable=status_var, fg="#1f3b4d")
    status_label.pack(anchor="w", pady=(12, 0))

    root.mainloop()


def run_cli(source_file: str) -> int:
    project_root = resolve_base_dir()
    output_root = project_root / "salidas"

    result = process_base_file(source_file, output_root)
    print("[OK] Archivo procesado")
    print(f"- Entrada: {result.source_path}")
    print(f"- Copia: {result.copied_input_path}")
    print(f"- Salida EPEC_ROMAN: {result.generated_base_path}")
    print(f"- Salida EPEC_E1KIA: {result.generated_phones_path}")
    print(f"- Filas: {result.rows}")
    print(f"- Columnas: {result.columns}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="UI simple para generacion de base por fecha")
    parser.add_argument(
        "--process-file",
        dest="process_file",
        help="Procesa un archivo directo por CLI (sin abrir UI)",
    )
    args = parser.parse_args()

    if args.process_file:
        return run_cli(args.process_file)

    run_ui()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
