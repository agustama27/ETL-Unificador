"""
Módulo para gestionar la lectura y normalización de datos desde ROMAN

Este módulo se encarga de:
1. Buscar archivos CSV de ROMAN en la carpeta roman/
2. Leer el CSV con detección automática de encoding
3. Normalizar la estructura de ROMAN a formato compatible con Retell
4. Retornar datos listos para merge
"""

import logging
import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd

# Importar función de lectura de CSV de retell_manager
from retell_manager import leer_csv_con_codificacion

# Importar configuración
from config_roman import (
    MAPEO_COLUMNAS_ROMAN,
    CAMPOS_VARIABLES_DINAMICAS,
    CAMPOS_POSTCALL,
    es_valor_valido,
    normalizar_booleano
)

# Configurar logger
logger = logging.getLogger('bancor.roman')
logger.setLevel(logging.INFO)

# Si no tiene handlers, agregar uno para consola
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def obtener_archivo_roman() -> Optional[Path]:
    """
    Busca el archivo CSV de ROMAN en la carpeta roman/

    Returns:
        Path al archivo si existe, None si no hay archivos

    Comportamiento:
        - Si hay 0 archivos: retorna None (ROMAN es opcional)
        - Si hay 1 archivo: retorna su Path
        - Si hay múltiples: retorna el más reciente + advertencia
    """
    # Obtener ruta de la carpeta roman
    base_dir = Path(__file__).parent.parent
    carpeta_roman = base_dir / "roman"

    # Verificar que la carpeta existe
    if not carpeta_roman.exists():
        logger.info("Carpeta roman/ no existe. ROMAN no será utilizado.")
        return None

    # Buscar archivos CSV
    archivos_csv = list(carpeta_roman.glob("*.csv"))

    if not archivos_csv:
        logger.info("No se encontraron archivos CSV en carpeta roman/")
        return None

    # Si hay múltiples archivos, usar el más reciente
    if len(archivos_csv) > 1:
        logger.warning(
            f"Se encontraron {len(archivos_csv)} archivos CSV en roman/. "
            f"Usando el más reciente."
        )
        # Ordenar por fecha de modificación (más reciente primero)
        archivos_csv.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    archivo_roman = archivos_csv[0]
    logger.info(f"Archivo ROMAN encontrado: {archivo_roman.name}")

    return archivo_roman


def validar_estructura_roman(df: pd.DataFrame) -> bool:
    """
    Valida que el DataFrame de ROMAN tenga la estructura esperada.

    Args:
        df: DataFrame leído desde CSV de ROMAN

    Returns:
        True si la estructura es válida

    Raises:
        ValueError: Si falta la columna "ID de Llamada" o si está vacío
    """
    # Validación 1: DataFrame no vacío
    if df.empty:
        raise ValueError("El archivo ROMAN está vacío (0 registros)")

    # Validación 2: Columna "ID de Llamada" existe
    if 'ID de Llamada' not in df.columns:
        raise ValueError(
            f"El archivo ROMAN no tiene columna 'ID de Llamada'. "
            f"Columnas encontradas: {', '.join(df.columns.tolist())}"
        )

    # Validación 3: Al menos un call_id válido
    call_ids_validos = df['ID de Llamada'].dropna()
    if len(call_ids_validos) == 0:
        raise ValueError("No se encontraron Call IDs válidos en ROMAN")

    # Advertencias (no errores)
    # Verificar si hay duplicados
    duplicados = df['ID de Llamada'].duplicated().sum()
    if duplicados > 0:
        logger.warning(f"Se encontraron {duplicados} Call IDs duplicados en ROMAN. Se usará la primera ocurrencia.")

    logger.info(f"Estructura ROMAN válida: {len(df)} registros, {len(df.columns)} columnas")

    return True


def normalizar_valor_campo(nombre_campo: str, valor: Any) -> Any:
    """
    Normaliza un valor de campo según su tipo esperado.

    Args:
        nombre_campo: Nombre del campo (después de mapeo)
        valor: Valor original del campo

    Returns:
        Valor normalizado según el tipo del campo
    """
    # Si el valor no es válido, retornar None
    if not es_valor_valido(valor):
        return None

    # Normalizar booleanos
    if nombre_campo in ['compromiso_de_pago_logrado', 'Email_valido']:
        return normalizar_booleano(valor)

    # Normalizar números
    if nombre_campo in ['Monto_compromiso']:
        try:
            # Eliminar espacios y convertir a float
            if isinstance(valor, str):
                valor = valor.strip().replace(',', '')
            return float(valor) if valor else None
        except (ValueError, TypeError):
            logger.warning(f"No se pudo convertir '{valor}' a número para {nombre_campo}")
            return None

    # Para strings, hacer strip y retornar
    if isinstance(valor, str):
        valor = valor.strip()
        return valor if valor else None

    return valor


def _normalizar_nombre_columna(nombre_columna: str) -> str:
    """Normaliza encabezados para matcheo tolerante entre variantes ROMAN."""
    texto = str(nombre_columna).strip().lower().replace("\ufeff", "")
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(char for char in texto if not unicodedata.combining(char))
    texto = re.sub(r'[^a-z0-9]+', '', texto)
    return texto


