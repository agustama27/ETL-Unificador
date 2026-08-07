from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import shutil
import unicodedata

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
TELEFONO_LONGITUD_MIN = 11
TELEFONO_LONGITUD_MAX = 13
TELEFONO_CELULAR_LONGITUD_MIN = 12
TELEFONO_CELULAR_LONGITUD_MAX = 13
MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00e2", "\u00d0", "\ufffd")
COLUMNAS_REQUERIDAS_BASE = (
    "SUMINISTRO",
    "CONTRATO",
    "RAZON_SOCIAL",
    "BARRIO",
    "DIRECCION",
    "FECHA_EJECUCION",
    "TELEFONO",
    "TELEFONO_CELULAR",
)
COLUMNA_MOTIVO = "MOTIVO"
COLUMNA_DESCRIPCION_COMPLETA = "DESCRIPCION_COMPLETA"
COLUMNA_FECHA_EJECUCION = "FECHA_EJECUCION"
COLUMNA_FECHA_EJECUTADO = "FECHA_EJECUTADO"
COLUMNA_ORD_FECHA_FIN = "ORD_FECHA_FIN"
BASE_EPEC_COLUMNAS_SALIDA = (
    "nombre_cliente",
    "telefono",
    "telefono_celular",
    "contrato",
    "dia_visita",
    "motivo",
    "direccion",
    "resultado_solicitud",
    "medidor",
    "dia_gestion",
    "suministro",
    "costo_instalacion",
    "gasto_movilidad",
)


@dataclass
class ProcessResult:
    source_path: Path
    copied_input_path: Path
    generated_base_path: Path
    generated_phones_path: Path
    processing_timestamp: str
    rows: int
    columns: int


def puntaje_mojibake(texto: str) -> int:
    return sum(texto.count(marker) for marker in MOJIBAKE_MARKERS)


def corregir_mojibake_utf8_latin1(valor: object) -> object:
    if pd.isna(valor):
        return valor

    if not isinstance(valor, str):
        return valor

    texto_original = valor
    if not texto_original:
        return texto_original

    score_original = puntaje_mojibake(texto_original)
    if score_original == 0:
        return texto_original

    texto_actual = texto_original
    score_actual = score_original

    for _ in range(2):
        try:
            texto_candidato = texto_actual.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break

        score_candidato = puntaje_mojibake(texto_candidato)
        if score_candidato >= score_actual:
            break

        texto_actual = texto_candidato
        score_actual = score_candidato

    return texto_actual if score_actual < score_original else texto_original


def normalizar_nombre_columna(columna: object) -> str:
    texto = unicodedata.normalize("NFKD", str(columna))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return texto.upper().replace(" ", "_")


def es_columna_descripcion_o_motivo(columna: object) -> bool:
    nombre = normalizar_nombre_columna(columna)
    return "DESCRIPCION" in nombre or "MOTIVO" in nombre


def sanear_columnas_descripcion(df: pd.DataFrame) -> pd.DataFrame:
    columnas_objetivo = [col for col in df.columns if es_columna_descripcion_o_motivo(col)]
    for columna in columnas_objetivo:
        df[columna] = df[columna].apply(corregir_mojibake_utf8_latin1)
    return df


def quitar_15_local_argentino(cuerpo: str) -> tuple[str, bool]:
    if not cuerpo:
        return cuerpo, False

    if len(cuerpo) != 12:
        return cuerpo, False

    for largo_caracteristica in (2, 3, 4):
        fin_caracteristica = largo_caracteristica
        if cuerpo[fin_caracteristica:fin_caracteristica + 2] != "15":
            continue

        largo_numero = len(cuerpo) - (largo_caracteristica + 2)
        if largo_numero < 6 or largo_numero > 8:
            continue

        cuerpo_sin_15 = cuerpo[:fin_caracteristica] + cuerpo[fin_caracteristica + 2:]
        if 8 <= len(cuerpo_sin_15) <= 10:
            return cuerpo_sin_15, True

    return cuerpo, False


