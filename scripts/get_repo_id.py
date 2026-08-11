import urllib.request, json

VERCEL_TOKEN = 'vcp_1ZFSDYQ8TG6615168tSP90U7lI6fGMWqCm5tkPMRyDFTcvyoMr2wPhW8'
GITHUB_TOKEN = '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'

# Get GitHub repo ID
print("Getting GitHub repository info...")
req = urllib.request.Request(
    'https://api.github.com/repos/denisprosperous/Aethera',
    headers={'Authorization': f'token {GITHUB_TOKEN}'}
)
r = urllib.request.urlopen(req, timeout=10)
repo = json.loads(r.read())
print(f"GitHub Repo ID: {repo.get('id')}")
print(f"Full Name: {repo.get('full_name')}")
