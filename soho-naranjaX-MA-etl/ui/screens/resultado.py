from __future__ import annotations

import os
from pathlib import Path

import customtkinter as ctk

from core.modelos import ResultadoDia


class ResultadoScreen(ctk.CTkFrame):
    def __init__(self, master: ctk.CTkFrame, resultado: ResultadoDia | None, error: str | None, output_dir: Path, on_reset) -> None:
        super().__init__(master)
        title = "Resultado"
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(20, 10))

        body = ctk.CTkTextbox(self, height=300)
        body.pack(fill="both", expand=True, padx=20, pady=8)

        if error:
            body.insert("end", f"Error: {error}\n")
        elif resultado is not None:
            body.insert("end", f"Modo de ejecucion: {resultado.modo_ejecucion}\n")
            body.insert("end", f"Registros procesados: {resultado.rows_roman}\n")
            body.insert("end", f"Exclusiones: {resultado.exclusiones_por_motivo}\n")
            body.insert("end", f"ROMAN: {resultado.output_roman}\n")
            body.insert("end", f"PCT: {resultado.output_pct}\n")
        body.configure(state="disabled")

        actions = ctk.CTkFrame(self)
        actions.pack(fill="x", padx=20, pady=(8, 20))
        ctk.CTkButton(actions, text="Abrir carpeta de salida", command=lambda: _open_folder(output_dir)).pack(side="left", padx=8)
        ctk.CTkButton(actions, text="Nueva ejecucion", command=on_reset).pack(side="left", padx=8)


def _open_folder(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))
