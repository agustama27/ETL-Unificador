from __future__ import annotations

import os
import queue
import subprocess
import sys
from datetime import date
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from cartasur_etl.config_store import SavedSettings, load_settings, save_settings
from cartasur_etl.models import EtlConfig, EtlResult, InputFiles
from cartasur_etl.runtime_paths import RuntimePathInputs, ensure_runtime_dirs, resolve_runtime_paths
from cartasur_etl.ui.worker import WorkerThread
from cartasur_etl.validators_archivos import validate_for_processing


def run_ui() -> int:
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = CartaSurApp()
    app.mainloop()
    return 0


class CartaSurApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CartaSur ETL")
        self.geometry("900x650")
        self.minsize(820, 560)
        self.events: queue.Queue = queue.Queue()
        self.worker: WorkerThread | None = None
        self.settings = load_settings()
        resolved = resolve_runtime_paths(settings=self.settings)
        ensure_runtime_dirs(resolved)

        self.input_var = ctk.StringVar(value=str(resolved.input_path or ""))
        self.output_var = ctk.StringVar(value=str(resolved.output_dir))
        self.log_dir_var = ctk.StringVar(value=str(resolved.log_dir))
        self.config_var = ctk.StringVar(value=str(resolved.config_path or ""))

        self.container = ctk.CTkFrame(self)
        self.container.pack(fill="both", expand=True, padx=20, pady=20)
        self._build_main_screen()
        self._validate_live()

    def _build_main_screen(self) -> None:
        self._clear()
        ctk.CTkLabel(self.container, text="Generación de Base CartaSur", font=("Arial", 24, "bold")).pack(anchor="w", pady=(0, 12))
        ctk.CTkLabel(self.container, text="Seleccioná la base cruda y generá los CSV dinámicos SOHO.").pack(anchor="w", pady=(0, 16))
        self._path_row("Base cruda (.xlsx/.csv)", self.input_var, self._choose_input).pack(fill="x", pady=6)
        self._path_row("Carpeta de salida", self.output_var, lambda: self._choose_dir(self.output_var)).pack(fill="x", pady=6)
        self._path_row("Carpeta de logs", self.log_dir_var, lambda: self._choose_dir(self.log_dir_var)).pack(fill="x", pady=6)
        self._path_row("YAML opcional", self.config_var, self._choose_config).pack(fill="x", pady=6)
        for var in (self.input_var, self.output_var, self.log_dir_var, self.config_var):
            var.trace_add("write", lambda *_: self._validate_live())
        self.validation_label = ctk.CTkLabel(self.container, text="", text_color="gray")
        self.validation_label.pack(anchor="w", pady=(8, 4))
        self.process_button = ctk.CTkButton(self.container, text="Procesar", command=self._process)
        self.process_button.pack(anchor="w", pady=8)
        self.progress = ctk.CTkProgressBar(self.container, mode="indeterminate")
        self.progress.pack(fill="x", pady=10)
        self.progress.stop()
        self.log_box = ctk.CTkTextbox(self.container, height=210)
        self.log_box.pack(fill="both", expand=True, pady=(8, 0))

    def _path_row(self, label: str, var: ctk.StringVar, command) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container)
        ctk.CTkLabel(frame, text=label, width=150).pack(side="left", padx=8, pady=8)
        ctk.CTkEntry(frame, textvariable=var).pack(side="left", fill="x", expand=True, padx=8, pady=8)
        ctk.CTkButton(frame, text="Buscar", width=90, command=command).pack(side="right", padx=8, pady=8)
        return frame

    def _choose_input(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("CartaSur", "*.xlsx *.xlsm *.csv"), ("Todos", "*.*")])
        if value:
            self.input_var.set(value)

    def _choose_config(self) -> None:
        value = filedialog.askopenfilename(filetypes=[("YAML", "*.yaml *.yml"), ("Todos", "*.*")])
        if value:
            self.config_var.set(value)

    def _choose_dir(self, var: ctk.StringVar) -> None:
        value = filedialog.askdirectory()
        if value:
            var.set(value)

    def _resolved(self):
        return resolve_runtime_paths(
            RuntimePathInputs(self.input_var.get(), self.output_var.get(), self.log_dir_var.get(), self.config_var.get())
        )

    def _validate_live(self) -> None:
        if not hasattr(self, "validation_label"):
            return
        result = validate_for_processing(self._resolved(), check_preconditions=False)
        text = "Listo para procesar." if result.ok else " | ".join(result.errors[:3])
        self.validation_label.configure(text=text, text_color=("green" if result.ok else "#d97706"))
        self.process_button.configure(state=("normal" if result.ok else "disabled"))

    def _process(self) -> None:
        resolved = self._resolved()
        validation = validate_for_processing(resolved, check_preconditions=True)
        if not validation.ok:
            self._append_log("No se puede procesar: " + " | ".join(validation.errors))
            self._validate_live()
            return
        save_settings(SavedSettings(str(resolved.input_path or ""), str(resolved.output_dir), str(resolved.log_dir), str(resolved.config_path or "")))
        self.process_button.configure(state="disabled")
        self.progress.start()
        self._append_log("Iniciando procesamiento...")
        config = EtlConfig(resolved.output_dir, resolved.log_dir, resolved.config_path, date.today(), False)
        self.worker = WorkerThread(config, InputFiles(resolved.input_path), self.events)  # type: ignore[arg-type]
        self.worker.start()
        self.after(100, self._drain_events)

    def _drain_events(self) -> None:
        keep_polling = True
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "log":
                self._append_log(str(payload))
            elif event == "done":
                keep_polling = False
                self.progress.stop()
                self._show_result(payload)
            elif event == "error":
                keep_polling = False
                self.progress.stop()
                self._append_log(str(payload))
                self.process_button.configure(state="normal")
        if keep_polling and self.worker and self.worker.is_alive():
            self.after(100, self._drain_events)

    def _show_result(self, result: EtlResult) -> None:
        self._clear()
        ctk.CTkLabel(self.container, text="Resultado", font=("Arial", 24, "bold")).pack(anchor="w", pady=(0, 12))
        state = "Proceso completado" if result.ok else "Proceso finalizado con errores"
        ctk.CTkLabel(self.container, text=state).pack(anchor="w", pady=4)
        ctk.CTkLabel(self.container, text=f"Registros válidos: {result.valid_records} | Incidencias: {result.issues}").pack(anchor="w", pady=4)
        if result.errors:
            ctk.CTkLabel(self.container, text="Errores: " + " | ".join(result.errors), text_color="#dc2626", wraplength=800).pack(anchor="w", pady=4)
        paths_text = "\n".join(f"{key}: {path}" for key, path in result.paths.items()) or "No se generaron archivos."
        box = ctk.CTkTextbox(self.container, height=180)
        box.pack(fill="both", expand=True, pady=10)
        box.insert("end", paths_text)
        out_dir = str(Path(next(iter(result.paths.values()))).parent if result.paths else self.output_var.get())
        ctk.CTkButton(self.container, text="Abrir carpeta de salida", command=lambda: self._open_folder(out_dir)).pack(anchor="w", pady=6)
        ctk.CTkButton(self.container, text="Nueva ejecución", command=self._build_main_screen).pack(anchor="w", pady=6)

    def _open_folder(self, folder: str) -> None:
        if sys.platform.startswith("win"):
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", folder])

    def _append_log(self, line: str) -> None:
        self.log_box.insert("end", line + "\n")
        self.log_box.see("end")

    def _clear(self) -> None:
        for child in self.container.winfo_children():
            child.destroy()
