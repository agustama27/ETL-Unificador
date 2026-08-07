"""Corre el pipeline directamente (no via exe) sobre el mismo input."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from filtrosAplicados_base_BANCOR.procesos.pipeline_wfm import ejecutar_pipeline_wfm

INPUT = Path(r"C:\Users\agustin.tamagusuku\Desktop\soho-bancor-cobranzas-etl\filtrosAplicados_base_BANCOR\dist\20-04-2026\entrada\GYM_Evoltis 16-04_162108.xlsx")

resultado = ejecutar_pipeline_wfm(INPUT, meses_permitidos=[2, 3])
print(f"ok: {resultado.get('ok')}")
for log in resultado.get('logs', []):
    print(f"  {log}")
print(f"output: {resultado.get('output_path')}")
if not resultado.get('ok'):
    print(f"error: {resultado.get('error')}")