def es_patron_trivial_invalido(digitos: str) -> bool:
    if not digitos:
        return True

    if set(digitos) == {"0"}:
        return True

    if len(set(digitos)) == 1:
        return True

    def es_secuencia(paso: int) -> bool:
        for i in range(1, len(digitos)):
            actual = int(digitos[i])
            previo = int(digitos[i - 1])
            if actual != (previo + paso) % 10:
                return False
        return True

    if es_secuencia(1) or es_secuencia(-1):
        return True

    for largo_bloque in (1, 2, 3, 4):
        if len(digitos) % largo_bloque != 0:
            continue
        bloque = digitos[:largo_bloque]
        if bloque * (len(digitos) // largo_bloque) == digitos:
            return True

    return False


def normalizar_numero_telefono(valor: object, tipo: str) -> str:
    if pd.isna(valor):
        return ""

    digitos = "".join(ch for ch in str(valor) if ch.isdigit())
    if not digitos:
        return ""

    digitos = digitos.lstrip("0")
    if not digitos:
        return ""

    if digitos.startswith("549"):
        cuerpo = digitos[3:]
    elif digitos.startswith("54"):
        cuerpo = digitos[2:]
    else:
        cuerpo = digitos

    while cuerpo.startswith("549"):
        cuerpo = cuerpo[3:]
    while cuerpo.startswith("54"):
        cuerpo = cuerpo[2:]

    cuerpo, _ = quitar_15_local_argentino(cuerpo)
    if not cuerpo:
        return ""

    prefijo = "54" if tipo == "fijo" else "549"
    return prefijo + cuerpo


def normalizar_columnas_telefono(df: pd.DataFrame) -> pd.DataFrame:
    if "TELEFONO" in df.columns:
        df["TELEFONO"] = df["TELEFONO"].apply(lambda x: normalizar_numero_telefono(x, "fijo"))
    if "TELEFONO_CELULAR" in df.columns:
        df["TELEFONO_CELULAR"] = df["TELEFONO_CELULAR"].apply(
            lambda x: normalizar_numero_telefono(x, "celular")
        )
    return df


def mapear_columnas_descripcion_a_motivo(df: pd.DataFrame) -> pd.DataFrame:
    if COLUMNA_DESCRIPCION_COMPLETA not in df.columns:
        return df

    descripcion = df[COLUMNA_DESCRIPCION_COMPLETA]
    if COLUMNA_MOTIVO not in df.columns:
        df[COLUMNA_MOTIVO] = descripcion
    else:
        motivo_vacio = df[COLUMNA_MOTIVO].isna() | (df[COLUMNA_MOTIVO].astype(str).str.strip() == "")
        df.loc[motivo_vacio, COLUMNA_MOTIVO] = descripcion[motivo_vacio]

    return df.drop(columns=[COLUMNA_DESCRIPCION_COMPLETA])


def normalizar_columna_fecha_ejecucion(df: pd.DataFrame) -> pd.DataFrame:
    aliases = [COLUMNA_FECHA_EJECUTADO, COLUMNA_ORD_FECHA_FIN]

    if COLUMNA_FECHA_EJECUCION in df.columns:
        aliases_presentes = [alias for alias in aliases if alias in df.columns]
        return df.drop(columns=aliases_presentes) if aliases_presentes else df

    for alias in aliases:
        if alias in df.columns:
            return df.rename(columns={alias: COLUMNA_FECHA_EJECUCION})
    return df


def validar_columnas_requeridas(df: pd.DataFrame, nombre_archivo: str) -> None:
    faltantes_base = [col for col in COLUMNAS_REQUERIDAS_BASE if col not in df.columns]
    if faltantes_base:
        raise ValueError(f"Archivo {nombre_archivo} sin columnas requeridas: {faltantes_base}")

    if COLUMNA_MOTIVO not in df.columns and COLUMNA_DESCRIPCION_COMPLETA not in df.columns:
        raise ValueError(
            f"Archivo {nombre_archivo} debe contener '{COLUMNA_MOTIVO}' o '{COLUMNA_DESCRIPCION_COMPLETA}'"
        )


def es_longitud_telefono_valida(valor: object, prefijo_esperado: str, longitud_min: int, longitud_max: int) -> bool:
    if pd.isna(valor):
        return False

    telefono = str(valor).strip()
    if not telefono or not telefono.isdigit() or not telefono.startswith(prefijo_esperado):
        return False

    cuerpo = telefono[len(prefijo_esperado):]
    if es_patron_trivial_invalido(cuerpo):
        return False

    return longitud_min <= len(telefono) <= longitud_max


def limpiar_telefonos_invalidos(df: pd.DataFrame) -> pd.DataFrame:
    if "TELEFONO" in df.columns:
        telefono = df["TELEFONO"].fillna("").astype(str).str.strip()
        telefono_no_vacio = telefono != ""
        telefono_valido = df["TELEFONO"].apply(
            lambda x: es_longitud_telefono_valida(
                x,
                prefijo_esperado="54",
                longitud_min=TELEFONO_LONGITUD_MIN,
                longitud_max=TELEFONO_LONGITUD_MAX,
            )
        )
        df.loc[telefono_no_vacio & ~telefono_valido, "TELEFONO"] = ""

    if "TELEFONO_CELULAR" in df.columns:
        celular = df["TELEFONO_CELULAR"].fillna("").astype(str).str.strip()
        celular_no_vacio = celular != ""
        celular_valido = df["TELEFONO_CELULAR"].apply(
            lambda x: es_longitud_telefono_valida(
                x,
                prefijo_esperado="549",
                longitud_min=TELEFONO_CELULAR_LONGITUD_MIN,
                longitud_max=TELEFONO_CELULAR_LONGITUD_MAX,
            )
        )
        df.loc[celular_no_vacio & ~celular_valido, "TELEFONO_CELULAR"] = ""

    return df


def separar_duplicados_por_pk_telefonos(df: pd.DataFrame, base_generada_dir: Path) -> pd.DataFrame:
    telefono_key = (
        df["TELEFONO"].fillna("").astype(str).str.strip()
        if "TELEFONO" in df.columns
        else pd.Series("", index=df.index)
    )
    celular_key = (
        df["TELEFONO_CELULAR"].fillna("").astype(str).str.strip()
        if "TELEFONO_CELULAR" in df.columns
        else pd.Series("", index=df.index)
    )

    claves_df = pd.DataFrame({"_pk_telefono": telefono_key, "_pk_telefono_celular": celular_key})
    mascara_grupo_duplicado = claves_df.duplicated(
        subset=["_pk_telefono", "_pk_telefono_celular"],
        keep=False,
    )

    df_excluidos = df[mascara_grupo_duplicado].copy()
    df_principal = df[~mascara_grupo_duplicado].copy()

    if not df_excluidos.empty:
        carpeta_debug = base_generada_dir / "debug"
        carpeta_debug.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta_debug = carpeta_debug / f"duplicados_telefono_excluidos_{timestamp}.csv"
        df_excluidos.to_csv(ruta_debug, sep=";", index=False, encoding="utf-8", na_rep="")

    return df_principal


def asignar_connection_result(row: pd.Series) -> str:
    tiene_medidor = False
    tiene_motivo = False

    if "MEDIDOR" in row.index:
        medidor = row["MEDIDOR"]
        if pd.notna(medidor) and str(medidor).strip() != "":
            tiene_medidor = True

    if "MOTIVO" in row.index:
        motivo = row["MOTIVO"]
        if pd.notna(motivo) and str(motivo).strip() != "":
            tiene_motivo = True

    if tiene_medidor:
        return "CX"
    if tiene_motivo:
        return "CXI"
    if not tiene_medidor and not tiene_motivo:
        return "CXWEB"
    return "NO IDENTIFICADO"


def _read_input_file(source_path: Path) -> pd.DataFrame:
    extension = source_path.suffix.lower()

    if extension == ".csv":
        last_error: Exception | None = None
        for encoding in ("utf-8", "latin-1", "cp1252", "iso-8859-1"):
            for separator in (";", ","):
                try:
                    df_temp = pd.read_csv(source_path, sep=separator, encoding=encoding, nrows=0)
                    dtype_dict: dict[str, type[str]] = {}
                    if "TELEFONO" in df_temp.columns:
                        dtype_dict["TELEFONO"] = str
                    if "TELEFONO_CELULAR" in df_temp.columns:
                        dtype_dict["TELEFONO_CELULAR"] = str

                    df = pd.read_csv(
                        source_path,
                        sep=separator,
                        encoding=encoding,
                        dtype=dtype_dict if dtype_dict else None,
                    )
                    if len(df.columns) > 1:
                        break
                except Exception as error:  # pragma: no cover - best effort fallback
                    last_error = error
                    continue
            else:
                continue
            break

        if "df" not in locals():
            for encoding in ("utf-8", "latin-1", "cp1252", "iso-8859-1"):
                try:
                    df_temp = pd.read_csv(source_path, encoding=encoding, nrows=0)
                    dtype_dict = {}
                    if "TELEFONO" in df_temp.columns:
                        dtype_dict["TELEFONO"] = str
                    if "TELEFONO_CELULAR" in df_temp.columns:
                        dtype_dict["TELEFONO_CELULAR"] = str
                    df = pd.read_csv(source_path, encoding=encoding, dtype=dtype_dict if dtype_dict else None)
                    break
                except Exception as error:  # pragma: no cover - best effort fallback
                    last_error = error
                    continue
            else:
                raise ValueError(f"No se pudo leer el CSV '{source_path.name}': {last_error}")

        return df

    if extension in {".xlsx", ".xls"}:
        try:
            df_temp = pd.read_excel(source_path, sheet_name=0, engine="openpyxl", nrows=0)
        except ImportError:
            try:
                df_temp = pd.read_excel(source_path, sheet_name=0, engine="xlrd", nrows=0)
            except ImportError as error:
                raise ImportError(
                    "Para leer archivos Excel se necesita instalar 'openpyxl' o 'xlrd'. "
                    "Ejecuta: pip install openpyxl"
                ) from error
        except Exception:
            df_temp = None

        dtype_dict = {}
        if df_temp is not None:
            if "TELEFONO" in df_temp.columns:
                dtype_dict["TELEFONO"] = str
            if "TELEFONO_CELULAR" in df_temp.columns:
                dtype_dict["TELEFONO_CELULAR"] = str

        try:
            return pd.read_excel(
                source_path,
                sheet_name=0,
                engine="openpyxl",
                dtype=dtype_dict if dtype_dict else None,
            )
        except ImportError:
            try:
                return pd.read_excel(
                    source_path,
                    sheet_name=0,
                    engine="xlrd",
                    dtype=dtype_dict if dtype_dict else None,
                )
            except ImportError as error:
                raise ImportError(
                    "Para leer archivos Excel se necesita instalar 'openpyxl' o 'xlrd'. "
                    "Ejecuta: pip install openpyxl"
                ) from error
        except Exception as error:
            try:
                return pd.read_excel(source_path, sheet_name=0, dtype=dtype_dict if dtype_dict else None)
            except Exception as fallback_error:
                raise ValueError(
                    f"No se pudo leer el Excel '{source_path.name}': {fallback_error}"
                ) from error

    raise ValueError(
        f"Extension no soportada: '{extension}'. Formatos permitidos: {sorted(SUPPORTED_EXTENSIONS)}"
    )


def _build_processing_paths(output_root: Path) -> tuple[Path, Path, str, str]:
    now = datetime.now()
    day_folder = now.strftime("%d-%m-%Y")
    timestamp = now.strftime("%H-%M-%S-%f")

    day_root = output_root / day_folder
    base_recibida_dir = day_root / "Base Recibida"
    base_generada_dir = day_root / "Base Generada"

    base_recibida_dir.mkdir(parents=True, exist_ok=True)
    base_generada_dir.mkdir(parents=True, exist_ok=True)

    return base_recibida_dir, base_generada_dir, timestamp, now.isoformat(timespec="seconds")


def _build_output_file_path(base_generada_dir: Path, base_name: str, date_key: str, timestamp: str) -> Path:
    default_path = base_generada_dir / f"{base_name}_{date_key}.csv"
    if not default_path.exists():
        return default_path
    return base_generada_dir / f"{base_name}_{date_key}_{timestamp}.csv"


def _prepare_dataframe(source_path: Path, base_generada_dir: Path) -> pd.DataFrame:
    df = _read_input_file(source_path)
    df = df.dropna(how="all")
    df = normalizar_columna_fecha_ejecucion(df)
    validar_columnas_requeridas(df, source_path.name)
    df = sanear_columnas_descripcion(df)
    df = mapear_columnas_descripcion_a_motivo(df)
    df = normalizar_columnas_telefono(df)

    columnas_prioritarias = ["RAZON_SOCIAL", "TELEFONO", "TELEFONO_CELULAR"]
    columnas_resto = [col for col in df.columns if col not in columnas_prioritarias]
    columnas_ordenadas = [col for col in columnas_prioritarias if col in df.columns] + sorted(columnas_resto)
    df = df[columnas_ordenadas]

    df = df.fillna("")
    df = normalizar_columnas_telefono(df)
    df = limpiar_telefonos_invalidos(df)
    df = separar_duplicados_por_pk_telefonos(df, base_generada_dir)
    df["CONNECTION_RESULT"] = df.apply(asignar_connection_result, axis=1)
    return df


def _guardar_base_epec(df: pd.DataFrame, output_path: Path) -> None:
    def columna_o_vacia(df_fuente: pd.DataFrame, nombre_columna: str) -> pd.Series:
        if nombre_columna in df_fuente.columns:
            columna = df_fuente[nombre_columna]
            if isinstance(columna, pd.DataFrame):
                columna = columna.iloc[:, 0]
            if isinstance(columna, pd.Series):
                return columna.fillna("")
        return pd.Series("", index=df_fuente.index)

    telefono = columna_o_vacia(df, "TELEFONO").astype(str).str.strip()
    telefono_celular = columna_o_vacia(df, "TELEFONO_CELULAR").astype(str).str.strip()

    df_salida = pd.DataFrame(
        {
            "nombre_cliente": columna_o_vacia(df, "RAZON_SOCIAL"),
            "telefono": telefono,
            "telefono_celular": telefono_celular,
            "contrato": columna_o_vacia(df, "CONTRATO"),
            "dia_visita": columna_o_vacia(df, "DIA_VISITA"),
            "motivo": columna_o_vacia(df, "MOTIVO"),
            "direccion": columna_o_vacia(df, "DIRECCION"),
            "resultado_solicitud": columna_o_vacia(df, "CONNECTION_RESULT"),
            "medidor": columna_o_vacia(df, "MEDIDOR"),
            "dia_gestion": columna_o_vacia(df, "FECHA_EJECUCION"),
            "suministro": columna_o_vacia(df, "SUMINISTRO"),
            "costo_instalacion": columna_o_vacia(df, "COSTO_INSTALACION"),
            "gasto_movilidad": columna_o_vacia(df, "GASTO_MOVILIDAD"),
        }
    )
    df_salida = df_salida[list(BASE_EPEC_COLUMNAS_SALIDA)]
    df_salida.to_csv(output_path, sep=";", index=False, encoding="utf-8", na_rep="")


def _guardar_telefonos_epec(df: pd.DataFrame, output_path: Path) -> None:
    if "TELEFONO" not in df.columns and "TELEFONO_CELULAR" not in df.columns:
        raise ValueError("No se encontraron columnas de telefono en los datos")

    numero_telefono = df["TELEFONO"] if "TELEFONO" in df.columns else pd.Series("", index=df.index)
    numero_celular = df["TELEFONO_CELULAR"] if "TELEFONO_CELULAR" in df.columns else pd.Series("", index=df.index)
    df_telefonos = pd.DataFrame({"NumeroTelefono": numero_telefono, "NumeroCelular": numero_celular}).fillna("")

    def normalizar_y_validar(valor: object, tipo: str) -> str:
        numero = normalizar_numero_telefono(valor, tipo)
        if not numero:
            return ""

        if tipo == "fijo":
            es_valido = es_longitud_telefono_valida(
                numero,
                prefijo_esperado="54",
                longitud_min=TELEFONO_LONGITUD_MIN,
                longitud_max=TELEFONO_LONGITUD_MAX,
            )
        else:
            es_valido = es_longitud_telefono_valida(
                numero,
                prefijo_esperado="549",
                longitud_min=TELEFONO_CELULAR_LONGITUD_MIN,
                longitud_max=TELEFONO_CELULAR_LONGITUD_MAX,
            )

        return numero if es_valido else ""

    df_telefonos["NumeroTelefono"] = df_telefonos["NumeroTelefono"].apply(
        lambda x: normalizar_y_validar(x, "fijo")
    )
    df_telefonos["NumeroCelular"] = df_telefonos["NumeroCelular"].apply(
        lambda x: normalizar_y_validar(x, "celular")
    )

    todos_los_numeros = [
        n for n in pd.concat([df_telefonos["NumeroTelefono"], df_telefonos["NumeroCelular"]], ignore_index=True) if n
    ]
    conteo_numeros = Counter(todos_los_numeros)
    duplicados = {numero for numero, total in conteo_numeros.items() if total > 1}

    if duplicados:
        duplicados_lista = list(duplicados)
        df_telefonos.loc[df_telefonos["NumeroTelefono"].isin(duplicados_lista), "NumeroTelefono"] = ""
        df_telefonos.loc[df_telefonos["NumeroCelular"].isin(duplicados_lista), "NumeroCelular"] = ""

    df_telefonos = df_telefonos[
        (df_telefonos["NumeroTelefono"] != "") | (df_telefonos["NumeroCelular"] != "")
    ].copy()
    df_telefonos.to_csv(output_path, sep=";", index=False, encoding="utf-8")


def process_base_file(source_file: str | Path, output_root: str | Path) -> ProcessResult:
    source_path = Path(source_file).expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise FileNotFoundError(f"No se encontro el archivo seleccionado: {source_path}")

    extension = source_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Archivo no soportado: '{source_path.name}'. Formatos permitidos: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    output_root_path = Path(output_root).expanduser().resolve()
    base_recibida_dir, base_generada_dir, timestamp, _ = _build_processing_paths(output_root_path)

    copied_input_path = base_recibida_dir / source_path.name
    shutil.copy2(source_path, copied_input_path)

    df_output = _prepare_dataframe(source_path, base_generada_dir)

    fecha_formato = datetime.now().strftime("%y%m%d")
    generated_base_path = _build_output_file_path(base_generada_dir, "EPEC_ROMAN", fecha_formato, timestamp)
    generated_phones_path = _build_output_file_path(base_generada_dir, "EPEC_E1KIA", fecha_formato, timestamp)

    _guardar_base_epec(df_output, generated_base_path)
    _guardar_telefonos_epec(df_output, generated_phones_path)

    return ProcessResult(
        source_path=source_path,
        copied_input_path=copied_input_path,
        generated_base_path=generated_base_path,
        generated_phones_path=generated_phones_path,
        processing_timestamp=timestamp,
        rows=len(df_output),
        columns=len(df_output.columns),
    )
