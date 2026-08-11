# AETHERA Deployment Guide

## Prerequisites

1. **GitHub Account** - Repository: https://github.com/denisprosperous/Aethera
2. **Railway Account** - https://railway.app/ (free tier available)
3. **Vercel Account** - https://vercel.com/ (free tier available)
4. **Neon Account** - https://console.neon.tech/ (free tier available)

---

## Phase 1: Backend Deployment (Railway)

### Step 1: Create Railway Project

1. Go to https://railway.app/
2. Click "New Project" → "Deploy from GitHub repo"
3. Select repository: `denisprosperous/Aethera`
4. Railway will auto-detect the Python app

### Step 2: Set Environment Variables

In Railway dashboard, go to Settings → Variables:

```
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/dbname?sslmode=require
PYTHONPATH=python
```

**Note:** Get `DATABASE_URL` from Neon (see Phase 1.3)

### Step 3: Deploy

1. Click "Deploy" in Railway
2. Wait for build to complete (~2-3 minutes)
3. Copy the public URL (e.g., `https://aethera-backend.up.railway.app`)
4. Verify: `https://aethera-backend.up.railway.app/api/health`

---

## Phase 1: Frontend Deployment (Vercel)

### Step 1: Create Vercel Project

1. Go to https://vercel.com/
2. Click "Add New..." → "Project"
3. Import GitHub repository: `denisprosperous/Aethera`
4. Vercel will auto-detect Next.js

### Step 2: Set Environment Variables

In Vercel dashboard, go to Settings → Environment Variables:

```
NEXT_PUBLIC_API_URL=https://aethera-backend.up.railway.app
```

### Step 3: Deploy

1. Click "Deploy"
2. Wait for build (~1 minute)
3. Copy the public URL (e.g., `https://aethera.vercel.app`)
4. Verify: `https://aethera.vercel.app/dashboard`

---

## Phase 1: Database Setup (Neon)

### Step 1: Create Neon Project

1. Go to https://console.neon.tech/
2. Click "New Project"
3. Name: `aethera-platform`
4. Region: `us-east-1`
5. Wait for provisioning (~30 seconds)

### Step 2: Get Connection String

1. Go to "Connection String" in Neon dashboard
2. Copy the connection string (looks like `postgresql://...`)
3. Keep this secure - it's your database password

### Step 3: Apply Schema

1. Go to "SQL Editor" in Neon
2. Copy and run the schema from `infra/db/schema.sql`
3. Verify tables are created

### Step 4: Update Railway

1. Go back to Railway dashboard
2. Settings → Variables
3. Add `DATABASE_URL` with the Neon connection string
4. Redeploy

---

## Phase 1: Keep-Alive Worker (Cloudflare)

### Step 1: Install Wrangler

```bash
npm install -g wrangler
```

### Step 2: Login to Cloudflare

```bash
wrangler login
```

### Step 3: Deploy Worker

```bash
cd C:\Users\PROSPERO\Aethera\workers\keep-alive
wrangler deploy
```

### Step 4: Set Secret

```bash
wrangler secret put BACKEND_URL
# Enter: https://aethera-backend.up.railway.app
```

---

## Phase 2: Scale Ingestion

### Run Ingestion Pipeline

```bash
cd C:\Users\PROSPERO\Aethera
python -m aethera.cli.main ingest --regions all --workers 4 --commit
```

This will:
1. Download Terrarium DEM tiles for all regions
2. Compute 3D surface areas
3. Store in database
4. Commit to Git after every 5 regions

### Monitor Progress

```bash
python -m aethera.cli.main audit
```

---

## Phase 3: Compile Rust Engine

### Install MSVC Build Tools

1. Download from: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
2. Run installer
3. Select "Desktop development with C++"
4. Complete installation

### Compile Rust

```bash
cd C:\Users\PROSPERO\Aethera\rust
cargo build --release
```

### Verify FFI

```bash
python -c "from aethera.engine_ffi.bridge import load_rust_lib; print(load_rust_lib())"
```

---

## Troubleshooting

### Issue: Railway deploy fails
**Fix:** Check logs in Railway dashboard → ensure DATABASE_URL is set

### Issue: Vercel deploy fails
**Fix:** Check `NEXT_PUBLIC_API_URL` is set correctly

### Issue: Database connection fails
**Fix:** Verify Neon connection string, ensure IP whitelist includes Railway

### Issue: Ingestion times out
**Fix:** Reduce `--workers` to 2, increase timeout

---

## Success Criteria

- [ ] Backend live on Railway: `https://aethera-backend.up.railway.app/api/health`
- [ ] Frontend live on Vercel: `https://aethera.vercel.app/dashboard`
- [ ] Cloudflare Worker active (pinging every 10 min)
- [ ] All 195+ countries ingested
- [ ] Rust engine compiled and loaded
- [ ] API response time < 500ms

---

## Next Steps

After deployment:
1. Update README.md with live URLs
2. Create demo video
3. Share with community
