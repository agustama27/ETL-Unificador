"""Interfaz Tkinter para ejecutar salida Bancor desde ROMAN + LOGCALL opcional."""

from pathlib import Path
from typing import Any, cast
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from procesos.pipeline_roman_only import ejecutar_pipeline_roman_only


def _append_estado(widget_estado: scrolledtext.ScrolledText, texto: str) -> None:
    widget_estado.configure(state="normal")
    widget_estado.insert(tk.END, f"{texto}\n")
    widget_estado.see(tk.END)
    widget_estado.configure(state="disabled")


def _hacer_selector(
    parent: ttk.Frame,
    label: str,
    sublabel: str,
    boton_texto: str,
    titulo_dialogo: str,
    widget_estado: scrolledtext.ScrolledText,
    log_prefix: str,
    opcional: bool = False,
) -> tuple[tk.StringVar, ttk.Button]:
    """Crea un bloque label + entry + botón seleccionar + botón limpiar (si opcional)."""
    color_label = "#555555" if opcional else "#000000"

    ttk.Label(parent, text=label, font=("", 9, "bold")).pack(anchor="w", pady=(8, 0))
    ttk.Label(parent, text=sublabel, foreground=color_label, font=("", 8)).pack(anchor="w", pady=(0, 4))

    frame = ttk.Frame(parent)
    frame.pack(fill="x", pady=(0, 2))

    ruta_var = tk.StringVar(value="")
    entry = ttk.Entry(frame, textvariable=ruta_var)
    entry.pack(side="left", fill="x", expand=True)

    def seleccionar() -> None:
        ruta = filedialog.askopenfilename(
            title=titulo_dialogo,
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if ruta:
            ruta_var.set(ruta)
            _append_estado(widget_estado, f"{log_prefix}: {Path(ruta).name}")

    boton = ttk.Button(frame, text=boton_texto, command=seleccionar)
    boton.pack(side="left", padx=(8, 0))

    if opcional:
        def limpiar() -> None:
            ruta_var.set("")
            _append_estado(widget_estado, f"{log_prefix} deseleccionado.")
        ttk.Button(frame, text="Limpiar", command=limpiar).pack(side="left", padx=(4, 0))

    return ruta_var, boton


def ejecutar_app() -> None:
    """Lanza la interfaz principal."""
    root = tk.Tk()
    root.title("BANCOR — Generador de Salida CRM")
    root.geometry("800x640")
    root.minsize(720, 580)

    frame_main = ttk.Frame(root, padding=14)
    frame_main.pack(fill="both", expand=True)

    ttk.Label(
        frame_main,
        text="BANCOR — Generador de Salida CRM",
        font=("", 11, "bold"),
    ).pack(anchor="w", pady=(0, 6))

    ttk.Separator(frame_main, orient="horizontal").pack(fill="x", pady=(0, 8))

    # Necesitamos el widget_estado antes de crear los selectores (los callbacks lo usan)
    # Lo creamos después, así que usamos una referencia diferida via lista
    _estado_ref: list[scrolledtext.ScrolledText] = []

    def get_estado() -> scrolledtext.ScrolledText:
        return _estado_ref[0]

    class DeferredLog:
        """Proxy para loguear al widget_estado antes de que esté construido."""
        def __init__(self, prefix: str) -> None:
            self._prefix = prefix
            self._pending: list[str] = []

        def __call__(self, texto: str) -> None:
            if _estado_ref:
                _append_estado(_estado_ref[0], texto)
            else:
                self._pending.append(texto)

        def flush(self) -> None:
            for msg in self._pending:
                if _estado_ref:
                    _append_estado(_estado_ref[0], msg)
            self._pending.clear()

    log_historial = DeferredLog("Historial")
    log_base_roman = DeferredLog("Base ROMAN")
    log_logcall = DeferredLog("LOGCALL")

    # --- 1. Historial de llamadas (Retell) ---
    ttk.Label(
        frame_main,
        text="1 · Historial de llamadas",
        font=("", 9, "bold"),
    ).pack(anchor="w", pady=(0, 0))
    ttk.Label(
        frame_main,
        text="Archivo exportado desde Retell con los estados de cada llamada  (ej. historial_llamadas.csv)",
        foreground="#333333",
        font=("", 8),
    ).pack(anchor="w", pady=(0, 4))

    frame_historial = ttk.Frame(frame_main)
    frame_historial.pack(fill="x", pady=(0, 8))
    ruta_historial_var = tk.StringVar(value="")
    ttk.Entry(frame_historial, textvariable=ruta_historial_var).pack(side="left", fill="x", expand=True)

    def sel_historial() -> None:
        ruta = filedialog.askopenfilename(
            title="Seleccionar Historial de llamadas (Retell)",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if ruta:
            ruta_historial_var.set(ruta)
            if _estado_ref:
                _append_estado(_estado_ref[0], f"Historial: {Path(ruta).name}")

    ttk.Button(frame_historial, text="Seleccionar historial", command=sel_historial).pack(side="left", padx=(8, 0))

    # --- 2. Base ROMAN ---
    ttk.Label(
        frame_main,
        text="2 · Base ROMAN  (para cruce LOGCALL)",
        font=("", 9, "bold"),
    ).pack(anchor="w", pady=(0, 0))
    ttk.Label(
        frame_main,
        text="Archivo BANCOR_ROMAN_YYYYMMDD.csv generado por el procesador de entrada  —  requerido si se adjunta LOGCALL",
        foreground="#333333",
        font=("", 8),
    ).pack(anchor="w", pady=(0, 4))

    frame_base_roman = ttk.Frame(frame_main)
    frame_base_roman.pack(fill="x", pady=(0, 8))
    ruta_base_roman_var = tk.StringVar(value="")
    ttk.Entry(frame_base_roman, textvariable=ruta_base_roman_var).pack(side="left", fill="x", expand=True)

    def sel_base_roman() -> None:
        ruta = filedialog.askopenfilename(
            title="Seleccionar Base ROMAN (BANCOR_ROMAN_YYYYMMDD.csv)",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if ruta:
            ruta_base_roman_var.set(ruta)
            if _estado_ref:
                _append_estado(_estado_ref[0], f"Base ROMAN: {Path(ruta).name}")

    def limpiar_base_roman() -> None:
        ruta_base_roman_var.set("")
        if _estado_ref:
            _append_estado(_estado_ref[0], "Base ROMAN deseleccionada.")

    ttk.Button(frame_base_roman, text="Seleccionar base ROMAN", command=sel_base_roman).pack(side="left", padx=(8, 0))
    ttk.Button(frame_base_roman, text="Limpiar", command=limpiar_base_roman).pack(side="left", padx=(4, 0))

    # --- 3. LOGCALL ---
    ttk.Label(
        frame_main,
        text="3 · LOGCALL  (opcional)",
        font=("", 9, "bold"),
    ).pack(anchor="w", pady=(0, 0))
    ttk.Label(
        frame_main,
        text="Archivo BANCOR_LOGCALL_YYYYMMDD.csv del marcador  —  incorpora registros sin contacto (E0005) no presentes en el historial",
        foreground="#555555",
        font=("", 8),
    ).pack(anchor="w", pady=(0, 4))

    frame_logcall = ttk.Frame(frame_main)
    frame_logcall.pack(fill="x", pady=(0, 8))
    ruta_logcall_var = tk.StringVar(value="")
    ttk.Entry(frame_logcall, textvariable=ruta_logcall_var).pack(side="left", fill="x", expand=True)

    def sel_logcall() -> None:
        ruta = filedialog.askopenfilename(
            title="Seleccionar LOGCALL (BANCOR_LOGCALL_YYYYMMDD.csv)",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if ruta:
            ruta_logcall_var.set(ruta)
            if _estado_ref:
                _append_estado(_estado_ref[0], f"LOGCALL: {Path(ruta).name}")

    def limpiar_logcall() -> None:
        ruta_logcall_var.set("")
        if _estado_ref:
            _append_estado(_estado_ref[0], "LOGCALL deseleccionado.")

    ttk.Button(frame_logcall, text="Seleccionar LOGCALL", command=sel_logcall).pack(side="left", padx=(8, 0))
    ttk.Button(frame_logcall, text="Limpiar", command=limpiar_logcall).pack(side="left", padx=(4, 0))

    ttk.Separator(frame_main, orient="horizontal").pack(fill="x", pady=(4, 8))

    # --- Área de estado ---
    ttk.Label(frame_main, text="Estado / Resultado:").pack(anchor="w")
    widget_estado = scrolledtext.ScrolledText(frame_main, height=10, state="disabled", wrap="word")
    widget_estado.pack(fill="both", expand=True, pady=(4, 10))
    _estado_ref.append(widget_estado)

    frame_actions = ttk.Frame(frame_main)
    frame_actions.pack(fill="x")

    boton_procesar = ttk.Button(frame_actions, text="Procesar")
    boton_procesar.pack(side="right")

    def procesar() -> None:
        ruta_historial = ruta_historial_var.get().strip()
        if not ruta_historial:
            messagebox.showerror("Archivo requerido", "Seleccioná el Historial de llamadas (Retell) antes de procesar.")
            return
        path_historial = Path(ruta_historial)
        if not path_historial.exists():
            messagebox.showerror("Archivo inexistente", "El archivo de Historial no existe en la ruta indicada.")
            return

        ruta_base_roman = ruta_base_roman_var.get().strip()
        path_base_roman: Path | None = None
        if ruta_base_roman:
            path_base_roman = Path(ruta_base_roman)
            if not path_base_roman.exists():
                messagebox.showerror("Archivo inexistente", "El archivo de Base ROMAN no existe en la ruta indicada.")
                return

        ruta_logcall = ruta_logcall_var.get().strip()
        path_logcall: Path | None = None
        if ruta_logcall:
            path_logcall = Path(ruta_logcall)
            if not path_logcall.exists():
                messagebox.showerror("Archivo inexistente", "El archivo de LOGCALL no existe en la ruta indicada.")
                return
            if not path_base_roman:
                messagebox.showerror(
                    "Base ROMAN requerida",
                    "Para procesar el LOGCALL también necesitás seleccionar la Base ROMAN (BANCOR_ROMAN_YYYYMMDD.csv).",
                )
                return

        partes = ["Historial"]
        if path_logcall:
            partes += ["Base ROMAN", "LOGCALL"]
        _append_estado(widget_estado, f"--- Iniciando procesamiento: {' + '.join(partes)} ---")

        boton_procesar.state(["disabled"])

        resultado: dict[str, Any] = ejecutar_pipeline_roman_only(
            path_historial,
            path_archivo_base_roman=path_base_roman,
            path_archivo_logcall=path_logcall,
        )

        logs_raw = resultado.get("logs", [])
        logs: list[str] = [str(i) for i in logs_raw] if isinstance(logs_raw, list) else [str(logs_raw)]
        for linea in logs:
            _append_estado(widget_estado, linea)

        if resultado.get("ok"):
            _append_estado(widget_estado, "Procesamiento finalizado correctamente.")
            _append_estado(widget_estado, f"Excel: {resultado.get('output_excel_path', '')}")
            _append_estado(widget_estado, f"CSV:   {resultado.get('output_csv_path', '')}")
            messagebox.showinfo("Proceso finalizado", "Archivos de salida generados correctamente.")
        else:
            error_msg = str(resultado.get("error", "Error desconocido"))
            _append_estado(widget_estado, f"Error: {error_msg}")
            messagebox.showerror("Error de procesamiento", error_msg)

        boton_procesar.state(["!disabled"])

    boton_procesar.configure(command=procesar)
    root.mainloop()
