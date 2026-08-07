from __future__ import annotations

import sys
from pathlib import Path


BACK_BASE_DIR = Path(__file__).resolve().parents[1]


sys.path.insert(0, str(BACK_BASE_DIR))
