"""Pipeline ROMAN-only para generar salida CRM Bancor sin Retell."""

from datetime import datetime
from pathlib import Path
from collections import Counter
import shutil
import sys
import re
from typing import Any


def obtener_carpeta_base() -> Path:
    """Devuelve carpeta de trabajo segun ejecucion script/exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent.parent


def _agregar_rutas_reutilizadas() -> None:
    """Agrega al path las carpetas de procesos reutilizadas."""
    repo_root = Path(__file__).resolve().parents[2]
    rutas = [
        repo_root / "back-resultados" / "procesos",
        repo_root / "back-cargaMasiva" / "procesos",
    ]

    for ruta in rutas:
        ruta_str = str(ruta)
        if ruta_str not in sys.path:
            sys.path.insert(0, ruta_str)


def _crear_estructura_diaria(base_dir: Path) -> tuple[Path, Path, Path]:
    """Crea la estructura DD-MM-YYYY/entrada y DD-MM-YYYY/salida."""
    fecha_hoy = datetime.now().strftime("%d-%m-%Y")
    carpeta_dia = base_dir / fecha_hoy
    carpeta_entrada = carpeta_dia / "entrada"
    carpeta_salida = carpeta_dia / "salida"
    carpeta_entrada.mkdir(parents=True, exist_ok=True)
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    return carpeta_dia, carpeta_entrada, carpeta_salida


def _copiar_archivo_entrada(path_origen: Path, carpeta_entrada: Path) -> Path:
    """Copia el archivo ROMAN seleccionado a la carpeta de entrada."""
    timestamp = datetime.now().strftime("%H%M%S")
    destino = carpeta_entrada / f"{path_origen.stem}_{timestamp}{path_origen.suffix.lower()}"
    shutil.copy2(path_origen, destino)
    return destino


def _leer_dataframe_roman(path_csv: Path) -> tuple[Any, str]:
    """Lee CSV de ROMAN con la misma logica de codificacion del proyecto."""
    import pandas as pd

    codificaciones = ["utf-8-sig", "utf-8", "cp1252", "latin-1", "iso-8859-1", "utf-16"]
    separadores = [",", ";"]
    ultimo_error = None

    for separador in separadores:
        for encoding in codificaciones:
            try:
                df = pd.read_csv(path_csv, sep=separador, encoding=encoding)
                return df, f"csv ({encoding}, sep='{separador}')"
            except Exception as exc:
                ultimo_error = exc

    # Fallback de tolerancia para archivos con caracteres dañados.
    for separador in separadores:
        try:
            df = pd.read_csv(path_csv, sep=separador, encoding="utf-8", encoding_errors="replace")
            return df, f"csv (utf-8/replace, sep='{separador}')"
        except Exception as exc:
            ultimo_error = exc

    raise ValueError(f"No se pudo leer el CSV ROMAN: {ultimo_error}")


_PATRON_MOJIBAKE = re.compile(r"[\u00C2\u00C3][\u0080-\u00BF]")


def _contar_mojibake(texto: str) -> int:
    """Cuenta patrones tipicos de mojibake UTF-8 interpretado como latin-1/cp1252."""
    return len(_PATRON_MOJIBAKE.findall(texto))


def _reparar_texto_mojibake(texto: str) -> tuple[str, bool]:
    """Repara texto mojibake de forma segura cuando mejora la calidad del string."""
    if not isinstance(texto, str):
        return texto, False

    mojibake_original = _contar_mojibake(texto)
    if mojibake_original == 0:
        return texto, False

    try:
        reparado = texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return texto, False

    if _contar_mojibake(reparado) < mojibake_original:
        return reparado, True

    return texto, False


def _reparar_mojibake_registros(registros: list[dict[str, Any]]) -> tuple[int, int]:
    """Repara mojibake en campos de texto de salida CRM y devuelve metricas."""
    campos_texto = ("Descripción", "Notas")
    filas_corregidas = 0
    celdas_corregidas = 0

    for registro in registros:
        fila_tuvo_cambios = False
        for campo in campos_texto:
            valor = registro.get(campo)
            if not isinstance(valor, str):
                continue

            valor_reparado, corregido = _reparar_texto_mojibake(valor)
            if corregido:
                registro[campo] = valor_reparado
                celdas_corregidas += 1
                fila_tuvo_cambios = True

        if fila_tuvo_cambios:
            filas_corregidas += 1

    return filas_corregidas, celdas_corregidas


def _es_valor_disponible(valor: Any) -> bool:
    """Evalua si un valor del CSV puede usarse para mapear."""
    if valor is None:
        return False

    valor_str = str(valor).strip()
    if not valor_str:
        return False

    return valor_str.lower() not in {"nan", "none", "null", "n/a", "-"}


def _buscar_columna_disponible(df_roman: Any, candidatos: list[str]) -> str | None:
    """Devuelve la primera columna existente segun una lista de candidatos."""
    for columna in candidatos:
        if columna in df_roman.columns:
            return columna
    return None


def _buscar_columna_con_datos(df_roman: Any, candidatos: list[str]) -> str | None:
    """Prioriza columnas candidatas que existan y tengan al menos un valor util."""
    primera_existente = None
    for columna in candidatos:
        if columna not in df_roman.columns:
            continue

        if primera_existente is None:
            primera_existente = columna

        serie = df_roman[columna]
        if serie.notna().any() and serie.astype(str).map(_es_valor_disponible).any():
            return columna

    return primera_existente


def _normalizar_cuit_entrada(valor: Any) -> str:
    """Normaliza CUIT/CUIL provenientes de CSV evitando artefactos de float."""
    if valor is None:
        return ""

    if isinstance(valor, float):
        if valor != valor:  # NaN
            return ""
        return str(int(valor))

    if isinstance(valor, int):
        return str(valor)

    valor_str = str(valor).strip()
    if not valor_str:
        return ""

    if re.fullmatch(r"\d+\.0+", valor_str):
        return valor_str.split(".", 1)[0]

    return "".join(ch for ch in valor_str if ch.isdigit())


def _completar_campos_entrada_roman(
    df_roman: Any,
    datos_roman: dict[str, dict[str, Any]],
) -> int:
    """Completa CUIL/Cuenta desde columnas [Entrada] para pipeline ROMAN-only."""
    columna_call_id = _buscar_columna_disponible(
        df_roman,
        ["ID de Llamada", "Call ID", "call_id", "CallID", "callId"],
    )
    if not columna_call_id:
        return 0

    columna_cuit = _buscar_columna_con_datos(
        df_roman,
        [
            "[Entrada] Cuil",
            "[Entrada] CUIL",
            "[Entrada] id_cuil",
            "CUIL",
            "Cuil",
            "CUIT",
            "Cuit",
        ],
    )
    columna_cuenta = _buscar_columna_con_datos(
        df_roman,
        ["[Entrada] Cuenta", "Cuenta"],
    )

    if not columna_cuit and not columna_cuenta:
        return 0

    total_completados = 0
    for _, fila in df_roman.iterrows():
        call_id = str(fila.get(columna_call_id, "")).strip()
        if not call_id or call_id not in datos_roman:
            continue

        variables_dinamicas = datos_roman[call_id].setdefault("variables_dinamicas", {})
        completo_algo = False

        if (
            columna_cuit
            and not _es_valor_disponible(variables_dinamicas.get("CUIL"))
            and _es_valor_disponible(fila.get(columna_cuit))
        ):
            valor_cuit = _normalizar_cuit_entrada(fila.get(columna_cuit))
            variables_dinamicas["CUIL"] = valor_cuit
            completo_algo = True

        if (
            columna_cuenta
            and not _es_valor_disponible(variables_dinamicas.get("Cuenta"))
            and _es_valor_disponible(fila.get(columna_cuenta))
        ):
            variables_dinamicas["Cuenta"] = str(fila.get(columna_cuenta)).strip()
            completo_algo = True

        if completo_algo:
            total_completados += 1

    return total_completados


def ejecutar_pipeline_roman_only(
    path_archivo_roman: Path,
    nombre_estudio: str = "EVOLTIS",
    path_archivo_base_roman: Path | None = None,
    path_archivo_logcall: Path | None = None,
) -> dict[str, Any]:
    """Ejecuta el pipeline completo ROMAN-only y retorna resultado estructurado."""
    logs: list[str] = []

    try:
        if not path_archivo_roman.exists():
            raise ValueError(f"Archivo no encontrado: {path_archivo_roman}")

        if path_archivo_roman.suffix.lower() != ".csv":
            raise ValueError("Formato no soportado. Debe ser un archivo .csv de ROMAN")

        _agregar_rutas_reutilizadas()

        from roman_manager import normalizar_datos_roman, validar_estructura_roman
        from mapeador import mapear_todos_los_registros, obtener_resumen_mapeo
        from validador import validar_registro
        from excel_generator import crear_csv_carga_masiva, crear_excel_carga_masiva

        base_dir = obtener_carpeta_base()
        carpeta_dia, carpeta_entrada, carpeta_salida = _crear_estructura_diaria(base_dir)
        logs.append(f"Carpeta diaria: {carpeta_dia}")

        path_copia_entrada = _copiar_archivo_entrada(path_archivo_roman, carpeta_entrada)
        logs.append(f"Entrada copiada: {path_copia_entrada}")

        df_roman, detalle_lectura = _leer_dataframe_roman(path_copia_entrada)
        df_roman.columns = df_roman.columns.str.strip()
        logs.append(f"Encoding detectado ROMAN: {detalle_lectura}")
        logs.append(f"Filas leidas ROMAN: {len(df_roman)}")

        columna_call_id = _buscar_columna_disponible(
            df_roman,
            ["ID de Llamada", "Call ID", "call_id", "CallID", "callId"],
        )
        if not columna_call_id:
            raise ValueError(
                "No se encontro columna de call_id en ROMAN. "
                "Se esperaba una de: ID de Llamada, Call ID, call_id, CallID, callId"
            )

        if columna_call_id != "ID de Llamada":
            df_roman["ID de Llamada"] = df_roman[columna_call_id]
            logs.append(
                f"Alias call_id aplicado: usando '{columna_call_id}' como 'ID de Llamada'"
            )

        validar_estructura_roman(df_roman)
        logs.append("Estructura ROMAN valida")

        datos_roman = normalizar_datos_roman(df_roman)
        total_completados = _completar_campos_entrada_roman(df_roman, datos_roman)
        logs.append(f"Registros ROMAN normalizados: {len(datos_roman)}")
        logs.append(f"Registros con CUIL/Cuenta completados desde [Entrada]: {total_completados}")
        if not datos_roman:
            raise ValueError("No se obtuvieron registros ROMAN validos para mapear")

        registros_mapeados = mapear_todos_los_registros(datos_roman, nombre_estudio)
        logs.append(f"Registros mapeados CRM (ROMAN): {len(registros_mapeados)}")
        if not registros_mapeados:
            raise ValueError("No hay registros con estado valido para cargar al CRM")

        # Integrar LOGCALL si se proporcionó archivo + base ROMAN para cruce
        if path_archivo_logcall and path_archivo_logcall.exists():
            from logcall_manager import procesar_logcall
            logs.append(f"Procesando LOGCALL: {path_archivo_logcall.name}")

            if path_archivo_base_roman and path_archivo_base_roman.exists():
                df_base_roman, _ = _leer_dataframe_roman(path_archivo_base_roman)
                df_base_roman.columns = df_base_roman.columns.str.strip()
                logs.append(f"Base ROMAN para cruce: {path_archivo_base_roman.name} ({len(df_base_roman)} filas)")
            else:
                df_base_roman = df_roman
                logs.append("ADVERTENCIA: Base ROMAN no seleccionada, usando historial para cruce (RECNUMBER puede no ser correcto)")

            cuil_en_salida = {r['CUIT'] for r in registros_mapeados if r.get('CUIT')}
            registros_logcall, logs_logcall = procesar_logcall(
                path_archivo_logcall, df_base_roman, nombre_estudio, cuil_en_salida
            )
            logs.extend(logs_logcall)
            registros_mapeados.extend(registros_logcall)
            logs.append(f"Total registros tras LOGCALL: {len(registros_mapeados)}")

        resumen_mapeo = obtener_resumen_mapeo(registros_mapeados)
        logs.append(f"Resumen por estado: {resumen_mapeo}")

        registros_validos: list[dict[str, str]] = []
        error_counter: Counter[str] = Counter()
        registros_con_error = 0
        for registro in registros_mapeados:
            es_valido, registro_normalizado, errores = validar_registro(registro)
            if es_valido:
                registros_validos.append(registro_normalizado)
            else:
                registros_con_error += 1
                error_counter.update(errores)

        total_errores = sum(error_counter.values())

        logs.append(f"Registros validos: {len(registros_validos)}")
        logs.append(f"Registros invalidos: {registros_con_error}")
        logs.append(f"Errores de validacion: {total_errores}")
        if error_counter:
            top_errores = ", ".join(
                f"{motivo} ({cantidad})" for motivo, cantidad in error_counter.most_common(5)
            )
            logs.append(f"Top errores validacion: {top_errores}")

        if not registros_validos:
            raise ValueError("No hay registros validos para generar salida CRM")

        filas_corregidas, celdas_corregidas = _reparar_mojibake_registros(registros_validos)
        logs.append(
            f"Reparacion mojibake: {'si' if filas_corregidas else 'no'} "
            f"(filas={filas_corregidas}, celdas={celdas_corregidas})"
        )

        output_excel = crear_excel_carga_masiva(
            registros=registros_validos,
            nombre_estudio=nombre_estudio,
            carpeta_salida=carpeta_salida,
        )
        output_csv = crear_csv_carga_masiva(
            registros=registros_validos,
            nombre_estudio=nombre_estudio,
            carpeta_salida=carpeta_salida,
        )

        logs.append(f"Excel generado: {output_excel}")
        logs.append(f"CSV generado: {output_csv}")

        return {
            "ok": True,
            "logs": logs,
            "input_history_path": str(path_copia_entrada),
            "output_excel_path": str(output_excel),
            "output_csv_path": str(output_csv),
            "rows_output": len(registros_validos),
        }

    except Exception as exc:
        logs.append(f"ERROR: {exc}")
        return {
            "ok": False,
            "logs": logs,
            "error": str(exc),
        }


if __name__ == "__main__":
    print("Modulo ROMAN-only. Abrir UI con: python archivos_salida_BANCOR_exe/main.py")
