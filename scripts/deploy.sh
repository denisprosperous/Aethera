#!/bin/bash
# Deploy AETHERA to Vercel. Requires VERCEL_TOKEN env var.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== AETHERA Deploy ==="

# 1. Run tests
echo "[1/4] Running Rust tests..."
cd "$ROOT/rust"
cargo test --release --workspace --exclude aethera-ffi 2>&1 | tail -5

echo "[2/4] Running Python tests..."
cd "$ROOT"
PYTHONPATH=python python -m pytest tests/test_integration.py -q 2>&1 | tail -3

echo "[3/4] Building Next.js..."
cd "$ROOT/web"
npm install --no-audit --no-fund 2>&1 | tail -3
npm run build 2>&1 | tail -5

echo "[4/4] Deploying to Vercel..."
npx vercel --token "$VERCEL_TOKEN" --prod --yes 2>&1 | tail -10

echo "=== Deploy complete ==="
