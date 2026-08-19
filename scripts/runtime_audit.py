"""
AETHERA v20.1 — Deep Runtime Audit
"""
import sys
import json
import urllib.request
import time

sys.path.insert(0, 'python')

BASE = 'http://127.0.0.1:8765/api'
RESULTS = {}

def test_module(name, method, path, data=None):
    url = f'{BASE}{path}'
    try:
        if data:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode(),
                headers={'Content-Type': 'application/json'},
                method=method
            )
        else:
            req = urllib.request.Request(url, method=method)
        
        start = time.time()
        r = urllib.request.urlopen(req, timeout=30)
        elapsed = (time.time() - start) * 1000
        
        result = json.loads(r.read().decode())
        RESULTS[name] = {
            'passed': True,
            'status': r.status,
            'time_ms': round(elapsed, 1),
            'result': result
        }
        print(f"[PASS] {name}: {r.status} ({elapsed:.0f}ms)")
        return True
    except Exception as e:
        RESULTS[name] = {'passed': False, 'error': str(e)}
        print(f"[FAIL] {name}: {e}")
        return False


print("="*60)
print("AETHERA v20.1 — Deep Runtime Audit")
print("="*60)

# Test all 9 modules
print("\n[1/9] Ghost Resolver...")
test_module('Ghost Resolver', 'POST', '/ghost/resolve', {
    'polygons': [
        {'name': 'A', 'area': 100, 'neighbours': ['B', 'C']},
        {'name': 'B', 'area': 200, 'neighbours': ['A', 'C']},
        {'name': 'C', 'area': None, 'neighbours': ['A', 'B']}
    ],
    'global_enclosure': 'World',
    'global_area': 500
})

print("\n[2/9] Physical Truth...")
test_module('Physical Truth', 'GET', '/solve/physical-truth')

print("\n[3/9] Distortion Observatory...")
test_module('Distortion', 'GET', '/projections/scores')

print("\n[4/9] Terraformer...")
test_module('Terraformer', 'POST', '/terraformation', {'sea_level_rise_m': 10})

print("\n[5/9] Alien Geometer...")
test_module('Alien Geometer', 'POST', '/alien/reconstruct', {
    'edges': [
        {'source': 'A', 'target': 'B', 'length': 1.0, 'source_type': 'topology'},
        {'source': 'B', 'target': 'C', 'length': 1.0, 'source_type': 'topology'},
        {'source': 'C', 'target': 'A', 'length': 1.0, 'source_type': 'topology'}
    ]
})

print("\n[6/9] Celestial Dynamics...")
test_module('Celestial Dynamics', 'POST', '/dynamics/simulate', {
    'start': [0, 0, 0],
    'initial_velocity': [1, 0, 0],
    'force_law': 'uniform',
    'uniform_accel': [0, 0, -9.81],
    'dt': 0.1,
    't_max': 5.0
})

print("\n[7/9] Data Inventory...")
test_module('Datasets', 'GET', '/datasets')

print("\n[8/9] Anomaly Detector...")
test_module('Anomaly', 'GET', '/anomaly/latest')

print("\n[9/9] LLM Status...")
test_module('LLM Status', 'GET', '/llm/status')

# Summary
print("\n" + "="*60)
print("AUDIT SUMMARY")
print("="*60)

passed = sum(1 for v in RESULTS.values() if v.get('passed'))
total = len(RESULTS)

print(f"\nModules Tested: {passed}/{total}")
print(f"Success Rate: {(passed/total*100):.0f}%")

if passed == total:
    print("\n[OK] ALL MODULES PASSING")
else:
    print(f"\n[X] {total - passed} MODULES FAILING")
    for name, result in RESULTS.items():
        if not result.get('passed'):
            print(f"  - {name}: {result.get('error')}")

print("\n" + "="*60)
