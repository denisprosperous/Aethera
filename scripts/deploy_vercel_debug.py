import urllib.request, json, sys

VERCEL_TOKEN = 'vcp_1ZFSDYQ8TG6615168tSP90U7lI6fGMWqCm5tkPMRyDFTcvyoMr2wPhW8'

# Try to get error details
deployment = {
    'name': 'aethera',
    'gitSource': {
        'type': 'github',
        'repo': 'denisprosperous/Aethera',
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
    print(json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}:")
    print(e.read().decode())
