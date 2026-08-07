import customtkinter as ctk

from core.config_store import load_config, save_config
from ui.screens.principal import PrincipalScreen
from ui.screens.resultado import ResultadoScreen
from ui.screens.selector_proceso import SelectorProcesoScreen


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NaranjaX MT ETL")
        self.geometry("980x640")
        self.minsize(920, 560)
        self._frame = None
        self._clear_last_run_selected_files()
        self.show_selector()

    def _clear_last_run_selected_files(self) -> None:
        cfg = load_config()
        cfg["back_resultados_input_file"] = ""
        cfg["back_resultados_cruce_file"] = ""
        cfg["back_resultados_cruce_lookup_file"] = ""
        cfg["back_resultados_m30_file"] = ""
        save_config(cfg)

    def _swap(self, frame_cls, **kwargs):
        if self._frame is not None:
            self._frame.destroy()
        self._frame = frame_cls(self, **kwargs)
        self._frame.pack(fill="both", expand=True)

    def show_selector(self):
        self._swap(SelectorProcesoScreen, on_select=self.show_principal)

    def show_principal(self, selected_tab: str = "back-base/"):
        self._swap(PrincipalScreen, on_done=self.show_resultado, selected_tab=selected_tab)

    def show_resultado(self, resultado):
        self._swap(ResultadoScreen, resultado=resultado, on_restart=self.show_selector)


def run_ui() -> int:
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("green")
    app = App()
    app.mainloop()
    return 0
