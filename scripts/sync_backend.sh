#!/usr/bin/env bash
# AETHERA v25.0 — sync the canonical python/aethera package into the
# Vercel serverless bundle (web/api/aethera). Run before `vercel deploy`.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rm -rf "$ROOT/web/api/aethera"
cp -r "$ROOT/python/aethera" "$ROOT/web/api/aethera"
find "$ROOT/web/api/aethera" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null || true
echo "synced python/aethera -> web/api/aethera"
