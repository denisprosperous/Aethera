import urllib.request, json

BASE = 'http://127.0.0.1:8765/api'

# Test terraformation
data = json.dumps({
    'sea_level_rise_m': 10
}).encode()

req = urllib.request.Request(
    f'{BASE}/terraformation',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    r = urllib.request.urlopen(req, timeout=10)
    result = json.loads(r.read().decode())
    print('SUCCESS:', json.dumps(result, indent=2)[:500])
except Exception as e:
    print('ERROR:', e)
