import urllib.request, json, time, sys

VERCEL_TOKEN = 'vcp_1ZFSDYQ8TG6615168tSP90U7lI6fGMWqCm5tkPMRyDFTcvyoMr2wPhW8'
PROJECT_ID = 'prj_9OEw4pKFKZ6TUoxfisZMkHJSPkaI'

print("Starting Vercel deployment...", flush=True)

deployment = {
    'name': 'aethera',
    'gitSource': {
        'type': 'github',
        'repoId': 1321976154,
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
    print(f"Deployment ID: {deployment_id}", flush=True)
    
    # Wait and check status
    for i in range(30):
        time.sleep(5)
        try:
            status_req = urllib.request.Request(
                f'https://api.vercel.com/v13/deployments/{deployment_id}',
                headers={'Authorization': f'Bearer {VERCEL_TOKEN}'}
            )
            status_r = urllib.request.urlopen(status_req, timeout=10)
            status_data = json.loads(status_r.read())
            state = status_data.get('state')
            url = status_data.get('url')
            print(f"[{i+1}] {state}: {url}", flush=True)
            if state in ['READY', 'ERROR', 'CANCELED']:
                print(f"Final: {state} - {url}", flush=True)
                break
        except Exception as e:
            print(f"Check error: {e}", flush=True)
except Exception as e:
    print(f"Error: {e}", flush=True)
