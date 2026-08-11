import urllib.request, json

VERCEL_TOKEN = 'vcp_1ZFSDYQ8TG6615168tSP90U7lI6fGMWqCm5tkPMRyDFTcvyoMr2wPhW8'

# First, get the user's projects
print("Getting Vercel projects...")
req = urllib.request.Request(
    'https://api.vercel.com/v9/projects',
    headers={'Authorization': f'Bearer {VERCEL_TOKEN}'}
)
r = urllib.request.urlopen(req, timeout=10)
data = json.loads(r.read())
print(f"Found {len(data.get('projects', []))} projects")
for p in data.get('projects', [])[:5]:
    print(f"  - {p.get('name')}: {p.get('id')}")
