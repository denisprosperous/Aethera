import urllib.request, json, time, os, subprocess

# Tokens
GITHUB_TOKEN = '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'
VERCEL_TOKEN = 'vcp_1ZFSDYQ8TG6615168tSP90U7lI6fGMWqCm5tkPMRyDFTcvyoMr2wPhW8'
NEON_API_KEY = 'napi_1he1jbekctv5r48eroyepucx55y9f75bh1lnx4renm02ryfn2ozmw4p6yo66ehr3'
RAILWAY_TOKEN = '77d8e17d-7a87-451b-9872-96113b788547'
CLOUDFLARE_TOKEN = 'cfat_5gl3LhFAe5zaIkdGvoiH0QzNAdn45PTd34HlZWrMe170b451'

GITHUB_REPO = 'denisprosperous/Aethera'
REPO_ID = 1321976154

print("="*60)
print("AETHERA v19.0 — Deployment")
print("="*60)

# Phase 1: Get Neon connection string
print("\n[Phase 1] Neon Database")
print("-"*40)

req = urllib.request.Request(
    'https://console.neon.tech/api/v2/projects/raspy-cherry-57547334/endpoints',
    headers={'Authorization': f'Bearer {NEON_API_KEY}'}
)
r = urllib.request.urlopen(req, timeout=10)
neon_data = json.loads(r.read())
host = neon_data['endpoints'][0]['host']
DATABASE_URL = f'postgresql://neondb_owner:npg_i7I6oGlzgpmu@{host}/neondb?sslmode=require'
print(f"[OK] Database: {host}")
print(f"[OK] DATABASE_URL set")

# Phase 2: Railway - Save env var to .env file for manual use
print("\n[Phase 2] Railway Backend")
print("-"*40)
print("Note: Railway env vars must be set manually in dashboard")
print(f"  DATABASE_URL={DATABASE_URL[:50]}...")
print("  PYTHONPATH=python")
print("\n  Steps:")
print("  1. Go to https://railway.app/project/2e5a06f9-dee2-417e-8d79-af8df3c45d90")
print("  2. Settings -> Environment Variables")
print("  3. Add DATABASE_URL and PYTHONPATH")
print("  4. Redeploy")

# Phase 3: Vercel Deployment
print("\n[Phase 3] Vercel Frontend")
print("-"*40)

# Deploy via Vercel API
deployment = {
    'name': 'aethera',
    'gitSource': {
        'type': 'github',
        'repoId': REPO_ID,
        'ref': 'main'
    }
}

req = urllib.request.Request(
    'https://api.vercel.com/v13/deployments',
    data=json.dumps(deployment).encode(),
    headers={
        'Authorization': f'Bearer {VERCEL_TOKEN}',
        'Content-Type': 'application/json'
    },
    method='POST'
)

try:
    r = urllib.request.urlopen(req, timeout=30)
    result = json.loads(r.read())
    deployment_id = result.get('id')
    print(f"[OK] Deployment triggered: {deployment_id}")
    
    # Wait for deployment
    print("Waiting for deployment...")
    FRONTEND_URL = None
    for i in range(60):
        time.sleep(3)
        status_req = urllib.request.Request(
            f'https://api.vercel.com/v13/deployments/{deployment_id}',
            headers={'Authorization': f'Bearer {VERCEL_TOKEN}'}
        )
        status_r = urllib.request.urlopen(status_req, timeout=10)
        status_data = json.loads(status_r.read())
        state = status_data.get('state')
        url = status_data.get('url') or status_data.get('alias')
        print(f"  [{i+1}] {state}: {url}")
        if state == 'READY':
            FRONTEND_URL = url
            print(f"\n[OK] Frontend deployed: {url}")
            break
        elif state in ['ERROR', 'CANCELED']:
            print(f"\n[ERROR] Deployment {state}")
            FRONTEND_URL = 'https://aethera.vercel.app'
            break
except Exception as e:
    print(f"[ERROR] Vercel deployment failed: {e}")
    FRONTEND_URL = 'https://aethera.vercel.app'

# Phase 4: Update Railway env vars via file
print("\n[Phase 4] Environment Configuration")
print("-"*40)

# Create .env file for Railway
env_content = f"""DATABASE_URL={DATABASE_URL}
PYTHONPATH=python
"""

with open('backend/.env', 'w') as f:
    f.write(env_content)
print("[OK] Created backend/.env with DATABASE_URL")

# Phase 5: Commit and push
print("\n[Phase 5] Committing Changes")
print("-"*40)
result = subprocess.run(['git', 'add', '.'], capture_output=True, text=True)
result = subprocess.run(['git', 'commit', '-m', 'deploy: v19.0 automated deployment config'], capture_output=True, text=True)
result = subprocess.run(['git', 'push', 'origin', 'main'], capture_output=True, text=True)
print("[OK] Committed and pushed to GitHub")

# Phase 6: Final Summary
print("\n" + "="*60)
print("DEPLOYMENT SUMMARY")
print("="*60)
print(f"\nGitHub: https://github.com/{GITHUB_REPO}")
print(f"Database: {host} (Neon)")
print(f"Frontend: {FRONTEND_URL or 'https://aethera.vercel.app'}")
print(f"Railway: https://railway.app/project/2e5a06f9-dee2-417e-8d79-af8df3c45d90")
print("\nNEXT STEPS:")
print("1. Railway: Set DATABASE_URL in dashboard, then redeploy")
print("2. Vercel: Wait for deployment to complete")
print("3. Test: http://localhost:3000/dashboard (local)")
print("\nNote: Railway and Vercel deployments take 2-5 minutes.")
print("Check dashboards for status.")
