"""Tab de UI para comparar telefonos entre BANCOR_E1KIA y BANCOR_ROMAN."""

from pathlib import Path
import queue
import threading
from typing import Any, Mapping
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from procesos.phone_compare_service import comparar_telefonos_archivos


def _append_estado(widget_estado: scrolledtext.ScrolledText, texto: str) -> None:
    widget_estado.configure(state="normal")
    widget_estado.insert(tk.END, f"{texto}\n")
    widget_estado.see(tk.END)
    widget_estado.configure(state="disabled")


def _render_resultado(widget_estado: scrolledtext.ScrolledText, resultado: Mapping[str, Any]) -> None:
    for linea in resultado.get("logs", []):
        _append_estado(widget_estado, str(linea))

    if str(resultado.get("status", "")).upper() == "CANCELLED":
        _append_estado(widget_estado, "")
        _append_estado(widget_estado, "Estado: CANCELLED")
        _append_estado(widget_estado, str(resultado.get("message", "Verificacion cancelada por usuario.")))
        messagebox.showinfo("Verificacion cancelada", "La verificacion fue cancelada por el usuario.")
        return

    if resultado.get("ok"):
        summary = resultado.get("summary", {})
        _append_estado(widget_estado, "")
        _append_estado(widget_estado, f"Estado: {resultado.get('status', '')}")
        _append_estado(widget_estado, str(resultado.get("message", "")))
        _append_estado(widget_estado, f"Apariciones source: {summary.get('source_apariciones', 0)}")
        _append_estado(widget_estado, f"Apariciones target: {summary.get('target_apariciones', 0)}")
        _append_estado(widget_estado, f"Unicos source: {summary.get('source_unicos', 0)}")
        _append_estado(widget_estado, f"Unicos target: {summary.get('target_unicos', 0)}")
        _append_estado(widget_estado, f"Faltantes en ROMAN (apariciones): {summary.get('faltantes_apariciones', 0)}")
        _append_estado(widget_estado, f"Faltantes en ROMAN (unicos): {summary.get('faltantes_unicos', 0)}")

        warnings = resultado.get("warnings", [])
        if warnings:
            _append_estado(widget_estado, "")
            for warning in warnings:
                _append_estado(widget_estado, f"Aviso: {warning}")

        missing_examples = resultado.get("missing_examples", [])
        if missing_examples:
            _append_estado(widget_estado, "")
            _append_estado(widget_estado, "Detalle de faltantes (hasta 10):")
            for item in missing_examples:
                numero = item.get("numero_referencia", "")
                apariciones = item.get("apariciones_source", 0)
                columna = item.get("columna_origen_ejemplo", "")
                fila = item.get("fila_origen_ejemplo", "")
                _append_estado(
                    widget_estado,
                    f"- {numero} | apariciones={apariciones} | ejemplo={columna} fila {fila}",
                )

        if resultado.get("no_anomaly"):
            messagebox.showinfo("Verificacion completada", "No se detectaron anomalias ni faltantes en BANCOR_ROMAN.")
        else:
            messagebox.showwarning("Anomalias detectadas", "Se detectaron faltantes en BANCOR_ROMAN.")
    else:
        error_msg = str(resultado.get("error", "Error desconocido"))
        _append_estado(widget_estado, f"Error: {error_msg}")
        messagebox.showerror("Error de verificacion", error_msg)


