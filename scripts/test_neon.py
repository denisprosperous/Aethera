import urllib.request, json

try:
    req = urllib.request.Request(
        'https://console.neon.tech/api/v2/projects',
        headers={'Authorization': 'Bearer napi_1he1jbekctv5r48eroyepucx55y9f75bh1lnx4renm02ryfn2ozmw4p6yo66ehr3'}
    )
    r = urllib.request.urlopen(req, timeout=10)
    data = json.loads(r.read())
    print('Status:', r.status)
    print('Response:', json.dumps(data, indent=2)[:800])
except Exception as e:
    print('Error:', e)
