import customtkinter as ctk


class SelectorProcesoScreen(ctk.CTkFrame):
    def __init__(self, master, on_select):
        super().__init__(master)
        self._on_select = on_select

        ctk.CTkLabel(self, text="NaranjaX MT ETL", font=("Segoe UI", 30, "bold")).pack(pady=(36, 10))
        ctk.CTkLabel(
            self,
            text="Elegi que flujo queres procesar",
            font=("Segoe UI", 18),
        ).pack(pady=(0, 20))

        panel = ctk.CTkFrame(self)
        panel.pack(fill="x", padx=120, pady=12)

        ctk.CTkButton(
            panel,
            text="Procesar base (back-base/)",
            height=46,
            command=lambda: self._on_select("back-base/"),
        ).pack(fill="x", padx=24, pady=(20, 10))

        ctk.CTkButton(
            panel,
            text="Procesar resultados (back-resultados/)",
            height=46,
            command=lambda: self._on_select("back-resultados/"),
        ).pack(fill="x", padx=24, pady=(0, 20))
