import urllib.request, json, time, sys

VERCEL_TOKEN = 'vcp_1ZFSDYQ8TG6615168tSP90U7lI6fGMWqCm5tkPMRyDFTcvyoMr2wPhW8'
GITHUB_REPO = 'denisprosperous/Aethera'

# Deploy to Vercel
print("Deploying to Vercel...")
deployment = {
    'name': 'aethera',
    'gitSource': {
        'type': 'github',
        'repo': GITHUB_REPO,
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
    print(f"Deployment triggered: {deployment_id}")
    
    # Wait for deployment
    print("Waiting for deployment...")
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
        print(f"  [{i+1}] Status: {state} - {url}")
        if state in ['READY', 'ERROR', 'CANCELED']:
            print(f"\nDeployment {state}: {url}")
            break
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
