import urllib.request, json, sys

VERCEL_TOKEN = 'vcp_1ZFSDYQ8TG6615168tSP90U7lI6fGMWqCm5tkPMRyDFTcvyoMr2wPhW8'

# Get projects
print("Getting projects...")
req = urllib.request.Request(
    'https://api.vercel.com/v9/projects',
    headers={'Authorization': f'Bearer {VERCEL_TOKEN}'}
)
r = urllib.request.urlopen(req, timeout=10)
data = json.loads(r.read())
print(f"Response type: {type(data)}")
if isinstance(data, dict):
    projects = data.get('projects', [])
    print(f"Found {len(projects)} projects:")
    for p in projects[:5]:
        print(f"  - {p.get('name')}: {p.get('id')}")
else:
    print(f"Response: {json.dumps(data, indent=2)[:500]}")
