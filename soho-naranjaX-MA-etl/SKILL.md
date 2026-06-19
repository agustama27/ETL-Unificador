---
name: etl-ui-executable
description: Implementa una UI de escritorio Windows (customtkinter) sobre un ETL existente, empaquetable como .exe one-file con PyInstaller, con CLI dual, configuracion persistente, workers en background, validacion de inputs y build trazable por rama+commit. Trigger: el usuario tiene un ETL en Python y quiere un ejecutable con UI similar a naranjax_etl.exe.
---

# ETL UI Executable — Skill

Patron de referencia: `soho-naranjaX-MA-etl` (rama `main`, commit `ae800fa`).
Artefacto objetivo: `dist-<branch>-<commit>\<app>.exe` que abra una UI nativa Windows con doble clic, sin Python en la maquina destino.

## 1) Resultado esperado

Al completar la skill, el proyecto destino tiene:

1. Entry point dual (UI por defecto, `--cli` para batch).
2. App `customtkinter` con 3 pantallas: Config inicial, Principal, Resultado.
3. Workers en threads que ejecutan el ETL sin congelar la UI.
4. Configuracion persistente en disco (carpeta estado + carpeta salida).
5. Validacion de inputs antes de habilitar `Procesar`.
6. PyInstaller spec one-file, console=False, con hidden imports del ETL.
7. `build.bat` que detecta rama+commit y emite `dist-<rama>-<commit>\app.exe` + `build-info.txt`.
8. CLI con `argparse` que reusa el mismo `procesar_dia` que la UI.

## 2) Stack y dependencias

- Python 3.11+ (probado 3.11 / 3.12).
- `customtkinter` (UI).
- `PyInstaller` (packaging).
- Lo que ya use el ETL (pandas, openpyxl, etc.).

`requirements-packaging.txt`:

```
customtkinter>=5.2
pyinstaller>=6.0
```

## 3) Layout del proyecto

```
<root>/
  <app_name>.py            # entry point dual UI/CLI
  cli/
    __init__.py
    main.py                # run_cli(argv) -> int
  core/
    modelos.py             # dataclasses: ConfigDia, ArchivosDia, ResultadoDia
    config_store.py        # load_config/save_config (JSON en %APPDATA% o user dir)
    runtime_paths.py       # resolve_estado_dir / resolve_output_dir con env vars
    procesar_dia.py        # orquesta el ETL — reusable por UI y CLI
    validators_archivos.py # validar_archivo, validar_estado_mensual, aggregate_messages
  ui/
    __init__.py
    app.py                 # App(ctk.CTk) — router de pantallas
    worker.py              # WorkerThread(threading.Thread) -> Queue de eventos
    screens/
      __init__.py
      config_inicial.py    # Configuracion inicial (carpetas)
      principal.py         # Seleccion de inputs + Procesar + log + progress
      resultado.py         # Resumen + abrir carpeta
  packaging/
    <app_name>.spec        # PyInstaller spec
    build.bat              # Build trazable rama+commit
    BUILD.md               # UAT y criterios PASS/FAIL
  requirements-packaging.txt
```

## 4) Contratos clave

### 4.1 Entry point dual (`<app_name>.py`)

```python
import sys

def main() -> int:
    if "--cli" in sys.argv[1:]:
        argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a != "--cli"]
        from cli.main import run_cli
        return run_cli(argv)
    from ui.app import run_ui
    return run_ui()

if __name__ == "__main__":
    raise SystemExit(main())
```

Regla: la UI y la CLI deben llamar **al mismo** `procesar_dia(config, archivos, log_cb=...)`. Cero divergencia de logica.

### 4.2 Modelo de datos (`core/modelos.py`)

Define al menos:

- `ConfigDia(estado_dir, output_dir, logs_dir, procesados_dir)` — todas `Path`.
- `ArchivosDia(...)` — paths de inputs del dia + flags (`usar_pagos`, `modo_sin_diarios`, etc.).
- `ResultadoDia(status, rows_*, output_*, exclusiones_por_motivo, errores, modo_ejecucion)`.

