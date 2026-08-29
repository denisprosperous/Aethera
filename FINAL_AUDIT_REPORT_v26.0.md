# AETHERA FINAL AUDIT REPORT — v26.0

**Platform:** AETHERA — Sovereign Computational Geometry Platform
**Audit date:** 2026-08-29
**Scope:** Live production deployment (Railway backend + Vercel frontend), full API verification, simulation suite, LLM integration, deployment-mode awareness.

---

## 1. Executive Summary

AETHERA v26.0 is **fully live on both deployment targets** with all 11 API
endpoints verified against each (24/24 semantic checks passed), all 6
master-prompt simulation scenarios passing on both platforms (12/12), all 9
frontend module pages serving, and NVIDIA free models operating as the
default LLM chain with zero end-user API-key entry.

The platform is now **Railway-aware**: the frontend transparently uses the
Railway backend when it is reachable and silently degrades to the same-origin
Vercel serverless function when it is not. Both modes serve identical data
from the same Neon PostgreSQL instance and the same intrinsic-geometry
engine, so module behaviour is invariant to which backend answers.

---

## 2. Deployment Status

| Target | URL | Mode reported | Solver | Status |
|---|---|---|---|---|
| Railway backend | `https://aethera-backend.up.railway.app` | `railway` | **rust** (FFI) | 🟢 LIVE |
| Vercel frontend | `https://aethera-lime.vercel.app` | `vercel-serverless` (same-origin `/api/*`) | `python_fallback` | 🟢 LIVE |
| Vercel serverless API | `https://aethera-lime.vercel.app/api/*` | `vercel-serverless` | `python_fallback` | 🟢 LIVE |
| Neon PostgreSQL | `ep-small-fire-awt6hp2b...neon.tech/neondb` | — | — | 🟢 CONNECTED (both) |

- Railway service `aethera-backend` (project `blissful-abundance`, id `2e5a06f9-dee2-417e-8d79-af8df3c45d90`) built from the root `Dockerfile` (Rust 1.97 builder stage → python:3.12-slim runtime), health-checked at `/api/health`.
- Environment variables set on Railway: `DATABASE_URL` (Neon), `NVIDIA_API_KEY`, `NVIDIA_API_KEY_BACKUP`, `NVIDIA_INTEGRATE_URL`.
- Environment variables set on Vercel: `NEXT_PUBLIC_RAILWAY_URL`, `NEXT_PUBLIC_RAILWAY_ENABLED`, `NEXT_PUBLIC_API_URL`, `DATABASE_URL`, NVIDIA keys (serverless fallback parity).
- Docker build fix: `m4 make gcc libc6-dev` installed in the rust-builder stage — `gmp-mpfr-sys` compiles vendored GMP/MPFR and failed with `No usable m4 in $PATH` before this fix.

---

## 3. Railway-Aware Dual-Mode Design

1. **Backend detection** (`python/aethera/api.py`): deployment mode resolved at
   startup from `RAILWAY_PUBLIC_DOMAIN` / `RAILWAY_PROJECT_ID` (→ `railway`),
   `VERCEL_ENV` / `VERCEL` (→ `vercel-serverless`), else `local`; reported in
   `/api/health` as `mode`.
2. **Frontend resolver** (`web/src/lib/api.ts`): `NEXT_PUBLIC_RAILWAY_URL`
   selects the absolute Railway base; `apiFetch()` probes Railway health once
   per session (2.5 s timeout) and caches the result.
3. **Runtime failover**: any network failure while using Railway flips the
   session to same-origin `/api/*` and retries the request transparently.
   With the variable unset the platform runs same-origin only — zero
   configuration required.

---

## 4. Live Endpoint Verification (Railway + Vercel)

All 11 endpoints exercised with payload-level semantics via
`scripts/verify_live.py`. Result: **24/24 PASS**.

| # | Endpoint | Railway | Vercel | Key evidence |
|---|---|---|---|---|
| 1 | `GET /api/health` | ✅ 224 ms | ✅ 266 ms | `mode=railway solver=rust v=0.26.0` / `mode=vercel-serverless` |
| 2 | `POST /api/ghost/resolve` | ✅ 340 ms | ✅ 251 ms | Antarctica area DERIVED from global enclosure, within ±5 % of 14 M km² |
| 3 | `GET /api/solve/physical-truth` | ✅ 8 578 ms | ✅ 1 373 ms | `stress_1 = 1.63e-08` convergence residual (SMACOF) |
| 4 | `GET /api/projections/scores` | ✅ 241 ms | ✅ 252 ms | 4 projections scored (Mercator, Robinson, AuthaGraph, EqualEarth) |
| 5 | `POST /api/terraformation` | ✅ 876 ms | ✅ 484 ms | 248 nations modelled; area-loss list returned |
| 6 | `POST /api/alien/reconstruct` | ✅ 256 ms | ✅ 255 ms | `shape=Flat`, residual `2.72e-16` (≈2.7e-16 acceptance) |
| 7 | `POST /api/dynamics/simulate` | ✅ 273 ms | ✅ 252 ms | 1 001-point trajectory, inertial force law |
| 8 | `GET /api/anomaly/latest` | ✅ 166 ms | ✅ 243 ms | alerts list (empty until multi-snapshot ingest) |
| 9 | `GET /api/datasets` | ✅ 908 ms | ✅ 294 ms | 11 intrinsic edge-dataset catalogues (Africa, Arctic Ocean, …) |
| 10 | `GET /api/llm/status` | ✅ 210 ms | ✅ 255 ms | NVIDIA NIM primary, 3 models, backup key available |
| 11 | `POST /api/llm/query` | ✅ 62 931 ms | ✅ 50 620 ms | non-empty natural-language answer (see §6) |

