from __future__ import annotations

import os
import subprocess
from datetime import date
from pathlib import Path
from queue import Empty, Queue

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.config_store import load_config, remove_config_key, save_config
from core.estado_inicial import generar_estado_inicial
from core.modelos import ArchivosDia, ConfigDia
from core.validators_archivos import aggregate_messages, validar_archivo, validar_estado_mensual
from ui.worker import BackResultadosWorkerThread, WorkerThread


def can_enable_process(paths: dict[str, Path | None], issues: dict[str, list[str]]) -> bool:
    selected = all(paths[k] is not None for k in ("base", "planes"))
    files_ok = all(len(issues[k]) == 0 for k in ("base", "planes", "pagos"))
    estado_ok = len(issues["estado"]) == 0
    return selected and files_ok and estado_ok


def collect_blocking_errors(issues: dict[str, list[str]]) -> list[str]:
    all_errors: list[str] = []
    for key in ("base", "planes", "pagos", "estado"):
        all_errors.extend(issues[key])
    return all_errors


def empty_picker_status(key: str) -> tuple[str, str]:
    if key == "pagos":
        return ("No cargado (opcional)", "gray")
    return ("-", "gray")


def selected_file_status(raw_path: str) -> tuple[str, str]:
    path_text = str(raw_path).strip()
    if not path_text:
        return ("-", "gray")
    path = Path(path_text)
    if not path.exists() or not path.is_file():
        return ("-", "gray")
    return (f"✓ {path.name} | {path.parent}", "green")


def format_omitted_by_reason(omitted_by_reason: dict[str, int]) -> str:
    if not omitted_by_reason:
        return "-"
    return ", ".join(f"{reason}: {count}" for reason, count in sorted(omitted_by_reason.items()))


def format_back_error_message(raw_error: str) -> str:
    lowered = raw_error.lower()
    if "no input file selected" in lowered or "no files found in default folder" in lowered:
        return "No hay input disponible: selecciona un archivo o carga uno en back-resultados/roman/."
    if "failed to read input file" in lowered:
        return "No se pudo leer el archivo input. Verifica formato, permisos y que no este bloqueado."
    if "missing required source columns" in lowered:
        return "El archivo no contiene columnas requeridas para Back Resultados. Revisa el layout de origen."
    if "unsupported input extension" in lowered:
        return "Formato de archivo no soportado. Usa .csv, .txt, .xlsx o .xls."
    if "no such file" in lowered or "cannot find" in lowered:
        return "No se encontro el archivo indicado. Verifica la ruta del input."
    return raw_error