`procesar_dia` recibe `(config, archivos, log_cb)` y retorna `ResultadoDia`. `log_cb(line: str)` es lo que la UI conecta a su `Queue` para drainar en el log textbox.

### 4.3 Worker thread (`ui/worker.py`)

```python
class WorkerThread(threading.Thread):
    def __init__(self, config, archivos, queue):
        super().__init__(daemon=True)
        self._config, self._archivos, self._queue = config, archivos, queue
    def run(self):
        try:
            resultado = procesar_dia(self._config, self._archivos, log_cb=self._on_log)
            self._queue.put(("done", resultado))
        except Exception as exc:
            self._queue.put(("error", str(exc)))
    def _on_log(self, line):
        self._queue.put(("log", line))
```

Patron en la UI: `self.after(50, self._drain_queue)` consume eventos `("log"|"done"|"error", payload)`. Mientras no llegue done/error, avanza `progress` indeterminado con `min(0.95, current + 0.01)`.

### 4.4 Router de pantallas (`ui/app.py`)

`App(ctk.CTk)` mantiene un solo frame activo (`self._frame`), destruye y reemplaza al cambiar de pantalla. Si no hay config persistida -> `ConfigInicialScreen`; si hay -> `PrincipalScreen`. Tras procesar -> `ResultadoScreen` con boton "Nueva ejecucion".

### 4.5 Config persistente (`core/config_store.py`)

JSON simple, leido/escrito en cada `Seleccionar`. Llaves minimas: `carpeta_estado`, `carpeta_salida`. Toda otra preferencia (ultimo path seleccionado, modos, etc.) se guarda con su propia clave.

### 4.6 Validaciones antes de habilitar `Procesar`

- `validar_archivo(path, extensiones)` -> lista de issues con `code` + `message`.
- `validar_estado_mensual(estado_dir, mes_yyyymm)` -> faltante crea boton `Generar estado inicial`.
- `aggregate_messages(issues)` -> strings legibles para `messagebox.showerror`.
- `can_enable_process(paths, issues)` -> bool; solo entonces el boton `Procesar` queda `normal`.

### 4.7 Runtime paths con override por env (`core/runtime_paths.py`)

Resolucion en cascada (de mayor a menor prioridad):

1. `--estado` / `--salida` (CLI explicit).
2. `NARANJAX_ESTADO_DIR` / `NARANJAX_OUTPUT_DIR` (env vars renombrar al proyecto).
3. `NARANJAX_RUNTIME_BASE_DIR` (fallback comun).
4. Lo guardado en config JSON.
5. Default hardcodeado (carpeta de persistencia conocida).

Esto permite que UAT corra apuntando a `C:\TEMP\...` sin tocar produccion.

## 5) Packaging — PyInstaller

### 5.1 Spec (`packaging/<app_name>.spec`)

Puntos no negociables:

- `console=False` (UI Windows, sin consola).
- `pathex` incluye el root + cualquier subpaquete del ETL (ej. `back-base`, `back-resultados`).
- `hiddenimports += collect_submodules("customtkinter")` y `collect_submodules("<paquete_etl>")` por cada paquete propio del ETL.
- `datas` incluye `packaging/assets` si existe.
- `excludes=["tkinter.test", "test", "unittest"]` para reducir tamanio.

Plantilla minima:

```python
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

PROJECT_ROOT = Path(SPECPATH).parent
hiddenimports = []
hiddenimports += collect_submodules("customtkinter")
hiddenimports += collect_submodules("<paquete_etl_1>")
# repetir por cada paquete propio

datas = []
assets = PROJECT_ROOT / "packaging" / "assets"
if assets.exists():
    datas.append((str(assets), "assets"))

a = Analysis(
    [str(PROJECT_ROOT / "<app_name>.py")],
    pathex=[str(PROJECT_ROOT), str(PROJECT_ROOT / "<subpaquete>")],
    binaries=[], datas=datas, hiddenimports=hiddenimports,
    excludes=["tkinter.test", "test", "unittest"], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
    name="<app_name>", debug=False, strip=False, upx=False, console=False)
```

### 5.2 Build trazable (`packaging/build.bat`)

Comportamientos obligatorios:

1. Detectar `BRANCH_NAME` via `git rev-parse --abbrev-ref HEAD` (fallback `unknown`, `HEAD` -> `detached-head`).
2. Detectar `COMMIT_SHORT` via `git rev-parse --short HEAD`.
3. Detectar `BUILD_DIRTY` via `git status --porcelain`. Si dirty y no `ALLOW_DIRTY_BUILD=1`, **abortar** con exit 1.
4. Normalizar `/` y `\` -> `-` en rama para nombre de carpeta valido.
5. Output a `dist-<BRANCH_SAFE>-<COMMIT_SAFE>\<app>.exe`, override por `DIST_DIR`.
6. Soportar `BUILD_DRY_RUN=1` (imprime variables y no compila).
7. Limpia `build\` y `<DIST_PATH>` previos. Falla rapido si el `.exe` esta bloqueado por otro proceso.
8. Emite `build-info.txt` con `branch=`, `commit=`, `timestamp=` (ISO), `dirty=true/false`.
9. Sugiere comandos de smoke al final (doble clic + `--cli --base ...`).

## 6) UAT — criterios PASS

(Replicar en `packaging/BUILD.md` con rutas del proyecto destino.)

- `dist-<rama>-<commit>\<app>.exe` abre por doble clic, sin popup de dependencia faltante.
- Cold start: cerrar, reiniciar sesion, reabrir -> abre OK.
- Si no hay `estado_YYMM.csv`, el boton `Generar estado inicial` lo crea y habilita `Procesar`.
- CLI valido retorna `exit code 0` y escribe solo en rutas temporales pasadas con `--salida` / `--estado`.
- CLI invalido (ej. `--arg-no-existe`) retorna `exit code != 0`.
- `build-info.txt` existe y refleja `branch=` / `commit=` esperados.

## 7) Checklist de adaptacion al ETL destino

Al portar este patron a otro ETL, completar en este orden:

1. [ ] Identificar la funcion entry del ETL existente (la equivalente a `procesar_dia`). Si no existe, refactorizar primero para que reciba `(config, archivos, log_cb)` y retorne un resultado tipado.
2. [ ] Definir `ConfigXxx` y `ArchivosXxx` segun inputs reales del ETL (base mensual, diarios, parametros).
3. [ ] Listar paquetes propios del ETL para `collect_submodules` y `pathex` en el spec.
4. [ ] Renombrar env vars (`NARANJAX_*` -> `<PROYECTO>_*`) y el default de persistencia en `runtime_paths.py`.
5. [ ] Adaptar pickers en `principal.py`: titulos, extensiones permitidas, validadores por tipo.
6. [ ] Adaptar el resumen en `resultado.py` a los campos reales del `Resultado` del ETL.
7. [ ] Renombrar `<app_name>` en spec, build.bat, entry point.
8. [ ] Probar `set BUILD_DRY_RUN=1 && packaging\build.bat` antes del build real.
9. [ ] Build real, validar UAT secciones 2-5 de `BUILD.md`.
10. [ ] Commitear todo limpio antes del build de release (la skill prohibe `ALLOW_DIRTY_BUILD` para releases).

## 8) Anti-patrones (no hacer)

- Llamar al ETL desde el hilo de UI (congela la ventana, parece colgada).
- Duplicar la logica del ETL en CLI vs UI: deben converger en una sola funcion.
- `console=True` en el spec final (abre consola negra al lanzar el .exe).
- Hardcodear paths productivos: siempre via `runtime_paths` con override por env.
- Build dirty para release: el `dirty=true` en `build-info.txt` invalida la trazabilidad.
- Pickers que habiliten `Procesar` sin pasar validaciones: el boton arranca disabled y solo se habilita con `can_enable_process(...) == True`.

## 9) Referencias del proyecto fuente

- Entry: `naranjax_etl.py`
- Router UI: `ui/app.py`
- Pantalla principal: `ui/screens/principal.py`
- Worker: `ui/worker.py`
- CLI: `cli/main.py`
- Resolucion de paths: `core/runtime_paths.py`
- Spec PyInstaller: `packaging/naranjax_etl.spec`
- Build trazable: `packaging/build.bat`
- UAT: `packaging/BUILD.md`
