"""
Configuración de campos y enums para encuestas Claro Uruguay.

Este archivo contiene pure data - sin clases ni I/O.
"""

# Columnas del output final (orden exacto)
COLUMNAS_SALIDA: list[str] = [
    'call_id', 'msisdn', 'customer_id', 'nombre_cliente', 'campaign_id',
    'encuesta_completada', 'motivo_cierre', 'fecha_hora', 'global_experience',
    'descripcion_inicial', 'comentario_mejora', 'sin_comentarios', 'detalle_experiencia',
    'tipo_experiencia', 'categoria', 'subcategoria', 'es_cobertura',
    'texto_domicilio_cliente', 'domicilio_validado', 'domicilio_normalizado',
    'domicilio_intentos', 'inconveniente_continua', 'pudiste_solucionarlo',
    'derivar_a_asesor', 'skill_destino', 'id_caso_reclamo'
]

COLUMNAS_FIJAS = COLUMNAS_SALIDA

# Mapeo de nombres de columnas ROMAN → nombres internos
MAPEO_COLUMNAS_ROMAN: dict[str, str] = {
    'ID de Llamada': 'call_id',
    'Call ID':       'call_id',
    'call_id':       'call_id',
    'CallID':        'call_id',
    'callId':        'call_id',
}

# Columnas aceptadas para call_id en CSV de entrada
COLUMNAS_CALL_ID = ['Call ID', 'ID de Llamada', 'call_id', 'CallID', 'callId']

# Grupos de campos por categoría semántica
CAMPOS_TIPIFICACION: list[str] = [
    'motivo_cierre', 'global_experience', 'tipo_experiencia', 'categoria', 'subcategoria'
]

CAMPOS_EXPERIENCIA: list[str] = [
    'descripcion_inicial', 'comentario_mejora', 'detalle_experiencia'
]

CAMPOS_DOMICILIO: list[str] = [
    'texto_domicilio_cliente', 'domicilio_validado', 'domicilio_normalizado', 'domicilio_intentos'
]

CAMPOS_CIERRE: list[str] = [
    'encuesta_completada', 'fecha_hora', 'sin_comentarios', 'es_cobertura',
    'inconveniente_continua', 'pudiste_solucionarlo', 'derivar_a_asesor',
    'skill_destino', 'id_caso_reclamo'
]

# Campos que ROMAN puede sobrescribir sobre Retell
CAMPOS_SOBRESCRIBIBLES: list[str] = (
    CAMPOS_TIPIFICACION + CAMPOS_EXPERIENCIA + CAMPOS_DOMICILIO + CAMPOS_CIERRE
)

# Campos que NUNCA se modifican por ROMAN (identidad del registro)
CAMPOS_PROTEGIDOS: list[str] = [
    'call_id', 'msisdn', 'customer_id', 'campaign_id'
]

# Valores considerados vacíos/nulos en cualquier fuente
VALORES_VACIOS: list = [None, '', 'null', 'NULL', 'n/a', 'N/A', '-', 'nan', 'NaN', 'None']

# Enums válidos por campo
ENUMS_GLOBAL_EXPERIENCE: list[str] = [
    'MUY_BUENA', 'PODRIA_MEJORAR', 'TUVO_INCONVENIENTES', 'NO_ENTENDIA'
]

ENUMS_MOTIVO_CIERRE: list[str] = [
    'OK_RECHAZO_CLIENTE', 'DERIVADO_ASESOR', 'FALLIDA_NULL_REC'
]

ENUMS_TIPO_EXPERIENCIA: list[str] = [
    'MEJORA', 'INCONVENIENTE'
]

ENUMS_CATEGORIA: list[str] = [
    'COBERTURA_SERVICIO', 'PORTABILIDAD', 'FACTURACION',
    'ACTIVACION', 'ATENCION_CLIENTES', 'OTROS'
]


def es_valor_valido(valor) -> bool:
    """Retorna True si el valor no es considerado vacío/nulo."""
    if valor is None:
        return False
    if isinstance(valor, str):
        return valor.strip() not in VALORES_VACIOS
    return True


def normalizar_booleano(valor) -> bool:
    """Convierte strings y enteros a bool. Retorna False para valores vacíos."""
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return bool(valor)
    if isinstance(valor, str):
        return valor.strip().lower() in ('true', '1', 'yes', 'sí', 'si', 'verdadero')
    return False
