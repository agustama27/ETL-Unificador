from typing import Dict
import pandas as pd


# Map de variantes de nombres de columnas -> nombres canónicos en español
SPANISH_COLUMN_MAP = {
    # claves variantes -> nombre canonical en español
    "idhost": "IdHost",
    "idh": "IdHost",
    "id_host": "IdHost",
    "id host": "IdHost",
    "nombre": "Nombre",
    "name": "Nombre",
    "documento": "Documento",
    "dni": "Documento",
    "cuit": "Documento",
    "codarea": "CodArea",
    "cod_area": "CodArea",
    "nrotelefonorestante": "NroTelefonoRestante",
    "nro_telefono_restante": "NroTelefonoRestante",
    "numerocompleto": "NumeroCompleto",
    "numero_completo": "NumeroCompleto",
    "telefono": "NumeroCompleto",
    "telefonofinal": "NumeroCompleto",
    "usodireccionpersona": "UsoDireccionPersona",
    "uso_direccion_persona": "UsoDireccionPersona",
    "deudavencidapesificada": "DeudaVencidaPesificada",
    "montovencido": "MontoVencido",
    "montoproducto": "MontoProducto",
    "numeroproductounified": "NumeroProductoUnified",
    "productotipo": "ProductoTipo",
    "email": "Email",
    "mail": "Email",
}


def standardize_column_names_spanish(df: pd.DataFrame, extra_map: Dict[str, str] = None) -> pd.DataFrame:
    """Devuelve DataFrame con nombres de columnas normalizados a forma canónica en español.

    - Usa `SPANISH_COLUMN_MAP` + `extra_map` para mapear variantes.
    - Normaliza las claves temporales quitando espacios, guiones y pasando a minúsculas.
    - Columnas no reconocidas se convierten a snake_case en minúsculas para evitar colisiones.
    """
    if extra_map is None:
        extra_map = {}

    def normalize_key(s: str) -> str:
        return "".join(ch for ch in str(s).lower() if ch.isalnum())

    lookup = {}
    for k, v in {**SPANISH_COLUMN_MAP, **extra_map}.items():
        lookup[normalize_key(k)] = v

    rename_map = {}
    for col in df.columns:
        nk = normalize_key(col)
        if nk in lookup:
            rename_map[col] = lookup[nk]
        else:
            # fallback: convertir a snake_case en minúsculas
            new = (
                col.strip()
                .replace(" ", "_")
                .replace("-", "_")
                .lower()
            )
            rename_map[col] = new

    return df.rename(columns=rename_map)
