from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.config_store import load_config, save_config


class ConfigInicialScreen(ctk.CTkFrame):
    def __init__(self, master, on_continue):
        super().__init__(master)
        self._on_continue = on_continue
        self._cfg = load_config()

        ctk.CTkLabel(self, text="Configuracion inicial", font=("Segoe UI", 28, "bold")).pack(pady=(28, 12))

        panel = ctk.CTkFrame(self)
        panel.pack(fill="x", padx=24, pady=12)

        self.estado_var = ctk.StringVar(value=self._cfg.get("carpeta_estado", ""))
        self.salida_var = ctk.StringVar(value=self._cfg.get("carpeta_salida", ""))

        self._folder_row(panel, "Carpeta estado", self.estado_var)
        self._folder_row(panel, "Carpeta salida", self.salida_var)

        ctk.CTkButton(self, text="Guardar y continuar", command=self._save).pack(pady=22)

    def _folder_row(self, parent, label, var):
        row = ctk.CTkFrame(parent)
        row.pack(fill="x", padx=12, pady=10)
        ctk.CTkLabel(row, text=label, width=140, anchor="w").pack(side="left", padx=(6, 10))
        ctk.CTkEntry(row, textvariable=var).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="Seleccionar", width=120, command=lambda v=var: self._pick_dir(v)).pack(side="left", padx=(10, 6))

    def _pick_dir(self, var):
        selected = filedialog.askdirectory()
        if selected:
            var.set(selected)

    def _save(self):
        estado = self.estado_var.get().strip()
        salida = self.salida_var.get().strip()
        if not estado or not salida:
            return
        Path(estado).mkdir(parents=True, exist_ok=True)
        Path(salida).mkdir(parents=True, exist_ok=True)
        cfg = load_config()
        cfg["carpeta_estado"] = estado
        cfg["carpeta_salida"] = salida
        save_config(cfg)
        self._on_continue()
