"""
Entrypoint principal para ejecutar procesos de back-resultados
"""
import argparse
import sys
from pathlib import Path

# Agregar el directorio procesos al path para importar retell-manager
procesos_dir = Path(__file__).parent / "procesos"
sys.path.insert(0, str(procesos_dir))

# Importar usando importlib para manejar el guión en el nombre del archivo
import importlib.util

retell_manager_path = procesos_dir / "retell-manager.py"
spec = importlib.util.spec_from_file_location("retell_manager_module", retell_manager_path)
retell_manager = importlib.util.module_from_spec(spec)
# Establecer el módulo en sys.modules antes de ejecutarlo para evitar problemas con dataclasses
sys.modules["retell_manager_module"] = retell_manager
spec.loader.exec_module(retell_manager)


def cmd_retell(args):
    """Ejecuta el proceso de enriquecimiento de Retell"""
    # Las rutas se calculan desde back-resultados/ (donde está main.py)
    base_dir = Path(__file__).resolve().parent
    input_dir = base_dir / "retell"
    output_dir = base_dir / "results"
    
    # Importar funciones necesarias
    find_latest_csv = retell_manager.find_latest_csv
    enrich_csv = retell_manager.enrich_csv
    
    # Buscar el CSV más reciente
    try:
        input_csv = find_latest_csv(input_dir, glob_pattern="export_*.csv")
    except FileNotFoundError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    
    # Crear directorio de salida si no existe
    output_dir.mkdir(parents=True, exist_ok=True)
    output_csv = output_dir / f"{input_csv.stem}_enriched.csv"
    
    # Ejecutar el enriquecimiento
    try:
        out = enrich_csv(input_csv, output_csv)
        print(f"[OK] Generado -> {out}")
    except Exception as e:
        print(f"[ERROR] Durante el enriquecimiento: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_tipif(args):
    """Genera el CSV de tipificaciones para Fravega Evoltis"""
    # Importar tipif_generator
    procesos_dir = Path(__file__).parent / "procesos"
    sys.path.insert(0, str(procesos_dir))
    
    import importlib.util
    tipif_generator_path = procesos_dir / "tipif_generator.py"
    spec = importlib.util.spec_from_file_location("tipif_generator_module", tipif_generator_path)
    tipif_generator = importlib.util.module_from_spec(spec)
    sys.modules["tipif_generator_module"] = tipif_generator
    spec.loader.exec_module(tipif_generator)
    
    # Ejecutar el generador
    try:
        tipif_generator.main()
    except Exception as e:
        print(f"[ERROR] Durante la generacion: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def cmd_update_tipif(args):
    """Actualiza la columna Tipificacion con datos del export de Retell"""
    # Importar tipif_updater
    procesos_dir = Path(__file__).parent / "procesos"
    sys.path.insert(0, str(procesos_dir))
    
    import importlib.util
    tipif_updater_path = procesos_dir / "tipif_updater.py"
    spec = importlib.util.spec_from_file_location("tipif_updater_module", tipif_updater_path)
    tipif_updater = importlib.util.module_from_spec(spec)
    sys.modules["tipif_updater_module"] = tipif_updater
    spec.loader.exec_module(tipif_updater)
    
    # Ejecutar el actualizador
    try:
        tipif_updater.main()
    except Exception as e:
        print(f"[ERROR] Durante la actualizacion: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="back-resultados",
        description="Procesos de enriquecimiento de datos de Retell"
    )
    
    subparsers = parser.add_subparsers(dest="cmd", help="Comando a ejecutar")
    
    # Comando retell
    retell_parser = subparsers.add_parser(
        "retell",
        help="Enriquece el último export_*.csv de Retell y guarda el CSV en results/"
    )
    
    # Comando tipif
    tipif_parser = subparsers.add_parser(
        "tipif",
        help="Genera CSV de tipificaciones fravega_gestiones_evoltis_AAAAMMDD.csv con variables específicas"
    )
    
    # Comando update-tipif
    update_tipif_parser = subparsers.add_parser(
        "update-tipif",
        help="Actualiza la columna Tipificacion del CSV de resultados con datos del export de Retell"
    )
    
    args = parser.parse_args()
    
    if not args.cmd:
        parser.print_help()
        sys.exit(1)
    
    if args.cmd == "retell":
        cmd_retell(args)
    elif args.cmd == "tipif":
        cmd_tipif(args)
    elif args.cmd == "update-tipif":
        cmd_update_tipif(args)
    else:
        print(f"[ERROR] Comando desconocido: {args.cmd}", file=sys.stderr)
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
