# AETHERA Deployment Environment Variables

## Required for production deployment

### Neon Database (permanent, no expiry)
```
DATABASE_URL=postgresql://neondb_owner:npg_i7I6oGlzgpmu@ep-small-fire-awt6hp2b.c-12.us-east-1.aws.neon.tech/neondb?sslmode=require
```
Neon project: `raspy-cherry-57547334` (region: aws-us-east-1)
Status: ✅ Active, permanent (no 30-day expiry like Render free tier)

### LLM API Keys (set at least ZAI_API_KEY for GLM-5.2)
```
ZAI_API_KEY=<your-zai-api-key>          # Primary: GLM-5.2
DEEPSEEK_API_KEY=<optional>             # Fallback 1
OPENAI_API_KEY=<optional>                # Fallback 2
GEMINI_API_KEY=<optional>               # Fallback 3
MISTRAL_API_KEY=<optional>              # Fallback 4
LOCAL_LLM_URL=http://localhost:11434    # Fallback 5 (Ollama)
```

### Cloudflare R2 (optional, for static asset CDN)
```
R2_ACCESS_KEY_ID=<r2-access-key>
R2_SECRET_ACCESS_KEY=<r2-secret-key>
R2_ENDPOINT_URL=https://<account-id>.r2.cloudflarestorage.com
NEXT_PUBLIC_CLOUDFLARE_R2_URL=https://cdn.yourdomain.com
```
Status: ⚠️ R2 must be enabled in Cloudflare Dashboard first (manual step)

### Cloudflare Worker (keep-alive, already deployed)
```
RENDER_APP_URL=https://aethera-backend.onrender.com
```
Worker: `aethera-keep-alive` — deployed, cron every 10 minutes
Status: ✅ Deployed and active

### Render Backend
```
PORT=8000
DATABASE_URL=<Neon connection string>
PYTHONPATH=/app/python
AETHERA_FFI_PATH=/usr/local/lib/libaethera_ffi.so
```

### Vercel Frontend
```
NEXT_PUBLIC_API_URL=https://aethera-backend.onrender.com
```

## Cloudflare setup (manual steps required)

### 1. Enable R2
1. Go to https://dash.cloudflare.com → R2
2. Click "Enable R2" (requires payment method on file)
3. Run: `python -m aethera.r2_config create_bucket`

### 2. Worker is already deployed
The `aethera-keep-alive` worker is deployed via Cloudflare API.
It pings `/api/health` every 10 minutes to prevent Render cold starts.
Verify at: https://aethera-keep-alive.<your-subdomain>.workers.dev
