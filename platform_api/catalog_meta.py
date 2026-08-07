"""Human-facing metadata layered over the declarative catalog."""

CLIENTS = {
    "naranjax": "Naranja X",
    "encuestacx": "Encuesta CX",
    "bancor": "Bancor",
    "epec": "EPEC",
    "fravega": "Frávega",
    "clarouy": "Claro Uruguay",
    "social": "Social Learning",
    "petersen": "Petersen",
}

INERT_REASONS = {
    "bancor.resultados.retell": "Requiere API Retell.ai con credenciales — integración pendiente.",
    "bancor.carga_masiva": "Diseño del módulo de carga masiva CRM pendiente.",
    "bancor.cupones": "El proceso legacy de cupones sigue en desarrollo (plantilla VBA).",
    "clarouy.encuestas.retell": "Requiere API Retell.ai con credenciales — integración pendiente.",
    "epec.tipif.retell": "Requiere API Retell.ai con credenciales — integración pendiente.",
    "fravega.resultados.retell": "Requiere API Retell.ai con credenciales — integración pendiente.",
    "petersen.retell": "Requiere API Retell.ai con credenciales — integración pendiente.",
}

DEADLINE_HINTS = {
    "bancor.base.daily": "Entrega miércoles y viernes antes de 12:30",
}

# Deadlines estructurados para /api/schedule. weekdays usa la convención de
# date.weekday(): lunes=0 ... domingo=6.
DEADLINES = {
    "bancor.base.daily": {"weekdays": (2, 4), "before": "12:30"},
}


def client_of(etl_id: str) -> str:
    prefix = etl_id.split(".", 1)[0]
    return CLIENTS.get(prefix, prefix)
