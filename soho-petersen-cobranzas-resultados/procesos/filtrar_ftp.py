"""
Script para filtrar archivos CSV de gestiones por EFECTO.

Toma los archivos CSV de la carpeta 'ftp/' y filtra las llamadas cuyos registros poseen:
- PROMESA DE PAGO
- NOTIFICADO TITULAR
- NOTIFICADO FLIAR
- YA PAGO

Los archivos filtrados se guardan en la carpeta 'sub_ftp/' dentro del mismo directorio de origen.

Adicionalmente, para archivos AG002_48.csv se genera un archivo 'promesas_bco_SJ.csv'
con los registros filtrados por los efectos válidos.

Uso:
    python filtrar_ftp.py <ruta_carpeta_ftp>

Ejemplo:
    python filtrar_ftp.py gestiones-validas/Gestiones_Petersen_20260122/archivos_codificacion/ftp
"""

import csv
import os
import sys
from pathlib import Path


EFECTOS_VALIDOS = [
    'PROMESA DE PAGO',
    'NOTIFICADO TITULAR',
    'NOTIFICADO FLIAR',
    'YA PAGO'
]

COLUMNA_EFECTO = 6  # Índice 6 = columna 7 (EFECTO)

# Mapeo de archivos AG002_48 a nombres de archivos de promesas por banco
MAPEO_PROMESAS = {
    'AG002_48.csv': 'promesas_bco_SJ.csv',  # San Juan
}


def filtrar_archivo(archivo_entrada: Path, archivo_salida: Path) -> tuple[int, int]:
    """
    Filtra un archivo CSV por los efectos válidos.

    Returns:
        tuple: (registros_originales, registros_filtrados)
    """
    with open(archivo_entrada, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        filas = list(reader)

    if not filas:
        return 0, 0

    header = filas[0]
    datos = filas[1:]

    # Filtrar por columna EFECTO
    filtrados = [header]
    for fila in datos:
        if len(fila) > COLUMNA_EFECTO and fila[COLUMNA_EFECTO] in EFECTOS_VALIDOS:
            filtrados.append(fila)

    # Guardar archivo filtrado
    with open(archivo_salida, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerows(filtrados)

    return len(datos), len(filtrados) - 1


def generar_archivo_promesas(archivo_entrada: Path, archivo_salida: Path) -> int:
    """
    Genera un archivo con los registros filtrados por efectos válidos.

    Returns:
        int: cantidad de registros filtrados
    """
    with open(archivo_entrada, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f, delimiter=';')
        filas = list(reader)

    if not filas:
        return 0

    header = filas[0]
    datos = filas[1:]

    # Filtrar por efectos válidos
    filtrados = [header]
    for fila in datos:
        if len(fila) > COLUMNA_EFECTO and fila[COLUMNA_EFECTO] in EFECTOS_VALIDOS:
            filtrados.append(fila)

    # Guardar archivo filtrado
    with open(archivo_salida, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerows(filtrados)

    return len(filtrados) - 1


def procesar_carpeta_ftp(carpeta_ftp: str) -> None:
    """
    Procesa todos los archivos CSV en la carpeta ftp y guarda los filtrados en sub_ftp.
    """
    carpeta_ftp = Path(carpeta_ftp)

    if not carpeta_ftp.exists():
        print(f"Error: La carpeta '{carpeta_ftp}' no existe.")
        sys.exit(1)

    # Crear carpeta sub_ftp en el mismo nivel que ftp
    carpeta_salida = carpeta_ftp.parent / 'sub_ftp'
    carpeta_salida.mkdir(exist_ok=True)

    # Buscar archivos CSV
    archivos_csv = list(carpeta_ftp.glob('*.csv'))

    if not archivos_csv:
        print(f"No se encontraron archivos CSV en '{carpeta_ftp}'")
        return

    print(f"\nProcesando {len(archivos_csv)} archivo(s) de '{carpeta_ftp}'")
    print(f"Guardando en '{carpeta_salida}'")
    print("-" * 60)

    total_originales = 0
    total_filtrados = 0

    archivos_promesas = []

    for archivo in archivos_csv:
        archivo_salida = carpeta_salida / archivo.name
        originales, filtrados = filtrar_archivo(archivo, archivo_salida)

        print(f"{archivo.name}: {originales} registros -> {filtrados} filtrados")
        total_originales += originales
        total_filtrados += filtrados

        # Si es un archivo AG002_48, generar archivo de promesas
        if archivo.name in MAPEO_PROMESAS:
            nombre_promesas = MAPEO_PROMESAS[archivo.name]
            archivo_promesas = carpeta_salida / nombre_promesas
            num_promesas = generar_archivo_promesas(archivo, archivo_promesas)
            archivos_promesas.append((nombre_promesas, num_promesas))

    print("-" * 60)
    print(f"TOTAL: {total_originales} registros originales -> {total_filtrados} registros filtrados")

    if archivos_promesas:
        print("\nArchivos adicionales generados:")
        for nombre, cantidad in archivos_promesas:
            print(f"  - {nombre}: {cantidad} registros")

    print(f"\nArchivos guardados en: {carpeta_salida}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nEfectos válidos:")
        for efecto in EFECTOS_VALIDOS:
            print(f"  - {efecto}")
        sys.exit(0)

    carpeta_ftp = sys.argv[1]
    procesar_carpeta_ftp(carpeta_ftp)


if __name__ == '__main__':
    main()
