import urllib.request, json

# Check Railway projects
req = urllib.request.Request(
    'https://railway.app/api/v1/projects',
    headers={'Authorization': 'Bearer 77d8e17d-7a87-451b-9872-96113b788547'}
)
try:
    r = urllib.request.urlopen(req, timeout=10)
    data = json.loads(r.read())
    print(f"Projects: {json.dumps(data, indent=2)[:1500]}")
except Exception as e:
    print(f"Error: {e}")
