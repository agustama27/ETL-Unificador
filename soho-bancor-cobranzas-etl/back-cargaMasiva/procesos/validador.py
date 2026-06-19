"""
Validador de datos para carga masiva CRM Bancor

Implementa todas las validaciones requeridas antes de generar el XLSX.
"""
import re
from typing import Dict, Any, List, Tuple, Optional

from config_catalogos import (
    TODOS_LOS_ESTADOS,
    ESTADOS_CON_SUBESTADO,
    SUBESTADOS_POR_ESTADO,
    RESPONSABLES,
    MAX_DESCRIPCION,
    LONGITUD_CUIT,
    es_valor_valido,
)


def normalizar_cuit(cuit: Any) -> str:
    """
    Normaliza un CUIT/CUIL eliminando guiones y espacios.

    Args:
        cuit: CUIT en cualquier formato

    Returns:
        CUIT como string de solo dígitos
    """
    if cuit is None:
        return ''
    cuit_str = str(cuit).strip()
    # Eliminar guiones, espacios y puntos
    cuit_str = re.sub(r'[-.\s]', '', cuit_str)
    # Eliminar .0 si viene de pandas
    if cuit_str.endswith('.0'):
        cuit_str = cuit_str[:-2]
    return cuit_str


def validar_cuit(cuit: Any) -> Tuple[bool, str, Optional[str]]:
    """
    Valida formato de CUIT: 11 dígitos numéricos.

    Args:
        cuit: CUIT a validar

    Returns:
        Tupla (es_válido, cuit_normalizado, mensaje_error)
    """
    cuit_normalizado = normalizar_cuit(cuit)

    if not cuit_normalizado:
        return False, '', "CUIT vacío"

    if not cuit_normalizado.isdigit():
        return False, '', f"CUIT contiene caracteres no numéricos: {cuit}"

    if len(cuit_normalizado) != LONGITUD_CUIT:
        return False, '', f"CUIT debe tener {LONGITUD_CUIT} dígitos, tiene {len(cuit_normalizado)}: {cuit}"

    return True, cuit_normalizado, None


def validar_estado(estado: Any) -> Tuple[bool, str, Optional[str]]:
    """
    Valida que el estado sea un código válido.

    Args:
        estado: Código de estado a validar

    Returns:
        Tupla (es_válido, estado_normalizado, mensaje_error)
    """
    if not es_valor_valido(estado):
        return False, '', "Estado vacío"

    estado_str = str(estado).strip().upper()

    # Normalizar formato (E0012 o E012 → E0012)
    if estado_str.startswith('E') and len(estado_str) == 4:
        estado_str = 'E0' + estado_str[1:]

    if estado_str not in TODOS_LOS_ESTADOS:
        return False, '', f"Estado inválido: {estado}"

    return True, estado_str, None


def validar_subestado(estado: str, subestado: Any) -> Tuple[bool, str, Optional[str]]:
    """
    Valida sub-estado según reglas:
    - Obligatorio para E0012 y E0002
    - Debe estar vacío para otros estados

    Args:
        estado: Código de estado (ya validado)
        subestado: Código de sub-estado a validar

    Returns:
        Tupla (es_válido, subestado_normalizado, mensaje_error)
    """
    requiere_subestado = estado in ESTADOS_CON_SUBESTADO
    tiene_subestado = es_valor_valido(subestado)

    if requiere_subestado:
        if not tiene_subestado:
            return False, '', f"Estado {estado} requiere sub-estado obligatorio"

        subestado_str = str(subestado).strip().upper()

        # Normalizar formato (E01 → E001, pero E003 se mantiene)
        if subestado_str.startswith('E') and len(subestado_str) == 3:
            subestado_str = 'E0' + subestado_str[1:]

        subestados_validos = SUBESTADOS_POR_ESTADO.get(estado, {})
        if subestado_str not in subestados_validos:
            validos = list(subestados_validos.keys())
            return False, '', f"Sub-estado '{subestado}' inválido para {estado}. Válidos: {validos}"

        return True, subestado_str, None
    else:
        # Estado sin sub-estado - limpiar cualquier valor
        return True, '', None


