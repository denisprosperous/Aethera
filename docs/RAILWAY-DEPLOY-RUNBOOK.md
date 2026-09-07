# AETHERA — Railway Backend Deployment Runbook (v31.3)

**Audience:** the account owner, at the Railway dashboard.
**Time to live backend once the plan is active: ~4 minutes. No CLI, no API calls.**

---

## Current state (verified 2026-09-08, CI run 34141454358)

| Component | Status |
|---|---|
| Repo config (`Dockerfile`, `railway.json`, `requirements.txt`) | ✅ Ready |
| Deploy workflow `.github/workflows/railway-deploy.yml` | ✅ Wired & tested |
| Repo secret `RAILWAY_TOKEN` | ✅ Set (encrypted, verified) |
| Vercel env contract (`NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_RAILWAY_URL` / `NEXT_PUBLIC_RAILWAY_ENABLED`) | ✅ Set (prod/preview/dev) |
| Vercel frontend | ✅ Live, 28/28 + 12/12 checks green |
| Railway workspace | ❌ **Trial expired — billing wall. Live CI log: "Your trial has expired. Please select a plan to continue using Railway."** |

The pipeline was fired end-to-end (workflow_dispatch) and stopped **only** at
Railway's billing gate. Nothing else blocks. No code path can bypass a
suspended workspace.

---

## Step 1 — Activate the workspace (~1 min)

1. Log in at <https://railway.app> (account that owns project
   `2e5a06f9-dee2-417e-8d79-af8df3c45d90`).
2. If prompted, select the **Hobby plan** ($5 monthly credit, first month free
   where eligible) or enter a payment method.
3. Open the existing project (it already contains service `aethera-backend`
   and the `DATABASE_URL` environment).

> Do **not** create a new project — the existing one keeps the Railway
> domain `aethera-backend.up.railway.app` that Vercel's env vars point to.

## Step 2 — Deploy (choose ONE; A is zero-touch)

**Option A — GitHub integration (zero-touch):**
1. In the project, click **New service → GitHub Repo**.
2. Pick `denisprosperous/Aethera` (authorize Railway's GitHub app if asked).
3. Railway auto-detects the root `Dockerfile` (via `railway.json`) and builds.
4. Deploy → done. Every later push to `main` touching `python/**` or the
   Dockerfile redeploys automatically via the CI workflow.

**Option B — let the CI workflow do it (zero-click):**
1. After Step 1, just open
   <https://github.com/denisprosperous/Aethera/actions/workflows/railway-deploy.yml>
2. Click **Run workflow → Run**. The workflow deploys and health-gates for
   10 minutes automatically (the `RAILWAY_TOKEN` secret is already installed).

## Step 3 — Environment variables (~1 min)

Service `aethera-backend` → **Variables** tab — add (skip any already present):

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon connection string (console.neon.tech) |
| `RAILWAY_ENABLED` | `true` |
| `NEXT_PUBLIC_API_URL` | `https://aethera-backend.up.railway.app` |
| `NEXT_PUBLIC_RAILWAY_URL` | `https://aethera-backend.up.railway.app` |
| `NEXT_PUBLIC_RAILWAY_ENABLED` | `true` |

Changing variables triggers a redeploy — accept it.

> The frontend already handles CORS (`Access-Control-Allow-Origin: *`) and
> dual-mode failover, so no Vercel changes are needed.

## Step 4 — Verify (agent-side, ~1 min)

Once deployed, any of these confirm the revival:

```bash
curl https://aethera-backend.up.railway.app/api/health
# → {"status":"ok","version":"0.30.1",...,"mode":"railway",...}

API_BASE=https://aethera-backend.up.railway.app python3 scripts/verify_live.py
python3 scripts/verify_v30.py https://aethera-backend.up.railway.app
# → 28/28 + 12/12 expected, with the Rust FFI solver (residual ~1.6e-08)
```

The Vercel frontend needs **no redeployment**: it probes
`NEXT_PUBLIC_RAILWAY_URL` per session and switches to Railway the moment the
health check passes.

---

## Why the backend matters (GTI impact)

| Solver | Residual | GTI accuracy component |
|---|---|---|
| `python_fallback` (Vercel serverless) | 0.095 | ≈ 0.51 → GTI 66.88 (C) |
| Rust FFI (Railway Docker) | 1.63e-08 | ≈ 1.00 → GTI ≈ 87 |

Reviving Railway lifts the platform's Truth Index grade from **C** to ~**87**,
restoring the full-fidelity Rust solver.
