import urllib.request, json

BASE = 'http://127.0.0.1:8765/api'

# Test ghost resolve
data = json.dumps({
    'polygons': [
        {'name': 'A', 'area': 100, 'neighbours': ['B', 'C']},
        {'name': 'B', 'area': 200, 'neighbours': ['A', 'C']},
        {'name': 'C', 'area': None, 'neighbours': ['A', 'B']},
    ],
    'global_enclosure': 'World',
    'global_area': 500
}).encode()

req = urllib.request.Request(
    f'{BASE}/ghost/resolve',
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
