import urllib.request, json

# Get endpoints
req = urllib.request.Request(
    'https://console.neon.tech/api/v2/projects/raspy-cherry-57547334/endpoints',
    headers={'Authorization': 'Bearer napi_1he1jbekctv5r48eroyepucx55y9f75bh1lnx4renm02ryfn2ozmw4p6yo66ehr3'}
)
r = urllib.request.urlopen(req, timeout=10)
data = json.loads(r.read())
print('Endpoints:', json.dumps(data, indent=2)[:1000])
