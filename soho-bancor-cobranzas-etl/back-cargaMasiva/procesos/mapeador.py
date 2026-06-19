"""
Mapeador de datos Retell/ROMAN -> formato CRM Bancor

Convierte la estructura de datos merged al formato de 13 columnas requerido.
"""
from typing import Dict, Any, List, Optional

from config_catalogos import (
    CLASE_OPERACION,
    COLUMNAS_SALIDA,
    RESPONSABLES,
    MAPEO_ESTADOS_RETELL_A_CRM,
    MAPEO_SUBESTADOS_DESCRIPTIVOS,
    ESTADOS_A_DESCARTAR,
    TODOS_LOS_ESTADOS,
    SUBESTADOS_VALIDOS,
    es_valor_valido,
)


# Mapeo de campos de entrada (Retell/ROMAN) a campos de salida (CRM)
MAPEO_CAMPOS = {
    # Campos de variables dinámicas
    'CUIL': 'CUIT',
    'Cuenta': 'Cuenta',
    # Campos de postcall
    'ESTADO': 'Estado',
    'SUBESTADO': 'Sub- Estado',
    'DESCRIPCION': 'Descripción',
    'Comentarios': 'Notas',
}

# Campos que vienen en variables_dinamicas vs postcall
CAMPOS_VARIABLES_DINAMICAS = ['CUIL', 'Cuenta', 'ClienteNombre', 'Cliente_BT']
CAMPOS_POSTCALL = ['ESTADO', 'SUBESTADO', 'DESCRIPCION', 'Comentarios']


def convertir_estado_a_crm(estado_retell: str) -> tuple:
    """
    Convierte un estado descriptivo de Retell/ROMAN a código CRM.

    Args:
        estado_retell: Estado en formato descriptivo (ej: "promesa_de_pago_acordada")

    Returns:
        Tupla (codigo_estado, codigo_subestado) o (None, None) si debe descartarse
    """
    if not estado_retell:
        return None, None

    estado_str = str(estado_retell).strip()

    # Si ya es un código válido del CRM (E0xxx), devolverlo directamente
    if estado_str.upper() in TODOS_LOS_ESTADOS:
        return estado_str.upper(), None

    # Buscar en el mapeo
    estado_lower = estado_str.lower().replace(' ', '_')

    if estado_lower in MAPEO_ESTADOS_RETELL_A_CRM:
        return MAPEO_ESTADOS_RETELL_A_CRM[estado_lower]

    # Buscar también con el valor original
    if estado_str in MAPEO_ESTADOS_RETELL_A_CRM:
        return MAPEO_ESTADOS_RETELL_A_CRM[estado_str]

    # Si está en la lista de descartar
    if estado_lower in [e.lower() for e in ESTADOS_A_DESCARTAR]:
        return None, None

    # Estado no reconocido - devolver None para que sea descartado
    return None, None


def extraer_valor(datos_llamada: Dict[str, Any], campo: str) -> Any:
    """
    Extrae un valor de los datos de la llamada, buscando en variables_dinamicas
    y postcall según corresponda.

    Args:
        datos_llamada: Diccionario con datos de la llamada
        campo: Nombre del campo a buscar

    Returns:
        Valor del campo o None si no existe
    """
    # Buscar en variables_dinamicas
    variables = datos_llamada.get('variables_dinamicas', {})
    if campo in variables:
        return variables[campo]

    # Buscar en postcall
    postcall = datos_llamada.get('postcall', {})
    if campo in postcall:
        return postcall[campo]

    # Buscar directamente en el diccionario (para datos ya aplanados)
    if campo in datos_llamada:
        return datos_llamada[campo]

    return None


