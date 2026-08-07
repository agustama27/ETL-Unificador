from __future__ import annotations

from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog


class ConfigInicialScreen(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkFrame, on_save) -> None:
        super().__init__(master)
        self._on_save = on_save
        self.estado_var = ctk.StringVar(value="")
        self.salida_var = ctk.StringVar(value="")

        ctk.CTkLabel(self, text="Configuracion inicial", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(24, 12))

        self._build_row("Carpeta estado", self.estado_var, self._pick_estado)
        self._build_row("Carpeta salida", self.salida_var, self._pick_salida)

        self.error_label = ctk.CTkLabel(self, text="", text_color="red")
        self.error_label.pack(pady=8)

        self.save_btn = ctk.CTkButton(self, text="Guardar configuracion", command=self._save)
        self.save_btn.pack(pady=12)
        self._refresh_button()

    def _build_row(self, title: str, var: ctk.StringVar, cmd) -> None:
        row = ctk.CTkFrame(self)
        row.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(row, text=title, width=160, anchor="w").pack(side="left", padx=(8, 8))
        ctk.CTkEntry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(row, text="Seleccionar", command=cmd, width=120).pack(side="left", padx=(0, 8))

    def _pick_estado(self) -> None:
        value = filedialog.askdirectory()
        if value:
            self.estado_var.set(value)
        self._refresh_button()

    def _pick_salida(self) -> None:
        value = filedialog.askdirectory()
        if value:
            self.salida_var.set(value)
        self._refresh_button()

    def _refresh_button(self) -> None:
        enabled = bool(self.estado_var.get().strip()) and bool(self.salida_var.get().strip())
        self.save_btn.configure(state="normal" if enabled else "disabled")

    def _save(self) -> None:
        estado = Path(self.estado_var.get().strip())
        salida = Path(self.salida_var.get().strip())
        if not estado.exists() or not estado.is_dir():
            self.error_label.configure(text="Carpeta de estado invalida")
            return
        if not salida.exists() or not salida.is_dir():
            self.error_label.configure(text="Carpeta de salida invalida")
            return
        if not _is_writable(estado) or not _is_writable(salida):
            self.error_label.configure(text="La carpeta seleccionada no tiene permisos de escritura")
            return
        self.error_label.configure(text="")
        self._on_save(estado, salida)


def _is_writable(path: Path) -> bool:
    probe = path / ".nx_write_test.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False
