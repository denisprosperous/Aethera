"""AETHERA API — Vercel Serverless Function entry point.

This exposes the FastAPI app as a Vercel serverless function.
Vercel automatically routes /api/* requests to this file.

The Python solver is used (no Rust FFI in serverless — shared libs
not supported). The solver is fast enough for 100-200 node graphs
(<2 seconds), which covers all current use cases.
"""

import sys
import os

# The aethera package is at ./aethera/ relative to this file.
# Vercel's Python runtime adds the api/ directory to sys.path.
_api_dir = os.path.dirname(os.path.abspath(__file__))
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

# Set the DATABASE_URL default (Neon permanent database).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_i7I6oGlzgpmu@ep-small-fire-awt6hp2b.c-12.us-east-1.aws.neon.tech/neondb?sslmode=require",
)

# Import the FastAPI app.
try:
    from aethera.api import app
except Exception as e:
    # Fallback: create a minimal app if imports fail.
    from fastapi import FastAPI
    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"status": "degraded", "error": str(e), "api_dir": _api_dir}

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def catch_all(path: str):
        return {"error": f"Module import failed: {e}", "path": path}
