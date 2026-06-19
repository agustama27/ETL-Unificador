"""
Extractor de teléfonos únicos para cargar en Retell.

Input: base_clarouy_DDMMAAAA.csv
Output: telefonos_x_cliente_DDMMAAAA.csv (lista de MSISDN sin duplicados)
"""
from pathlib import Path
import pandas as pd

# ── Constants ──────────────────────────────────────────────────────────────────

# ── Functions ─────────────────────────────────────────────────────────────────

def buscar_base_generada(carpeta: Path) -> Path | None:
    """
    Busca el archivo de base más reciente en una carpeta.
    
    Args:
        carpeta: Ruta a la carpeta de búsqueda
    
    Returns:
        Ruta al archivo CSV encontrado o None
    """
    csvs = list(carpeta.glob("base_clarouy_*.csv"))
    if not csvs:
        return None
    return max(csvs, key=lambda p: p.stat().st_mtime)


def extraer_telefonos(base_path: Path, output_path: Path) -> int:
    """
    Extrae teléfonos únicos de la base consolidada.
    
    Args:
        base_path: Ruta al CSV de base consolidada
        output_path: Ruta para el archivo de salida
    
    Returns:
        Cantidad de teléfonos extraídos
    """
    print(f"\n  Leyendo base: {base_path.name}")
    
    df = pd.read_csv(base_path, sep=';', encoding='utf-8', dtype=str)
    
    telefonos = df['msisdn'].dropna().unique()
    telefonos = [str(t).replace('.0', '') for t in telefonos]
    telefonos = [t for t in telefonos if t and len(t) >= 12]
    telefonos = sorted(set(telefonos))
    
    print(f"  Teléfonos únicos encontrados: {len(telefonos)}")
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for telefono in telefonos:
            f.write(f"{telefono}\n")
    
    print(f"  Archivo generado: {output_path.name}")
    
    return len(telefonos)


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from datetime import datetime
    
    BASE_DIR = Path(__file__).parent.parent
    carpeta_base = BASE_DIR / "back-base" / "base-generada" / "con-filtros"
    
    base_path = buscar_base_generada(carpeta_base)
    if not base_path:
        print("ERROR: No se encontró base_clarouy_*.csv")
        print(f"Buscar en: {carpeta_base}")
    else:
        fecha = datetime.today().strftime('%d%m%Y')
        output_path = carpeta_base / f"telefonos_x_cliente_{fecha}.csv"
        
        cantidad = extraer_telefonos(base_path, output_path)
        print(f"\nOK: {cantidad} teléfonos extraídos")
