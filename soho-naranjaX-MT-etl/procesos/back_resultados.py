"""
ETL back-resultados para Naranja X MT.

Procesa LOGCALL + historial_llamadas + base M30 y genera:
- DEELO_NAR_USUEVOLTIS_YYYYMMDD_HH.txt (pipe, CRLF, 40 columnas)
- _anomalias_YYYYMMDD_HHMMSS.txt
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re


BASE_DIR = Path(__file__).resolve().parent.parent
BACK_RESULTADOS_DIR = BASE_DIR / "back-resultados"
BACK_RECIBIDA_DIR = BACK_RESULTADOS_DIR / "back_recibida"
BACK_LOGCALL_DIR = BACK_RECIBIDA_DIR / "logcall"
BACK_HISTORIAL_DIR = BACK_RECIBIDA_DIR / "historial"
BACK_PROCESADA_DIR = BACK_RESULTADOS_DIR / "back_procesada"
BACK_BASE_DIR = BASE_DIR / "back-base"
BASE_RECIBIDA_DIR = BACK_BASE_DIR / "base_recibida"

USUOLOS_COLS = 40
CAMPANA_ACTIGROUP = "M"
RESULT_BOT = "10"
PHONE_IRRECUPERABLE_MAX_RATIO = 0.05

# ===================================================================
# Configuracion del formato de salida (alineado con feedback cliente)
# ===================================================================
OUTPUT_FILENAME_PREFIX = "DEELO_NAR_USUEVOLTIS_"
TIPO_REGISTRO = "USUEVOLTIS"  # col 8
GRUPO_GESTION = "EVOLTIS"  # col 36
SISTEMA_ORIGEN = "NARANJA"  # col 3
ACCION = "MAKE CALL"  # col 10
CANAL_BOT = "VOICEBOT"  # col 12 (cuando aplica)
ESTADO_PENDIENTE = "PENDING"  # col 39

# Resultado para RESULT=10 sin match en HISTORIAL (pendiente confirmar)
RESULT_BOT_SIN_HISTORIAL = "VOLVER A LLAMAR"

MAPEO_TIPIFICACION = {
    "Promesa de pago": "PROMISE",
    "Dificultad de pago": "PAYMENT DIFFICULTY",
    "Manifiesta pago": "PAID",
    "Contestador": "MESSAGE",
    "No responde": "HANGUP",
    "Notificado titular": "MENSAJE OPERADOR",
    "Notificado familiar": "MENSAJE OPERADOR",
    "No es titular": "MENSAJE OPERADOR",
    "No reconoce deuda": "MENSAJE OPERADOR",
    "Conoce titular": "MENSAJE OPERADOR",
    "Sin voluntad de pago": "VOLVER A LLAMAR",
}

MAPEO_RESULT_LOGCALL = {
    "9": "MESSAGE",
    "1004": "VOLVER A LLAMAR",
    "7": "BUSY",
    "8": "NO ANSWER",
    "16": "VOLVER A LLAMAR",
}


def _parse_delimited(path: Path, delimiter: str) -> list[list[str]]:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        return list(csv.reader(handle, delimiter=delimiter))


def _detect_csv_delimiter(path: Path, default: str = ",") -> str:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        sample = handle.read(4096)
    if not sample:
        return default
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;|").delimiter
    except csv.Error:
        return default


def _clean_phone(value: str) -> str:
    digits = "".join(c for c in str(value or "") if c.isdigit())
    if digits.startswith("549"):
        digits = digits[3:]
    elif digits.startswith("54"):
        digits = digits[2:]
    return digits.lstrip("0")


def normalizar_phone_logcall(raw: str) -> tuple[str, str, bool]:
    value = (raw or "").strip()
    if not value:
        return "", "", False

    sci = bool(re.search(r"[eE]", value))
    digits = ""
    irrecoverable = False

    if sci:
        normalized = value.replace(",", ".")
        try:
            dec = Decimal(normalized)
            if dec <= 0:
                return "", "", False
            digits = str(int(dec.to_integral_value()))
            mantissa = re.split(r"[eE]", value, maxsplit=1)[0]
            significant = sum(1 for ch in mantissa if ch.isdigit())
            if significant < 11:
                irrecoverable = True
        except (InvalidOperation, ValueError):
            digits = ""
            irrecoverable = True
    else:
        digits = "".join(ch for ch in value if ch.isdigit())

    clean = _clean_phone(digits)
    return digits, clean, irrecoverable


def normalizar_fecha(fecha_str: str) -> str:
    raw = (fecha_str or "").strip()
    if not raw:
        return ""
    for fmt in ("%d/%m/%y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y%m%d") + "235858"
        except ValueError:
            continue
    return ""


def _autodiscover(pattern: str, directory: Path) -> Path:
    files = list(directory.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No se encontraron archivos {pattern} en {directory}")
    return max(files, key=lambda p: p.stat().st_mtime)


def _build_e164(area: str, numero: str, tipo: str) -> str:
    if not area or not numero or not tipo:
        return ""
    tipo_norm = tipo.strip().upper()
    if tipo_norm == "CEL":
        num_sin_15 = numero[2:] if numero.startswith("15") else numero
        return f"549{area}{num_sin_15}"
    return f"54{area}{numero}"


def construir_indice_clientes(
    m30olos_path: Path,
) -> tuple[dict[str, dict[str, str]], dict[str, list[dict[str, str]]], dict[str, list[dict[str, str]]]]:
    if m30olos_path.suffix.lower() != ".txt":
        raise ValueError(
            "El back-resultados requiere M30OLOS pipe-delimited (.txt) con 33 columnas para descomposicion exacta."
        )

    e164_index: dict[str, dict[str, str]] = {}
    last8_index: dict[str, list[dict[str, str]]] = defaultdict(list)
    customer_tel_index: dict[str, list[dict[str, str]]] = defaultdict(list)

    with open(m30olos_path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        for line in handle:
            cols = line.rstrip("\r\n").split("|")
            if len(cols) < 33:
                continue

            customer_id = cols[0].strip()
            extended_id = cols[30].strip() if len(cols) > 30 else customer_id
            slots = [
                (3, 11, 12, 13),
                (4, 14, 15, 16),
                (5, 17, 18, 19),
                (6, 20, 21, 22),
                (7, 23, 24, 25),
                (8, 26, 27, 28),
            ]

            for tel_i, area_i, num_i, tipo_i in slots:
                tel_full = cols[tel_i].strip()
                area = cols[area_i].strip()
                numero = cols[num_i].strip()
                tipo = cols[tipo_i].strip().upper()
                if not (tel_full and area and numero and tipo):
                    continue

                e164 = _build_e164(area, numero, tipo)
                if not e164:
                    continue

                info = {
                    "customer_id": customer_id,
                    "extended_id": extended_id,
                    "numero": numero,
                    "area_code": area,
                    "tel_type": tipo,
                    "e164": e164,
                }
                e164_index[e164] = info
                last8_index[e164[-8:]].append(info)
                customer_tel_index[customer_id].append(info)
                if extended_id:
                    customer_tel_index[extended_id].append(info)
                customer_tel_index[_normalizar_du_id(customer_id)].append(info)
                if extended_id:
                    customer_tel_index[_normalizar_du_id(extended_id)].append(info)

    return e164_index, dict(last8_index), dict(customer_tel_index)


def matchear_telefono_en_cliente(
    phone_logcall_digits: str,
    phone_logcall_clean: str,
    customer_id: str,
    idx_customer_tels: dict[str, list[dict[str, str]]],
) -> dict[str, str] | None:
    tels = idx_customer_tels.get(customer_id, [])
    if not tels:
        tels = idx_customer_tels.get(_normalizar_du_id(customer_id), [])
    if not tels:
        return None

    phone_digits = "".join(c for c in str(phone_logcall_digits or "") if c.isdigit())
    if phone_digits:
        for tel in tels:
            if tel.get("e164") == phone_digits:
                return tel

    if phone_logcall_clean and phone_logcall_clean.startswith("9"):
        candidate = f"54{phone_logcall_clean}"
        for tel in tels:
            if tel.get("e164") == candidate:
                return tel

    if not phone_digits and phone_logcall_clean:
        phone_digits = f"54{phone_logcall_clean}"

    if not phone_digits:
        return None

    last8 = phone_digits[-8:]
    for tel in tels:
        if (tel.get("e164") or "").endswith(last8):
            return tel
    return None


def matchear_telefono(
    phone_logcall_digits: str,
    phone_logcall_clean: str,
    idx_e164: dict[str, dict[str, str]],
    idx_last8: dict[str, list[dict[str, str]]],
) -> dict[str, str] | None:
    phone_digits = "".join(c for c in str(phone_logcall_digits or "") if c.isdigit())
    if phone_digits in idx_e164:
        return idx_e164[phone_digits]

    if phone_logcall_clean and phone_logcall_clean.startswith("9"):
        candidate = f"54{phone_logcall_clean}"
        if candidate in idx_e164:
            return idx_e164[candidate]

    if not phone_digits and phone_logcall_clean:
        phone_digits = f"54{phone_logcall_clean}"

    if not phone_digits:
        return None

    last8 = phone_digits[-8:]
    candidates = idx_last8.get(last8, [])
    if candidates:
        return candidates[0]

    return None


def normalizar_monto(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""

    last_dot = s.rfind(".")
    last_comma = s.rfind(",")

    if last_dot > last_comma:
        left = s[:last_dot].replace(".", "").replace(",", "")
        right = s[last_dot + 1 :].replace(".", "").replace(",", "")
        return f"{left},{right}" if right else left

    if last_comma > last_dot:
        left = s[:last_comma].replace(".", "").replace(",", "")
        right = s[last_comma + 1 :].replace(".", "").replace(",", "")
        return f"{left},{right}" if right else left

    if last_dot >= 0:
        decimals = len(s) - last_dot - 1
        if 1 <= decimals <= 2:
            left = s[:last_dot].replace(".", "")
            right = s[last_dot + 1 :].replace(".", "")
            return f"{left},{right}" if right else left
        return s.replace(".", "")

    return s


def _normalizar_du_id(customer_id: str) -> str:
    cid = (customer_id or "").strip().upper()
    if not cid.startswith("DU"):
        return cid
    numero = cid[2:]
    if not numero.isdigit():
        return cid
    return f"DU{int(numero)}"


def extraer_monto_compromiso(historial_row: dict[str, str]) -> str:
    raw = (
        historial_row.get("monto_promesa")
        or historial_row.get("[Salida] monto_promesa")
        or historial_row.get("[Salida] Monto_promesa")
        or historial_row.get("[Salida] monto_compromiso")
        or historial_row.get("[Salida] Monto_compromiso")
        or historial_row.get("[Salida] monto_compromiso_tc")
        or historial_row.get("[Salida] monto_compromiso_nd")
        or ""
    ).strip()
    if raw:
        return normalizar_monto(raw)

    # Fallback para historiales donde el monto no viene estructurado
    # y solo aparece en el texto narrativo.
    sources = [
        historial_row.get("Resumen") or "",
        historial_row.get("[Salida] OBSERVACIONES") or "",
        historial_row.get("[Salida] detalle_experiencia") or "",
    ]
    pattern = re.compile(r"\$\s*\d+(?:[.,]\d+)*")
    matches: list[str] = []
    for text in sources:
        matches.extend(pattern.findall(text))

    if not matches:
        return ""

    # Usar el ultimo monto mencionado: suele ser el compromiso y no la deuda.
    candidate = matches[-1].replace("$", "").strip()
    return normalizar_monto(candidate)


def id_extendido_con_padding(customer_id: str) -> str:
    if not customer_id or not customer_id.startswith("DU"):
        return ""
    numero = customer_id[2:]
    if not numero.isdigit():
        return ""
    return "DU" + numero.zfill(11)


def construir_indice_historial(historial_path: Path) -> dict[str, dict[str, str]]:
    rows = _parse_delimited(historial_path, ",")
    if not rows:
        return {}

    header = rows[0]
    data_rows = rows[1:]
    header_map = {name.strip(): i for i, name in enumerate(header)}
    idx_user = header_map.get("[Entrada] user_number")

    index: dict[str, dict[str, str]] = {}
    if idx_user is None:
        return index

    for row in data_rows:
        user_number = row[idx_user] if len(row) > idx_user else ""
        key = _clean_phone(user_number)
        if not key:
            continue
        if key not in index:
            index[key] = {header[i]: row[i] if i < len(row) else "" for i in range(len(header))}
    return index


def mapear_col_11(logcall_row: dict[str, str], fila_historial: dict[str, str] | None) -> str:
    result = (logcall_row.get("RESULT") or "").strip()
    if result == RESULT_BOT:
        if fila_historial:
            tip = (fila_historial.get("[Salida] Tipificaciones") or "").strip()
            return MAPEO_TIPIFICACION.get(tip, "VOLVER A LLAMAR")
        return RESULT_BOT_SIN_HISTORIAL
    return MAPEO_RESULT_LOGCALL.get(result, "VOLVER A LLAMAR")


def _to_float(raw: str) -> float | None:
    text = (raw or "").strip().replace(".", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def construir_fila_usuolos(
    logcall_row: dict[str, str],
    idx_historial: dict[str, dict[str, str]],
    idx_e164: dict[str, dict[str, str]],
    idx_last8: dict[str, list[dict[str, str]]],
    idx_customer_tels: dict[str, list[dict[str, str]]],
    anomalias: dict[str, list[str]],
) -> list[str] | None:
    phone_raw = (logcall_row.get("PHONE") or "").strip()
    phone_digits, phone_clean, phone_irrecoverable = normalizar_phone_logcall(phone_raw)
    if not phone_clean:
        anomalias["telefono_vacio"].append(logcall_row.get("CALLREFID", ""))
        return None
    if phone_irrecoverable:
        anomalias["phone_irrecuperable"].append(
            f"CALLREFID={logcall_row.get('CALLREFID','')} PHONE_RAW={phone_raw}"
        )

    historial_row = idx_historial.get(phone_clean)
    cliente_info = matchear_telefono(phone_digits, phone_clean, idx_e164, idx_last8) or {}
    customer_id = (cliente_info.get("customer_id") or "").strip()
    if not customer_id and historial_row:
        customer_id = (historial_row.get("[Entrada] customer_id") or historial_row.get("[Entrada] id_dni") or "").strip()
        cliente_info = matchear_telefono_en_cliente(phone_digits, phone_clean, customer_id, idx_customer_tels) or {}
    if not customer_id:
        anomalias["sin_customer_id"].append(f"CALLREFID={logcall_row.get('CALLREFID','')} PHONE={phone_clean}")

    resultado = mapear_col_11(logcall_row, historial_row)
    nacional = (cliente_info.get("numero") or "").strip()
    area_code = (cliente_info.get("area_code") or "").strip()
    tel_type = (cliente_info.get("tel_type") or "").strip()
    if not nacional:
        nacional = phone_clean
        area_code = ""
        tel_type = ""

    monto_compromiso = ""
    fecha_compromiso = ""
    numero_cuenta = ""
    nombre_cliente = ""

    if historial_row:
        monto_compromiso = extraer_monto_compromiso(historial_row)
        fecha_compromiso = normalizar_fecha(
            historial_row.get("[Salida] fecha_compromiso")
            or historial_row.get("[Salida] Fecha_compromiso")
            or historial_row.get("[Salida] fecha_compromiso_tc")
            or historial_row.get("[Salida] fecha_compromiso_nd")
            or ""
        )
        numero_cuenta = (historial_row.get("[Entrada] numero_cuenta") or "").strip()
        nombre_cliente = (historial_row.get("[Entrada] customer_name") or historial_row.get("[Entrada] nombre_cliente") or "").strip()

        monto_deuda = _to_float(historial_row.get("[Entrada] monto_deuda") or "")
        monto_prom = _to_float(monto_compromiso)
        if monto_deuda is not None and monto_prom is not None and monto_prom > monto_deuda:
            anomalias["monto_mayor_deuda"].append(f"CUSTOMER_ID={customer_id} monto={monto_prom} deuda={monto_deuda}")

        if resultado == "PROMISE" and not monto_compromiso:
            anomalias["compromiso_sin_monto"].append(f"CUSTOMER_ID={customer_id} CALLREFID={logcall_row.get('CALLREFID','')}")

    ts = ((logcall_row.get("LOGDATE") or "").strip() + (logcall_row.get("LOGTIME") or "").strip())
    id_intento = (logcall_row.get("CALLREFID") or "").strip()
    fila = [""] * USUOLOS_COLS
    fila[0] = ts
    fila[1] = customer_id
    fila[2] = SISTEMA_ORIGEN
    fila[3] = id_extendido_con_padding(customer_id) if resultado == "PROMISE" else ""
    fila[4] = SISTEMA_ORIGEN if resultado == "PROMISE" else ""
    fila[5] = SISTEMA_ORIGEN if resultado == "PROMISE" else ""
    fila[6] = id_intento
    fila[7] = TIPO_REGISTRO
    fila[8] = "N"
    fila[9] = ACCION
    fila[10] = resultado
    fila[11] = CANAL_BOT if resultado != "NO ANSWER" else ""
    fila[14] = nacional
    fila[15] = area_code
    fila[16] = tel_type
    fila[27] = monto_compromiso
    fila[28] = fecha_compromiso if resultado == "PROMISE" else ""
    fila[30] = "N" if resultado == "PROMISE" else ""
    fila[35] = GRUPO_GESTION
    fila[36] = "1"
    fila[38] = ESTADO_PENDIENTE
    fila[39] = ts
    return fila


def _write_usuolos(path: Path, rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        for row in rows:
            handle.write("|".join(row) + "\r\n")


def _write_anomalias(path: Path, anomalias: dict[str, list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as handle:
        for key, values in anomalias.items():
            handle.write(f"[{key}] total={len(values)}\n")
            for value in values:
                handle.write(f"- {value}\n")
            handle.write("\n")


def procesar(
    logcall_path: Path | None = None,
    historial_path: Path | None = None,
    m30olos_path: Path | None = None,
    output_dir: Path | None = None,
    strict_phone_quality: bool = False,
    max_phone_irrecoverable_ratio: float = PHONE_IRRECUPERABLE_MAX_RATIO,
) -> tuple[Path, Path, int]:
    logcall_path = Path(logcall_path) if logcall_path else _autodiscover("LOGCALL*.csv", BACK_LOGCALL_DIR)
    historial_path = Path(historial_path) if historial_path else _autodiscover("historial_llamadas*.csv", BACK_HISTORIAL_DIR)
    if m30olos_path:
        m30olos_path = Path(m30olos_path)
    else:
        try:
            m30olos_path = _autodiscover("*.txt", BASE_RECIBIDA_DIR)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                "No se encontro M30OLOS .txt en base_recibida/. Para back-resultados se requiere el original pipe-delimited."
            ) from exc

    output_dir = Path(output_dir) if output_dir else BACK_PROCESADA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    idx_e164, idx_last8, idx_customer_tels = construir_indice_clientes(m30olos_path)
    idx_historial = construir_indice_historial(historial_path)

    anomalias: dict[str, list[str]] = defaultdict(list)
    filas: list[list[str]] = []

    logcall_delimiter = _detect_csv_delimiter(logcall_path, default=",")
    with open(logcall_path, "r", encoding="utf-8", errors="replace", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=logcall_delimiter)
        for row in reader:
            if (row.get("ACTIGROUP") or "").strip() != CAMPANA_ACTIGROUP:
                continue

            fila = construir_fila_usuolos(row, idx_historial, idx_e164, idx_last8, idx_customer_tels, anomalias)
            if fila:
                filas.append(fila)

    total_logcall_m = len(filas) + len(anomalias.get("telefono_vacio", []))
    if strict_phone_quality and total_logcall_m > 0:
        irrecoverables = len(anomalias.get("phone_irrecuperable", []))
        ratio = irrecoverables / total_logcall_m
        if ratio > max_phone_irrecoverable_ratio:
            raise ValueError(
                "Calidad de PHONE insuficiente en LOGCALL: "
                f"{irrecoverables}/{total_logcall_m} ({ratio:.2%}) irrecuperables, "
                f"umbral permitido {max_phone_irrecoverable_ratio:.2%}."
            )

    filas.sort(key=lambda r: r[0])
    for i, fila in enumerate(filas, start=1):
        fila[6] = str(i)

    for fila in filas:
        if len(fila) != USUOLOS_COLS:
            raise ValueError(f"Fila inválida: se esperaban {USUOLOS_COLS} columnas y llegaron {len(fila)}")

    stamp = datetime.now()
    usuolos_path = output_dir / f"{OUTPUT_FILENAME_PREFIX}{stamp:%Y%m%d_%H}.txt"
    anomalias_path = output_dir / f"_anomalias_{stamp:%Y%m%d_%H%M%S}.txt"

    _write_usuolos(usuolos_path, filas)
    _write_anomalias(anomalias_path, anomalias)

    return usuolos_path, anomalias_path, len(filas)


def main() -> None:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="ETL back-resultados Naranja X MT")
    parser.add_argument("--logcall", type=Path, default=None)
    parser.add_argument("--historial", type=Path, default=None)
    parser.add_argument("--m30", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()

    try:
        usuolos, anomalias, total = procesar(
            logcall_path=args.logcall,
            historial_path=args.historial,
            m30olos_path=args.m30,
            output_dir=args.output_dir,
        )
        print(f"Archivo USUOLOS generado: {usuolos}")
        print(f"Reporte de anomalías: {anomalias}")
        print(f"Filas generadas: {total}")
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
