#!/bin/bash
# Deploy AETHERA backend to Render + frontend to Vercel.
# Usage: ./scripts/deploy.sh

set -e

echo "=== AETHERA Deployment ==="

# 1. Build Rust FFI.
echo "[1/5] Building Rust FFI..."
cd rust
cargo build -p aethera-ffi --release
cd ..

# 2. Run tests.
echo "[2/5] Running tests..."
PYTHONPATH=python python3 -m pytest tests/ -q

# 3. Deploy backend to Render.
echo "[3/5] Deploying backend to Render..."
# Render reads render.yaml from the GitHub repo.
# Push to GitHub triggers the deploy.
git push origin main

# 4. Deploy frontend to Vercel.
echo "[4/5] Deploying frontend to Vercel..."
cd web
npx vercel --prod --token "$VERCEL_TOKEN" --yes
cd ..

echo "[5/5] Deployment complete."
echo "Backend: https://aethera-backend.onrender.com (after Render builds)"
echo "Frontend: https://web-sigma-drab-26.vercel.app"
