"""
Módulo para realizar merge inteligente entre datos de Retell y ROMAN

Este módulo implementa la lógica de merge con las siguientes reglas:
1. ROMAN tiene prioridad para campos de [Salida] cuando existe el call_id
2. Retell es la base completa - nunca se pierden llamadas
3. Campos vacíos en ROMAN no sobrescriben
4. Se generan estadísticas detalladas del merge
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Tuple
from copy import deepcopy

from config_roman import (
    CAMPOS_SOBRESCRIBIBLES,
    CAMPOS_PROTEGIDOS,
    CAMPOS_VARIABLES_DINAMICAS,
    CAMPOS_POSTCALL,
    es_valor_valido
)

# Configurar logger
logger = logging.getLogger('bancor.roman')


@dataclass
class MergeStats:
    """
    Estadísticas del proceso de merge entre Retell y ROMAN

    Attributes:
        total_retell: Total de llamadas en Retell
        total_roman: Total de llamadas en ROMAN
        total_merged: Total de llamadas en resultado final
        solo_retell: Llamadas que solo están en Retell (no modificadas)
        actualizados_por_roman: Llamadas que fueron actualizadas por ROMAN
        campos_sobrescritos: Diccionario {campo: cantidad_veces_sobrescrito}
        llamadas_solo_roman: Call IDs que están en ROMAN pero no en Retell (ignoradas)
        tiempo_merge: Tiempo en segundos que tomó el merge
    """
    total_retell: int = 0
    total_roman: int = 0
    total_merged: int = 0
    solo_retell: int = 0
    actualizados_por_roman: int = 0
    campos_sobrescritos: Dict[str, int] = field(default_factory=dict)
    llamadas_solo_roman: int = 0
    tiempo_merge: float = 0.0


def buscar_valor_en_estructura(datos: Dict[str, Any], campo: str) -> Any:
    """
    Busca un campo en la estructura de datos de Retell/ROMAN.

    La estructura tiene dos niveles: variables_dinamicas y postcall

    Args:
        datos: Diccionario con estructura {variables_dinamicas: {}, postcall: {}}
        campo: Nombre del campo a buscar

    Returns:
        Valor del campo si se encuentra, None si no existe
    """
    # Buscar en variables_dinamicas
    if campo in CAMPOS_VARIABLES_DINAMICAS:
        return datos.get('variables_dinamicas', {}).get(campo)

    # Buscar en postcall
    if campo in CAMPOS_POSTCALL:
        return datos.get('postcall', {}).get(campo)

    # Buscar en ambos (por si acaso)
    valor = datos.get('variables_dinamicas', {}).get(campo)
    if valor is not None:
        return valor

    valor = datos.get('postcall', {}).get(campo)
    return valor


def actualizar_valor_en_estructura(datos: Dict[str, Any], campo: str, valor: Any):
    """
    Actualiza un campo en la estructura de datos.

    Args:
        datos: Diccionario con estructura {variables_dinamicas: {}, postcall: {}}
        campo: Nombre del campo a actualizar
        valor: Nuevo valor del campo
    """
    # Actualizar en la categoría correcta
    if campo in CAMPOS_VARIABLES_DINAMICAS:
        if 'variables_dinamicas' not in datos:
            datos['variables_dinamicas'] = {}
        datos['variables_dinamicas'][campo] = valor

    elif campo in CAMPOS_POSTCALL:
        if 'postcall' not in datos:
            datos['postcall'] = {}
        datos['postcall'][campo] = valor


def merge_single_call(
    call_id: str,
    datos_retell: Dict[str, Any],
    datos_roman: Dict[str, Any],
    stats: MergeStats
) -> Dict[str, Any]:
    """
    Realiza el merge de un solo call_id.

    Args:
        call_id: ID de la llamada
        datos_retell: Datos de Retell para este call_id
        datos_roman: Datos de ROMAN para este call_id
        stats: Objeto de estadísticas (se modifica in-place)

    Returns:
        Diccionario con datos merged
    """
    # Crear copia profunda de datos_retell (para no modificar original)
    resultado = deepcopy(datos_retell)

    # Contador de campos modificados para este call_id
    campos_modificados_en_este_call = 0

    # Iterar sobre campos sobrescribibles
    for campo in CAMPOS_SOBRESCRIBIBLES:
        # Obtener valor de ROMAN
        valor_roman = buscar_valor_en_estructura(datos_roman, campo)

        # Si el valor de ROMAN es válido, sobrescribir
        if es_valor_valido(valor_roman):
            # Obtener valor actual de Retell (para logging)
            valor_retell = buscar_valor_en_estructura(datos_retell, campo)

            # Solo sobrescribir si son diferentes
            if valor_roman != valor_retell:
                actualizar_valor_en_estructura(resultado, campo, valor_roman)
                campos_modificados_en_este_call += 1

                # Actualizar estadísticas de campos
                if campo not in stats.campos_sobrescritos:
                    stats.campos_sobrescritos[campo] = 0
                stats.campos_sobrescritos[campo] += 1

    # Si se modificó al menos un campo, incrementar contador
    if campos_modificados_en_este_call > 0:
        stats.actualizados_por_roman += 1

    return resultado


def validar_merge(
    datos_retell: Dict[str, Dict[str, Any]],
    datos_merged: Dict[str, Dict[str, Any]]
) -> Tuple[bool, list]:
    """
    Valida que el merge se haya realizado correctamente.

    Args:
        datos_retell: Datos originales de Retell
        datos_merged: Datos después del merge

    Returns:
        Tupla (es_valido, errores) donde:
            - es_valido: True si la validación pasó
            - errores: Lista de strings con errores encontrados
    """
    errores = []

    # Validación 1: No se perdieron call_ids
    if set(datos_retell.keys()) != set(datos_merged.keys()):
        call_ids_perdidos = set(datos_retell.keys()) - set(datos_merged.keys())
        errores.append(f"Se perdieron {len(call_ids_perdidos)} call_ids durante el merge")

    # Validación 2: Todos los call_ids tienen estructura correcta
    for call_id, datos in datos_merged.items():
        if 'variables_dinamicas' not in datos or 'postcall' not in datos:
            errores.append(f"Estructura inválida en call_id {call_id}")

    # Validación 3: Campos protegidos no fueron modificados
    for call_id in datos_merged.keys():
        for campo_protegido in CAMPOS_PROTEGIDOS:
            valor_original = buscar_valor_en_estructura(datos_retell[call_id], campo_protegido)
            valor_merged = buscar_valor_en_estructura(datos_merged[call_id], campo_protegido)

            if valor_original != valor_merged:
                errores.append(
                    f"Campo protegido '{campo_protegido}' fue modificado en call_id {call_id}"
                )

    return (len(errores) == 0, errores)


def merge_datos_inteligente(
    datos_retell: Dict[str, Dict[str, Any]],
    datos_roman: Dict[str, Dict[str, Any]]
) -> Tuple[Dict[str, Dict[str, Any]], MergeStats]:
    """
    Realiza merge inteligente entre datos de Retell y ROMAN.

    Algoritmo:
    1. Iterar sobre todos los call_ids de Retell (base completa)
    2. Si call_id existe en ROMAN:
       - Sobrescribir campos sobrescribibles con valores de ROMAN
       - Registrar estadísticas
    3. Si call_id NO existe en ROMAN:
       - Mantener datos de Retell sin cambios
    4. Validar integridad del merge
    5. Retornar datos merged + estadísticas

    Args:
        datos_retell: Diccionario de datos de Retell
        datos_roman: Diccionario de datos de ROMAN

    Returns:
        Tupla (datos_merged, estadisticas)
    """
    inicio = time.time()

    # Inicializar estadísticas
    stats = MergeStats()
    stats.total_retell = len(datos_retell)
    stats.total_roman = len(datos_roman)

    logger.info(f"Iniciando merge: {stats.total_retell} llamadas en Retell, {stats.total_roman} en ROMAN")

    # Diccionario para resultado
    datos_merged = {}

    # Iterar sobre todos los call_ids de Retell (base completa)
    for call_id, datos_retell_call in datos_retell.items():
        # Verificar si existe en ROMAN
        if call_id in datos_roman:
            # Hacer merge
            datos_merged[call_id] = merge_single_call(
                call_id,
                datos_retell_call,
                datos_roman[call_id],
                stats
            )
        else:
            # No existe en ROMAN, mantener datos de Retell
            datos_merged[call_id] = deepcopy(datos_retell_call)
            stats.solo_retell += 1

    # Verificar llamadas que están solo en ROMAN (informativo)
    llamadas_solo_roman = set(datos_roman.keys()) - set(datos_retell.keys())
    stats.llamadas_solo_roman = len(llamadas_solo_roman)

    if llamadas_solo_roman:
        logger.warning(
            f"Se encontraron {stats.llamadas_solo_roman} llamadas en ROMAN que no están en Retell (serán ignoradas)"
        )

    # Total merged debe ser igual a Retell
    stats.total_merged = len(datos_merged)

    # Validar integridad del merge
    es_valido, errores = validar_merge(datos_retell, datos_merged)

    if not es_valido:
        logger.error("Validación de merge falló:")
        for error in errores:
            logger.error(f"  - {error}")
        raise ValueError("El merge no pasó las validaciones de integridad")

    # Calcular tiempo
    stats.tiempo_merge = time.time() - inicio

    logger.info(f"Merge completado exitosamente en {stats.tiempo_merge:.2f} segundos")

    return datos_merged, stats


def generar_reporte_merge(stats: MergeStats) -> str:
    """
    Genera un reporte legible para mostrar al usuario.

    Args:
        stats: Estadísticas del merge

    Returns:
        String con el reporte formateado
    """
    # Calcular porcentajes
    porcentaje_sin_modificar = (stats.solo_retell / stats.total_retell * 100) if stats.total_retell > 0 else 0
    porcentaje_actualizados = (stats.actualizados_por_roman / stats.total_retell * 100) if stats.total_retell > 0 else 0

    reporte = []
    reporte.append("=" * 60)
    reporte.append("REPORTE DE MERGE RETELL + ROMAN")
    reporte.append("=" * 60)
    reporte.append("")

    reporte.append("Fuentes de datos:")
    reporte.append(f"  • Retell (API):    {stats.total_retell:,} llamadas")
    reporte.append(f"  • ROMAN (CSV):     {stats.total_roman:,} llamadas")
    reporte.append("")

    reporte.append("Resultado del merge:")
    reporte.append(f"  • Total procesadas: {stats.total_merged:,} llamadas")
    reporte.append(f"  • Sin modificar:    {stats.solo_retell:,} llamadas ({porcentaje_sin_modificar:.1f}%)")
    reporte.append(f"  • Actualizadas:     {stats.actualizados_por_roman:,} llamadas ({porcentaje_actualizados:.1f}%)")

    if stats.llamadas_solo_roman > 0:
        reporte.append(f"  • Solo en ROMAN:    {stats.llamadas_solo_roman:,} llamadas (ignoradas)")

    if stats.campos_sobrescritos:
        reporte.append("")
        reporte.append("Campos actualizados por ROMAN:")

        # Ordenar campos por cantidad (más frecuentes primero)
        campos_ordenados = sorted(
            stats.campos_sobrescritos.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for campo, cantidad in campos_ordenados:
            reporte.append(f"  • {campo:25} {cantidad:,} veces")

    reporte.append("")
    reporte.append(f"Tiempo de merge: {stats.tiempo_merge:.2f} segundos")
    reporte.append("=" * 60)

    return "\n".join(reporte)


if __name__ == "__main__":
    # Test básico
    print("Módulo data_merger cargado correctamente")
