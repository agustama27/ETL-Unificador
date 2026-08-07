"""
Configuración para integración ROMAN

Este módulo define la configuración para el merge entre datos de Retell y ROMAN,
incluyendo mapeos de columnas, campos sobrescribibles y validaciones.
"""

# Mapeo de nombres de columnas ROMAN → Retell
MAPEO_COLUMNAS_ROMAN = {
    'ID de Llamada': 'call_id',
    '[Salida] Estado': 'ESTADO',
    '[Salida] ESTADO': 'ESTADO',
    '[Salida] Subestado': 'SUBESTADO',
    '[Salida] SUBESTADO': 'SUBESTADO',
    '[Salida] Descripcion': 'DESCRIPCION',
    '[Salida] DESCRIPCION': 'DESCRIPCION',
    '[Salida] Observaciones': 'OBSERVACIONES',
    '[Salida] OBSERVACIONES': 'OBSERVACIONES',
    '[Salida] Email Valido': 'Email_valido',
    '[Salida] Email_valido': 'Email_valido',
    '[Salida] Fecha Compromiso': 'Fecha_compromiso',
    '[Salida] Fecha_compromiso': 'Fecha_compromiso',
    '[Salida] Monto Compromiso': 'Monto_compromiso',
    '[Salida] Monto_compromiso': 'Monto_compromiso',
    '[Salida] Compromiso De Pago Logrado': 'compromiso_de_pago_logrado',
    '[Salida] compromiso_de_pago_logrado': 'compromiso_de_pago_logrado',
}

# Campos que ROMAN puede sobrescribir (organizados por categoría)
CAMPOS_TIPIFICACION = ['ESTADO', 'SUBESTADO', 'DESCRIPCION', 'OBSERVACIONES']
CAMPOS_COMPROMISO = ['Fecha_compromiso', 'Monto_compromiso', 'compromiso_de_pago_logrado']
CAMPOS_VALIDACION = ['Email_valido']

# Lista completa de campos sobrescribibles
CAMPOS_SOBRESCRIBIBLES = (
    CAMPOS_TIPIFICACION +
    CAMPOS_COMPROMISO +
    CAMPOS_VALIDACION
)

# Campos que pertenecen a variables_dinamicas (vs postcall)
# Estos son campos que se recolectan durante la llamada
CAMPOS_VARIABLES_DINAMICAS = [
    'compromiso_de_pago_logrado',
    'Monto_compromiso',
    'Fecha_compromiso',
]

# Campos que pertenecen a postcall
# Estos son campos de análisis posterior a la llamada
CAMPOS_POSTCALL = [
    'ESTADO',
    'SUBESTADO',
    'DESCRIPCION',
    'OBSERVACIONES',
    'Email_valido',
]

# Campos protegidos que NUNCA deben modificarse
# Estos son datos del cliente y metadatos de la llamada
CAMPOS_PROTEGIDOS = [
    'call_id',
    'AgrupadorProducto',
    'CUIL',
    'ClienteNombre',
    'Cliente_BT',
    'Cuenta',
    'user_number',
]

# Valores que se consideran vacíos y NO deben sobrescribir
VALORES_VACIOS = [None, '', 'null', 'NULL', 'n/a', 'N/A', '-']

def es_valor_valido(valor) -> bool:
    """
    Determina si un valor es válido para sobrescribir.

    Args:
        valor: Valor a validar

    Returns:
        True si el valor es válido, False si es vacío/nulo
    """
    if valor in VALORES_VACIOS:
        return False

    # Verificar si es string vacío o solo espacios
    if isinstance(valor, str) and valor.strip() == '':
        return False

    return True


def normalizar_booleano(valor) -> bool:
    """
    Convierte valores diversos a booleano.

    Args:
        valor: Valor a convertir (puede ser str, bool, int, etc.)

    Returns:
        bool: Valor booleano normalizado
    """
    if isinstance(valor, bool):
        return valor

    if isinstance(valor, str):
        valor_lower = valor.lower().strip()
        if valor_lower in ['true', 'sí', 'si', 'yes', '1']:
            return True
        elif valor_lower in ['false', 'no', '0']:
            return False

    if isinstance(valor, (int, float)):
        return bool(valor)

    return False
