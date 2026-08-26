import pandas as pd
import os


def read_smart_excel(path: str) -> pd.DataFrame:
    """
    Reads an Excel or CSV file, attempting different engines/sheets/encodings if necessary.

    This function provides robust reading capabilities by:
    - Detecting CSV files and trying multiple common encodings (utf-8-sig, utf-8, latin-1)
      and common delimiters (tab, semicolon, comma, pipe).
    - For older .xls files, it first attempts to read them as a CSV (if they are actually
      renamed CSVs) or as HTML (some vendors export "xls" as HTML tables), then tries
      Excel engines (xlrd).
    - For .xlsx files, it uses the 'openpyxl' engine.
    - Includes error handling to provide context on read failures.

    Args:
        path: The file path to read.

    Returns:
        A pandas DataFrame containing the file's data.

    Raises:
        RuntimeError: If the file cannot be read after multiple attempts.
    """
    try:
        if str(path).lower().endswith('.csv'):
            # Try various encodings and separator detection for robustness
            encodings = ('utf-8-sig', 'utf-8', 'latin-1')
            def detect_sep(sample_text: str) -> str:
                # Prefer tab if present, then ';', ',', and '|' as a last resort
                if '\t' in sample_text:
                    return '\t'
                for c in (';', ',', '|'):
                    if c in sample_text:
                        return c
                return ','

            for enc in encodings:
                try:
                    with open(path, 'rb') as fh:
                        sample = fh.read(2048).decode(enc, errors='ignore')
                    sep = detect_sep(sample)
                    return pd.read_csv(path, encoding=enc, sep=sep, engine='python', on_bad_lines='skip')
                except Exception:
                    try:
                        # Fallback to auto-detection with python engine
                        return pd.read_csv(path, encoding=enc, sep=None, engine='python', on_bad_lines='skip')
                    except Exception:
                        continue
            # If none worked, raise the last exception using latin-1
            with open(path, 'rb') as fh:
                sample = fh.read(2048).decode('latin-1', errors='ignore')
            sep = detect_sep(sample)
            return pd.read_csv(path, encoding='latin-1', sep=sep, engine='python', on_bad_lines='skip')
        
        # For Excel files (.xls, .xlsx)
        if str(path).lower().endswith('.xls'):
            # First try to read as a renamed CSV
            try:
                with open(path, 'rb') as fh:
                    sample = fh.read(2048)
                text = sample.decode('latin-1', errors='ignore')

                # Some ".xls" files are actually HTML tables. Try that early.
                text_l = text.lower()
                if '<html' in text_l or '<table' in text_l:
                    try:
                        tables = pd.read_html(path)
                        if tables:
                            return tables[0]
                    except Exception:
                        pass

                # Detect separator: prefer tab, then ';', ',', '|'
                if '\t' in text:
                    sep = '\t'
                elif ';' in text:
                    sep = ';'
                elif ',' in text:
                    sep = ','
                elif '|' in text:
                    sep = '|'
                else:
                    sep = None
                if sep:
                    return pd.read_csv(path, encoding='latin-1', sep=sep, engine='python', on_bad_lines='skip')
            except Exception:
                pass
            
            # Attempt with different engines for .xls
            engines_to_try = ['xlrd']
            for engine in engines_to_try:
                try:
                    return pd.read_excel(path, engine=engine)
                except Exception:
                    continue
            
            # Last attempt: without specifying engine
            try:
                return pd.read_excel(path)
            except Exception:
                raise RuntimeError(
                    "No se pudo leer archivo .xls. "
                    "Sugerencia: instalar 'xlrd==2.0.1' (requerido para .xls). "
                    f"Archivo: {path}"
                )
        
        # For .xlsx use openpyxl
        if str(path).lower().endswith('.xlsx'):
            return pd.read_excel(path, engine="openpyxl")
        
        # Generic fallback for other Excel types
        return pd.read_excel(path)
        
    except Exception as exc:
        # Re-raise with context
        raise RuntimeError(f"Error leyendo archivo {path}: {exc}") from exc
