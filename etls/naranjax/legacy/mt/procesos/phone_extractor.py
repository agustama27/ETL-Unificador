"""
Script para extraer los números de teléfono de la base procesada.
Genera un CSV con un registro por cliente y todos sus teléfonos agrupados.
"""

import csv
from pathlib import Path
from datetime import datetime

# Rutas base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
BACK_BASE_DIR = BASE_DIR / "back-base"
BASE_PROCESADA_DIR = BACK_BASE_DIR / "base_procesada"
SALIDA_DIR = BASE_PROCESADA_DIR

# Delimitadores: ";" para compatibilidad con Excel en español (Argentina/Latinoamérica)
DELIMITER_ENTRADA = ";"
DELIMITER_SALIDA = ";"

# Columnas a extraer: solo teléfonos y customer_id al final
HEADER_SALIDA = "TEL1,TEL2,TEL3,TEL4,TEL5,TEL6,customer_id"

# Índices de columnas en el CSV de base_procesada
COL_CUSTOMER_ID = 0
COL_NOMBRE = 1
COL_TEL_1 = 2
COL_TEL_2 = 3
COL_TEL_3 = 4
COL_TEL_4 = 5
COL_TEL_5 = 6
COL_TEL_6 = 7


def extraer_telefonos(archivo_entrada: Path | None = None, output_dir: Path | None = None) -> Path:
    """
    Lee el CSV de base_procesada y extrae customer_id, nombre y teléfonos.
    Genera telefonos_naranja_DDMMAAAA.csv con un registro por cliente.

    Args:
        archivo_entrada: Ruta al CSV. Si es None, usa el más reciente
            NARANJA_X_MT_*.csv (o base_naranja_*.csv por compatibilidad).

    Returns:
        Ruta al archivo CSV generado.

    Raises:
        FileNotFoundError: Si no hay archivos en base_procesada.
    """
    output_base_dir = Path(output_dir) if output_dir is not None else BASE_PROCESADA_DIR
    output_base_dir.mkdir(parents=True, exist_ok=True)

    if archivo_entrada is None:
        archivos = list(output_base_dir.glob("NARANJAX_MT_ROMAN_*.csv"))
        if not archivos:
            archivos = list(output_base_dir.glob("NARANJA_X_MT_*.csv"))
        if not archivos:
            archivos = list(output_base_dir.glob("base_naranja_*.csv"))
        if not archivos:
            raise FileNotFoundError(
                f"No se encontraron archivos NARANJAX_MT_ROMAN_*.csv, NARANJA_X_MT_*.csv ni base_naranja_*.csv en {output_base_dir}"
            )
        archivo_entrada = max(archivos, key=lambda p: p.stat().st_mtime)

    archivo_entrada = Path(archivo_entrada)
    if not archivo_entrada.exists():
        raise FileNotFoundError(f"El archivo no existe: {archivo_entrada}")

    # Nombre de salida: NARANJAX_MT_E1KIA_YYMMDD.csv
    fecha = datetime.now().strftime("%y%m%d")
    archivo_salida = output_base_dir / f"NARANJAX_MT_E1KIA_{fecha}.csv"

    with open(archivo_entrada, "r", encoding="utf-8", errors="replace") as f_in:
        lineas = f_in.readlines()

    if not lineas:
        raise ValueError("El archivo de entrada está vacío")

    header_entrada = lineas[0].strip()
    if not header_entrada.startswith("customer_id"):
        raise ValueError("El archivo no tiene el formato esperado (header con customer_id)")

    # Procesar y recolectar todas las filas
    filas = []
    for linea in lineas[1:]:
        linea = linea.strip()
        if not linea:
            continue

        columnas = linea.split(DELIMITER_ENTRADA)

        # Extraer columnas del cliente y teléfonos (asegurar al menos 9 columnas)
        customer_id = columnas[COL_CUSTOMER_ID] if len(columnas) > COL_CUSTOMER_ID else ""
        nombre = columnas[COL_NOMBRE] if len(columnas) > COL_NOMBRE else ""
        tel_1 = columnas[COL_TEL_1] if len(columnas) > COL_TEL_1 else ""
        tel_2 = columnas[COL_TEL_2] if len(columnas) > COL_TEL_2 else ""
        tel_3 = columnas[COL_TEL_3] if len(columnas) > COL_TEL_3 else ""
        tel_4 = columnas[COL_TEL_4] if len(columnas) > COL_TEL_4 else ""
        tel_5 = columnas[COL_TEL_5] if len(columnas) > COL_TEL_5 else ""
        tel_6 = columnas[COL_TEL_6] if len(columnas) > COL_TEL_6 else ""

        telefonos = [tel_1, tel_2, tel_3, tel_4, tel_5, tel_6]
        cantidad_tel = sum(1 for t in telefonos if t.strip())

        filas.append((cantidad_tel, tel_1, tel_2, tel_3, tel_4, tel_5, tel_6, customer_id))

    # Ordenar por cantidad de teléfonos (mayor primero)
    filas.sort(key=lambda x: x[0], reverse=True)

    with open(archivo_salida, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.writer(f_out, delimiter=DELIMITER_SALIDA)
        # Escribir header de salida
        writer.writerow(HEADER_SALIDA.split(","))

        # Escribir filas ordenadas: TEL 1-6 y customer_id al final
        for _, tel_1, tel_2, tel_3, tel_4, tel_5, tel_6, customer_id in filas:
            writer.writerow([tel_1, tel_2, tel_3, tel_4, tel_5, tel_6, customer_id])

    return archivo_salida


def main():
    """Punto de entrada del script."""
    import sys

    archivo = None
    if len(sys.argv) > 1:
        archivo = Path(sys.argv[1])
        if not archivo.is_absolute():
            archivo = BASE_DIR / archivo

    try:
        resultado = extraer_telefonos(archivo)
        print(f"Archivo de teléfonos generado: {resultado}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
