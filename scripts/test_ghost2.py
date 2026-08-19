import sys, json
sys.path.insert(0, 'python')
import urllib.request

# Simpler test case
data = json.dumps({
    'polygons': [
        {'name': 'A', 'area': 100, 'neighbours': ['B', 'C']},
        {'name': 'B', 'area': 200, 'neighbours': ['A', 'C']},
        {'name': 'C', 'area': None, 'neighbours': ['A', 'B']}
    ],
    'global_enclosure': 'World',
    'global_area': 500
}).encode()

print("Sending request...")
req = urllib.request.Request(
    'http://127.0.0.1:8765/api/ghost/resolve',
    data=data,
    headers={'Content-Type': 'application/json'},
    method='POST'
)

try:
    r = urllib.request.urlopen(req, timeout=10)
    print(f"Status: {r.status}")
    print(f"Response: {r.read().decode()[:500]}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}:")
    print(e.read().decode())
except Exception as e:
    print(f"Exception: {e}")
