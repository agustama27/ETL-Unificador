"""
Catálogos de configuración para carga masiva al CRM Bancor

Define todos los valores válidos para estados, sub-estados y responsables
según las especificaciones del sistema de cargas masivas.
"""

# Clase de operación - siempre fija
CLASE_OPERACION = "ZCE1"

# Estados que NO requieren sub-estado
ESTADOS_SIN_SUBESTADO = {
    "E0004": "03. Contactado con terceros",
    "E0021": "04. Carta",
    "E0024": "05. IVR",
    "E0025": "06. Contactado con Titular",
    "E0020": "07ti. PdP Total Incumplida",
    "E0022": "07pc. PdP Parcial Cumplida",
    "E0026": "7pac. PdP Parc. Ac. Cumplida",
    "E0027": "7pi. PdP Parcial Incumplida",
    "E0028": "7pai. PdP Parc. Ac. Incumplida",
    "E0029": "09. Refinanciación",
    "E0005": "10. Sin Contacto con Titular",
    "E0030": "11. Sin datos de Contactación",
    "E0023": "12. Sin voluntad de pago",
    "E0006": "13. Aduce Fallecimiento",
    "E0003": "14. Posible Fraude",
    "E0014": "Asignación prejudicial (inicial)",
}

# Estados que SÍ requieren sub-estado obligatorio
ESTADOS_CON_SUBESTADO = {
    "E0012": "07. Promesa de Pago Pactada",
    "E0002": "08. Gestión de Refinanciación",
}

# Sub-estados válidos por estado
SUBESTADOS_POR_ESTADO = {
    "E0012": {
        "E001": "Parcial",
        "E002": "Parcial Acordado",
        "E003": "Total",
    },
    "E0002": {
        "E001": "En curso / Recibida",
        "E002": "Enviada a Bancor / Con Observaciones",
        "E003": "Enviada a liquidar",
    },
}

# Lista de todos los sub-estados válidos
SUBESTADOS_VALIDOS = ["E001", "E002", "E003"]

# Mapeo de nombres descriptivos de sub-estados a códigos CRM
MAPEO_SUBESTADOS_DESCRIPTIVOS = {
    # Para E0012 (Promesa de Pago Pactada)
    "parcial": "E001",
    "parcial acordado": "E002",
    "total": "E003",
    # Para E0002 (Gestión de Refinanciación)
    "en curso": "E001",
    "recibida": "E001",
    "en curso / recibida": "E001",
    "enviada a bancor": "E002",
    "con observaciones": "E002",
    "enviada a bancor / con observaciones": "E002",
    "enviada a liquidar": "E003",
}

# Todos los estados válidos (para validación rápida)
TODOS_LOS_ESTADOS = list(ESTADOS_SIN_SUBESTADO.keys()) + list(ESTADOS_CON_SUBESTADO.keys())

# Mapeo de nombres descriptivos (Retell/ROMAN) a códigos CRM
# Los estados que no tienen mapeo serán descartados
MAPEO_ESTADOS_RETELL_A_CRM = {
    # Estados con promesa de pago
    "promesa_de_pago_acordada": ("E0012", "E003"),  # Promesa de Pago Pactada - Total
    "promesa_de_pago_pactada": ("E0012", "E003"),   # Promesa de Pago Pactada - Total
    "promesa_parcial": ("E0012", "E001"),           # Promesa de Pago Pactada - Parcial
    "promesa_de_pago": ("E0012", "E003"),           # Promesa de Pago Pactada - Total

    # Estados de contacto
    "no_contesta": ("E0005", None),                 # Sin Contacto con Titular
    "sin_contacto_con_titular": ("E0005", None),                # Sin Contacto con Titular
    "contacto_con_titular": ("E0025", None),            # Contactado con Titular
    "contactado_con_titular": ("E0025", None),          # Alias defensivo
    "contacto_con_terceros": ("E0004", None),            # Contactado con Terceros
    "informa_pago": ("E0025", None),                # Contactado con Titular

    # Estados negativos
    "sin_voluntad_de_pago": ("E0023", None),        # Sin voluntad de pago
    "Sin_voluntad_de_pago": ("E0023", None),        # Sin voluntad de pago (variante)
    "decision_propia": ("E0023", None),             # Sin voluntad de pago

    # Estados de error/sin datos
    "llamada_interrumpida": ("E0030", None),        # Sin datos de Contactación
    "datos_erroneos": ("E0030", None),              # Sin datos de Contactación
    "sin_datos_de_contactacion": ("E0030", None),                   # Sin datos de Contactación

    # Refinanciación
    "refinanciacion": ("E0002", "E001"),            # Gestión de Refinanciación - En curso
    "gestion_de_refinanciacion": ("E0025", None),    # Gestión de Refinanciación - En curso

    # Otros
    "fallecido": ("E0006", None),                   # Aduce Fallecimiento
    "fraude": ("E0003", None),                      # Posible Fraude
    "ivr": ("E0024", None),                         # IVR
    "carta": ("E0021", None),                       # Carta
    "terceros": ("E0004", None),                    # Contactado con terceros
}

# Estados que deben ser descartados (no se cargan al CRM)
ESTADOS_A_DESCARTAR = [
    "llamada_interrumpida",  # No aporta valor para el CRM
    "datos_erroneos",        # Datos inválidos
]

# Mapeo de responsables (nombre estudio → código)
RESPONSABLES = {
    "ALTERMAN": "7000004923",
    "DIAZ YOFRE": "7000002877",
    "EVOLTIS": "5000000786",
    "GEEX": "5000000784",
    "JLC": "7000002901",
    "KONECTA": "5000000785",
    "RECOVERY MANAGEMENT": "7000005550",
    "TILLARD": "7000002878",
    "TONELLI": "7000005647",
    "VILATTA": "7000002897",
}

# Mapeo inverso (código → nombre) para referencia
RESPONSABLES_POR_CODIGO = {v: k for k, v in RESPONSABLES.items()}

# Longitudes máximas
MAX_DESCRIPCION = 100
LONGITUD_CUIT = 11

# Columnas de salida (orden exacto requerido por el CRM)
COLUMNAS_SALIDA = [
    "Clase de Operación",
    "Estado",
    "Sub- Estado",  # Nota: tiene espacio antes de Estado (así está en la plantilla)
    "CUIT",
    "Cuenta",
    "Desc. Acuerdo Comercial",
    "Acuerdo Comercial",
    "Responsable",
    "Descripción",
    "Persona de Contacto",
    "Juzgado",
    "Garante",
    "Notas",
]

# Nombre de la hoja en el Excel
NOMBRE_HOJA = "MODELO envio"

# Valores que se consideran vacíos
VALORES_VACIOS = [None, '', 'null', 'NULL', 'n/a', 'N/A', '-', 'nan', 'NaN', 'None']


def es_valor_valido(valor) -> bool:
    """
    Determina si un valor es válido (no vacío/nulo).

    Args:
        valor: Valor a validar

    Returns:
        True si el valor es válido, False si es vacío/nulo
    """
    if valor in VALORES_VACIOS:
        return False
    if isinstance(valor, str) and valor.strip() == '':
        return False
    return True
