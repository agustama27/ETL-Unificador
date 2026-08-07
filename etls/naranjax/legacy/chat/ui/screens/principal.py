from __future__ import annotations

from datetime import date
from pathlib import Path
from queue import Empty, Queue

import customtkinter as ctk
from tkinter import filedialog, messagebox

from core.config_store import load_config, remove_config_key, save_config
from core.estado_inicial import generar_estado_inicial
from core.modelos import ArchivosDia, ConfigDia
from core.validators_archivos import aggregate_messages, validar_archivo, validar_estado_mensual
from ui.worker import WorkerThread


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

        ctk.CTkLabel(self, text="Ejecucion diaria", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(18, 8))

        self._build_picker("base", "Base mensual", (("Excel", "*.xlsx"),))
        self._build_picker("planes", "Planes mensual", (("Archivos", "*.xlsx;*.csv"),))
        self._build_picker("pagos", "Pagos (opcional, ignorado)", (("Archivos", "*.csv;*.txt"),))

        self.process_btn = ctk.CTkButton(self, text="Procesar", state="disabled", command=self._start_processing)
        self.process_btn.pack(pady=8)
        self.process_start_month_btn = ctk.CTkButton(
            self,
            text="Inicio de mes sin diarios",
            state="disabled",
            command=self._start_processing_without_daily_files,
        )
        self.process_start_month_btn.pack(pady=(0, 8))
        self.generate_state_btn = ctk.CTkButton(
            self,
            text="Generar estado inicial",
            state="disabled",
            command=self._generate_initial_state,
        )
        self.generate_state_btn.pack(pady=(0, 8))

        self.progress = ctk.CTkProgressBar(self)
        self.progress.pack(fill="x", padx=20, pady=8)
        self.progress.set(0)

        self.log_view = ctk.CTkTextbox(self, height=220)
        self.log_view.pack(fill="both", expand=True, padx=20, pady=(8, 20))
        self.log_view.insert("end", "Listo para procesar.\n")

    def _build_picker(self, key: str, title: str, filetypes) -> None:
        row = ctk.CTkFrame(self)
        row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(row, text=title, width=130, anchor="w").pack(side="left", padx=(8, 8))
        status_text, status_color = empty_picker_status(key)
        status = ctk.CTkLabel(row, text=status_text, text_color=status_color, width=160, anchor="w")
        status.pack(side="left")
        self._status_labels[key] = status
        ctk.CTkButton(row, text="Seleccionar", width=130, command=lambda k=key, ft=filetypes: self._pick_file(k, ft)).pack(
            side="left", padx=8
        )
        ctk.CTkLabel(row, textvariable=ctk.StringVar(value=""), anchor="w")

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
            self._status_labels[key].configure(text="✓" if ok else "✗", text_color="green" if ok else "red")

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
        done = False
        while True:
            try:
                event, payload = self._queue.get_nowait()
            except Empty:
                break
            if event == "log":
                self.log_view.insert("end", f"{payload}\n")
                self.log_view.see("end")
            elif event == "error":
                done = True
                self._on_result(None, str(payload))
            elif event == "done":
                done = True
                self.progress.set(1)
                resultado = payload
                if hasattr(resultado, "status") and getattr(resultado, "status") != "success":
                    errores = getattr(resultado, "errores", []) or []
                    detalle = "\n".join(str(error) for error in errores if str(error).strip())
                    self._on_result(None, detalle or "La ejecucion fallo. Revisar logs para mas detalle.")
                else:
                    self._on_result(resultado, None)

        if not done:
            current = self.progress.get()
            self.progress.set(min(0.95, current + 0.01))
            self.after(50, self._drain_queue)