---

## 5. Simulation Suite (6/6 on BOTH platforms)

`scripts/run_simulations.py` executed against each live target:

| Scenario | Acceptance criterion | Railway | Vercel |
|---|---|---|---|
| Ghost Resolver | Antarctica derived within 5 % of ~14 M km² | ✅ PASS | ✅ PASS |
| Physical Truth | convergence residual < 0.001 | ✅ 1.63e-08 (140 nodes) | ✅ 1.63e-08 |
| Projection Scores | 4 projections scored | ✅ PASS | ✅ PASS |
| Terraformation | ≥ 10 nations with area loss | ✅ 248 nations | ✅ 248 nations |
| Alien Reconstruct | Shape=Flat, residual ~2.7e-16 | ✅ 2.72e-16 | ✅ 2.72e-16 |
| Celestial Dynamics | non-empty trajectory | ✅ 1 001 points | ✅ 1 001 points |

Frontend: all 9 module pages (`ghost-resolver`, `distortion-observatory`,
`consensus-hall`, `terraformer`, `anomaly-detector`, `physical-truth`,
`alien-reconstruct`, `dynamics`, `terraformation`) return HTTP 200 from
`https://aethera-lime.vercel.app/dashboard/*`.

---

## 6. LLM Integration (NVIDIA free models — default, key-free for users)

- **Default chain** (`python/aethera/llm.py`):
  `deepseek-ai/deepseek-v4-flash-0731` → `nvidia/nemotron-3.5-lightning-30b-a3b` → `moonshotai/kimi-k3`.
- **Zero key entry**: platform ships with built-in keys; `NVIDIA_API_KEY`
  env-var override supported; `POST /api/llm/key` rotates at runtime; the
  Ctrl+K palette's Settings tab sets/resets keys (localStorage per-request
  override + server rotation).
- **Legacy fallback chain retained**: Z.ai (GLM-5.2) → DeepSeek → ChatGPT →
  Gemini → Mistral → Local LLM.
- **Live behaviour**: `deepseek-v4-flash-0731` exhibits long reasoning
  (>120 s) on some prompts; per-model timeout (30–45 s) triggers automatic
  failover to `nemotron-3.5-lightning-30b-a3b`, which answered the France
  area query in 50–63 s round-trip including the fallback window.
  Success rate across the audit: 100 % (all queries returned non-empty
  responses on both platforms).

---

## 7. Zero-Bias Compliance (Axiom IV)

Scan (`scripts/audit_zero_bias.py`) across 20 engine files: **PASS**.
No `lon`/`lat`/`WGS84`/`EPSG`/shapely/geopandas/fiona/pyproj in the engine
path. Measurement instrumentation remains documented as exempt. All derived
values carry Rationale Engine logs and sealed hashes (Axiom V).

## 8. CI/CD

- `End-to-End Simulations`: **success** on latest main (runs against the live deployment and commits `SIMULATION_RESULTS.md`).
- `Frontend Navigation Tests` + `CI`: fixed in `b8ee36f` — root cause was
  `.gitignore`'s bare `lib/` rule silently excluding the new
  `web/src/lib/api.ts`, breaking the Next.js production build
  (`Module not found: '@/lib/api'`).
- `Final Audit v25.0`: push-from-tag fixed (detached HEAD now pushes
  explicitly to `main`, artifact-push failure no longer fails the audit).

## 9. Commits & Tags

| Artifact | Value |
|---|---|
| v25.0 tag | pushed to `origin` (was blocked by dead token) |
| v25.0 commit | `f909010` |
| v26.0 dual-mode + Railway | `0f3a745` |
| CI URL fixes | `3beb76c` |
| Dockerfile m4 fix | `2276400` |
| gitignore/api.ts fix + verify suite | `b8ee36f` |
| v26.0 tag | `v26.0` (this report) |

## 10. Remaining Notes

- The Railway service is currently deployed via `railway up` (upload); the
  GitHub-repo webhook did not fire because the project token cannot complete
  account-scoped linking. Reconnect the repo (Railway dashboard → Service →
  Settings → Source) or wire a `railway up` deploy Action for push-to-deploy.
- `deepseek-v4-flash-0731`'s extended reasoning latency keeps end-to-end LLM
  responses at 50–63 s; the chain's per-model timeouts mask this for users.
- `aethera.vercel.app` is owned by a foreign Vercel account; the canonical
  production URL is `https://aethera-lime.vercel.app`.
