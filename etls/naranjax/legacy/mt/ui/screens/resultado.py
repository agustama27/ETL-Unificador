from tkinter import messagebox

import customtkinter as ctk


class ResultadoScreen(ctk.CTkFrame):
    def __init__(self, master, resultado, on_restart):
        super().__init__(master)
        ctk.CTkLabel(self, text="Resultado", font=("Segoe UI", 30, "bold")).pack(pady=(26, 12))

        estado = "OK" if resultado.status == "ok" else "ERROR"
        ctk.CTkLabel(self, text=f"Estado: {estado}", font=("Segoe UI", 18)).pack(pady=8)

        ctk.CTkLabel(self, text=f"Base generada: {resultado.output_base or '-'}", wraplength=900).pack(pady=8)
        ctk.CTkLabel(self, text=f"Telefonos generados: {resultado.output_telefonos or '-'}", wraplength=900).pack(pady=8)

        if resultado.errores:
            messagebox.showerror("Errores", "\n".join(resultado.errores))

        ctk.CTkButton(self, text="Nueva ejecucion", command=on_restart).pack(pady=24)
