from __future__ import annotations

from pathlib import Path

import customtkinter as ctk

from core.config_store import load_config, save_config
from core.modelos import ConfigDia, ResultadoDia
from ui.screens.config_inicial import ConfigInicialScreen
from ui.screens.principal import PrincipalScreen
from ui.screens.resultado import ResultadoScreen


class App(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Naranja X - Mora Avanzada")
        self.geometry("960x700")
        self._frame: ctk.CTkFrame | None = None
        self._cfg = self._load_runtime_config()
        if self._cfg is None:
            self.show_config()
        else:
            self.show_main()

    def _set_screen(self, frame: ctk.CTkFrame) -> None:
        if self._frame is not None:
            self._frame.destroy()
        self._frame = frame
        self._frame.pack(fill="both", expand=True)

    def _load_runtime_config(self) -> ConfigDia | None:
        cfg = load_config()
        estado = cfg.get("carpeta_estado")
        salida = cfg.get("carpeta_salida")
        if not estado or not salida:
            return None
        output = Path(salida)
        return ConfigDia(
            estado_dir=Path(estado),
            output_dir=output,
            logs_dir=output / "logs",
            procesados_dir=output / "procesados",
        )

    def show_config(self) -> None:
        self._set_screen(ConfigInicialScreen(self, self._on_save_config))

    def show_main(self) -> None:
        assert self._cfg is not None
        self._set_screen(PrincipalScreen(self, self._cfg, self.show_result))

    def show_result(self, resultado: ResultadoDia | None, error: str | None) -> None:
        assert self._cfg is not None
        self._set_screen(ResultadoScreen(self, resultado, error, self._cfg.output_dir, self.show_main))

    def _on_save_config(self, estado: Path, salida: Path) -> None:
        save_config({"carpeta_estado": str(estado), "carpeta_salida": str(salida)})
        self._cfg = self._load_runtime_config()
        self.show_main()


def run_ui() -> int:
    app = App()
    app.mainloop()
    return 0
