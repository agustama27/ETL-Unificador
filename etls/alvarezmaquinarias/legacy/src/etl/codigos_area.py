"""Tabla localidad → código de área para completar teléfonos de saldos.

El export "ficha por página" de Saldos de clientes trae la localidad de cada
cliente como `CP - NOMBRE` (p. ej. `6120 - LABOULAYE`). Esta tabla mapea el
código postal a la característica telefónica según los directorios públicos
de prefijos argentinos (codigodearea.com.ar, caracteristicatelefonica.com).

Solo se usa para completar números locales que vienen sin código de área.
Un CP fuera de la tabla deja el teléfono como esté: nunca se adivina.

Supuesto de negocio (ver docs/ASSUMPTIONS.md): el teléfono del cliente
pertenece a la característica de su localidad declarada. Cada completado se
informa como conteo agregado en la corrida.
"""

from __future__ import annotations

import re
from typing import Optional

_LOCALIDAD_CP_RE = re.compile(r"^\s*(\d{4})\s*-")

# CP → característica. Ampliar acá cuando aparezcan localidades nuevas;
# verificar el prefijo en un directorio público antes de agregarlo.
AREA_POR_CP: dict[str, str] = {
    # AMBA
    "1004": "11",  # Capital Federal
    "1008": "11",
    "1034": "11",
    "1092": "11",
    "1106": "11",
    "1613": "11",  # Los Polvorines
    "1900": "221",  # La Plata
    # Santa Fe
    "2173": "3464",  # Chabás
    "2505": "3471",  # Las Parejas
    "6100": "3382",  # Rufino
    # Córdoba
    "2650": "3463",  # Canals
    "2651": "3463",  # Aldea Santa María
    "2670": "3584",  # La Carlota
    "5101": "3382",  # La Cesira
    "5800": "358",  # Río Cuarto
    "5809": "358",  # General Cabrera
    "5831": "3585",  # Monte de los Gauchos
    "5843": "3585",  # Adelia María
    "5923": "358",  # General Deheza (corrida 25/08/2026)
    "5929": "353",  # Hernando
    "6120": "3385",  # Laboulaye
    "6123": "3385",  # Melo
    "6125": "3385",  # Serrano
    "6127": "3385",  # Jovita
    "6132": "3385",  # General Levalle
    "6140": "3583",  # Vicuña Mackenna (corrida 25/08/2026)
    # San Luis
    "5730": "2657",  # Villa Mercedes
    "5736": "2657",  # Fraga y Dpto. Pringles (corrida 12/08/2026)
    # Buenos Aires
    "3260": "3442",  # Concepción del Uruguay (Entre Ríos)
    "6030": "236",  # Vedia
    "6034": "236",  # Alberdi (Leandro N. Alem)
    "6105": "3388",  # Cañada Seca / Santa Regina (Gral. Villegas)
    "6241": "3388",  # Emilio V. Bunge
    "6244": "3388",  # Banderaló
}


def postal_code_for_locality(localidad_raw: Optional[str]) -> Optional[str]:
    """Devuelve el CP de una localidad `CP - NOMBRE`, esté mapeado o no.

    Sirve para reportar qué códigos postales faltan en `AREA_POR_CP`: sin
    eso, un teléfono sin completar solo se ve como un conteo y hay que
    adivinar qué agregar a la tabla. El CP identifica una localidad, no a un
    cliente, así que puede loguearse sin exponer datos personales.
    """
    if not localidad_raw:
        return None
    match = _LOCALIDAD_CP_RE.match(str(localidad_raw))
    return match.group(1) if match else None


def area_code_for_locality(localidad_raw: Optional[str]) -> Optional[str]:
    """Devuelve la característica para una localidad `CP - NOMBRE`, o None
    si el CP no está mapeado (el teléfono queda sin completar)."""
    cp = postal_code_for_locality(localidad_raw)
    return AREA_POR_CP.get(cp) if cp else None
