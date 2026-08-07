"""
Módulo de validación para promesas de pago en archivos CSV generados.

Valida que todas las promesas de pago (filas con EFECTO = "PROMESA DE PAGO") tengan
todos los campos requeridos completos y con valores válidos.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Importar función de validación de fecha promesa desde tipif_generator
from .tipif_generator import _validate_fecha_promesa, _es_dia_habil


@dataclass
class ValidationError:
    """Representa un error de validación en una promesa de pago."""
    banco: str
    fila: int
    nro_cliente: str
    campo: str
    problema: str
    valor_actual: str


@dataclass
class ValidationResult:
    """Resultado de la validación de promesas de pago."""
    total_promesas: int
    promesas_validas: int
    promesas_con_errores: int
    errores: List[ValidationError]
    archivos_analizados: List[str]


def _to_str(val: Optional[str]) -> str:
    """Convierte un valor a string, tratando None y valores vacíos."""
    if val is None:
        return ""
    return str(val).strip()


def _normalize_monto_promesa(monto_str: str) -> tuple[str, bool]:
    """
    Normaliza MONTO_PROMESA eliminando separador de miles, manteniendo coma como separador decimal.
    
    Ejemplo: "213.570,30" → "213570,30"
    
    Args:
        monto_str: String con el monto en formato español (puede tener separador de miles)
        
    Returns:
        Tupla (monto_normalizado, fue_corregido)
        - monto_normalizado: String con el monto sin separador de miles
        - fue_corregido: True si se aplicó alguna corrección, False si ya estaba normalizado
    """
    if not monto_str or monto_str.strip() == "":
        return monto_str, False
    
    monto_original = monto_str.strip()
    # Eliminar puntos (separadores de miles), mantener coma como separador decimal
    monto_normalizado = monto_original.replace(".", "")
    
    fue_corregido = monto_normalizado != monto_original
    return monto_normalizado, fue_corregido


def _truncate_motivo_atraso(motivo_str: str, max_length: int = 50) -> tuple[str, bool]:
    """
    Trunca MOTIVO_ATRASO a máximo 50 caracteres si excede el límite.
    
    Args:
        motivo_str: String con el motivo de atraso
        max_length: Longitud máxima permitida (default: 50)
        
    Returns:
        Tupla (motivo_truncado, fue_corregido)
        - motivo_truncado: String truncado si excedía el límite, original si no
        - fue_corregido: True si se aplicó truncamiento, False si ya estaba dentro del límite
    """
    if not motivo_str:
        return motivo_str, False
    
    motivo_original = motivo_str.strip()
    if len(motivo_original) <= max_length:
        return motivo_original, False
    
    # Truncar a max_length caracteres
    motivo_truncado = motivo_original[:max_length].rstrip()
    return motivo_truncado, True


def _sanitize_text_field(text_str: str) -> tuple[str, bool]:
    """
    Sanitiza campos de texto para CSV:
    1. Remueve comillas (simples y dobles) del texto
    2. Reemplaza ";" por "," para evitar conflictos con el separador CSV
    
    Esta función debe aplicarse a TODOS los campos de texto antes de escribir el CSV.
    
    Args:
        text_str: String con el texto a sanitizar
        
    Returns:
        Tupla (texto_sanitizado, fue_corregido)
        - texto_sanitizado: String sin comillas y con ";" reemplazado por ","
        - fue_corregido: True si se aplicó alguna corrección, False si no
    """
    if not text_str:
        return text_str, False
    
    text_original = text_str
    # Remover comillas (simples y dobles)
    text_sanitizada = text_original.replace('"', '').replace("'", "")
    # Reemplazar punto y coma por coma
    text_sanitizada = text_sanitizada.replace(";", ",")
    
    fue_corregido = text_sanitizada != text_original
    return text_sanitizada, fue_corregido


def _sanitize_observaciones(obs_str: str) -> tuple[str, bool]:
    """
    Sanitiza OBSERVACIONES usando la función general de sanitización.
    Mantenida por compatibilidad, pero ahora usa _sanitize_text_field.
    """
    return _sanitize_text_field(obs_str)


def _parse_monto(monto_str: str) -> float:
    """
    Parsea un monto en formato español (ej: "164.906,64") a float.
    Retorna 0.0 si no se puede parsear o está vacío.
    """
    if not monto_str or monto_str.strip() == "":
        return 0.0
    
    # Remover puntos (separadores de miles) y reemplazar coma por punto
    cleaned = monto_str.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_fecha(fecha_str: str) -> Optional[datetime]:
    """
    Parsea una fecha en formato "dd/mm/yyyy" a datetime.
    Retorna None si no se puede parsear o está vacía.
    """
    if not fecha_str or fecha_str.strip() == "":
        return None
    
    try:
        return datetime.strptime(fecha_str.strip(), "%d/%m/%Y")
    except ValueError:
        return None


def _is_promesa_de_pago(efecto: str) -> bool:
    """Verifica si el EFECTO indica una promesa de pago."""
    if not efecto:
        return False
    efecto_upper = efecto.upper().strip()
    return efecto_upper == "PROMESA DE PAGO" or efecto_upper == "PROMESA_DE_PAGO"


def _is_ya_pago(efecto: str) -> bool:
    """Verifica si el EFECTO indica 'YA PAGO'."""
    if not efecto:
        return False
    efecto_upper = efecto.upper().strip()
    return efecto_upper == "YA PAGO"


def _is_notificado_titular(efecto: str) -> bool:
    """Verifica si el EFECTO indica 'NOTIFICADO TITULAR'."""
    if not efecto:
        return False
    efecto_upper = efecto.upper().strip()
    return efecto_upper == "NOTIFICADO TITULAR"


def _is_notificado_filiar(efecto: str) -> bool:
    """Verifica si el EFECTO indica 'NOTIFICADO FLIAR'."""
    if not efecto:
        return False
    efecto_upper = efecto.upper().strip()
    return efecto_upper == "NOTIFICADO FLIAR"


def _is_telefono_equivocado(efecto: str) -> bool:
    """Verifica si el EFECTO indica 'TELEFONO EQUIVOCADO'."""
    if not efecto:
        return False
    efecto_upper = efecto.upper().strip()
    return efecto_upper == "TELEFONO EQUIVOCADO"


def _is_desconoce_deuda(efecto: str) -> bool:
    """Verifica si el EFECTO indica 'DESCONOCE DEUDA'."""
    if not efecto:
        return False
    efecto_upper = efecto.upper().strip()
    return efecto_upper == "DESCONOCE DEUDA"


def _is_no_afronta_deuda(efecto: str) -> bool:
    """Verifica si el EFECTO indica 'NO AFRONTA DEUDA'."""
    if not efecto:
        return False
    efecto_upper = efecto.upper().strip()
    return efecto_upper == "NO AFRONTA DEUDA"


def _is_fallecido(efecto: str) -> bool:
    """Verifica si el EFECTO indica 'FALLECIDO'."""
    if not efecto:
        return False
    efecto_upper = efecto.upper().strip()
    return efecto_upper == "FALLECIDO"


def _is_tipificacion_simple(efecto: str) -> bool:
    """
    Verifica si el EFECTO es una tipificación simple que requiere validación especial.
    Tipificaciones simples: YA PAGO, NOTIFICADO TITULAR, NOTIFICADO FLIAR,
    TELEFONO EQUIVOCADO, DESCONOCE DEUDA, NO AFRONTA DEUDA, FALLECIDO
    """
    return (
        _is_ya_pago(efecto) or
        _is_notificado_titular(efecto) or
        _is_notificado_filiar(efecto) or
        _is_telefono_equivocado(efecto) or
        _is_desconoce_deuda(efecto) or
        _is_no_afronta_deuda(efecto) or
        _is_fallecido(efecto)
    )


def _clean_and_validate_simple_tipification_row(row: Dict[str, str], column_names: List[str]) -> Optional[Dict[str, str]]:
    """
    Limpia y valida una fila con EFECTO de tipificación simple.
    Tipificaciones simples: "YA PAGO", "NOTIFICADO TITULAR", "NOTIFICADO FLIAR"
    
    Campos que deben tener datos:
    - Usuario asignado
    - TIPO_PROMESA
    - NRO_CLIENTE
    - SUCURSAL
    - ACCION
    - EFECTO
    - CONTACTO
    - OBSERVACIONES_GESTION
    - FECHA_ALTA
    
    Todos los demás campos deben estar vacíos.
    
    Returns:
        Diccionario limpio y validado, o None si falta algún campo requerido
    """
    # Campos requeridos para tipificaciones simples (YA PAGO, NOTIFICADO TITULAR, NOTIFICADO FLIAR)
    campos_requeridos = [
        "Usuario asignado",
        "TIPO_PROMESA",
        "NRO_CLIENTE",
        "SUCURSAL",
        "ACCION",
        "EFECTO",
        "CONTACTO",
        "OBSERVACIONES_GESTION",
        "FECHA_ALTA",
    ]
    
    # Crear una copia de la fila limpia
    fila_limpia: Dict[str, str] = {}
    
    # Validar que todos los campos requeridos tengan valores
    for campo in campos_requeridos:
        valor = _to_str(row.get(campo, ""))
        if not valor:
            # Si falta algún campo requerido, retornar None
            return None
        fila_limpia[campo] = valor
    
    # Para todos los demás campos, asegurar que estén vacíos
    for columna in column_names:
        if columna not in campos_requeridos:
            fila_limpia[columna] = ""
    
    return fila_limpia


def validate_promesa_row(
    row: Dict[str, str],
    banco: str,
    fila_num: int,
    headers: Dict[str, int]
) -> List[ValidationError]:
    """
    Valida una fila que contiene una promesa de pago.
    
    Retorna una lista de errores encontrados (vacía si no hay errores).
    """
    errors: List[ValidationError] = []
    nro_cliente = _to_str(row.get("NRO_CLIENTE", ""))
    
    # Campos requeridos para promesas de pago
    campos_requeridos = {
        "FECHA_ALTA": "Debe tener una fecha de alta",
        "FECHA_PROMESA": "Debe tener una fecha de promesa",
        "MONTO_PROMESA": "Debe tener un monto mayor a 0",
        "PUNTAJE_PROMESA": "Debe tener un puntaje asignado",
        "TIPO_PROMESA": "Debe tener un tipo de promesa",
        "MOTIVO_ATRASO": "Debe tener un motivo de atraso",
        "NRO_PRODUCTO": "Debe tener un número de producto",
        "SUC_PRODUCTO": "Debe tener una sucursal de producto",
        "TIPO_PROD": "Debe tener un tipo de producto (27, 4, o 1)",
    }
    
    for campo, mensaje in campos_requeridos.items():
        valor = _to_str(row.get(campo, ""))
        
        if campo == "MONTO_PROMESA":
            # Validación especial: debe ser mayor a 0
            monto = _parse_monto(valor)
            if monto <= 0:
                errors.append(ValidationError(
                    banco=banco,
                    fila=fila_num,
                    nro_cliente=nro_cliente,
                    campo=campo,
                    problema=f"{mensaje} (valor actual: {valor})",
                    valor_actual=valor
                ))
        elif not valor:
            # Para otros campos, solo verificar que no estén vacíos
            errors.append(ValidationError(
                banco=banco,
                fila=fila_num,
                nro_cliente=nro_cliente,
                campo=campo,
                problema=mensaje,
                valor_actual=valor
            ))
    
    # Validación adicional: FECHA_PROMESA debe ser mayor o igual que FECHA_ALTA
    fecha_alta_str = _to_str(row.get("FECHA_ALTA", ""))
    fecha_promesa_str = _to_str(row.get("FECHA_PROMESA", ""))
    
    if fecha_alta_str and fecha_promesa_str:
        fecha_alta = _parse_fecha(fecha_alta_str)
        fecha_promesa = _parse_fecha(fecha_promesa_str)
        
        if fecha_alta and fecha_promesa:
            # Normalizar fechas (solo fecha, sin hora)
            fecha_alta_sin_hora = fecha_alta.replace(hour=0, minute=0, second=0, microsecond=0)
            fecha_promesa_sin_hora = fecha_promesa.replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Permitir que FECHA_PROMESA sea el mismo día o posterior a FECHA_ALTA
            if fecha_promesa_sin_hora < fecha_alta_sin_hora:
                errors.append(ValidationError(
                    banco=banco,
                    fila=fila_num,
                    nro_cliente=nro_cliente,
                    campo="FECHA_PROMESA",
                    problema=f"FECHA_PROMESA debe ser mayor o igual que FECHA_ALTA (FECHA_ALTA: {fecha_alta_str}, FECHA_PROMESA: {fecha_promesa_str})",
                    valor_actual=fecha_promesa_str
                ))
    
    return errors


def validate_csv_file(csv_path: Path) -> tuple[List[ValidationError], int]:
    """
    Valida todas las promesas de pago en un archivo CSV.
    
    Retorna:
        - Lista de errores encontrados
        - Número total de promesas encontradas
    """
    errors: List[ValidationError] = []
    promesas_count = 0
    banco = csv_path.stem.replace("gestiones_", "").replace("_", " ")
    
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            
            if not reader.fieldnames:
                return errors, promesas_count
            
            # Normalizar nombres de columnas (eliminar espacios)
            normalized_headers = {name.strip(): name for name in reader.fieldnames if name}
            
            fila_num = 1  # Empezar en 1 (header es fila 0)
            for row in reader:
                fila_num += 1
                efecto = _to_str(row.get("EFECTO", ""))
                
                if _is_promesa_de_pago(efecto):
                    promesas_count += 1
                    row_errors = validate_promesa_row(row, banco, fila_num, normalized_headers)
                    errors.extend(row_errors)
    
    except Exception as e:
        # Si hay un error al leer el archivo, agregarlo como error
        errors.append(ValidationError(
            banco=banco,
            fila=0,
            nro_cliente="",
            campo="ARCHIVO",
            problema=f"Error al leer el archivo: {str(e)}",
            valor_actual=""
        ))
    
    return errors, promesas_count


def validate_all_results(results_dir: Path) -> ValidationResult:
    """
    Valida todas las promesas de pago en todos los archivos CSV de resultados.
    
    Args:
        results_dir: Directorio que contiene los archivos CSV de resultados
        
    Returns:
        ValidationResult con el resumen de la validación
    """
    all_errors: List[ValidationError] = []
    total_promesas = 0
    archivos_analizados: List[str] = []
    
    # Buscar todos los archivos CSV que empiecen con "gestiones_"
    csv_files = sorted(results_dir.glob("gestiones_*.csv"))
    
    for csv_file in csv_files:
        archivos_analizados.append(csv_file.name)
        errors, promesas = validate_csv_file(csv_file)
        all_errors.extend(errors)
        total_promesas += promesas
    
    # Contar promesas con errores (una promesa puede tener múltiples errores)
    promesas_con_errores = len(set((e.banco, e.fila, e.nro_cliente) for e in all_errors))
    promesas_validas = total_promesas - promesas_con_errores
    
    return ValidationResult(
        total_promesas=total_promesas,
        promesas_validas=promesas_validas,
        promesas_con_errores=promesas_con_errores,
        errores=all_errors,
        archivos_analizados=archivos_analizados
    )


def print_validation_report(result: ValidationResult) -> None:
    """
    Imprime un reporte detallado de la validación.
    """
    print("\n" + "="*80)
    print("REPORTE DE VALIDACION DE PROMESAS DE PAGO")
    print("="*80)
    
    print(f"\nResumen General:")
    print(f"   - Archivos analizados: {len(result.archivos_analizados)}")
    print(f"   - Total de promesas encontradas: {result.total_promesas}")
    print(f"   - Promesas validas: {result.promesas_validas} [OK]")
    print(f"   - Promesas con errores: {result.promesas_con_errores} [ERROR]")
    print(f"   - Total de errores detectados: {len(result.errores)}")
    
    if result.archivos_analizados:
        print(f"\nArchivos analizados:")
        for archivo in result.archivos_analizados:
            print(f"   - {archivo}")
    
    if result.errores:
        print(f"\nErrores encontrados:")
        print("-" * 80)
        
        # Agrupar errores por banco y fila
        errores_por_promesa: Dict[tuple, List[ValidationError]] = {}
        for error in result.errores:
            key = (error.banco, error.fila, error.nro_cliente)
            if key not in errores_por_promesa:
                errores_por_promesa[key] = []
            errores_por_promesa[key].append(error)
        
        for (banco, fila, nro_cliente), errors in sorted(errores_por_promesa.items()):
            print(f"\n   Banco: {banco} | Fila: {fila} | NRO_CLIENTE: {nro_cliente}")
            for error in errors:
                print(f"      [X] {error.campo}: {error.problema}")
                if error.valor_actual:
                    print(f"        Valor actual: '{error.valor_actual}'")
    else:
        print(f"\n[TODAS LAS PROMESAS DE PAGO SON VALIDAS]")
    
    print("\n" + "="*80 + "\n")


def validate_results(results_dir: Path, print_report: bool = True) -> ValidationResult:
    """
    Función principal para validar todos los resultados.
    
    Args:
        results_dir: Directorio que contiene los archivos CSV de resultados
        print_report: Si True, imprime el reporte en consola
        
    Returns:
        ValidationResult con el resumen de la validación
    """
    result = validate_all_results(results_dir)
    
    if print_report:
        print_validation_report(result)
    
    return result


@dataclass
class NormalizationReport:
    """Reporte de normalizaciones y correcciones aplicadas."""
    filas_corregidas_monto: int = 0
    filas_corregidas_motivo: int = 0
    filas_corregidas_obs_gestion: int = 0
    filas_corregidas_obs_promesa: int = 0
    filas_corregidas_texto: int = 0  # Campos de texto sanitizados (comillas y punto y coma)
    filas_corregidas_fecha_alta: int = 0  # Filas con FECHA_ALTA actualizada a fecha de hoy
    filas_corregidas_fecha_promesa: int = 0  # Filas con FECHA_PROMESA ajustada por validación
    total_filas_procesadas: int = 0


def export_valid_promesas(results_dir: Path, output_dir: Path) -> Dict[str, Path]:
    """
    Exporta promesas de pago validadas y tipificaciones simples a archivos CSV separados por banco.

    Tipificaciones incluidas:
    - PROMESA DE PAGO (validadas)
    - YA PAGO (validadas y limpiadas)
    - NOTIFICADO TITULAR (validadas y limpiadas)
    - NOTIFICADO FLIAR (validadas y limpiadas)
    - TELEFONO EQUIVOCADO (validadas y limpiadas)
    - DESCONOCE DEUDA (validadas y limpiadas)
    - NO AFRONTA DEUDA (validadas y limpiadas)
    - FALLECIDO (validadas y limpiadas)
    
    Aplica normalización y sanitización antes de escribir:
    - MONTO_PROMESA: elimina separador de miles
    - MOTIVO_ATRASO: trunca a máximo 50 caracteres
    - OBSERVACIONES_*: reemplaza ";" por ","
    
    Estructura de archivos generada:
    Crea una subcarpeta con formato Gestiones_Petersen_AAAAMMDD dentro de output_dir.
    Dentro de esta carpeta, crea dos subcarpetas:
    - archivos_codificacion/: archivos con códigos (AG002_45.csv, AG002_46.csv, etc.)
    - archivos_nombre/: archivos con nombres descriptivos (gestiones_validas_BSF.csv, etc.)
    
    Mapeo de bancos:
    - Santa Fe → AG002_45.csv / gestiones_validas_BSF.csv
    - Entre Ríos → AG002_46.csv / gestiones_validas_BER.csv
    - Santa Cruz → AG002_47.csv / gestiones_validas_BSC.csv
    - San Juan → AG002_48.csv / gestiones_validas_BSJ.csv
    
    Ambos archivos (codificación y nombre) contienen exactamente el mismo contenido validado.
    
    Args:
        results_dir: Directorio que contiene los archivos CSV de resultados originales
        output_dir: Directorio base donde se crearán las carpetas de promesas validadas (gestiones-validas)
        
    Returns:
        Diccionario con el nombre del banco como clave y la ruta del archivo de codificación como valor
    """
    # Crear directorio base si no existe
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Crear subcarpeta con formato Gestiones_Petersen_AAAAMMDD
    fecha_actual = datetime.now()
    nombre_carpeta = f"Gestiones_Petersen_{fecha_actual.strftime('%Y%m%d')}"
    carpeta_promesas = output_dir / nombre_carpeta
    carpeta_promesas.mkdir(parents=True, exist_ok=True)
    print(f"\nCarpeta creada: {nombre_carpeta}/")
    
    # Crear subcarpetas para archivos codificados y con nombre
    carpeta_codificacion = carpeta_promesas / "archivos_codificacion"
    carpeta_nombre = carpeta_promesas / "archivos_nombre"
    carpeta_fechas_originales = carpeta_promesas / "archivos_fechas_originales"
    carpeta_codificacion.mkdir(parents=True, exist_ok=True)
    carpeta_nombre.mkdir(parents=True, exist_ok=True)
    carpeta_fechas_originales.mkdir(parents=True, exist_ok=True)
    
    # Mapeo de bancos a códigos y siglas
    MAPEO_BANCOS = {
        "Santa Fe": {"codigo": "AG002_45", "sigla": "BSF"},
        "Entre Ríos": {"codigo": "AG002_46", "sigla": "BER"},
        "Santa Cruz": {"codigo": "AG002_47", "sigla": "BSC"},
        "San Juan": {"codigo": "AG002_48", "sigla": "BSJ"},
    }
    
    # Buscar todos los archivos CSV que empiecen con "gestiones_"
    csv_files = sorted(results_dir.glob("gestiones_*.csv"))
    
    # Diccionario para almacenar promesas válidas y "YA PAGO" por banco
    # También almacenamos los nombres de columnas por banco
    filas_por_banco: Dict[str, List[Dict[str, str]]] = {}
    columnas_por_banco: Dict[str, List[str]] = {}
    archivos_generados: Dict[str, Path] = {}
    
    # Reporte de normalizaciones (por banco)
    reportes_por_banco: Dict[str, NormalizationReport] = {}
    
    # Primero, validar todas las promesas para identificar cuáles son válidas
    validation_result = validate_all_results(results_dir)
    
    # Crear un set de tuplas (banco, fila, nro_cliente) que tienen errores
    promesas_con_errores = set(
        (e.banco, e.fila, e.nro_cliente) for e in validation_result.errores
    )
    
    # Leer todos los archivos y filtrar promesas válidas y "YA PAGO"
    for csv_file in csv_files:
        banco = csv_file.stem.replace("gestiones_", "").replace("_", " ")
        
        # Normalizar el nombre del banco para que coincida con el mapeo
        # Si es "Entre Rios" (sin tilde), convertirlo a "Entre Ríos" (con tilde)
        if banco == "Entre Rios":
            banco = "Entre Ríos"
        
        if banco not in filas_por_banco:
            filas_por_banco[banco] = []
            reportes_por_banco[banco] = NormalizationReport()
        
        try:
            with csv_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter=";")
                
                if not reader.fieldnames:
                    continue
                
                # Guardar los nombres de columnas para este banco
                column_names = list(reader.fieldnames)
                columnas_por_banco[banco] = column_names
                
                fila_num = 1  # Empezar en 1 (header es fila 0)
                for row in reader:
                    fila_num += 1
                    efecto = _to_str(row.get("EFECTO", ""))
                    
                    # Incluir promesas de pago válidas
                    if _is_promesa_de_pago(efecto):
                        # Verificar si esta promesa tiene errores
                        nro_cliente = _to_str(row.get("NRO_CLIENTE", ""))
                        if (banco, fila_num, nro_cliente) not in promesas_con_errores:
                            # Esta promesa es válida, agregarla
                            filas_por_banco[banco].append(row)
                    
                    # Incluir tipificaciones simples validadas y limpiadas
                    # (YA PAGO, NOTIFICADO TITULAR, NOTIFICADO FLIAR)
                    elif _is_tipificacion_simple(efecto):
                        fila_limpia = _clean_and_validate_simple_tipification_row(row, column_names)
                        if fila_limpia is not None:
                            filas_por_banco[banco].append(fila_limpia)
        
        except Exception as e:
            print(f"Error al leer archivo {csv_file.name}: {str(e)}")
            continue
    
    # Escribir archivos CSV para cada banco aplicando normalizaciones
    for banco, filas in filas_por_banco.items():
        if not filas:
            continue
        
        # Validación: eliminar duplicados por NRO_CLIENTE (priorizando PROMESA DE PAGO)
        # Aplicar tanto para promesas como para tipificaciones simples
        filas_sin_duplicados: List[Dict[str, str]] = []
        duplicados_encontrados = 0
        
        # Agrupar filas por NRO_CLIENTE
        filas_por_cliente: Dict[str, List[Dict[str, str]]] = {}
        for fila in filas:
            nro_cliente = _to_str(fila.get("NRO_CLIENTE", ""))
            
            if not nro_cliente:
                # Si no tiene NRO_CLIENTE, agregarlo directamente
                filas_sin_duplicados.append(fila)
            else:
                if nro_cliente not in filas_por_cliente:
                    filas_por_cliente[nro_cliente] = []
                filas_por_cliente[nro_cliente].append(fila)
        
        # Procesar cada grupo de clientes
        for nro_cliente, filas_cliente in filas_por_cliente.items():
            if len(filas_cliente) == 1:
                # Solo una fila para este cliente, agregarla directamente
                filas_sin_duplicados.append(filas_cliente[0])
            else:
                # Múltiples filas para el mismo cliente
                # Priorizar PROMESA DE PAGO
                promesas = [f for f in filas_cliente if _is_promesa_de_pago(_to_str(f.get("EFECTO", "")))]
                
                if promesas:
                    # Hay al menos una promesa, tomar la primera promesa encontrada
                    fila_seleccionada = promesas[0]
                    filas_sin_duplicados.append(fila_seleccionada)
                    duplicados_encontrados += len(filas_cliente) - 1
                    efectos_duplicados = [_to_str(f.get("EFECTO", "")) for f in filas_cliente if f != fila_seleccionada]
                    print(f"  [ADVERTENCIA] Duplicado detectado en {banco}: NRO_CLIENTE {nro_cliente} - se prioriza PROMESA DE PAGO (se descartan: {', '.join(efectos_duplicados)})")
                else:
                    # No hay promesas, tomar la primera fila (comportamiento original)
                    fila_seleccionada = filas_cliente[0]
                    filas_sin_duplicados.append(fila_seleccionada)
                    duplicados_encontrados += len(filas_cliente) - 1
                    efectos_duplicados = [_to_str(f.get("EFECTO", "")) for f in filas_cliente[1:]]
                    print(f"  [ADVERTENCIA] Duplicado detectado en {banco}: NRO_CLIENTE {nro_cliente} (EFECTO: {_to_str(fila_seleccionada.get('EFECTO', ''))}) - se mantiene solo la primera ocurrencia (se descartan: {', '.join(efectos_duplicados)})")
        
        if duplicados_encontrados > 0:
            print(f"  Total de duplicados eliminados en {banco}: {duplicados_encontrados}")
        
        # Aplicar normalizaciones y sanitización a cada fila, y contar correcciones
        filas_normalizadas: List[Dict[str, str]] = []
        filas_con_fecha_original: List[Dict[str, str]] = []
        reporte = reportes_por_banco[banco]
        
        for fila in filas_sin_duplicados:
            # Crear copia para normalizar
            fila_original = fila.copy()
            fila_normalizada = fila.copy()
            fila_con_fecha_original = fila.copy()
            
            # Normalizar MONTO_PROMESA
            if "MONTO_PROMESA" in fila_normalizada:
                monto_original = _to_str(fila_original.get("MONTO_PROMESA", ""))
                monto_normalizado, fue_corregido = _normalize_monto_promesa(monto_original)
                if fue_corregido:
                    reporte.filas_corregidas_monto += 1
                fila_normalizada["MONTO_PROMESA"] = monto_normalizado
                fila_con_fecha_original["MONTO_PROMESA"] = monto_normalizado
            
            # Truncar MOTIVO_ATRASO
            if "MOTIVO_ATRASO" in fila_normalizada:
                motivo_original = _to_str(fila_original.get("MOTIVO_ATRASO", ""))
                motivo_truncado, fue_truncado = _truncate_motivo_atraso(motivo_original)
                if fue_truncado:
                    reporte.filas_corregidas_motivo += 1
                # Sanitizar después de truncar (comillas y punto y coma)
                motivo_sanitizado, fue_sanitizado = _sanitize_text_field(motivo_truncado)
                if fue_sanitizado:
                    reporte.filas_corregidas_texto += 1
                fila_normalizada["MOTIVO_ATRASO"] = motivo_sanitizado
                fila_con_fecha_original["MOTIVO_ATRASO"] = motivo_sanitizado
            
            # Sanitizar OBSERVACIONES_GESTION
            if "OBSERVACIONES_GESTION" in fila_normalizada:
                obs_gestion_original = _to_str(fila_original.get("OBSERVACIONES_GESTION", ""))
                obs_gestion_sanitizada, fue_corregido = _sanitize_text_field(obs_gestion_original)
                if fue_corregido:
                    reporte.filas_corregidas_obs_gestion += 1
                fila_normalizada["OBSERVACIONES_GESTION"] = obs_gestion_sanitizada
                fila_con_fecha_original["OBSERVACIONES_GESTION"] = obs_gestion_sanitizada
            
            # Sanitizar OBSERVACIONES_PROMESA
            if "OBSERVACIONES_PROMESA" in fila_normalizada:
                obs_promesa_original = _to_str(fila_original.get("OBSERVACIONES_PROMESA", ""))
                obs_promesa_sanitizada, fue_corregido = _sanitize_text_field(obs_promesa_original)
                if fue_corregido:
                    reporte.filas_corregidas_obs_promesa += 1
                fila_normalizada["OBSERVACIONES_PROMESA"] = obs_promesa_sanitizada
                fila_con_fecha_original["OBSERVACIONES_PROMESA"] = obs_promesa_sanitizada
            
            # Sanitizar TODOS los demás campos de texto
            campos_texto = [
                "Usuario asignado",
                "GESTION_RELACIONADA",
                "TIPO_PROMESA",
                "ACCION",
                "EFECTO",
                "CONTACTO",
            ]
            for campo in campos_texto:
                if campo in fila_normalizada:
                    valor_original = _to_str(fila_original.get(campo, ""))
                    valor_sanitizado, fue_corregido = _sanitize_text_field(valor_original)
                    if fue_corregido:
                        reporte.filas_corregidas_texto += 1
                    fila_normalizada[campo] = valor_sanitizado
                    fila_con_fecha_original[campo] = valor_sanitizado
            
            # Versión con FECHA_ALTA = fecha de hoy (para archivos_codificacion y archivos_nombre)
            fecha_alta_original = _to_str(fila_original.get("FECHA_ALTA", ""))
            fecha_alta_hoy = fecha_actual.strftime("%d/%m/%Y")
            
            if fecha_alta_original != fecha_alta_hoy:
                reporte.filas_corregidas_fecha_alta += 1
            fila_normalizada["FECHA_ALTA"] = fecha_alta_hoy
            
            # Revalidar FECHA_PROMESA después de actualizar FECHA_ALTA (solo para promesas de pago)
            if _is_promesa_de_pago(_to_str(fila_normalizada.get("EFECTO", ""))):
                fecha_promesa_original = _to_str(fila_original.get("FECHA_PROMESA", ""))
                if fecha_promesa_original:
                    fecha_promesa_validada = _validate_fecha_promesa(fecha_promesa_original, fecha_actual)
                    if fecha_promesa_validada != fecha_promesa_original:
                        reporte.filas_corregidas_fecha_promesa += 1
                    fila_normalizada["FECHA_PROMESA"] = fecha_promesa_validada
            
            filas_normalizadas.append(fila_normalizada)
            
            # Versión con FECHA_ALTA original (para archivos_fechas_originales)
            # Intentar obtener la fecha original de fecha_llamada_original si está disponible
            fecha_llamada_original_raw = _to_str(fila_original.get("fecha_llamada_original", ""))
            if fecha_llamada_original_raw:
                # Extraer la fecha de fecha_llamada_original (formato "dd/mm/yyyy, HH:MM" o "dd/mm/yyyy")
                if "," in fecha_llamada_original_raw:
                    fecha_alta_desde_llamada = fecha_llamada_original_raw.split(",")[0].strip()
                else:
                    fecha_alta_desde_llamada = fecha_llamada_original_raw.strip()
                # Validar que tenga el formato correcto
                if re.match(r'^\d{2}/\d{2}/\d{4}$', fecha_alta_desde_llamada):
                    fila_con_fecha_original["FECHA_ALTA"] = fecha_alta_desde_llamada
                else:
                    # Si no se puede parsear, usar FECHA_ALTA original o fecha de hoy como fallback
                    fila_con_fecha_original["FECHA_ALTA"] = fecha_alta_original if fecha_alta_original else fecha_alta_hoy
            elif fecha_alta_original:
                fila_con_fecha_original["FECHA_ALTA"] = fecha_alta_original
            else:
                # Si no hay fecha original, usar fecha de hoy como fallback
                fila_con_fecha_original["FECHA_ALTA"] = fecha_alta_hoy
            
            # Revalidar FECHA_PROMESA contra FECHA_ALTA original (solo para promesas de pago)
            if _is_promesa_de_pago(_to_str(fila_con_fecha_original.get("EFECTO", ""))):
                fecha_promesa_original = _to_str(fila_original.get("FECHA_PROMESA", ""))
                if fecha_promesa_original:
                    fecha_alta_para_validar = _parse_fecha(fila_con_fecha_original["FECHA_ALTA"])
                    if fecha_alta_para_validar:
                        fecha_promesa_validada_original = _validate_fecha_promesa(fecha_promesa_original, fecha_alta_para_validar)
                        if fecha_promesa_validada_original != fecha_promesa_original:
                            # Solo contar como corrección si la fecha original era diferente de hoy
                            if fecha_alta_original and fecha_alta_original != fecha_alta_hoy:
                                reporte.filas_corregidas_fecha_promesa += 1
                        fila_con_fecha_original["FECHA_PROMESA"] = fecha_promesa_validada_original
                    else:
                        # Fallback si no se puede parsear la fecha
                        fecha_promesa_validada_fallback = _validate_fecha_promesa(fecha_promesa_original, fecha_actual)
                        fila_con_fecha_original["FECHA_PROMESA"] = fecha_promesa_validada_fallback
            
            filas_con_fecha_original.append(fila_con_fecha_original)
            reporte.total_filas_procesadas += 1
        
        # Contar promesas y tipificaciones simples para el reporte
        promesas_count = sum(1 for f in filas_normalizadas if _is_promesa_de_pago(_to_str(f.get("EFECTO", ""))))
        ya_pago_count = sum(1 for f in filas_normalizadas if _is_ya_pago(_to_str(f.get("EFECTO", ""))))
        notificado_titular_count = sum(1 for f in filas_normalizadas if _is_notificado_titular(_to_str(f.get("EFECTO", ""))))
        notificado_filiar_count = sum(1 for f in filas_normalizadas if _is_notificado_filiar(_to_str(f.get("EFECTO", ""))))
        telefono_equivocado_count = sum(1 for f in filas_normalizadas if _is_telefono_equivocado(_to_str(f.get("EFECTO", ""))))
        desconoce_deuda_count = sum(1 for f in filas_normalizadas if _is_desconoce_deuda(_to_str(f.get("EFECTO", ""))))
        no_afronta_deuda_count = sum(1 for f in filas_normalizadas if _is_no_afronta_deuda(_to_str(f.get("EFECTO", ""))))
        fallecido_count = sum(1 for f in filas_normalizadas if _is_fallecido(_to_str(f.get("EFECTO", ""))))
        
        # Obtener los nombres de columnas para este banco
        column_names = columnas_por_banco.get(banco, list(filas_normalizadas[0].keys()) if filas_normalizadas else [])
        
        # Filtrar fecha_llamada_original de las columnas (es solo un campo auxiliar)
        column_names_finales = [col for col in column_names if col != "fecha_llamada_original"]
        
        # Obtener código y sigla del banco
        banco_info = MAPEO_BANCOS.get(banco, {"codigo": f"AG002_XX", "sigla": "BXX"})
        codigo_archivo = banco_info["codigo"]
        sigla_archivo = banco_info["sigla"]
        
        # Definir rutas de los tres archivos
        archivo_codificacion = carpeta_codificacion / f"{codigo_archivo}.csv"
        archivo_nombre = carpeta_nombre / f"gestiones_validas_{sigla_archivo}.csv"
        archivo_fechas_originales = carpeta_fechas_originales / f"gestiones_originales_{sigla_archivo}.csv"
        
        # Función auxiliar para escribir el CSV
        def escribir_csv(ruta_archivo: Path, filas_a_escribir: List[Dict[str, str]]) -> None:
            """Escribe el contenido normalizado en el archivo CSV especificado."""
            # Crear copias de las filas sin fecha_llamada_original
            filas_limpias = []
            for fila in filas_a_escribir:
                fila_limpia = {k: v for k, v in fila.items() if k != "fecha_llamada_original"}
                filas_limpias.append(fila_limpia)
            
            with ruta_archivo.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=column_names_finales, delimiter=";", extrasaction="ignore")
                writer.writeheader()
                writer.writerows(filas_limpias)
        
        # Escribir los tres archivos
        try:
            escribir_csv(archivo_codificacion, filas_normalizadas)
            escribir_csv(archivo_nombre, filas_normalizadas)
            escribir_csv(archivo_fechas_originales, filas_con_fecha_original)
            
            # Retornar el archivo de codificación como principal (para compatibilidad)
            archivos_generados[banco] = archivo_codificacion
            
            tipificaciones_simples = (
                ya_pago_count + notificado_titular_count + notificado_filiar_count +
                telefono_equivocado_count + desconoce_deuda_count + no_afronta_deuda_count + fallecido_count
            )
            print(f"Archivos generados para {banco}:")
            print(f"  - {archivo_codificacion.name} (archivos_codificacion/ - FECHA_ALTA: hoy)")
            print(f"  - {archivo_nombre.name} (archivos_nombre/ - FECHA_ALTA: hoy)")
            print(f"  - {archivo_fechas_originales.name} (archivos_fechas_originales/ - FECHA_ALTA: original)")
            print(f"  ({len(filas_normalizadas)} filas: {promesas_count} promesas, {tipificaciones_simples} tipificaciones simples)")
            print(f"    Detalle tipificaciones: {ya_pago_count} YA PAGO, {notificado_titular_count} NOT.TITULAR, {notificado_filiar_count} NOT.FLIAR, "
                  f"{telefono_equivocado_count} TEL.EQUIVOCADO, {desconoce_deuda_count} DESC.DEUDA, {no_afronta_deuda_count} NO AFRONTA, {fallecido_count} FALLECIDO")
        
        except Exception as e:
            print(f"Error al escribir archivos para {banco}: {str(e)}")
    
    # Imprimir reporte de normalizaciones
    print("\n" + "="*80)
    print("REPORTE DE NORMALIZACION Y SANITIZACION")
    print("="*80)
    
    total_corregidas_monto = 0
    total_corregidas_motivo = 0
    total_corregidas_obs_gestion = 0
    total_corregidas_obs_promesa = 0
    total_corregidas_texto = 0
    total_corregidas_fecha_alta = 0
    total_corregidas_fecha_promesa = 0
    total_filas_procesadas = 0
    
    for banco, reporte in reportes_por_banco.items():
        if reporte.total_filas_procesadas > 0:
            print(f"\n{banco}:")
            print(f"   - Filas procesadas: {reporte.total_filas_procesadas}")
            print(f"   - MONTO_PROMESA normalizado: {reporte.filas_corregidas_monto} filas")
            print(f"   - MOTIVO_ATRASO truncado (>50 chars): {reporte.filas_corregidas_motivo} filas")
            print(f"   - OBSERVACIONES_GESTION sanitizado: {reporte.filas_corregidas_obs_gestion} filas")
            print(f"   - OBSERVACIONES_PROMESA sanitizado: {reporte.filas_corregidas_obs_promesa} filas")
            print(f"   - Campos de texto sanitizados (comillas y punto y coma): {reporte.filas_corregidas_texto} filas")
            print(f"   - FECHA_ALTA actualizada a fecha de hoy: {reporte.filas_corregidas_fecha_alta} filas")
            print(f"   - FECHA_PROMESA ajustada por validación: {reporte.filas_corregidas_fecha_promesa} filas")
            
            total_corregidas_monto += reporte.filas_corregidas_monto
            total_corregidas_motivo += reporte.filas_corregidas_motivo
            total_corregidas_obs_gestion += reporte.filas_corregidas_obs_gestion
            total_corregidas_obs_promesa += reporte.filas_corregidas_obs_promesa
            total_corregidas_texto += reporte.filas_corregidas_texto
            total_corregidas_fecha_alta += reporte.filas_corregidas_fecha_alta
            total_corregidas_fecha_promesa += reporte.filas_corregidas_fecha_promesa
            total_filas_procesadas += reporte.total_filas_procesadas
    
    print("\n" + "-"*80)
    print("TOTALES:")
    print(f"   - Total filas procesadas: {total_filas_procesadas}")
    print(f"   - Total MONTO_PROMESA normalizado: {total_corregidas_monto} filas")
    print(f"   - Total MOTIVO_ATRASO truncado: {total_corregidas_motivo} filas")
    print(f"   - Total OBSERVACIONES_GESTION sanitizado: {total_corregidas_obs_gestion} filas")
    print(f"   - Total OBSERVACIONES_PROMESA sanitizado: {total_corregidas_obs_promesa} filas")
    print(f"   - Total campos de texto sanitizados (comillas y punto y coma): {total_corregidas_texto} filas")
    print(f"   - Total FECHA_ALTA actualizada a fecha de hoy: {total_corregidas_fecha_alta} filas")
    print(f"   - Total FECHA_PROMESA ajustada por validación: {total_corregidas_fecha_promesa} filas")
    print("="*80 + "\n")

    return archivos_generados


def export_all_gestiones_fecha_original(
    results_dir: Path,
    output_dir: Path
) -> Dict[str, Path]:
    """
    Exporta TODAS las gestiones (todos los efectos) preservando fechas originales.

    Diferencias con export_valid_promesas:
    - Incluye TODOS los efectos (RELLAMAR, PROMESA DE PAGO, etc.)
    - NO elimina duplicados (un cliente puede aparecer múltiples veces)
    - Preserva FECHA_ALTA original de cada llamada
    - Solo genera archivos_fechas_originales/

    Args:
        results_dir: Directorio con archivos CSV originales (debug/gestiones_totales_AAAAMMDD/)
        output_dir: Directorio base (gestiones-validas-fecha-original/)

    Returns:
        Dict {banco: path} con rutas de archivos generados
    """
    # 1. Configurar paths de salida
    fecha_proceso = datetime.now().strftime("%Y%m%d")
    carpeta_gestion = output_dir / f"Gestiones_Petersen_{fecha_proceso}"
    carpeta_fechas_originales = carpeta_gestion / "archivos_fechas_originales"
    carpeta_fechas_originales.mkdir(parents=True, exist_ok=True)

    # Mapeo de bancos a siglas
    MAPEO_BANCOS = {
        "Santa Fe": "BSF",
        "Entre Ríos": "BER",
        "Santa Cruz": "BSC",
        "San Juan": "BSJ",
    }

    # 2. Leer archivos CSV y colectar TODAS las filas
    filas_por_banco: Dict[str, List[Dict[str, str]]] = {}
    columnas_por_banco: Dict[str, List[str]] = {}

    csv_files = sorted(results_dir.glob("gestiones_*.csv"))

    for csv_file in csv_files:
        # Extraer nombre del banco del archivo
        banco = csv_file.stem.replace("gestiones_", "").replace("_", " ")

        # Normalizar el nombre del banco
        if banco == "Entre Rios":
            banco = "Entre Ríos"

        if banco not in filas_por_banco:
            filas_por_banco[banco] = []

        try:
            with csv_file.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f, delimiter=";")

                if not reader.fieldnames:
                    continue

                # Guardar nombres de columnas
                column_names = list(reader.fieldnames)
                columnas_por_banco[banco] = column_names

                # Leer TODAS las filas (solo validar que tenga nro_cliente)
                for row in reader:
                    nro_cliente = _to_str(row.get("NRO_CLIENTE", ""))
                    if nro_cliente:
                        filas_por_banco[banco].append(row)

        except Exception as e:
            print(f"Error al leer archivo {csv_file.name}: {str(e)}")
            continue

    # 3. Para cada banco, normalizar y escribir archivo
    archivos_generados = {}

    for banco, filas in filas_por_banco.items():
        if not filas:
            continue

        # Normalizar cada fila preservando fecha original
        filas_normalizadas = []

        for fila in filas:
            fila_normalizada = fila.copy()

            # Preservar FECHA_ALTA original (de fecha_llamada_original)
            fecha_llamada_original_raw = _to_str(fila.get("fecha_llamada_original", ""))
            if fecha_llamada_original_raw:
                # Extraer la fecha de fecha_llamada_original (formato "dd/mm/yyyy, HH:MM" o "dd/mm/yyyy")
                if "," in fecha_llamada_original_raw:
                    fecha_alta_desde_llamada = fecha_llamada_original_raw.split(",")[0].strip()
                else:
                    fecha_alta_desde_llamada = fecha_llamada_original_raw.strip()
                # Validar que tenga el formato correcto
                if re.match(r'^\d{2}/\d{2}/\d{4}$', fecha_alta_desde_llamada):
                    fila_normalizada["FECHA_ALTA"] = fecha_alta_desde_llamada

            # Normalizar MONTO_PROMESA (eliminar puntos de miles)
            monto_promesa = _to_str(fila.get("MONTO_PROMESA", ""))
            if monto_promesa:
                fila_normalizada["MONTO_PROMESA"] = monto_promesa.replace(".", "")

            # Truncar MOTIVO_ATRASO a 50 caracteres
            motivo = _to_str(fila.get("MOTIVO_ATRASO", ""))
            if len(motivo) > 50:
                fila_normalizada["MOTIVO_ATRASO"] = motivo[:50]

            # Sanitizar campos de texto (comillas, punto y coma)
            for campo in ["OBSERVACIONES_GESTION", "OBSERVACIONES_PROMESA", "MOTIVO_ATRASO"]:
                valor = _to_str(fila.get(campo, ""))
                if valor:
                    valor = valor.replace('"', '').replace("'", "")
                    valor = valor.replace(";", ",")
                    fila_normalizada[campo] = valor

            filas_normalizadas.append(fila_normalizada)

        # Obtener nombres de columnas para este banco
        column_names = columnas_por_banco.get(banco, list(filas_normalizadas[0].keys()) if filas_normalizadas else [])

        # Filtrar fecha_llamada_original de las columnas (es solo un campo auxiliar)
        column_names_finales = [col for col in column_names if col != "fecha_llamada_original"]

        # Obtener sigla del banco
        sigla_archivo = MAPEO_BANCOS.get(banco, "BXX")

        # Escribir archivo CSV
        archivo_path = carpeta_fechas_originales / f"gestiones_originales_{sigla_archivo}.csv"

        try:
            # Crear copias de las filas sin fecha_llamada_original
            filas_limpias = []
            for fila in filas_normalizadas:
                fila_limpia = {k: v for k, v in fila.items() if k != "fecha_llamada_original"}
                filas_limpias.append(fila_limpia)

            with archivo_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=column_names_finales, delimiter=";", extrasaction="ignore")
                writer.writeheader()
                writer.writerows(filas_limpias)

            archivos_generados[banco] = archivo_path
            print(f"  [OK] {banco}: {len(filas_normalizadas)} gestiones exportadas")

        except Exception as e:
            print(f"Error al escribir archivo para {banco}: {str(e)}")
            continue

    return archivos_generados

