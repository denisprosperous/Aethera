import urllib.request, json, time

VERCEL_TOKEN = 'vcp_1ZFSDYQ8TG6615168tSP90U7lI6fGMWqCm5tkPMRyDFTcvyoMr2wPhW8'
PROJECT_ID = 'prj_9OEw4pKFKZ6TUoxfisZMkHJSPkaI'  # web project

# Deploy to existing Vercel project
print("Deploying to Vercel project 'web'...")
deployment = {
    'name': 'aethera',
    'gitSource': {
        'type': 'github',
        'repoId': 1321976154,
        'ref': 'main'
    },
    'projectSettings': {
        'framework': 'nextjs'
    }
}

req = urllib.request.Request(
    f'https://api.vercel.com/v13/deployments',
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
    for i in range(60):
        time.sleep(3)
        status_req = urllib.request.Request(
            f'https://api.vercel.com/v13/deployments/{deployment_id}',
            headers={'Authorization': f'Bearer {VERCEL_TOKEN}'}
        )
        status_r = urllib.request.urlopen(status_req, timeout=10)
        status_data = json.loads(status_r.read())
        state = status_data.get('state')
        url = status_data.get('url')
        print(f"  [{i+1}] {state}: {url}")
        if state == 'READY':
            print(f"\n[OK] Frontend deployed: {url}")
            break
        elif state in ['ERROR', 'CANCELED']:
            print(f"\n[ERROR] Deployment {state}")
            break
except Exception as e:
    print(f"[ERROR] Vercel deployment failed: {e}")