def crear_tab_verificacion_telefonos(parent: ttk.Frame) -> None:
    """Construye controles para comparar telefonos source vs target."""
    ttk.Label(parent, text="Archivo source BANCOR_E1KIA (CSV):").pack(anchor="w", pady=(0, 4))

    frame_source = ttk.Frame(parent)
    frame_source.pack(fill="x", pady=(0, 8))

    source_var = tk.StringVar(value="")
    source_entry = ttk.Entry(frame_source, textvariable=source_var)
    source_entry.pack(side="left", fill="x", expand=True)

    def seleccionar_source() -> None:
        ruta = filedialog.askopenfilename(
            title="Seleccionar CSV source BANCOR_E1KIA",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if ruta:
            source_var.set(ruta)

    boton_seleccionar_source = ttk.Button(frame_source, text="Seleccionar source", command=seleccionar_source)
    boton_seleccionar_source.pack(side="left", padx=(8, 0))

    ttk.Label(parent, text="Archivo target BANCOR_ROMAN (CSV):").pack(anchor="w", pady=(0, 4))

    frame_target = ttk.Frame(parent)
    frame_target.pack(fill="x", pady=(0, 8))

    target_var = tk.StringVar(value="")
    target_entry = ttk.Entry(frame_target, textvariable=target_var)
    target_entry.pack(side="left", fill="x", expand=True)

    def seleccionar_target() -> None:
        ruta = filedialog.askopenfilename(
            title="Seleccionar CSV target BANCOR_ROMAN",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if ruta:
            target_var.set(ruta)

    boton_seleccionar_target = ttk.Button(frame_target, text="Seleccionar target", command=seleccionar_target)
    boton_seleccionar_target.pack(side="left", padx=(8, 0))

    ttk.Label(parent, text="Columnas source (opcional, separadas por coma):").pack(anchor="w", pady=(2, 4))
    source_columns_var = tk.StringVar(value="")
    source_columns_entry = ttk.Entry(parent, textvariable=source_columns_var)
    source_columns_entry.pack(fill="x", pady=(0, 8))

    ttk.Label(parent, text="Columnas target (opcional, separadas por coma):").pack(anchor="w", pady=(0, 4))
    target_columns_var = tk.StringVar(value="")
    target_columns_entry = ttk.Entry(parent, textvariable=target_columns_var)
    target_columns_entry.pack(fill="x", pady=(0, 8))

    generar_reporte_var = tk.BooleanVar(value=False)
    check_reporte = ttk.Checkbutton(
        parent,
        text="Generar CSV de faltantes en la carpeta del source",
        variable=generar_reporte_var,
    )
    check_reporte.pack(anchor="w", pady=(0, 8))

    frame_acciones_superior = ttk.Frame(parent)
    frame_acciones_superior.pack(fill="x", pady=(0, 8))

    boton_iniciar = ttk.Button(frame_acciones_superior, text="Iniciar verificacion")
    boton_iniciar.pack(side="left")

    boton_cancelar = ttk.Button(frame_acciones_superior, text="Cancelar")
    boton_cancelar.pack(side="left", padx=(8, 0))
    boton_cancelar.state(["disabled"])

    ttk.Label(parent, text="Resultado verificacion:").pack(anchor="w")
    widget_estado = scrolledtext.ScrolledText(parent, height=14, state="disabled", wrap="word")
    widget_estado.pack(fill="both", expand=True, pady=(4, 10))

    progress_var = tk.DoubleVar(value=0.0)
    progress_text_var = tk.StringVar(value="0% - Listo para iniciar")
    progress_bar = ttk.Progressbar(parent, orient="horizontal", mode="determinate", maximum=100, variable=progress_var)
    progress_bar.pack(fill="x", pady=(0, 4))
    ttk.Label(parent, textvariable=progress_text_var).pack(anchor="w", pady=(0, 10))

    frame_acciones = ttk.Frame(parent)
    frame_acciones.pack(fill="x")

    boton_verificar = ttk.Button(frame_acciones, text="Verificar telefonos")
    boton_verificar.pack(side="right")

    botones_accion = [boton_iniciar, boton_verificar]
    controles_bloqueables: list[ttk.Widget] = [
        source_entry,
        target_entry,
        source_columns_entry,
        target_columns_entry,
        boton_seleccionar_source,
        boton_seleccionar_target,
        check_reporte,
    ]
    cancel_event: threading.Event | None = None

    def _set_running(running: bool) -> None:
        estado_controles = ["disabled"] if running else ["!disabled"]
        for control in controles_bloqueables:
            control.state(estado_controles)

        estado_botones = ["disabled"] if running else ["!disabled"]
        for boton in botones_accion:
            boton.state(estado_botones)

        if running:
            boton_cancelar.state(["!disabled"])
        else:
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

    def verificar() -> None:
        nonlocal cancel_event
        source_path_raw = source_var.get().strip()
        target_path_raw = target_var.get().strip()

        if not source_path_raw:
            messagebox.showerror("Archivo requerido", "Debes seleccionar el archivo BANCOR_E1KIA.")
            return
        if not target_path_raw:
            messagebox.showerror("Archivo requerido", "Debes seleccionar el archivo BANCOR_ROMAN.")
            return

        source_path = Path(source_path_raw)
        target_path = Path(target_path_raw)
        if not source_path.exists():
            messagebox.showerror("Archivo inexistente", "La ruta del source no existe.")
            return
        if not target_path.exists():
            messagebox.showerror("Archivo inexistente", "La ruta del target no existe.")
            return

        cancel_event = threading.Event()
        _set_running(True)
        _append_estado(widget_estado, "--- Iniciando verificacion de telefonos ---")
        progress_var.set(0)
        progress_text_var.set("0% - Iniciando...")

        cola_eventos: queue.Queue[tuple[str, Any]] = queue.Queue()

        def _actualizar_progreso(porcentaje: int, mensaje: str) -> None:
            cola_eventos.put(("progress", (porcentaje, mensaje)))

        def _worker() -> None:
            try:
                resultado = comparar_telefonos_archivos(
                    source_path=source_path,
                    target_path=target_path,
                    source_columns_raw=source_columns_var.get().strip(),
                    target_columns_raw=target_columns_var.get().strip(),
                    generar_reporte_csv=generar_reporte_var.get(),
                    output_report_path=None,
                    progress_callback=_actualizar_progreso,
                    cancel_event=cancel_event,
                )
                cola_eventos.put(("done", resultado))
            except Exception as exc:  # pragma: no cover - fallback defensivo UI
                cola_eventos.put(("error", str(exc)))

        def _finalizar_resultado(resultado: Mapping[str, Any]) -> None:
            _render_resultado(widget_estado, resultado)

            report_path = resultado.get("output_report_path", "")
            if report_path:
                _append_estado(widget_estado, f"Reporte generado: {report_path}")

            if bool(resultado.get("ok")):
                progress_var.set(100)
                if bool(resultado.get("no_anomaly")):
                    progress_text_var.set("100% - Verificacion finalizada sin anomalias")
                else:
                    progress_text_var.set("100% - Verificacion finalizada con anomalias")
            elif str(resultado.get("status", "")).upper() == "CANCELLED":
                porcentaje = int(progress_var.get())
                progress_text_var.set(f"{porcentaje}% - Verificacion cancelada")
            else:
                porcentaje = int(progress_var.get())
                progress_text_var.set(f"{porcentaje}% - Error durante la verificacion")

            _set_running(False)

        def _poll_cola() -> None:
            reintentar = True
            while True:
                try:
                    tipo, payload = cola_eventos.get_nowait()
                except queue.Empty:
                    break

                if tipo == "progress":
                    porcentaje, mensaje = payload
                    progress_var.set(max(0, min(100, int(porcentaje))))
                    progress_text_var.set(f"{int(progress_var.get())}% - {mensaje}")
                elif tipo == "done":
                    _finalizar_resultado(payload)
                    reintentar = False
                elif tipo == "error":
                    porcentaje = int(progress_var.get())
                    progress_text_var.set(f"{porcentaje}% - Error durante la verificacion")
                    _append_estado(widget_estado, f"Error inesperado: {payload}")
                    messagebox.showerror("Error de verificacion", str(payload))
                    _set_running(False)
                    reintentar = False

            if reintentar:
                parent.after(120, _poll_cola)

        threading.Thread(target=_worker, daemon=True).start()
        parent.after(120, _poll_cola)

    boton_iniciar.configure(command=verificar)
    boton_verificar.configure(command=verificar)
    boton_cancelar.configure(command=cancelar)
