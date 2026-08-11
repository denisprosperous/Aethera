import urllib.request, json

BASE = 'http://127.0.0.1:8765/api'

# Test dynamics simulate
data = json.dumps({
    'start': [0, 0, 0],
    'initial_velocity': [1, 0, 0],
    'force_law': 'uniform',
    'uniform_accel': [0, 0, -9.81],
    'dt': 0.1,
    't_max': 5.0
}).encode()

req = urllib.request.Request(
    f'{BASE}/dynamics/simulate',
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
