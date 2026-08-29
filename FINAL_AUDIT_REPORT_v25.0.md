# AETHERA FINAL AUDIT REPORT — v25.0

- Generated: 2026-08-29T12:45:17.704304+00:00
- Report hash: `cf70b624`

## 1. Executive Summary

AETHERA v25.0 delivers the sovereign geometric substrate end-to-end:
real ETOPO1 ingestion, all 9 dashboard modules navigable, six
acceptance simulations, NVIDIA NIM as the default LLM provider with
zero user configuration, and a single-origin Vercel deployment
(Next.js frontend + FastAPI serverless backend on Neon Postgres).

## 2. Platform Modules (frontend)

- 1. ghost-resolver
- 2. distortion-observatory
- 3. consensus-hall
- 4. terraformer
- 5. anomaly-detector
- 6. physical-truth
- 7. alien-reconstruct
- 8. dynamics
- 9. terraformation

Total: **9 modules** (requirement: 9)

## 3. API Endpoints (backend)

- `/api/aics/coordinates/{region_name}`
- `/api/alien/reconstruct`
- `/api/anomaly/latest`
- `/api/datasets`
- `/api/distortion/global`
- `/api/distortion/ranking`
- `/api/distortion/region/{region_name}`
- `/api/dynamics/simulate`
- `/api/ghost/antarctica`
- `/api/ghost/resolve`
- `/api/health`
- `/api/llm/key`
- `/api/llm/query`
- `/api/llm/status`
- `/api/projections/scores`
- `/api/regions/list`
- `/api/regions/{region}/edges`
- `/api/solve/manifold`
- `/api/solve/physical-truth`
- `/api/terraformation`
- `/api/upload/survey`

Total: **21 endpoints**

## 4. LLM Integration (v25.0)

- Primary provider: **NVIDIA NIM (free) — no API key required**
- Default models: deepseek-ai/deepseek-v4-flash-0731 → nvidia/nemotron-3.5-lightning-30b-a3b → moonshotai/kimi-k3
- Built-in key active: **yes** (user entry optional; rotation via `POST /api/llm/key` or the dashboard palette Ctrl+K → Settings)
- Fallback chain: GLM-5.2 → DeepSeek → ChatGPT → Gemini → Mistral → Local

## 5. Zero-Bias Verification (Axiom 4)

- Scan verdict: **PASS**

## 6. Test Suite

- pytest: 40 passed in 1.84s

## Physical Substrate (Neon Postgres)

- Regions with derived physical truth: **248**
- Zero-area regions: **0**
- Total derived surface: **507,344,131 km2**
- Graph points / edges: **46,555** / **43,882**

## 7. Deployment

- Frontend + backend: **Vercel** (single origin, `web/` root with `api/index.py` FastAPI serverless)
- Database: **Neon Postgres** (`DATABASE_URL` secret)
- Legacy Railway backend: retired (token/app no longer available); same-origin serverless replaces it

## 8. Known Limitations

- deepseek-v4-flash-0731 may exceed its per-model timeout under load; the chain falls back to nemotron-3.5-lightning automatically
- Antarctica derived area (~12.4M km2 at bounding-box sampling) sits below the 14.2M km2 accepted figure incl. ice shelves; refine with polygon-exact sampling
- GitHub Actions ingestion requires the `DATABASE_URL` repository secret to be (re)set after token rotation

