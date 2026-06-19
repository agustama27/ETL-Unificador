"""
Script para procesar archivos de base recibida: agregar header, convertir a CSV con delimitador ";"
y generar archivo en base_procesada.
"""

import os
from pathlib import Path
from datetime import datetime

# Rutas base del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
BACK_BASE_DIR = BASE_DIR / "back-base"
BASE_RECIBIDA_DIR = BACK_BASE_DIR / "base_recibida"
BASE_PROCESADA_DIR = BACK_BASE_DIR / "base_procesada"

# Header de salida (sin columna DNI)
HEADER = (
    "customer_id,NOMBRE Y APELLIDO,TEL1,TEL2,TEL3,TEL4,TEL5,TEL6,"
    "ESTRATEGIA,PROVEEDOR,TEL_TYPE1,TEL_TYPE2,TEL_TYPE3,TEL_TYPE4,TEL_TYPE5,TEL_TYPE6,"
    "prefijo1,prefijo2,prefijo3,prefijo4,prefijo5,"
    "MONTO ADEUDADO,FECHA DE VTO,account_number,RIESGO CREDITICIO"
)

# Delimitadores
INPUT_DELIMITER = "|"
OUTPUT_DELIMITER = ";"

# Número esperado de columnas en entrada
EXPECTED_COLUMNS = 33

# Índices de columnas TEL 1-6 y sus grupos correspondientes (AREA_CODE, telephone_number, TEL_TYPE)
# Cada TEL N se matchea con el grupo N por últimos 4 dígitos
TEL_COLUMNS = [2, 3, 4, 5, 6, 7]  # TEL 1 a TEL 6 (sin DNI en salida)
# Para cada grupo: (indice telephone_number, indice TEL_TYPE) en columnas de salida
TEL_GROUPS = [
    (10, 11),   # grupo 1
    (12, 13),   # grupo 2
    (14, 15),   # grupo 3
    (16, 17),   # grupo 4
    (18, 19),   # grupo 5
    (20, 21),   # grupo 6
]

MIN_DIGITS = 8
MAX_DIGITS = 11


def _solo_digitos(valor: str) -> str:
    return "".join(c for c in str(valor) if c.isdigit())


def _inferir_tel_type(digitos: str, area_code: str, base_nacional: str) -> str:
    if digitos.startswith("549"):
        return "CEL"

    for area_len in (4, 3, 2):
        if len(base_nacional) > area_len + 2 and base_nacional[area_len:area_len + 2] == "15":
            return "CEL"

    area = _solo_digitos(area_code).lstrip("0")
    if area and base_nacional.startswith(area):
        resto = base_nacional[len(area):]
        if resto.startswith("15") and len(resto) >= 8:
            return "CEL"

    return "TEL"


def _normalizar_telefono(tel_valor: str, columnas: list, grupo_preferido: int | None = None) -> str:
    """
    Normaliza un número de teléfono a formato internacional.
    - CEL: 549 + número (sin 0 inicial)
    - TEL: 54 + número (sin 0 inicial)

    Busca el grupo AREA_CODE/telephone_number/TEL_TYPE que corresponda
    comparando los últimos 4 dígitos del número con cada telephone_number.
    Si grupo_preferido está definido, se intenta primero ese grupo.
    """
    if not tel_valor or not tel_valor.strip():
        return tel_valor

    tel_valor = tel_valor.strip()
    # Extraer solo digitos para la comparacion
    digitos = _solo_digitos(tel_valor)
    if len(digitos) < 4:
        return tel_valor

    ultimos_4 = digitos[-4:]

    # Orden de búsqueda: grupo preferido primero (por posición TEL N -> grupo N), luego el resto
    orden_grupos = list(range(len(TEL_GROUPS)))
    if grupo_preferido is not None and 0 <= grupo_preferido < len(TEL_GROUPS):
        orden_grupos = [grupo_preferido] + [i for i in orden_grupos if i != grupo_preferido]

    tel_type = None
    for grupo_idx in orden_grupos:
        tel_num_idx, tel_type_idx = TEL_GROUPS[grupo_idx]
        if tel_num_idx < len(columnas):
            telephone_number = str(columnas[tel_num_idx]).strip()
            if len(telephone_number) >= 4 and telephone_number[-4:] == ultimos_4:
                tel_type = str(columnas[tel_type_idx]).strip() if tel_type_idx < len(columnas) else ""
                break

    # Normalizar base nacional para luego aplicar prefijo internacional
    base_nacional = digitos
    if base_nacional.startswith("549"):
        base_nacional = base_nacional[3:]
    elif base_nacional.startswith("54"):
        base_nacional = base_nacional[2:]
    base_nacional = base_nacional.lstrip("0")

    if len(base_nacional) > MAX_DIGITS:
        for area_len in (4, 3, 2):
            if len(base_nacional) > area_len + 2 and base_nacional[area_len:area_len + 2] == "15":
                candidato = base_nacional[:area_len] + base_nacional[area_len + 2:]
                if MIN_DIGITS <= len(candidato) <= MAX_DIGITS:
                    base_nacional = candidato
                    break

    if len(base_nacional) > MAX_DIGITS and base_nacional.startswith("11"):
        candidato = base_nacional[2:]
        if MIN_DIGITS <= len(candidato) <= MAX_DIGITS:
            base_nacional = candidato

    if not (MIN_DIGITS <= len(base_nacional) <= MAX_DIGITS):
        return tel_valor

    if not tel_type:
        tel_type = _inferir_tel_type(digitos, "", base_nacional)
    elif digitos.startswith("549"):
        tel_type = "CEL"
    elif digitos.startswith("54"):
        tel_type = "TEL"

    if tel_type == "CEL":
        for area_len in (4, 3, 2):
            if len(base_nacional) > area_len + 2 and base_nacional[area_len:area_len + 2] == "15":
                base_nacional = base_nacional[:area_len] + base_nacional[area_len + 2:]
                break

    if tel_type == "CEL":
        return "549" + base_nacional
    elif tel_type == "TEL":
        return "54" + base_nacional
    else:
        return tel_valor


