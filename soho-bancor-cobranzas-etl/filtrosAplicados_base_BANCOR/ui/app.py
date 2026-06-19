"""Interfaz Tkinter para procesar base WFM y verificar cobertura telefonica."""

from pathlib import Path
import queue
import threading
from typing import Any, cast
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from procesos.pipeline_wfm import ejecutar_pipeline_wfm
from ui.phone_compare_tab import crear_tab_verificacion_telefonos


MESES = [
    (1, "Enero"),
    (2, "Febrero"),
    (3, "Marzo"),
    (4, "Abril"),
    (5, "Mayo"),
    (6, "Junio"),
    (7, "Julio"),
    (8, "Agosto"),
    (9, "Septiembre"),
    (10, "Octubre"),
    (11, "Noviembre"),
    (12, "Diciembre"),
]


def _append_estado(widget_estado: scrolledtext.ScrolledText, texto: str) -> None:
    widget_estado.configure(state="normal")
    widget_estado.insert(tk.END, f"{texto}\n")
    widget_estado.see(tk.END)
    widget_estado.configure(state="disabled")


def _crear_tab_procesamiento(parent: ttk.Frame) -> None:
    frame_bottom = ttk.Frame(parent)
    frame_bottom.pack(side="bottom", fill="x")

    ttk.Label(parent, text="Archivo de base (XLSX/CSV):").pack(anchor="w", pady=(0, 4))

    frame_archivo = ttk.Frame(parent)
    frame_archivo.pack(fill="x", pady=(0, 10))

    ruta_var = tk.StringVar(value="")
    entry_ruta = ttk.Entry(frame_archivo, textvariable=ruta_var)
    entry_ruta.pack(side="left", fill="x", expand=True)

    ttk.Label(
        parent,
        text="Meses permitidos para Fecha_Entrega:",
    ).pack(anchor="w")

    frame_meses = ttk.Frame(parent)
    frame_meses.pack(fill="x", pady=(4, 10))

    meses_vars: dict[int, tk.BooleanVar] = {}
    checkboxes_meses: list[ttk.Checkbutton] = []
    for index, (numero, nombre) in enumerate(MESES):
        var = tk.BooleanVar(value=numero in {2, 3})
        meses_vars[numero] = var
        checkbox_mes = ttk.Checkbutton(frame_meses, text=nombre, variable=var)
        checkbox_mes.grid(
            row=index // 4,
            column=index % 4,
            sticky="w",
            padx=8,
            pady=3,
        )
        checkboxes_meses.append(checkbox_mes)

    incluir_vacios_var = tk.BooleanVar(value=False)
    checkbox_vacios = ttk.Checkbutton(
        parent,
        text="Incluir Fecha_Entrega vacia",
        variable=incluir_vacios_var,
    )
    checkbox_vacios.pack(anchor="w", pady=(0, 10))

    ttk.Label(parent, text="Estado / Resultado:").pack(anchor="w")
    widget_estado = scrolledtext.ScrolledText(parent, height=15, state="disabled", wrap="word")
    widget_estado.pack(fill="both", expand=True, pady=(4, 10))

    progress_var = tk.DoubleVar(value=0.0)
    progress_text_var = tk.StringVar(value="0% - Listo para iniciar")
    progress_bar = ttk.Progressbar(
        frame_bottom,
        orient="horizontal",
        mode="determinate",
        maximum=100,
        variable=progress_var,
    )
    progress_bar.pack(fill="x", pady=(0, 4))
    ttk.Label(frame_bottom, textvariable=progress_text_var).pack(anchor="w", pady=(0, 10))

    frame_actions = ttk.Frame(frame_bottom)
    frame_actions.pack(fill="x")

    boton_cancelar = ttk.Button(frame_actions, text="Cancelar")
    boton_cancelar.pack(side="right", padx=(0, 8))

    boton_procesar = ttk.Button(frame_actions, text="Procesar")
    boton_procesar.pack(side="right")

    boton_cancelar.state(["disabled"])
    cancel_event: threading.Event | None = None

    def seleccionar_base() -> None:
        ruta = filedialog.askopenfilename(
            title="Seleccionar base",
            filetypes=[("Archivos soportados", "*.xlsx *.xls *.csv"), ("Todos", "*.*")],
        )
        if ruta:
            ruta_var.set(ruta)
            _append_estado(widget_estado, f"Base seleccionada: {ruta}")

    boton_seleccionar_base = ttk.Button(frame_archivo, text="Seleccionar base", command=seleccionar_base)
    boton_seleccionar_base.pack(
        side="left", padx=(8, 0)
    )

    controles_bloqueables: list[ttk.Widget] = [entry_ruta, boton_seleccionar_base, checkbox_vacios, *checkboxes_meses]

    def _set_running(running: bool) -> None:
        estado_controles = ["disabled"] if running else ["!disabled"]
        for control in controles_bloqueables:
            control.state(estado_controles)

        if running:
            boton_procesar.state(["disabled"])
            boton_cancelar.state(["!disabled"])
        else:
            boton_procesar.state(["!disabled"])
            boton_cancelar.state(["disabled"])

    def cancelar() -> None:
        nonlocal cancel_event
        if cancel_event is None or cancel_event.is_set():
            return
        cancel_event.set()
        boton_cancelar.state(["disabled"])
        _append_estado(widget_estado, "Solicitando cancelacion...")
        porcentaje = int(progress_var.get())
        progress_text_var.set(f"{porcentaje}% - Cancelando...")

    def procesar() -> None:
        nonlocal cancel_event
        ruta = ruta_var.get().strip()
        if not ruta:
            messagebox.showerror("Archivo requerido", "Selecciona un archivo antes de procesar.")
            return

        path_archivo = Path(ruta)
        if not path_archivo.exists():
            messagebox.showerror("Archivo inexistente", "La ruta seleccionada no existe.")
            return

        meses_seleccionados = [mes for mes, var in meses_vars.items() if var.get()]
        if not meses_seleccionados:
            messagebox.showerror("Meses requeridos", "Selecciona al menos un mes para Fecha_Entrega.")
            return

        cancel_event = threading.Event()
        _set_running(True)
        _append_estado(widget_estado, "--- Iniciando procesamiento ---")
        progress_var.set(0)
        progress_text_var.set("0% - Iniciando...")

        cola_eventos: queue.Queue[tuple[str, Any]] = queue.Queue()

        def _actualizar_progreso(porcentaje: int, mensaje: str) -> None:
            cola_eventos.put(("progress", (porcentaje, mensaje)))

        def _worker() -> None:
            try:
                resultado = ejecutar_pipeline_wfm(
                    path_archivo,
                    meses_seleccionados,
                    incluir_fechas_vacias=incluir_vacios_var.get(),
                    progress_callback=_actualizar_progreso,
                    cancel_event=cancel_event,
                )
                cola_eventos.put(("done", resultado))
            except Exception as exc:  # pragma: no cover - fallback defensivo UI
                cola_eventos.put(("error", str(exc)))

        def _render_resultado(resultado: dict[str, Any]) -> None:
            logs_raw = resultado.get("logs", [])
            logs: list[str]
            if isinstance(logs_raw, list):
                logs = [str(item) for item in logs_raw]
            else:
                logs = [str(logs_raw)]

            for linea in logs:
                _append_estado(widget_estado, linea)

            artifacts_raw = resultado.get("artifacts", [])
            artifacts = artifacts_raw if isinstance(artifacts_raw, list) else []
            status = str(resultado.get("status", "success" if resultado.get("ok") else "failed"))

            if artifacts:
                nombres = {
                    "xlsx": "XLSX",
                    "roman": "ROMAN",
                    "e1kia": "E1KIA",
                }
                _append_estado(widget_estado, "Artefactos:")
                for artifact in artifacts:
                    if not isinstance(artifact, dict):
                        continue
                    nombre = nombres.get(str(artifact.get("name", "")), str(artifact.get("name", "")))
                    estado = str(artifact.get("status", "")).lower()
                    ruta = str(artifact.get("path", ""))
                    if estado == "generated":
                        _append_estado(widget_estado, f"- [{nombre}] generated: {ruta}")
                    else:
                        error = str(artifact.get("error", "Error desconocido"))
                        _append_estado(widget_estado, f"- [{nombre}] failed: {error}")

            if status == "success":
                progress_var.set(100)
                progress_text_var.set("100% - Procesamiento finalizado")
                _append_estado(widget_estado, "Procesamiento finalizado correctamente.")
                salida = str(cast(object, resultado.get("output_path", "")))
                _append_estado(widget_estado, f"Salida: {salida}")
                messagebox.showinfo("Proceso finalizado", "Base procesada correctamente.")
            elif status == "partial_failure":
                progress_var.set(100)
                progress_text_var.set("100% - Finalizado con advertencias")
                _append_estado(widget_estado, "Procesamiento finalizado con fallas parciales en exportes auxiliares.")
                messagebox.showwarning(
                    "Proceso con advertencias",
                    "La base principal se genero, pero hubo errores en uno o mas artefactos auxiliares.",
                )
            elif status == "cancelled":
                porcentaje = int(progress_var.get())
                progress_text_var.set(f"{porcentaje}% - Proceso cancelado")
                _append_estado(widget_estado, "Proceso cancelado por usuario.")
                messagebox.showinfo("Proceso cancelado", "El procesamiento fue cancelado.")
            else:
                error_msg = str(resultado.get("error", "Error desconocido"))
                porcentaje = int(progress_var.get())
                progress_text_var.set(f"{porcentaje}% - Error durante el procesamiento")
                _append_estado(widget_estado, "Proceso finalizado con error.")
                _append_estado(widget_estado, f"Detalle: {error_msg}")
                messagebox.showerror("Error de procesamiento", error_msg)

            _set_running(False)

        def _poll_cola() -> None:
            reintentar = True
            while True:
                try:
                    tipo, payload = cola_eventos.get_nowait()
                except queue.Empty:
                    break

                if tipo == "progress":
                    porcentaje, mensaje = cast(tuple[int, str], payload)
                    progress_var.set(max(0, min(100, int(porcentaje))))
                    progress_text_var.set(f"{int(progress_var.get())}% - {mensaje}")
                elif tipo == "done":
                    _render_resultado(cast(dict[str, Any], payload))
                    reintentar = False
                elif tipo == "error":
                    porcentaje = int(progress_var.get())
                    progress_text_var.set(f"{porcentaje}% - Error durante el procesamiento")
                    _append_estado(widget_estado, f"Error inesperado: {payload}")
                    messagebox.showerror("Error de procesamiento", str(payload))
                    _set_running(False)
                    reintentar = False

            if reintentar:
                parent.after(120, _poll_cola)

        threading.Thread(target=_worker, daemon=True).start()
        parent.after(120, _poll_cola)

    boton_procesar.configure(command=procesar)
    boton_cancelar.configure(command=cancelar)


def ejecutar_app() -> None:
    """Lanza la interfaz principal."""
    root = tk.Tk()
    root.title("Filtros Aplicados Base BANCOR")
    root.geometry("760x560")
    root.minsize(700, 500)

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    tab_procesamiento = ttk.Frame(notebook, padding=12)
    tab_telefonos = ttk.Frame(notebook, padding=12)

    notebook.add(tab_procesamiento, text="Filtros base")
    notebook.add(tab_telefonos, text="Verificacion telefonos")

    _crear_tab_procesamiento(tab_procesamiento)
    crear_tab_verificacion_telefonos(tab_telefonos)

    root.mainloop()
