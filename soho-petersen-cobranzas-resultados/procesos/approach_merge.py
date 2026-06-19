"""
Módulo para fusionar reportes de approach con la base de datos.

Toma el reporte de la carpeta approach (excluyendo filas con RESULT="10"),
busca cada PHONE en la base (TEL1, TEL2, TEL3, TEL4) y genera un CSV en debug
con PHONE, RESULT, DAT3 (número de cliente), DAT6 y SUCURSAL para las filas que matchearon.

Además, puede generar tipificaciones "NO RESPONDE OCUPADO" para clientes que aún no
tienen tipificación en gestiones-validas, agregándolas a los archivos correspondientes
según el banco (DAT6).
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from procesos.paths import get_project_root

# Mapeo DAT6 (base) -> nombre del banco (gestiones-validas)
# Debe coincidir con MAPEO_BANCOS en promesa_validator
DAT6_TO_BANK: Dict[str, str] = {
    "Banco de Entre Ríos": "Entre Ríos",
    "Banco de Entre Rios": "Entre Ríos",
    "Banco de Santa Fe": "Santa Fe",
    "Banco de Santa Cruz": "Santa Cruz",
    "Banco de San Juan": "San Juan",
}

# Códigos de archivo por banco (igual que promesa_validator)
BANK_TO_CODIGO: Dict[str, Tuple[str, str]] = {
    "Santa Fe": ("AG002_45", "BSF"),
    "Entre Ríos": ("AG002_46", "BER"),
    "Santa Cruz": ("AG002_47", "BSC"),
    "San Juan": ("AG002_48", "BSJ"),
}

# Header estándar para archivos de gestiones (19 columnas)
_GESTIONES_HEADER = (
    "Usuario asignado;GESTION_RELACIONADA;TIPO_PROMESA;NRO_CLIENTE;SUCURSAL;ACCION;"
    "EFECTO;CONTACTO;MOTIVO_ATRASO;OBSERVACIONES_GESTION;NRO_PRODUCTO;SUC_PRODUCTO;"
    "TIPO_PROD;FECHA_ALTA;FECHA_PROMESA;MONTO_PROMESA;CANAL_DE_PAGO;PUNTAJE_PROMESA;"
    "OBSERVACIONES_PROMESA"
)


def _normalize_phone(phone: str) -> str:
    """Normaliza un número de teléfono para comparación."""
    if not phone:
        return ""
    return str(phone).strip().strip('"')


def _resolve_field(fields: list[str], candidates: list[str]) -> Optional[str]:
    """
    Devuelve el nombre real de la columna que matchea con alguno de los
    candidatos, de forma case-insensitive.
    """
    lower_map = {f.lower(): f for f in fields}
    for cand in candidates:
        if cand.lower() in lower_map:
            return lower_map[cand.lower()]
    return None


def _build_phone_to_base_lookup(base_path: Path) -> dict[str, tuple[str, str, str]]:
    """
    Construye un diccionario phone -> (nro_cliente, banco, sucursal) a partir del CSV de base.

    Soporta distintos formatos de export:
    - Base antigua: columnas TEL1..TEL4, DAT3, DAT6, SUCURSAL
    - Base nueva:   columnas tel1..tel4, numero_cliente, dat6, sucursal

    El match se hace case-insensitive y se aceptan alias conocidos para
    el identificador de cliente.
    """
    lookup: dict[str, tuple[str, str, str]] = {}

    with open(base_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        fields = reader.fieldnames or []

        tel_cols = [
            _resolve_field(fields, [f"TEL{i}", f"tel{i}"]) for i in range(1, 5)
        ]
        tel_cols = [c for c in tel_cols if c]
        dat3_field = _resolve_field(fields, ["DAT3", "dat3", "numero_cliente", "NUMERO_CLIENTE"])
        dat6_field = _resolve_field(fields, ["DAT6", "dat6"])
        sucursal_field = _resolve_field(fields, ["SUCURSAL", "sucursal"])

        if not dat3_field or not tel_cols:
            return lookup

        for row in reader:
            dat3 = _normalize_phone(row.get(dat3_field, ""))
            dat6 = _normalize_phone(row.get(dat6_field, "")) if dat6_field else ""
            sucursal = _normalize_phone(row.get(sucursal_field, "")) if sucursal_field else ""
            if not dat3:
                continue
            for tel_col in tel_cols:
                phone = _normalize_phone(row.get(tel_col, ""))
                if phone and phone not in lookup:
                    lookup[phone] = (dat3, dat6, sucursal)

    return lookup


def _get_latest_csv(folder: Path) -> Optional[Path]:
    """Obtiene el CSV más reciente en la carpeta."""
    csv_files = list(folder.glob("*.csv"))
    if not csv_files:
        return None
    return max(csv_files, key=lambda p: p.stat().st_mtime)


def _sanitize_for_csv(text: str) -> str:
    """Sanitiza texto para CSV: remueve comillas y reemplaza ';' por ','."""
    if not text:
        return ""
    return str(text).replace('"', "").replace("'", "").replace(";", ",")


def _dat6_to_bank(dat6: str) -> Optional[str]:
    """Mapea DAT6 (ej: 'Banco de Entre Ríos') al nombre del banco para gestiones-validas."""
    dat6_clean = (dat6 or "").strip()
    return DAT6_TO_BANK.get(dat6_clean)


def _get_existing_nro_clientes(gestiones_dir: Path) -> Set[str]:
    """Obtiene el set de NRO_CLIENTE ya presentes en los 4 archivos de archivos_codificacion."""
    existentes: Set[str] = set()
    carpeta_codificacion = gestiones_dir / "archivos_codificacion"
    if not carpeta_codificacion.exists():
        return existentes

    for codigo, _ in BANK_TO_CODIGO.values():
        archivo = carpeta_codificacion / f"{codigo}.csv"
        if not archivo.exists():
            continue
        try:
            with open(archivo, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    nro = (row.get("NRO_CLIENTE") or "").strip()
                    if nro:
                        existentes.add(nro)
        except Exception:
            continue
    return existentes


def _build_tipification_line(dat3: str, sucursal: str, fecha_hoy: str) -> str:
    """Construye la línea de tipificación 'NO RESPONDE OCUPADO' para añadir a gestiones-validas."""
    obs = _sanitize_for_csv("Cliente no responde.")
    return (
        f"scesano;;PRINCIPAL;{dat3};{sucursal};LLAMADA SALIENTE;NO RESPONDE OCUPADO;BLANK;;{obs};;;;{fecha_hoy};;;;;"
    )


def _append_tipification_to_gestiones(
    gestiones_dir: Path,
    banco: str,
    linea: str,
) -> None:
    """Añade una línea de tipificación a archivos_codificacion, archivos_nombre y archivos_fechas_originales."""
    if banco not in BANK_TO_CODIGO:
        return
    codigo, sigla = BANK_TO_CODIGO[banco]
    carpetas = [
        gestiones_dir / "archivos_codificacion",
        gestiones_dir / "archivos_nombre",
        gestiones_dir / "archivos_fechas_originales",
    ]
    archivos = [
        f"{codigo}.csv",
        f"gestiones_validas_{sigla}.csv",
        f"gestiones_originales_{sigla}.csv",
    ]
    for carpeta, nombre in zip(carpetas, archivos):
        archivo = carpeta / nombre
        carpeta.mkdir(parents=True, exist_ok=True)
        if archivo.exists():
            with open(archivo, "a", encoding="utf-8-sig", newline="") as f:
                f.write(linea + "\r\n")
        else:
            with open(archivo, "w", encoding="utf-8-sig", newline="") as f:
                f.write(_GESTIONES_HEADER + "\r\n" + linea + "\r\n")


def run_approach_merge(
    approach_folder: Optional[Path] = None,
    base_folder: Optional[Path] = None,
    debug_folder: Optional[Path] = None,
) -> Path:
    """
    Ejecuta el merge de approach con la base.

    Args:
        approach_folder: Carpeta con reportes approach (default: approach/)
        base_folder: Carpeta con CSV de base (default: base/)
        debug_folder: Carpeta de salida (default: debug/)

    Returns:
        Path del archivo CSV generado en debug.

    Raises:
        FileNotFoundError: Si no hay archivos en approach o base.
    """
    proyecto = get_project_root()
    approach_dir = approach_folder or proyecto / "approach"
    base_dir = base_folder or proyecto / "base"
    debug_dir = debug_folder or proyecto / "debug"

    approach_file = _get_latest_csv(approach_dir)
    if not approach_file:
        raise FileNotFoundError(f"No se encontró ningún CSV en {approach_dir}")

    base_file = _get_latest_csv(base_dir)
    if not base_file:
        raise FileNotFoundError(f"No se encontró ningún CSV en {base_dir}")

    phone_to_base = _build_phone_to_base_lookup(base_file)

    resultados: list[tuple[str, str, str, str, str]] = []

    with open(approach_file, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if "PHONE" not in (reader.fieldnames or []):
            raise ValueError(f"El archivo {approach_file.name} no tiene columna PHONE")
        if "RESULT" not in (reader.fieldnames or []):
            raise ValueError(f"El archivo {approach_file.name} no tiene columna RESULT")

        for row in reader:
            result = _normalize_phone(row.get("RESULT", ""))
            if result == "10":
                continue
            phone = _normalize_phone(row.get("PHONE", ""))
            if not phone:
                continue
            base_data = phone_to_base.get(phone)
            if base_data is not None:
                dat3, dat6, sucursal = base_data
                resultados.append((phone, result, dat3, dat6, sucursal))

    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = debug_dir / f"approach_merge_{timestamp}.csv"

    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PHONE", "RESULT", "DAT3", "DAT6", "SUCURSAL"])
        writer.writerows(resultados)

    return output_path


def run_approach_merge_and_tipify(
    gestiones_dir: Path,
    approach_folder: Optional[Path] = None,
    base_folder: Optional[Path] = None,
    debug_folder: Optional[Path] = None,
) -> Tuple[Path, Dict[str, int]]:
    """
    Ejecuta el merge de approach con la base y genera tipificaciones "NO RESPONDE OCUPADO"
    para clientes que aún no tienen tipificación en gestiones-validas.

    Para cada fila matcheada: si el DAT3 (NRO_CLIENTE) no existe ya en los archivos de
    gestiones-validas, se genera una tipificación y se añade al archivo del banco
    correspondiente según DAT6.

    Args:
        gestiones_dir: Ruta a Gestiones_Petersen_AAAAMMDD (ej: gestiones-validas/Gestiones_Petersen_20260210)
        approach_folder: Carpeta con reportes approach (default: approach/)
        base_folder: Carpeta con CSV de base (default: base/)
        debug_folder: Carpeta de salida para el CSV de debug (default: debug/)

    Returns:
        Tupla (path_del_csv_debug, estadisticas) donde estadisticas tiene:
        - total_matcheados: filas que matchearon con la base
        - ya_tipificados: clientes que ya tenían tipificación (se omiten)
        - banco_desconocido: clientes cuyo DAT6 no mapea a banco conocido
        - tipificaciones_agregadas: total de tipificaciones añadidas
    """
    proyecto = get_project_root()
    approach_dir = approach_folder or proyecto / "approach"
    base_dir = base_folder or proyecto / "base"
    debug_dir = debug_folder or proyecto / "debug"

    stats: Dict[str, int] = {
        "total_matcheados": 0,
        "ya_tipificados": 0,
        "banco_desconocido": 0,
        "tipificaciones_agregadas": 0,
    }

    # 1. Ejecutar merge (obtener resultados)
    approach_file = _get_latest_csv(approach_dir)
    if not approach_file:
        raise FileNotFoundError(f"No se encontró ningún CSV en {approach_dir}")

    base_file = _get_latest_csv(base_dir)
    if not base_file:
        raise FileNotFoundError(f"No se encontró ningún CSV en {base_dir}")

    print(f"  [1/5] Cargando base de teléfonos desde {base_file.name}...")
    phone_to_base = _build_phone_to_base_lookup(base_file)
    resultados: list[tuple[str, str, str, str, str]] = []

    print(f"  [2/5] Leyendo approach {approach_file.name}...")
    with open(approach_file, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if "PHONE" not in (reader.fieldnames or []):
            raise ValueError(f"El archivo {approach_file.name} no tiene columna PHONE")
        if "RESULT" not in (reader.fieldnames or []):
            raise ValueError(f"El archivo {approach_file.name} no tiene columna RESULT")

        for row in reader:
            result = _normalize_phone(row.get("RESULT", ""))
            if result == "10":
                continue
            phone = _normalize_phone(row.get("PHONE", ""))
            if not phone:
                continue
            base_data = phone_to_base.get(phone)
            if base_data is not None:
                dat3, dat6, sucursal = base_data
                resultados.append((phone, result, dat3, dat6, sucursal))

    stats["total_matcheados"] = len(resultados)
    print(f"  [3/5] {stats['total_matcheados']} matcheos encontrados")

    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = debug_dir / f"approach_merge_{timestamp}.csv"
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["PHONE", "RESULT", "DAT3", "DAT6", "SUCURSAL"])
        writer.writerows(resultados)

    existentes = _get_existing_nro_clientes(gestiones_dir)

    vistos: Set[str] = set()
    resultados_unicos: list[tuple[str, str, str]] = []
    for _, _, dat3, dat6, sucursal in resultados:
        if dat3 in vistos:
            continue
        vistos.add(dat3)
        resultados_unicos.append((dat3, dat6, sucursal))

    total_unicos = len(resultados_unicos)
    print(f"  [4/5] Deduplicados: {total_unicos} clientes únicos")
    print(f"  [5/5] Generando tipificaciones (puede tomar unos minutos)...")
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    procesados = 0
    for dat3, dat6, sucursal in resultados_unicos:
        procesados += 1
        if procesados % 2000 == 0:
            print(f"        ... {procesados}/{total_unicos} procesados")
        if dat3 in existentes:
            stats["ya_tipificados"] += 1
            continue
        banco = _dat6_to_bank(dat6)
        if banco is None:
            stats["banco_desconocido"] += 1
            continue
        linea = _build_tipification_line(dat3, sucursal, fecha_hoy)
        _append_tipification_to_gestiones(gestiones_dir, banco, linea)
        stats["tipificaciones_agregadas"] += 1
        existentes.add(dat3)

    return output_path, stats


def run_tipify_excluded(
    gestiones_dir: Path,
    excluded_folder: Optional[Path] = None,
) -> Dict[str, int]:
    """
    Genera tipificaciones "NO RESPONDE OCUPADO" para clientes excluidos de la campaña
    a partir de la base en datos-excluidos.

    La base de datos excluidos tiene el mismo formato que la base original (DAT3, DAT6, SUCURSAL).
    Para cada fila: si el DAT3 (NRO_CLIENTE) no existe ya en los archivos de gestiones-validas,
    se genera una tipificación y se añade al archivo del banco correspondiente según DAT6.

    Args:
        gestiones_dir: Ruta a Gestiones_Petersen_AAAAMMDD (ej: gestiones-validas/Gestiones_Petersen_20260210)
        excluded_folder: Carpeta con CSV de datos excluidos (default: datos-excluidos/)

    Returns:
        Diccionario de estadísticas con:
        - total_excluidos: clientes únicos leídos desde datos-excluidos
        - excluidos_ya_tipificados: clientes que ya tenían tipificación (se omiten)
        - excluidos_banco_desconocido: clientes cuyo DAT6 no mapea a banco conocido
        - tipificaciones_excluidos_agregadas: total de tipificaciones añadidas
    """
    proyecto = get_project_root()
    excluded_dir = excluded_folder or proyecto / "datos-excluidos"

    stats: Dict[str, int] = {
        "total_excluidos": 0,
        "excluidos_ya_tipificados": 0,
        "excluidos_banco_desconocido": 0,
        "tipificaciones_excluidos_agregadas": 0,
    }

    excluded_file = _get_latest_csv(excluded_dir)
    if not excluded_file:
        raise FileNotFoundError(f"No se encontró ningún CSV en {excluded_dir}")

    dat3_col = "DAT3"
    dat6_col = "DAT6"
    sucursal_col = "SUCURSAL"

    resultados_unicos: list[tuple[str, str, str]] = []
    vistos: Set[str] = set()

    with open(excluded_file, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        fields = reader.fieldnames or []
        if dat3_col not in fields:
            raise ValueError(f"El archivo {excluded_file.name} no tiene columna {dat3_col}")

        for row in reader:
            dat3 = _normalize_phone(row.get(dat3_col, ""))
            if not dat3:
                continue
            if dat3 in vistos:
                continue
            vistos.add(dat3)

            dat6 = _normalize_phone(row.get(dat6_col, ""))
            sucursal = _normalize_phone(row.get(sucursal_col, ""))
            resultados_unicos.append((dat3, dat6, sucursal))

    stats["total_excluidos"] = len(resultados_unicos)

    existentes = _get_existing_nro_clientes(gestiones_dir)

    fecha_hoy = datetime.now().strftime("%d/%m/%Y")
    for dat3, dat6, sucursal in resultados_unicos:
        if dat3 in existentes:
            stats["excluidos_ya_tipificados"] += 1
            continue
        banco = _dat6_to_bank(dat6)
        if banco is None:
            stats["excluidos_banco_desconocido"] += 1
            continue
        linea = _build_tipification_line(dat3, sucursal, fecha_hoy)
        _append_tipification_to_gestiones(gestiones_dir, banco, linea)
        stats["tipificaciones_excluidos_agregadas"] += 1
        existentes.add(dat3)  # Evitar duplicados si el mismo cliente aparece en otro banco

    return stats


if __name__ == "__main__":
    out = run_approach_merge()
    print(f"Archivo generado: {out}")
    print(f"Filas escritas: {sum(1 for _ in open(out, encoding='utf-8')) - 1}")
