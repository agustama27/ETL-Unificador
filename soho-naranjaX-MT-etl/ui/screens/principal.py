from __future__ import annotations

import os
from pathlib import Path
from queue import Queue
from tkinter import filedialog, messagebox

import customtkinter as ctk

from core.config_store import load_config, save_config
from core.modelos import ArchivosDia
from core.runtime_paths import build_config
from core.validators_archivos import (
    aggregate_messages,
    can_enable_process,
    validar_archivo,
)
from ui.worker import BackResultadosWorkerThread, WorkerThread


class PrincipalScreen(ctk.CTkFrame):
    def __init__(self, master, on_done, selected_tab: str = "back-base/"):
        super().__init__(master)
        self._on_done = on_done
        self._queue = Queue()
        self._back_queue = Queue()
        self._progress = 0.0

        ctk.CTkLabel(self, text="NaranjaX MT ETL", font=("Segoe UI", 28, "bold")).pack(pady=(14, 8))

        tabs = ctk.CTkTabview(self)
        tabs.pack(fill="both", expand=True, padx=18, pady=(2, 10))
        tab_dia_name = "back-base/"
        tab_back_name = "back-resultados/"
        tab_dia = tabs.add(tab_dia_name)
        tab_back = tabs.add(tab_back_name)

        self._build_dia_tab(tab_dia)
        self._build_back_resultados_tab(tab_back)

        if selected_tab in (tab_dia_name, tab_back_name):
            tabs.set(selected_tab)

    def _build_dia_tab(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(parent, text="Procesa back-base/: base recibida -> base procesada -> telefonos").pack(pady=(8, 10))

        box = ctk.CTkFrame(parent)
        box.pack(fill="x", padx=10, pady=8)

        cfg = load_config()
        self.salida_dir_var = ctk.StringVar(value=cfg.get("carpeta_salida", ""))

        row_salida = ctk.CTkFrame(box)
        row_salida.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(row_salida, text="Carpeta salida", width=130, anchor="w").pack(side="left", padx=(6, 10))
        ctk.CTkEntry(row_salida, textvariable=self.salida_dir_var).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row_salida, text="Seleccionar", command=self._pick_salida_dir).pack(side="left", padx=(10, 6))

        self.base_mode = ctk.StringVar(value="manual")
        self.base_var = ctk.StringVar(value="")

        row_mode = ctk.CTkFrame(box)
        row_mode.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(row_mode, text="Modo", width=130, anchor="w").pack(side="left", padx=(6, 10))
        ctk.CTkRadioButton(
            row_mode,
            text="Usar ultimo TXT de back-base/base_recibida/",
            variable=self.base_mode,
            value="auto",
            command=self._refresh_base_mode,
        ).pack(side="left", padx=6)
        ctk.CTkRadioButton(
            row_mode,
            text="Adjuntar TXT manual",
            variable=self.base_mode,
            value="manual",
            command=self._refresh_base_mode,
        ).pack(side="left", padx=6)

        row = ctk.CTkFrame(box)
        row.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(row, text="Base TXT", width=130, anchor="w").pack(side="left", padx=(6, 10))
        self.base_entry = ctk.CTkEntry(row, textvariable=self.base_var)
        self.base_entry.pack(side="left", fill="x", expand=True)
        self.base_pick_btn = ctk.CTkButton(row, text="Seleccionar", command=self._pick_base)
        self.base_pick_btn.pack(side="left", padx=(10, 6))

        self.progress = ctk.CTkProgressBar(parent)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=12, pady=(8, 8))

        self.log = ctk.CTkTextbox(parent, height=180)
        self.log.pack(fill="both", expand=True, padx=12, pady=8)

        self.btn_process = ctk.CTkButton(parent, text="Procesar", command=self._start)
        self.btn_process.pack(pady=(6, 14))
        self._refresh_base_mode()

    def _build_back_resultados_tab(self, parent: ctk.CTkFrame) -> None:
        cfg = load_config()

        ctk.CTkLabel(
            parent,
            text="Procesa back-resultados/: adjunta los inputs necesarios y genera la salida.",
        ).pack(pady=(8, 6))

        box = ctk.CTkFrame(parent)
        box.pack(fill="x", padx=10, pady=8)

        self.back_input_mode = ctk.StringVar(value=cfg.get("back_resultados_input_mode", "roman"))
        self.back_input_file = ctk.StringVar(value=cfg.get("back_resultados_input_file", ""))
        self.back_cruce_file = ctk.StringVar(value=cfg.get("back_resultados_cruce_file", ""))
        self.back_lookup_file = ctk.StringVar(
            value=cfg.get("back_resultados_m30_file", cfg.get("back_resultados_cruce_lookup_file", ""))
        )
        self.back_output_dir = ctk.StringVar(value=cfg.get("back_resultados_output_dir", cfg.get("carpeta_salida", "")))

        row_mode = ctk.CTkFrame(box)
        row_mode.pack(fill="x", padx=12, pady=(12, 8))
        ctk.CTkLabel(row_mode, text="Input", width=150, anchor="w").pack(side="left")
        ctk.CTkRadioButton(row_mode, text="roman", variable=self.back_input_mode, value="roman", command=self._save_back_cfg).pack(side="left", padx=6)
        ctk.CTkRadioButton(row_mode, text="file", variable=self.back_input_mode, value="file", command=self._save_back_cfg).pack(side="left", padx=6)

        row_input = ctk.CTkFrame(box)
        row_input.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row_input, text="Historial ROMAN", width=150, anchor="w").pack(side="left")
        ctk.CTkEntry(row_input, textvariable=self.back_input_file).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row_input, text="Seleccionar", command=self._pick_back_input).pack(side="left", padx=(8, 0))

        row_cruce = ctk.CTkFrame(box)
        row_cruce.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row_cruce, text="Input LOGCALL", width=150, anchor="w").pack(side="left")
        ctk.CTkEntry(row_cruce, textvariable=self.back_cruce_file).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row_cruce, text="Seleccionar", command=self._pick_back_cruce).pack(side="left", padx=(8, 0))

        row_lookup = ctk.CTkFrame(box)
        row_lookup.pack(fill="x", padx=12, pady=8)
        ctk.CTkLabel(row_lookup, text="Cruce LOGCALL(Archivo original M30OLO)", width=290, anchor="w").pack(side="left")
        ctk.CTkEntry(row_lookup, textvariable=self.back_lookup_file).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row_lookup, text="Seleccionar", command=self._pick_back_lookup).pack(side="left", padx=(8, 0))

        row_output = ctk.CTkFrame(box)
        row_output.pack(fill="x", padx=12, pady=(8, 12))
        ctk.CTkLabel(row_output, text="Output dir", width=150, anchor="w").pack(side="left")
        ctk.CTkEntry(row_output, textvariable=self.back_output_dir).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row_output, text="Seleccionar", command=self._pick_back_output).pack(side="left", padx=(8, 0))

        self.back_status = ctk.CTkLabel(parent, text="Estado: pendiente")
        self.back_status.pack(anchor="w", padx=12, pady=(6, 2))
        self.back_metrics = ctk.CTkLabel(parent, text="Metricas: -")
        self.back_metrics.pack(anchor="w", padx=12, pady=(0, 8))

        self.back_log = ctk.CTkTextbox(parent, height=170)
        self.back_log.pack(fill="both", expand=True, padx=12, pady=6)

        actions = ctk.CTkFrame(parent)
        actions.pack(fill="x", padx=12, pady=(6, 12))
        ctk.CTkButton(actions, text="Procesar", command=self._start_back_resultados).pack(side="left")
        ctk.CTkButton(actions, text="Abrir carpeta de salida", command=self._open_back_output).pack(side="left", padx=8)

    def _save_back_cfg(self) -> None:
        cfg = load_config()
        cfg.update(
            {
                "back_resultados_input_mode": self.back_input_mode.get(),
                "back_resultados_input_file": self.back_input_file.get(),
                "back_resultados_cruce_mode": "logcall",
                "back_resultados_cruce_file": self.back_cruce_file.get(),
                "back_resultados_cruce_lookup_file": self.back_lookup_file.get(),
                "back_resultados_m30_file": self.back_lookup_file.get(),
                "back_resultados_output_dir": self.back_output_dir.get(),
            }
        )
        save_config(cfg)

    def _pick_base(self):
        selected = filedialog.askopenfilename(filetypes=[("Text files", "*.txt")])
        if not selected:
            return
        self.base_var.set(selected)
        issues = validar_archivo(selected, (".txt",))

        if issues:
            messagebox.showerror("Validacion", aggregate_messages(issues))
        self.btn_process.configure(state="normal" if can_enable_process(selected, issues) else "disabled")

    def _pick_salida_dir(self) -> None:
        selected = filedialog.askdirectory()
        if not selected:
            return
        self.salida_dir_var.set(selected)
        cfg = load_config()
        cfg["carpeta_salida"] = selected
        save_config(cfg)

    def _refresh_base_mode(self) -> None:
        is_auto = self.base_mode.get() == "auto"
        self.base_entry.configure(state="disabled" if is_auto else "normal")
        self.base_pick_btn.configure(state="disabled" if is_auto else "normal")
        if is_auto:
            self.btn_process.configure(state="normal")
            return
        selected = self.base_var.get().strip()
        self.btn_process.configure(state="normal" if selected and Path(selected).exists() else "disabled")

    def _start(self):
        self.btn_process.configure(state="disabled")
        self.progress.set(0.05)
        self.log.delete("1.0", "end")

        cfg = load_config()
        salida_dir = self.salida_dir_var.get().strip()
        if salida_dir:
            cfg["carpeta_salida"] = salida_dir
        save_config(cfg)
        config = build_config(salida_cli=cfg.get("carpeta_salida"))
        if self.base_mode.get() == "auto":
            archivos = ArchivosDia(base_entrada=None, usar_base_reciente=True)
        else:
            archivos = ArchivosDia(base_entrada=Path(self.base_var.get()), usar_base_reciente=False)

        worker = WorkerThread(config, archivos, self._queue)
        worker.start()
        self.after(50, self._drain_queue)

    def _drain_queue(self):
        should_continue = True
        while not self._queue.empty():
            kind, payload = self._queue.get()
            if kind == "log":
                self.log.insert("end", f"{payload}\n")
                self.log.see("end")
            elif kind == "done":
                self.progress.set(1)
                self._on_done(payload)
                should_continue = False
            elif kind == "error":
                messagebox.showerror("Error", str(payload))
                self.btn_process.configure(state="normal")
                should_continue = False

        if should_continue:
            self._progress = min(0.95, self._progress + 0.01)
            self.progress.set(max(0.05, self._progress))
            self.after(50, self._drain_queue)

    def _pick_back_input(self) -> None:
        selected = filedialog.askopenfilename(filetypes=[("Soportados", "*.csv *.txt *.xlsx *.xls")])
        if selected:
            self.back_input_file.set(selected)
            self._save_back_cfg()

    def _pick_back_cruce(self) -> None:
        selected = filedialog.askopenfilename(filetypes=[("CSV", "*.csv")])
        if selected:
            self.back_cruce_file.set(selected)
            self._save_back_cfg()

    def _pick_back_lookup(self) -> None:
        selected = filedialog.askopenfilename(filetypes=[("TXT", "*.txt")])
        if selected:
            self.back_lookup_file.set(selected)
            self._save_back_cfg()

    def _pick_back_output(self) -> None:
        selected = filedialog.askdirectory()
        if selected:
            self.back_output_dir.set(selected)
            self._save_back_cfg()

    def _friendly_back_error(self, raw: str) -> str:
        text = (raw or "").lower()
        if "no input file selected" in text or "no files found in default folder" in text:
            return "No hay input disponible: selecciona un archivo o carga uno en back-resultados/roman/."
        if "failed to read input file" in text:
            return "No se pudo leer el archivo input. Verifica formato, permisos y que no este bloqueado."
        if "missing required source columns" in text:
            return "El archivo no contiene columnas requeridas para Back Resultados. Revisa el layout de origen."
        if "unsupported input extension" in text:
            return "Formato de archivo no soportado. Usa .csv, .txt, .xlsx o .xls."
        if "no such file" in text or "cannot find" in text:
            return "No se encontro el archivo indicado. Verifica la ruta del input."
        if "no se encontro m30olos .txt" in text:
            return "Falta la base M30OLOS (.txt). Seleccionala en 'Base M30 (.txt)' para procesar back-resultados."
        return raw

    def _start_back_resultados(self) -> None:
        self._save_back_cfg()
        self.back_log.delete("1.0", "end")
        self.back_status.configure(text="Estado: procesando...")
        self.back_metrics.configure(text="Metricas: -")

        selected_input = ""
        if self.back_input_mode.get() == "file":
            selected_input = self.back_input_file.get().strip()

        output_dir = self.back_output_dir.get().strip()
        if not output_dir:
            messagebox.showerror("Back Resultados", "Debes seleccionar Output dir.")
            return

        worker = BackResultadosWorkerThread(
            selected_input=selected_input,
            output_dir=output_dir,
            queue=self._back_queue,
            cruce_origen="logcall" if self.back_cruce_file.get().strip() else "none",
            cruce_path=self.back_cruce_file.get().strip() or None,
            cruce_lookup_path=self.back_lookup_file.get().strip() or None,
        )
        worker.start()
        self.after(50, self._drain_back_queue)

    def _drain_back_queue(self) -> None:
        should_continue = True
        while not self._back_queue.empty():
            kind, payload = self._back_queue.get()
            if kind == "log":
                self.back_log.insert("end", f"{payload}\n")
                self.back_log.see("end")
            elif kind == "done":
                if payload.status == "success":
                    self.back_status.configure(text=f"Estado: OK - {payload.output_path}")
                    self.back_metrics.configure(
                        text=(
                            f"Metricas: input={payload.total_input_rows} output={payload.total_output_rows} "
                            f"omitidas={payload.omitted_rows_total} warnings={payload.warning_count}"
                        )
                    )
                else:
                    raw = "\n".join(payload.errores) if payload.errores else "Error desconocido"
                    self.back_status.configure(text="Estado: ERROR")
                    messagebox.showerror("Back Resultados", self._friendly_back_error(raw))
                should_continue = False
            elif kind == "error":
                self.back_status.configure(text="Estado: ERROR")
                messagebox.showerror("Back Resultados", self._friendly_back_error(str(payload)))
                should_continue = False

        if should_continue:
            self.after(50, self._drain_back_queue)

    def _open_back_output(self) -> None:
        output_dir = self.back_output_dir.get().strip()
        if not output_dir:
            messagebox.showinfo("Back Resultados", "No hay carpeta de salida configurada.")
            return
        path = Path(output_dir)
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))