def _procesar_linea_con_normalizacion(linea: str, delimiter: str) -> str:
    """Procesa una línea: normaliza los TEL 1-6 y aplica el delimitador de salida."""
    columnas = linea.split(delimiter)
    if len(columnas) != EXPECTED_COLUMNS:
        return linea.replace(delimiter, OUTPUT_DELIMITER)

    # Copiar DNI en customer_id y remover DNI de la salida
    if len(columnas) > 1:
        columnas[1] = columnas[0]
    prefijos = [
        columnas[12] if len(columnas) > 12 else "",
        columnas[15] if len(columnas) > 15 else "",
        columnas[18] if len(columnas) > 18 else "",
        columnas[21] if len(columnas) > 21 else "",
        columnas[24] if len(columnas) > 24 else "",
    ]
    columnas_trabajo = [
        col
        for idx, col in enumerate(columnas[1:])
        if idx not in {10, 13, 16, 19, 22, 25}
    ]

    # Normalizar cada columna TEL (TEL N usa grupo N-1 como preferido)
    for i, tel_col_idx in enumerate(TEL_COLUMNS):
        if tel_col_idx < len(columnas_trabajo) and columnas_trabajo[tel_col_idx]:
            columnas_trabajo[tel_col_idx] = _normalizar_telefono(
                columnas_trabajo[tel_col_idx], columnas_trabajo, grupo_preferido=i
            )

    # Eliminar columnas telephone_number
    columnas_salida = [
        col
        for idx, col in enumerate(columnas_trabajo)
        if idx not in {10, 12, 14, 16, 18, 20}
    ]

    # Agregar procesamiento de columnas solicitadas de entrada
    for i, valor in enumerate(prefijos):
        columnas_salida.insert(16 + i, valor)

    return OUTPUT_DELIMITER.join(columnas_salida)


def procesar_base(archivo_entrada: Path | None = None, output_dir: Path | None = None) -> Path:
    """
    Procesa un archivo TXT de base_recibida: agrega header, cambia delimitador a ";"
    y genera CSV en base_procesada.

    Args:
        archivo_entrada: Ruta al archivo TXT. Si es None, usa el más reciente en base_recibida.

    Returns:
        Ruta al archivo CSV generado.

    Raises:
        FileNotFoundError: Si no hay archivos TXT en base_recibida.
        ValueError: Si el número de columnas no coincide con lo esperado.
    """
    if archivo_entrada is None:
        archivos_txt = list(BASE_RECIBIDA_DIR.glob("*.txt"))
        if not archivos_txt:
            raise FileNotFoundError(
                f"No se encontraron archivos .txt en {BASE_RECIBIDA_DIR}"
            )
        archivo_entrada = max(archivos_txt, key=lambda p: p.stat().st_mtime)

    archivo_entrada = Path(archivo_entrada)
    if not archivo_entrada.exists():
        raise FileNotFoundError(f"El archivo no existe: {archivo_entrada}")

    output_base_dir = Path(output_dir) if output_dir is not None else BASE_PROCESADA_DIR
    output_base_dir.mkdir(parents=True, exist_ok=True)

    # Nombre de salida: NARANJAX_MT_ROMAN_YYMMDD.csv
    fecha = datetime.now().strftime("%y%m%d")
    archivo_salida = output_base_dir / f"NARANJAX_MT_ROMAN_{fecha}.csv"

    with open(archivo_entrada, "r", encoding="utf-8", errors="replace") as f_in:
        lineas = f_in.readlines()

    if not lineas:
        raise ValueError("El archivo de entrada está vacío")

    # Validar primera línea de datos
    primera_linea = lineas[0].strip()
    columnas_primera = primera_linea.split(INPUT_DELIMITER)
    if len(columnas_primera) != EXPECTED_COLUMNS:
        raise ValueError(
            f"Se esperaban {EXPECTED_COLUMNS} columnas, se detectaron {len(columnas_primera)}. "
            f"Revisar el archivo de entrada."
        )

    # Escribir archivo de salida con header y datos
    with open(archivo_salida, "w", encoding="utf-8", newline="") as f_out:
        # Escribir header (ya está en formato con comas, reemplazar por ;)
        header_csv = HEADER.replace(",", OUTPUT_DELIMITER)
        f_out.write(header_csv + "\n")

        # Escribir cada línea: normalizar teléfonos y aplicar delimitador
        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue
            linea_procesada = _procesar_linea_con_normalizacion(linea, INPUT_DELIMITER)
            f_out.write(linea_procesada + "\n")

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
        resultado = procesar_base(archivo)
        print(f"Archivo procesado correctamente: {resultado}")
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