class PrincipalScreen(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkFrame, config: ConfigDia, on_result) -> None:
        super().__init__(master)
        self._config = config
        self._on_result = on_result
        self._paths: dict[str, Path | None] = {"base": None, "planes": None, "pagos": None}
        self._pagos_selected_current_session = False
        self._status_labels: dict[str, ctk.CTkLabel] = {}
        self._issues: dict[str, list[str]] = {"base": [], "planes": [], "pagos": [], "estado": []}
        self._queue: Queue[tuple[str, object]] | None = None
        self._active_run = "daily"
        self._last_back_output_path: Path | None = None

        ctk.CTkLabel(self, text="Procesos", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(18, 8))

        self._module_selector = ctk.CTkSegmentedButton(
            self,
            values=["Ejecucion diaria", "Back Resultados"],
            command=self._show_module,
        )
        self._module_selector.pack(padx=20, pady=(0, 12))

        self._daily_frame = ctk.CTkFrame(self)
        self._daily_frame.pack(fill="both", expand=True)
        self._back_resultados_frame = ctk.CTkFrame(self)

        self._build_daily_section(self._daily_frame)
        self._build_back_resultados_section(self._back_resultados_frame)
        self._module_selector.set("Ejecucion diaria")
        self._show_module("Ejecucion diaria")

    def _build_daily_section(self, container: ctk.CTkFrame) -> None:
        ctk.CTkLabel(container, text="Ejecucion diaria", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(6, 8))

        self._build_picker(container, "base", "Base mensual", (("Excel", "*.xlsx"),))
        self._build_picker(container, "planes", "Planes mensual", (("Archivos", "*.xlsx;*.csv"),))
        self._build_picker(container, "pagos", "Pagos (opcional, ignorado)", (("Archivos", "*.csv;*.txt"),))

        self.process_btn = ctk.CTkButton(container, text="Procesar", state="disabled", command=self._start_processing)
        self.process_btn.pack(pady=8)
        self.process_start_month_btn = ctk.CTkButton(
            container,
            text="Inicio de mes sin diarios",
            state="disabled",
            command=self._start_processing_without_daily_files,
        )
        self.process_start_month_btn.pack(pady=(0, 8))
        self.generate_state_btn = ctk.CTkButton(
            container,
            text="Generar estado inicial",
            state="disabled",
            command=self._generate_initial_state,
        )
        self.generate_state_btn.pack(pady=(0, 8))

        self.progress = ctk.CTkProgressBar(container)
        self.progress.pack(fill="x", padx=20, pady=8)
        self.progress.set(0)

        self.log_view = ctk.CTkTextbox(container, height=220)
        self.log_view.pack(fill="both", expand=True, padx=20, pady=(8, 20))
        self.log_view.insert("end", "Listo para procesar.\n")

    def _build_back_resultados_section(self, container: ctk.CTkFrame) -> None:
        ctk.CTkLabel(container, text="Back Resultados", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(6, 10))

        source_row = ctk.CTkFrame(container)
        source_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(source_row, text="Input", width=130, anchor="w").pack(side="left", padx=(8, 8))
        self._back_input_mode = ctk.StringVar(value="roman")
        ctk.CTkRadioButton(
            source_row,
            text="Default roman/",
            variable=self._back_input_mode,
            value="roman",
            command=self._on_back_mode_changed,
        ).pack(side="left", padx=4)
        ctk.CTkRadioButton(
            source_row,
            text="Archivo especifico",
            variable=self._back_input_mode,
            value="file",
            command=self._on_back_mode_changed,
        ).pack(side="left", padx=4)
        self._back_input_file = ctk.StringVar(value="")
        self._back_input_btn = ctk.CTkButton(source_row, text="Seleccionar", width=130, command=self._pick_back_input_file)
        self._back_input_btn.pack(side="left", padx=8)
        self._back_input_status = ctk.CTkLabel(source_row, text="-", text_color="gray", width=520, anchor="w")
        self._back_input_status.pack(side="left", padx=(4, 0))

        cruce_row = ctk.CTkFrame(container)
        cruce_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(cruce_row, text="Input LOGCALL", width=130, anchor="w").pack(side="left", padx=(8, 8))
        self._back_cruce_mode = ctk.StringVar(value="logcall")
        self._back_cruce_file = ctk.StringVar(value="")
        self._back_cruce_btn = ctk.CTkButton(cruce_row, text="Seleccionar", width=130, command=self._pick_back_cruce_file)
        self._back_cruce_btn.pack(side="left", padx=8)
        self._back_cruce_status = ctk.CTkLabel(cruce_row, text="-", text_color="gray", width=520, anchor="w")
        self._back_cruce_status.pack(side="left", padx=(4, 0))

        lookup_row = ctk.CTkFrame(container)
        lookup_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(lookup_row, text="Cruce LOGCALL", width=130, anchor="w").pack(side="left", padx=(8, 8))
        self._back_lookup_file = ctk.StringVar(value="")
        self._back_lookup_btn = ctk.CTkButton(lookup_row, text="Seleccionar", width=130, command=self._pick_back_lookup_file)
        self._back_lookup_btn.pack(side="left", padx=8)
        self._back_lookup_status = ctk.CTkLabel(lookup_row, text="-", text_color="gray", width=520, anchor="w")
        self._back_lookup_status.pack(side="left", padx=(4, 0))

        output_row = ctk.CTkFrame(container)
        output_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(output_row, text="Output dir", width=130, anchor="w").pack(side="left", padx=(8, 8))
        self._back_output_dir = ctk.StringVar(value=str((self._config.output_dir / "back-resultados").resolve()))
        self._back_output_entry = ctk.CTkEntry(output_row, width=420, textvariable=self._back_output_dir)
        self._back_output_entry.pack(side="left", padx=4)
        ctk.CTkButton(output_row, text="Seleccionar", width=130, command=self._pick_back_output_dir).pack(side="left", padx=8)

        self.back_process_btn = ctk.CTkButton(container, text="Procesar", command=self._start_back_resultados_processing)
        self.back_process_btn.pack(pady=8)
        self._back_status_label = ctk.CTkLabel(container, text="Listo para ejecutar.", text_color="gray")
        self._back_status_label.pack(pady=(0, 8))
        self._back_open_output_btn = ctk.CTkButton(
            container,
            text="Abrir carpeta de salida",
            state="disabled",
            command=self._open_back_output,
        )
        self._back_open_output_btn.pack(pady=(0, 8))

        metrics_frame = ctk.CTkFrame(container)
        metrics_frame.pack(fill="x", padx=20, pady=(0, 8))
        self._back_metrics_label = ctk.CTkLabel(metrics_frame, text="Metricas: -", justify="left", anchor="w")
        self._back_metrics_label.pack(fill="x", padx=10, pady=6)
        self._back_contract_label = ctk.CTkLabel(
            metrics_frame,
            text="Contrato de salida: pipe |, cp1252, 7 columnas, fecha yyyyMMdd",
            justify="left",
            anchor="w",
            text_color="gray",
        )
        self._back_contract_label.pack(fill="x", padx=10, pady=(0, 6))

        self.back_progress = ctk.CTkProgressBar(container)
        self.back_progress.pack(fill="x", padx=20, pady=8)
        self.back_progress.set(0)

        self.back_log_view = ctk.CTkTextbox(container, height=220)
        self.back_log_view.pack(fill="both", expand=True, padx=20, pady=(8, 20))
        self.back_log_view.insert("end", "Listo para ejecutar Back Resultados.\n")

        cfg = load_config()
        self._back_input_mode.set(cfg.get("back_resultados_input_mode", "roman"))
        self._back_input_file.set("")
        self._back_cruce_mode.set(cfg.get("back_resultados_cruce_mode", "logcall"))
        self._back_cruce_file.set("")
        self._back_lookup_file.set("")
        self._back_output_dir.set(cfg.get("back_resultados_output_dir", self._back_output_dir.get()))
        self._on_back_mode_changed()
        self._on_back_cruce_mode_changed()
        self._refresh_back_selection_statuses()

    def _show_module(self, value: str) -> None:
        if value == "Back Resultados":
            self._daily_frame.pack_forget()
            self._back_resultados_frame.pack(fill="both", expand=True)
            return
        self._back_resultados_frame.pack_forget()
        self._daily_frame.pack(fill="both", expand=True)

    def _build_picker(self, container: ctk.CTkFrame, key: str, title: str, filetypes) -> None:
        row = ctk.CTkFrame(container)
        row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row, text=title, width=130, anchor="w").pack(side="left", padx=(8, 8))
        status_text, status_color = empty_picker_status(key)
        status = ctk.CTkLabel(row, text=status_text, text_color=status_color, width=520, anchor="w")
        status.pack(side="left")
        self._status_labels[key] = status
        ctk.CTkButton(row, text="Seleccionar", width=130, command=lambda k=key, ft=filetypes: self._pick_file(k, ft)).pack(
            side="left", padx=8
        )
    def _on_back_mode_changed(self) -> None:
        mode = self._back_input_mode.get()
        self._back_input_btn.configure(state="normal" if mode == "file" else "disabled")
        cfg = load_config()
        cfg["back_resultados_input_mode"] = mode
        save_config(cfg)
        self._refresh_back_selection_statuses()

    def _on_back_cruce_mode_changed(self) -> None:
        mode = self._back_cruce_mode.get() or "logcall"
        self._back_cruce_btn.configure(state="normal")
        cfg = load_config()
        cfg["back_resultados_cruce_mode"] = mode
        save_config(cfg)

    def _pick_back_input_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=(("Archivos", "*.csv;*.xlsx;*.xls"),))
        if not path:
            return
        self._back_input_file.set(path)
        cfg = load_config()
        cfg["back_resultados_input_file"] = path
        save_config(cfg)
        self._refresh_back_selection_statuses()

    def _pick_back_cruce_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=(("Archivos", "*.csv;*.xlsx;*.xls"),))
        if not path:
            return
        self._back_cruce_file.set(path)
        cfg = load_config()
        cfg["back_resultados_cruce_file"] = path
        save_config(cfg)
        self._refresh_back_selection_statuses()

    def _pick_back_lookup_file(self) -> None:
        path = filedialog.askopenfilename(filetypes=(("Archivos", "*.csv;*.xlsx;*.xls"),))
        if not path:
            return
        self._back_lookup_file.set(path)
        cfg = load_config()
        cfg["back_resultados_cruce_lookup_file"] = path
        save_config(cfg)
        self._refresh_back_selection_statuses()

    def _refresh_back_selection_statuses(self) -> None:
        input_mode = self._back_input_mode.get()
        input_path = self._back_input_file.get().strip()
        if input_mode == "roman":
            self._back_input_status.configure(text="✓ Default roman/", text_color="green")
        else:
            input_text, input_color = selected_file_status(input_path)
            self._back_input_status.configure(text=input_text, text_color=input_color)

        cruce_path = self._back_cruce_file.get().strip()
        cruce_text, cruce_color = selected_file_status(cruce_path)
        self._back_cruce_status.configure(text=cruce_text, text_color=cruce_color)

        lookup_path = self._back_lookup_file.get().strip()
        lookup_text, lookup_color = selected_file_status(lookup_path)
        self._back_lookup_status.configure(text=lookup_text, text_color=lookup_color)

    def _pick_back_output_dir(self) -> None:
        path = filedialog.askdirectory()
        if not path:
            return
        self._back_output_dir.set(path)
        cfg = load_config()
        cfg["back_resultados_output_dir"] = path
        save_config(cfg)

    def _pick_file(self, key: str, filetypes) -> None:
        path = filedialog.askopenfilename(filetypes=filetypes)
        if not path:
            return
        self._paths[key] = Path(path)
        if key == "pagos":
            self._pagos_selected_current_session = True
            cfg = load_config()
            cfg["ultima_ruta_pagos"] = str(self._paths[key])
            save_config(cfg)
        self._run_validations()

    def _run_validations(self) -> None:
        ext = {"base": (".xlsx",), "planes": (".xlsx", ".csv"), "pagos": (".csv", ".txt")}
        for key in ("base", "planes", "pagos"):
            p = self._paths[key]
            if p is None:
                self._issues[key] = []
                status_text, status_color = empty_picker_status(key)
                self._status_labels[key].configure(text=status_text, text_color=status_color)
                continue
            issues = validar_archivo(p, ext[key])
            self._issues[key] = aggregate_messages(issues)
            ok = len(self._issues[key]) == 0
            if ok:
                self._status_labels[key].configure(text=f"✓ {p.name} | {p.parent}", text_color="green")
            else:
                self._status_labels[key].configure(text=f"✗ {p.name} | {p.parent}", text_color="red")

        if self._paths["base"]:
            today_mes = date.today().strftime("%Y%m")
            self._issues["estado"] = aggregate_messages(validar_estado_mensual(self._config.estado_dir, today_mes))
        else:
            self._issues["estado"] = []
        self._refresh_process_button()

    def _refresh_process_button(self) -> None:
        enabled = can_enable_process(self._paths, self._issues)
        self.process_btn.configure(state="normal" if enabled else "disabled")
        can_start_month_without_daily = self._paths["base"] is not None and len(self._issues["base"]) == 0
        self.process_start_month_btn.configure(state="normal" if can_start_month_without_daily else "disabled")
        can_generate_state = self._paths["base"] is not None and len(self._issues["base"]) == 0 and len(self._issues["estado"]) > 0
        self.generate_state_btn.configure(state="normal" if can_generate_state else "disabled")

    def _generate_initial_state(self) -> None:
        base = self._paths["base"]
        if base is None:
            return
        mes = date.today().strftime("%Y%m")
        try:
            estado_path = generar_estado_inicial(self._config.estado_dir, base, mes)
        except Exception as exc:
            messagebox.showerror("Estado inicial", f"No se pudo generar el estado inicial: {exc}")
            return

        self.log_view.insert("end", f"Estado inicial generado: {estado_path}\n")
        self.log_view.see("end")
        self._run_validations()

    def _start_processing_without_daily_files(self) -> None:
        self._start_processing(modo_sin_diarios=True)

    def _start_processing(self, modo_sin_diarios: bool = False) -> None:
        self._active_run = "daily"
        all_errors = collect_blocking_errors(self._issues)
        if modo_sin_diarios:
            excluded = set(self._issues["planes"] + self._issues["pagos"] + self._issues["estado"])
            all_errors = [error for error in all_errors if error not in excluded]
        if all_errors:
            messagebox.showerror("Validacion", "\n".join(sorted(set(all_errors))))
            return

        assert self._paths["base"] is not None
        base = self._paths["base"]
        planes = self._paths["planes"]
        pagos = self._paths["pagos"]
        usar_pagos = self._pagos_selected_current_session and not modo_sin_diarios
        if not usar_pagos:
            remove_config_key("ultima_ruta_pagos")

        if not modo_sin_diarios:
            assert planes is not None
        diarios_dir = planes.parent if planes is not None else base.parent

        fecha = date.today().strftime("%Y%m%d")
        archivos = ArchivosDia(
            fecha=fecha,
            mes=fecha[:6],
            input_base=base,
            diarios_dir=diarios_dir,
            planes=None if modo_sin_diarios else planes,
            pagos=(pagos if usar_pagos else None),
            usar_pagos=usar_pagos,
            autodetect_planes=False,
            autodetect_pagos=False,
            modo_sin_diarios=modo_sin_diarios,
        )
        self.process_btn.configure(state="disabled")
        self.process_start_month_btn.configure(state="disabled")
        self.progress.set(0.1)
        if modo_sin_diarios:
            self.log_view.insert("end", "Iniciando proceso (inicio de mes sin diarios)...\n")
        else:
            self.log_view.insert("end", "Iniciando proceso...\n")
        self.log_view.see("end")
        self._queue = Queue()
        worker = WorkerThread(self._config, archivos, self._queue)
        worker.start()
        self.after(50, self._drain_queue)

    def _drain_queue(self) -> None:
        if self._queue is None:
            return
        run_mode = getattr(self, "_active_run", "daily")
        done = False
        while True:
            try:
                event, payload = self._queue.get_nowait()
            except Empty:
                break
            if event == "log":
                target = self.back_log_view if run_mode == "back_resultados" else self.log_view
                target.insert("end", f"{payload}\n")
                target.see("end")
            elif event == "error":
                done = True
                if run_mode == "back_resultados":
                    friendly_error = format_back_error_message(str(payload))
                    self._back_status_label.configure(text="Error en ejecucion.", text_color="red")
                    self.back_process_btn.configure(state="normal")
                    self.back_progress.set(1)
                    self.back_log_view.insert("end", f"ERROR: {friendly_error}\n")
                    self.back_log_view.see("end")
                else:
                    self._on_result(None, str(payload))
            elif event == "done":
                done = True
                resultado = payload
                if run_mode == "back_resultados":
                    self.back_progress.set(1)
                    if hasattr(resultado, "status") and getattr(resultado, "status") == "success":
                        output_path = getattr(resultado, "output_path", None)
                        self._last_back_output_path = Path(output_path) if output_path else None
                        self._back_open_output_btn.configure(state="normal")
                        metrics_text = (
                            f"Metricas: input={getattr(resultado, 'total_input_rows', 0)} | "
                            f"output={getattr(resultado, 'total_output_rows', 0)} | "
                            f"omitidos={getattr(resultado, 'omitted_rows_total', 0)} | "
                            f"warnings={getattr(resultado, 'warning_count', 0)}\n"
                            f"Omitidos por motivo: {format_omitted_by_reason(getattr(resultado, 'omitted_by_reason', {}))}\n"
                            f"Output path: {output_path}"
                        )
                        contract = getattr(resultado, "output_contract", {}) or {}
                        contract_text = (
                            "Contrato de salida: "
                            f"pipe {contract.get('delimiter', '|')}, "
                            f"{contract.get('encoding', 'cp1252')}, "
                            f"{contract.get('columns', 7)} columnas, "
                            f"fecha {contract.get('date_format', 'yyyyMMdd')}"
                        )
                        self._back_metrics_label.configure(text=metrics_text)
                        self._back_contract_label.configure(text=contract_text)
                        self._back_status_label.configure(text="Ejecucion finalizada con exito.", text_color="green")
                        self.back_log_view.insert("end", f"Output: {output_path}\n")
                        self.back_log_view.see("end")
                    else:
                        errores = getattr(resultado, "errores", []) or []
                        detalle_raw = "; ".join(str(error) for error in errores if str(error).strip())
                        detalle = format_back_error_message(detalle_raw)
                        self._last_back_output_path = None
                        self._back_open_output_btn.configure(state="disabled")
                        self._back_status_label.configure(text="Ejecucion finalizada con error.", text_color="red")
                        self.back_log_view.insert("end", f"ERROR: {detalle or 'Fallo de ejecucion'}\n")
                        self.back_log_view.see("end")
                    self.back_process_btn.configure(state="normal")
                    continue

                self.progress.set(1)
                if hasattr(resultado, "status") and getattr(resultado, "status") != "success":
                    errores = getattr(resultado, "errores", []) or []
                    detalle = "\n".join(str(error) for error in errores if str(error).strip())
                    self._on_result(None, detalle or "La ejecucion fallo. Revisar logs para mas detalle.")
                else:
                    self._on_result(resultado, None)

        if not done:
            if run_mode == "back_resultados":
                current = self.back_progress.get()
                self.back_progress.set(min(0.95, current + 0.01))
            else:
                current = self.progress.get()
                self.progress.set(min(0.95, current + 0.01))
            self.after(50, self._drain_queue)

    def _start_back_resultados_processing(self) -> None:
        mode = self._back_input_mode.get()
        selected_input = self._back_input_file.get().strip() if mode == "file" else ""
        cruce_mode = "logcall"
        selected_cruce = self._back_cruce_file.get().strip()
        selected_lookup = self._back_lookup_file.get().strip()
        output_dir = self._back_output_dir.get().strip()

        if mode == "file" and not selected_input:
            messagebox.showerror("Back Resultados", "Selecciona un archivo de input o usa el modo default roman/.")
            return
        if not selected_cruce:
            messagebox.showerror("Back Resultados", "Selecciona el archivo LOGCALL para combinar con ROMAN.")
            return
        if not output_dir:
            messagebox.showerror("Back Resultados", "Selecciona un directorio de salida.")
            return

        cfg = load_config()
        cfg["back_resultados_input_mode"] = mode
        cfg["back_resultados_input_file"] = selected_input
        cfg["back_resultados_cruce_mode"] = cruce_mode
        cfg["back_resultados_cruce_file"] = selected_cruce
        cfg["back_resultados_cruce_lookup_file"] = selected_lookup
        cfg["back_resultados_output_dir"] = output_dir
        save_config(cfg)

        self._active_run = "back_resultados"
        self._last_back_output_path = None
        self.back_process_btn.configure(state="disabled")
        self._back_open_output_btn.configure(state="disabled")
        self.back_progress.set(0.1)
        self._back_status_label.configure(text="Ejecutando...", text_color="gray")
        self._back_metrics_label.configure(text="Metricas: procesando...")
        self.back_log_view.insert("end", "Iniciando ejecucion de Back Resultados...\n")
        self.back_log_view.see("end")
        self._queue = Queue()
        worker = BackResultadosWorkerThread(
            selected_input if mode == "file" else None,
            output_dir,
            self._queue,
            cruce_origen=cruce_mode,
            cruce_path=selected_cruce or None,
            cruce_lookup_path=selected_lookup or None,
        )
        worker.start()
        self.after(50, self._drain_queue)

    def _open_back_output(self) -> None:
        target = self._last_back_output_path
        if target is None:
            messagebox.showerror("Back Resultados", "No hay output generado para abrir.")
            return
        folder = target.parent if target.is_file() else target
        if not folder.exists():
            messagebox.showerror("Back Resultados", f"No existe la carpeta de salida: {folder}")
            return
        try:
            if os.name == "nt":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror("Back Resultados", f"No se pudo abrir la carpeta de salida: {exc}")
