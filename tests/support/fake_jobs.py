from __future__ import annotations

import os
import sys
import time
from pathlib import Path


mode = sys.argv[1]
secret = os.environ.get("JOB_SECRET", "")

if mode == "success":
    print(f"out:{os.getcwd()}:{secret}", flush=True)
    print(f"err:{secret}", file=sys.stderr, flush=True)
elif mode == "nonzero":
    Path("partial.csv").write_text("partial", encoding="utf-8")
    print("partial-output", flush=True)
    print("failed-after-output", file=sys.stderr, flush=True)
    raise SystemExit(7)
elif mode == "interleave":
    for index in range(2_000):
        print(f"stdout-{index}-{secret}", flush=True)
        print(f"stderr-{index}-{secret}", file=sys.stderr, flush=True)
elif mode == "sleep":
    print("before-timeout", flush=True)
    time.sleep(30)
else:
    raise SystemExit(f"unknown mode: {mode}")