def mapear_registro(
    call_id: str,
    datos_llamada: Dict[str, Any],
    nombre_estudio: str,
) -> Optional[Dict[str, str]]:
    """
    Mapea un registro de Retell/ROMAN al formato CRM de 13 columnas.

    Args:
        call_id: ID de la llamada
        datos_llamada: Datos combinados de Retell + ROMAN
        nombre_estudio: Nombre del estudio para campo Responsable

    Returns:
        Diccionario con las 13 columnas del CRM o None si no tiene estado válido
    """
    # Extraer estado original
    estado_original = extraer_valor(datos_llamada, 'ESTADO')
    if not es_valor_valido(estado_original):
        return None

    # Convertir estado a código CRM
    codigo_estado, subestado_default = convertir_estado_a_crm(estado_original)

    # Si no se pudo convertir, descartar el registro
    if not codigo_estado:
        return None

    # Obtener sub-estado: primero del mapeo, luego del dato original
    subestado = subestado_default
    subestado_original = extraer_valor(datos_llamada, 'SUBESTADO')
    if subestado_original and es_valor_valido(subestado_original):
        subestado_str = str(subestado_original).strip()
        subestado_upper = subestado_str.upper()
        subestado_lower = subestado_str.lower()

        # Si ya es un código válido (E001, E002, E003)
        if subestado_upper in SUBESTADOS_VALIDOS:
            subestado = subestado_upper
        # Si es un nombre descriptivo, convertir a código
        elif subestado_lower in MAPEO_SUBESTADOS_DESCRIPTIVOS:
            subestado = MAPEO_SUBESTADOS_DESCRIPTIVOS[subestado_lower]

    # Obtener código de responsable
    nombre_estudio_upper = nombre_estudio.upper().strip()
    codigo_responsable = RESPONSABLES.get(nombre_estudio_upper, '')

    if not codigo_responsable:
        # Buscar por coincidencia parcial
        for nombre, codigo in RESPONSABLES.items():
            if nombre_estudio_upper in nombre or nombre in nombre_estudio_upper:
                codigo_responsable = codigo
                break

    # Obtener descripción del campo OBSERVACIONES de Retell
    descripcion = extraer_valor(datos_llamada, 'OBSERVACIONES') or ''

    # Crear registro con las 13 columnas
    registro = {
        'Clase de Operación': CLASE_OPERACION,
        'Estado': codigo_estado,
        'Sub- Estado': subestado or '',
        'CUIT': extraer_valor(datos_llamada, 'CUIL') or '',
        'Cuenta': '',
        'Desc. Acuerdo Comercial': '',
        'Acuerdo Comercial': '',
        'Responsable': codigo_responsable,
        'Descripción': descripcion,
        'Persona de Contacto': '',
        'Juzgado': '',
        'Garante': '',
        'Notas': '',
    }

    return registro


def mapear_todos_los_registros(
    datos_merged: Dict[str, Dict[str, Any]],
    nombre_estudio: str,
) -> List[Dict[str, str]]:
    """
    Mapea todos los registros merged al formato CRM.

    Filtra registros sin estado válido (no se pueden cargar al CRM).

    Args:
        datos_merged: Diccionario {call_id: datos_llamada} con datos combinados
        nombre_estudio: Nombre del estudio para campo Responsable

    Returns:
        Lista de diccionarios con las 13 columnas del CRM
    """
    registros_mapeados = []
    registros_sin_estado = 0

    for call_id, datos_llamada in datos_merged.items():
        registro = mapear_registro(call_id, datos_llamada, nombre_estudio)

        if registro:
            registros_mapeados.append(registro)
        else:
            registros_sin_estado += 1

    if registros_sin_estado > 0:
        print(f"  - Registros sin estado (omitidos): {registros_sin_estado}")

    print(f"  - Registros mapeados: {len(registros_mapeados)}")

    return registros_mapeados


def obtener_resumen_mapeo(
    registros: List[Dict[str, str]]
) -> Dict[str, int]:
    """
    Genera un resumen del mapeo por estado.

    Args:
        registros: Lista de registros mapeados

    Returns:
        Diccionario con conteo por estado
    """
    resumen = {}

    for registro in registros:
        estado = registro.get('Estado', 'SIN_ESTADO')
        resumen[estado] = resumen.get(estado, 0) + 1

    return resumen
