from pathlib import Path
import pandas as pd
import csv


def _read_csv_with_fallback(source_file: Path) -> pd.DataFrame:
    """Primero intenta leer con ';' y luego autodetección de separador."""
    attempts = (
        {"sep": ";", "engine": "python"},
        {"sep": None, "engine": "python"},  # autodetección
    )
    errors = []

    for opts in attempts:
        try:
            # Leemos todo como texto para preservar el formato original
            # (ej: decimales con coma) y evitar floats con ".0".
            df = pd.read_csv(source_file, dtype=str, keep_default_na=False, **opts)
            return df
        except Exception as exc:  # pragma: no cover - defensivo
            errors.append(str(exc))

    raise ValueError(
        "No se pudo leer el CSV con separador ';' ni con autodetección. "
        f"Errores: {errors}"
    )


def _format_cel(value: str) -> str:
    """Devuelve el celular con prefijo +549 (sin duplicarlo)."""
    if value is None:
        return value

    s = str(value).strip()
    if s == "":
        return s

    # Normaliza a dígitos (manteniendo solo números) para evitar ".0", espacios, etc.
    digits = "".join(ch for ch in s if ch.isdigit())
    if digits == "":
        return s

    if digits.startswith("549"):
        return f"+{digits}"
    if digits.startswith("54"):
        # ya tiene país pero no el 9
        return f"+549{digits[2:]}"

    return f"+549{digits}"


def _consolidate_clients(df: pd.DataFrame) -> pd.DataFrame:
    """
    Consolida clientes que tienen más de 2 filas (créditos) por DNI.
    Reglas de consolidación:
    - Credito: concatenar valores separados por coma
    - Importe: sumar todos los valores
    - Cuotas: concatenar valores separados por coma
    - Tipo de Cartera: concatenar valores separados por coma
    - Dias atraso: tomar el valor máximo
    - Resto de columnas: tomar el primer valor
    """
    if "DNI" not in df.columns:
        return df

    def consolidate_group(group):
        if len(group) <= 1:
            # Si tiene 1 o menos filas, mantener como está
            return group

        # Crear una fila consolidada
        consolidated = group.iloc[0].copy()

        # Credito: concatenar con coma
        creditos = [str(c).strip() for c in group["Credito"] if str(c).strip()]
        consolidated["Credito"] = ",".join(creditos)

        # Importe: sumar (convertir de formato con coma a numérico, sumar, volver a formato)
        importes = []
        for imp in group["Importe"]:
            if pd.notna(imp) and str(imp).strip():
                # Reemplazar coma por punto para convertir a float
                imp_str = str(imp).strip().replace(",", ".")
                try:
                    importes.append(float(imp_str))
                except ValueError:
                    pass
        if importes:
            total = sum(importes)
            # Formatear de vuelta con coma como separador decimal (sin punto de miles)
            # Usar :.2f para 2 decimales y luego reemplazar punto por coma
            consolidated["Importe"] = f"{total:.2f}".replace(".", ",")

        # Cuotas: concatenar con coma
        cuotas = [str(c).strip() for c in group["Cuotas"] if str(c).strip()]
        consolidated["Cuotas"] = ",".join(cuotas)

        # Ultima cuota: concatenar con coma
        ultimas_cuotas = [str(uc).strip() for uc in group["Ultima cuota"] if str(uc).strip()]
        consolidated["Ultima cuota"] = ",".join(ultimas_cuotas)

        # Tipo de Cartera: concatenar con coma
        tipos = [str(t).strip() for t in group["Tipo de Cartera"] if str(t).strip()]
        # Eliminar duplicados manteniendo el orden
        tipos_unicos = []
        for t in tipos:
            if t not in tipos_unicos:
                tipos_unicos.append(t)
        consolidated["Tipo de Cartera"] = ",".join(tipos_unicos)

        # Dias atraso: máximo
        dias_values = pd.to_numeric(group["Dias atraso"], errors="coerce")
        dias_max = dias_values.max()
        if pd.notna(dias_max):
            consolidated["Dias atraso"] = int(dias_max)

        return pd.DataFrame([consolidated])

    # Agrupar por DNI y consolidar
    consolidated_rows = []
    for dni, group in df.groupby("DNI"):
        consolidated = consolidate_group(group)
        consolidated_rows.append(consolidated)

    if consolidated_rows:
        result = pd.concat(consolidated_rows, ignore_index=True)
        return result

    return df


def clean_base(
    input_dir: str = "base_recibida",
    output_dir: str = "base_procesada",
    output_filename: str = "fravega_base.csv",
) -> Path:
    """
    Lee el CSV en input_dir, elimina filas con "Dias atraso" negativo,
    agrega prefijo +549 a la columna "Cel" y guarda el resultado.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró la carpeta de entrada: {input_path}")

    csv_files = sorted(input_path.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No hay archivos CSV en: {input_path}")

    # Usa el primer CSV encontrado en la carpeta.
    source_file = csv_files[0]

    df = _read_csv_with_fallback(source_file)

    if "Dias atraso" not in df.columns or "Cel" not in df.columns:
        raise KeyError(
            'Las columnas requeridas "Dias atraso" y "Cel" deben existir en el CSV.'
        )

    dias = pd.to_numeric(df["Dias atraso"], errors="coerce")
    filtered = df[dias >= 0].copy()

    # "Dias atraso" como entero (sin .0)
    filtered["Dias atraso"] = pd.to_numeric(filtered["Dias atraso"], errors="coerce").astype(
        "Int64"
    )

    # Cel con prefijo +549 (string)
    filtered["Cel"] = filtered["Cel"].apply(_format_cel)

    # Elimina columnas basura que vienen del trailing ";;;;;" del CSV original
    filtered = filtered.loc[
        :,
        [c for c in filtered.columns if c and not str(c).startswith("Unnamed")],
    ]

    # Consolida clientes con más de 2 filas (créditos) por DNI
    filtered = _consolidate_clients(filtered)

    output_path.mkdir(parents=True, exist_ok=True)
    destination = output_path / output_filename
    
    # Exporta con ';' usando el módulo csv para control total del formato
    # utf-8-sig con BOM para que Excel/Windows lo reconozca correctamente
    with open(destination, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";", lineterminator="\n")
        # Escribe el encabezado (limpia espacios en nombres de columnas)
        writer.writerow([str(col).strip() for col in filtered.columns.tolist()])
        # Escribe las filas (limpia espacios y convierte NaN a string vacío)
        for _, row in filtered.iterrows():
            cleaned_row = []
            for val in row:
                if pd.isna(val):
                    cleaned_row.append("")
                else:
                    cleaned_row.append(str(val).strip())
            writer.writerow(cleaned_row)

    # Genera archivo adicional con solo los valores de la columna "Cel" (sin encabezado)
    cel_list_filename = "fravega_cel_list.csv"
    cel_list_destination = output_path / cel_list_filename
    with open(cel_list_destination, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter=";", lineterminator="\n")
        # Escribe solo los valores de Cel, uno por línea, sin encabezado
        for cel_value in filtered["Cel"]:
            if not pd.isna(cel_value) and str(cel_value).strip():
                writer.writerow([str(cel_value).strip()])

    return destination

