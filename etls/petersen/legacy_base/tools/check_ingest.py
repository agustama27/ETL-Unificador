"""
Diagnostic tool to check simplified ingestion for Petersen ETL.

This script only checks INTEGRACION.csv and PRODCLI_DEELO.csv files.
All other files are ignored.
"""
import sys
import os
import traceback
from pathlib import Path
from collections import defaultdict

# Ensure project root is in Python path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from lib.common.io import read_smart_excel
from lib.common.file_utils import extract_bank_code, get_bank_name, extract_date_from_filename

# Find all files in input folder
folder = str(project_root / 'inputs' / 'petersen' / 'incoming')
if not os.path.isdir(folder):
    print(f'[ERROR] Carpeta no existe: {folder}')
    sys.exit(1)

files = [os.path.join(folder, f) for f in os.listdir(folder)
         if f.lower().endswith(('.xlsx', '.xls', '.csv'))]
print(f'[INFO] Total archivos encontrados: {len(files)}\n')

# Group files by bank code
bank_files = defaultdict(list)
for f in files:
    bank_code = extract_bank_code(f)
    if bank_code:
        bank_files[bank_code].append(f)
    else:
        bank_files['UNKNOWN'].append(f)

# Process each bank
for bank_code in sorted(bank_files.keys()):
    if bank_code == 'UNKNOWN':
        continue
    
    bank_name = get_bank_name(bank_code)
    files_for_bank = bank_files[bank_code]
    
    print('=' * 80)
    print(f'BANCO: {bank_code} - {bank_name}')
    print('=' * 80)
    
    # Classify files: only INTEGRACION and PRODCLI_DEELO
    integracion_files = []
    deelo_files = []
    otros_files = []
    
    for p in files_for_bank:
        name = os.path.basename(p).upper()
        if 'INTEGRACION' in name:
            integracion_files.append(p)
        elif 'PRODCLI_DEELO' in name or 'PRODCLI_DEELO' in name:
            deelo_files.append(p)
        else:
            otros_files.append(p)
    
    print(f'\n[ARCHIVOS PROCESADOS]')
    print(f'  INTEGRACION: {len(integracion_files)} archivo(s)')
    print(f'  PRODCLI_DEELO: {len(deelo_files)} archivo(s)')
    if otros_files:
        print(f'\n[ARCHIVOS IGNORADOS]: {len(otros_files)} archivo(s)')
    
    # Try to read and display information for INTEGRACION files
    def _read_and_display(file_list, label):
        """Read files and display their structure."""
        if not file_list:
            print(f'\n[{label.upper()}]')
            print('  -> Sin archivos')
            return
        
        print(f'\n[{label.upper()}]')
        total_rows = 0
        all_columns = set()
        
        for path in file_list:
            date = extract_date_from_filename(path)
            date_str = f' (Fecha: {date})' if date else ''
            print(f'\n  Archivo: {os.path.basename(path)}{date_str}')
            try:
                df = read_smart_excel(path)
                if df.empty:
                    print('    -> DataFrame vacío')
                    continue
                
                rows, cols = df.shape
                total_rows += rows
                all_columns.update(df.columns)
                
                print(f'    Filas: {rows:,}')
                print(f'    Columnas: {cols}')
                print(f'    Columnas: {list(df.columns)[:15]}')
                
                # Check for required columns
                if label == 'INTEGRACION':
                    if 'DAT3' in df.columns:
                        print(f'    ✓ Columna DAT3 encontrada (ID de cliente)')
                        print(f'    Valores DAT3 únicos: {df["DAT3"].nunique():,}')
                    else:
                        print(f'    ✗ ADVERTENCIA: Columna DAT3 no encontrada')
                
                elif label == 'PRODCLI_DEELO':
                    if 'NUMERO CLIENTE' in df.columns:
                        print(f'    ✓ Columna NUMERO CLIENTE encontrada')
                        print(f'    Valores NUMERO CLIENTE únicos: {df["NUMERO CLIENTE"].nunique():,}')
                    else:
                        print(f'    ✗ ADVERTENCIA: Columna NUMERO CLIENTE no encontrada')
                    
                    if 'DEUDA VENCIDA' in df.columns:
                        print(f'    ✓ Columna DEUDA VENCIDA encontrada')
                    else:
                        print(f'    ✗ ADVERTENCIA: Columna DEUDA VENCIDA no encontrada')
                    
                    if 'TIPO DE PRODUCTO' in df.columns:
                        print(f'    ✓ Columna TIPO DE PRODUCTO encontrada')
                    else:
                        print(f'    ✗ ADVERTENCIA: Columna TIPO DE PRODUCTO no encontrada')
                
            except Exception as e:
                print(f'    ERROR: {type(e).__name__}: {e}')
                traceback.print_exc()
        
        if total_rows > 0:
            print(f'\n  RESUMEN {label.upper()}:')
            print(f'    Total filas: {total_rows:,}')
            print(f'    Total columnas únicas: {len(all_columns)}')
    
    # Display information for each file type
    _read_and_display(integracion_files, 'INTEGRACION')
    _read_and_display(deelo_files, 'PRODCLI_DEELO')
    
    if otros_files:
        print(f'\n[ARCHIVOS IGNORADOS (NO PROCESADOS)]')
        for f in sorted(otros_files):
            print(f'  - {os.path.basename(f)}')
    
    print('\n')

# Summary
print('=' * 80)
print('RESUMEN GENERAL')
print('=' * 80)
print(f'Total bancos detectados: {len([b for b in bank_files.keys() if b != "UNKNOWN"])}')
for bank_code in sorted([b for b in bank_files.keys() if b != 'UNKNOWN']):
    bank_name = get_bank_name(bank_code)
    files_for_bank = bank_files[bank_code]
    integracion_count = len([f for f in files_for_bank if 'INTEGRACION' in os.path.basename(f).upper()])
    deelo_count = len([f for f in files_for_bank if 'PRODCLI_DEELO' in os.path.basename(f).upper()])
    print(f'  {bank_code} - {bank_name}:')
    print(f'    INTEGRACION: {integracion_count} archivo(s)')
    print(f'    PRODCLI_DEELO: {deelo_count} archivo(s)')

if 'UNKNOWN' in bank_files:
    print(f'\n  UNKNOWN: {len(bank_files["UNKNOWN"])} archivos sin banco detectado')
