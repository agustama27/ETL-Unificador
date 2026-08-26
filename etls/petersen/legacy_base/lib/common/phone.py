import re
from typing import Dict


def normalize_phone(value: str, rules: Dict[str, str]) -> str:
    """Normaliza un teléfono a formato +CCXXXXXXXX.

    Reglas simples:
    - Elimina todo lo que no sean dígitos.
    - Si el número ya contiene el código de país (54 o 549), lo mantiene y añade '+' delante.
    - Si no contiene código de país, antepone `prefijo_nacional` si se proporciona en `rules`,
      si no, usa '+54' por defecto.

    Esta implementación es intencionalmente conservadora; adaptar según muestras reales.
    """
    if value is None:
        return ""

    s = str(value)
    # eliminar espacios y caracteres no numéricos
    digits = re.sub(r"\D", "", s)
    if not digits:
        return ""

    # si ya tiene country code 54 o 549
    if digits.startswith("549") or digits.startswith("54"):
        return "+" + digits

    # normalmente los números locales pueden comenzar con 0 o sin 54
    pref_nac = rules.get("prefijo_nacional") if rules else None
    if not pref_nac:
        pref_nac = "+54"

    # quitar ceros a la izquierda
    digits = digits.lstrip("0")
    return pref_nac + digits
