"""Vercel Serverless entry for the AETHERA FastAPI backend (v25.0).

Serves the full python/aethera API from the same origin as the frontend.
The aethera package is synced into web/api/aethera by
scripts/sync_backend.sh before deployment (committed as a build artifact).
"""

import os
import sys
from pathlib import Path

_API_DIR = Path(__file__).resolve().parent
for candidate in (_API_DIR, _API_DIR.parent):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

# Serverless-friendly tuning: single-threaded BLAS, no bytecode writes to
# read-only FS.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMBA_CACHE_DIR", "/tmp")

from aethera.api import app  # noqa: E402

# Vercel's Python runtime looks for a module-level `app`.
handler = app
