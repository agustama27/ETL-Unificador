from __future__ import annotations

import sys
from pathlib import Path


BACK_RESULTADOS_ROOT = Path(__file__).resolve().parents[1]
if str(BACK_RESULTADOS_ROOT) not in sys.path:
    sys.path.insert(0, str(BACK_RESULTADOS_ROOT))