def _resolver_columnas_mapeadas(df: pd.DataFrame) -> Dict[str, str]:
    """Resuelve columnas ROMAN reales con matching exacto + tolerante."""
    columnas_resueltas: Dict[str, str] = {}

    # Mapa normalizado -> nombre real (primera ocurrencia)
    normalizadas_a_reales: Dict[str, str] = {}
    for columna_real in df.columns:
        clave_normalizada = _normalizar_nombre_columna(columna_real)
        if clave_normalizada and clave_normalizada not in normalizadas_a_reales:
            normalizadas_a_reales[clave_normalizada] = columna_real

    for columna_roman in MAPEO_COLUMNAS_ROMAN:
        if columna_roman in df.columns:
            columnas_resueltas[columna_roman] = columna_roman
            continue

        clave_normalizada = _normalizar_nombre_columna(columna_roman)
        columna_real = normalizadas_a_reales.get(clave_normalizada)
        if columna_real:
            columnas_resueltas[columna_roman] = columna_real

    return columnas_resueltas


def normalizar_datos_roman(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    """
    Convierte DataFrame de ROMAN a estructura compatible con Retell.

    La estructura de Retell es:
    {
        'call_id': {
            'variables_dinamicas': {...},
            'postcall': {...}
        }
    }

    Args:
        df: DataFrame leído desde CSV de ROMAN

    Returns:
        Diccionario con estructura compatible con Retell
    """
    resultado = {}

    columnas_resueltas = _resolver_columnas_mapeadas(df)

    # Procesar cada fila
    for idx, row in df.iterrows():
        # Obtener call_id
        call_id = str(row['ID de Llamada']).strip()

        if not call_id or call_id in ['nan', 'None']:
            continue

        # Inicializar estructura para este call_id
        datos_call = {
            'variables_dinamicas': {},
            'postcall': {},
            '_origen': 'roman'  # Metadato para debugging
        }

        # Procesar cada campo mapeado
        for columna_roman, campo_retell in MAPEO_COLUMNAS_ROMAN.items():
            # Saltar call_id (ya lo procesamos)
            if campo_retell == 'call_id':
                continue

            columna_origen = columnas_resueltas.get(columna_roman)
            if not columna_origen:
                continue

            # Obtener valor
            valor = row[columna_origen]

            # Normalizar valor
            valor_normalizado = normalizar_valor_campo(campo_retell, valor)

            # Si el valor no es válido, no agregar
            if valor_normalizado is None:
                continue

            # Agregar a la categoría correcta
            if campo_retell in CAMPOS_VARIABLES_DINAMICAS:
                datos_call['variables_dinamicas'][campo_retell] = valor_normalizado
            elif campo_retell in CAMPOS_POSTCALL:
                datos_call['postcall'][campo_retell] = valor_normalizado

        # Agregar al resultado (solo si tiene datos)
        if datos_call['variables_dinamicas'] or datos_call['postcall']:
            resultado[call_id] = datos_call

    logger.info(f"Normalizados {len(resultado)} registros de ROMAN")

    return resultado


def obtener_datos_roman() -> Dict[str, Dict[str, Any]]:
    """
    Función principal - punto de entrada para obtener datos de ROMAN.

    Este método encapsula todo el flujo:
    1. Buscar archivo CSV en carpeta roman/
    2. Leer el archivo con detección de encoding
    3. Validar estructura
    4. Normalizar a formato compatible con Retell

    Returns:
        Diccionario con datos de ROMAN normalizados.
        Retorna diccionario vacío {} si no hay archivo o hay error (sin lanzar excepción)

    Nota:
        Esta función NUNCA debe lanzar excepciones que detengan el flujo principal.
        En caso de error, registra el problema y retorna diccionario vacío.
    """
    try:
        # Paso 1: Buscar archivo
        archivo_roman = obtener_archivo_roman()

        if archivo_roman is None:
            return {}

        # Paso 2: Leer CSV con detección de encoding
        logger.info(f"Leyendo archivo ROMAN: {archivo_roman.name}")

        try:
            # Intentar primero con separador de coma
            df, encoding = leer_csv_con_codificacion(archivo_roman, separador=',')
        except:
            # Si falla, intentar con punto y coma
            try:
                df, encoding = leer_csv_con_codificacion(archivo_roman, separador=';')
            except Exception as e:
                logger.error(f"Error al leer archivo ROMAN: {str(e)}")
                return {}

        # Limpiar espacios en nombres de columnas
        df.columns = df.columns.str.strip()

        # Paso 3: Validar estructura
        try:
            validar_estructura_roman(df)
        except ValueError as e:
            logger.error(f"Validación de ROMAN falló: {str(e)}")
            return {}

        # Paso 4: Normalizar datos
        datos_normalizados = normalizar_datos_roman(df)

        if not datos_normalizados:
            logger.warning("No se obtuvieron datos válidos de ROMAN")
            return {}

        logger.info(f"✓ Datos de ROMAN cargados exitosamente: {len(datos_normalizados)} llamadas")

        return datos_normalizados

    except Exception as e:
        # Capturar cualquier error inesperado
        logger.error(f"Error inesperado al procesar ROMAN: {str(e)}")
        return {}


if __name__ == "__main__":
    # Test básico
    print("Probando lectura de ROMAN...")
    datos = obtener_datos_roman()
    print(f"\nTotal de registros: {len(datos)}")

    if datos:
        # Mostrar primer registro como ejemplo
        primer_call_id = list(datos.keys())[0]
        print(f"\nEjemplo - Call ID: {primer_call_id}")
        print(f"Variables dinámicas: {datos[primer_call_id]['variables_dinamicas']}")
        print(f"Postcall: {datos[primer_call_id]['postcall']}")