def validar_responsable(responsable: Any) -> Tuple[bool, str, Optional[str]]:
    """
    Valida y convierte nombre de estudio a código de responsable.

    Args:
        responsable: Nombre del estudio o código

    Returns:
        Tupla (es_válido, código_responsable, mensaje_error)
    """
    if not es_valor_valido(responsable):
        return False, '', "Responsable vacío"

    responsable_str = str(responsable).strip().upper()

    # Si ya es un código numérico válido
    if responsable_str.isdigit() and responsable_str in RESPONSABLES.values():
        return True, responsable_str, None

    # Buscar por nombre
    if responsable_str in RESPONSABLES:
        return True, RESPONSABLES[responsable_str], None

    # Buscar por nombre parcial
    for nombre, codigo in RESPONSABLES.items():
        if responsable_str in nombre or nombre in responsable_str:
            return True, codigo, None

    nombres_validos = list(RESPONSABLES.keys())
    return False, '', f"Responsable '{responsable}' no encontrado. Válidos: {nombres_validos}"


def truncar_descripcion(descripcion: Any) -> str:
    """
    Trunca descripción a MAX_DESCRIPCION caracteres.

    Args:
        descripcion: Texto de la descripción

    Returns:
        Descripción truncada si excede el límite
    """
    if not es_valor_valido(descripcion):
        return ''

    desc_str = str(descripcion).strip()

    if len(desc_str) > MAX_DESCRIPCION:
        return desc_str[:99]

    return desc_str


def limpiar_texto(texto: Any) -> str:
    """
    Limpia un campo de texto eliminando caracteres problemáticos.

    Args:
        texto: Texto a limpiar

    Returns:
        Texto limpio
    """
    if not es_valor_valido(texto):
        return ''

    texto_str = str(texto).strip()
    # Eliminar caracteres de control y no imprimibles
    texto_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', texto_str)
    return texto_str


def validar_registro(registro: Dict[str, Any]) -> Tuple[bool, Dict[str, str], List[str]]:
    """
    Valida un registro completo y lo normaliza.

    Args:
        registro: Diccionario con los campos del registro

    Returns:
        Tupla (es_válido, registro_normalizado, lista_errores)
    """
    errores = []
    registro_normalizado = {}

    # Validar CUIT (obligatorio)
    cuit_valido, cuit_norm, error_cuit = validar_cuit(registro.get('CUIT'))
    if not cuit_valido:
        errores.append(error_cuit)
    registro_normalizado['CUIT'] = cuit_norm

    # Validar Estado (obligatorio)
    estado_valido, estado_norm, error_estado = validar_estado(registro.get('Estado'))
    if not estado_valido:
        errores.append(error_estado)
    registro_normalizado['Estado'] = estado_norm

    # Validar Sub-Estado (condicional)
    if estado_valido:
        sub_valido, sub_norm, error_sub = validar_subestado(
            estado_norm, registro.get('Sub- Estado')
        )
        if not sub_valido:
            errores.append(error_sub)
        registro_normalizado['Sub- Estado'] = sub_norm
    else:
        registro_normalizado['Sub- Estado'] = ''

    # Validar Responsable (obligatorio)
    resp_valido, resp_norm, error_resp = validar_responsable(registro.get('Responsable'))
    if not resp_valido:
        errores.append(error_resp)
    registro_normalizado['Responsable'] = resp_norm

    # Campos que se limpian/truncan pero no son críticos
    registro_normalizado['Clase de Operación'] = 'ZCE1'  # Siempre fijo
    registro_normalizado['Cuenta'] = limpiar_texto(registro.get('Cuenta'))
    registro_normalizado['Desc. Acuerdo Comercial'] = limpiar_texto(
        registro.get('Desc. Acuerdo Comercial')
    )
    registro_normalizado['Acuerdo Comercial'] = limpiar_texto(
        registro.get('Acuerdo Comercial')
    )
    registro_normalizado['Descripción'] = truncar_descripcion(registro.get('Descripción'))
    registro_normalizado['Persona de Contacto'] = limpiar_texto(
        registro.get('Persona de Contacto')
    )
    registro_normalizado['Juzgado'] = limpiar_texto(registro.get('Juzgado'))
    registro_normalizado['Garante'] = limpiar_texto(registro.get('Garante'))
    registro_normalizado['Notas'] = limpiar_texto(registro.get('Notas'))

    # Determinar si el registro es válido (campos críticos sin errores)
    es_valido = len(errores) == 0

    return es_valido, registro_normalizado, errores
