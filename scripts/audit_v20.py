"""
AETHERA v20.0 — Full Platform Audit Script
Tests all modules, endpoints, and bias checks.
"""
import sys
import json
import urllib.request
import time

sys.path.insert(0, 'python')

BASE_URL = 'http://127.0.0.1:8765/api'
RESULTS = {}

def test_endpoint(name, method, path, data=None, expected_status=200):
    """Test an API endpoint and return result."""
    url = f'{BASE_URL}{path}'
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
        
        r = urllib.request.urlopen(req, timeout=10)
        result = json.loads(r.read().decode())
        status = r.status
        
        passed = status == expected_status
        RESULTS[name] = {
            'passed': passed,
            'status': status,
            'result': result if passed else f'Expected {expected_status}, got {status}'
        }
        print(f"{'[PASS]' if passed else '[FAIL]'} {name}: {status}")
        return passed
    except Exception as e:
        RESULTS[name] = {'passed': False, 'error': str(e)}
        print(f"[FAIL] {name}: {e}")
        return False


def run_audit():
    print("="*60)
    print("AETHERA v20.0 — Full Platform Audit")
    print("="*60)
    
    # Phase 1: Backend API Tests
    print("\n[Phase 1] Backend API Tests")
    print("-"*40)
    
    # Health check
    test_endpoint('Health', 'GET', '/health')
    
    # Ghost Resolver
    test_endpoint('Ghost Resolver', 'POST', '/ghost/resolve', {
        'polygons': [
            {'name': 'A', 'area': 100, 'neighbours': ['B', 'C']},
            {'name': 'B', 'area': 200, 'neighbours': ['A', 'C']},
            {'name': 'C', 'area': None, 'neighbours': ['A', 'B']},
        ],
        'global_enclosure': 'World',
        'global_area': 500
    })
    
    # Physical Truth
    test_endpoint('Physical Truth', 'GET', '/solve/physical-truth')
    
    # Distortion Scores
    test_endpoint('Distortion Scores', 'GET', '/projections/scores')
    
    # Terraformation
    test_endpoint('Terraformation', 'POST', '/terraformation', {
        'sea_level_rise_m': 10
    })
    
    # Alien Geometer
    test_endpoint('Alien Geometer', 'POST', '/alien/reconstruct', {
        'edges': [
            {'source': 'A', 'target': 'B', 'length': 1.0, 'source_type': 'topology'},
            {'source': 'B', 'target': 'C', 'length': 1.0, 'source_type': 'topology'},
            {'source': 'C', 'target': 'A', 'length': 1.0, 'source_type': 'topology'}
        ]
    })
    
    # Celestial Dynamics
    test_endpoint('Celestial Dynamics', 'POST', '/dynamics/simulate', {
        'start': [0, 0, 0],
        'initial_velocity': [1, 0, 0],
        'force_law': 'uniform',
        'uniform_accel': [0, 0, -9.81],
        'dt': 0.1,
        't_max': 5.0
    })
    
    # Datasets
    test_endpoint('Datasets', 'GET', '/datasets')
    
    # Anomaly
    test_endpoint('Anomaly', 'GET', '/anomaly/latest')
    
    # LLM Status
    test_endpoint('LLM Status', 'GET', '/llm/status')
    
    # Phase 2: Bias Checks
    print("\n[Phase 2] Bias Validation")
    print("-"*40)
    
    # Check for biased code
    import os
    import re
    
    bias_checks = [
        ('lon/lat references', r'\\blon\\b|\\ blat\\b|longitude|latitude', 'python/aethera/'),
        ('WGS84/EPSG', r'wgs84|WGS84|epsg|EPSG', 'python/aethera/'),
        ('Earth radius', r'6371|6378|6\.371', 'python/aethera/'),
        ('Shapely/Geopandas', r'shapely|geopandas|fiona|pyproj', 'python/aethera/'),
        ('PostGIS', r'PostGIS|ST_Area|geometry', 'python/aethera/'),
    ]
    
    bias_results = {}
    for name, pattern, directory in bias_checks:
        count = 0
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            matches = re.findall(pattern, content, re.IGNORECASE)
                            count += len(matches)
                    except:
                        pass
        bias_results[name] = count
        status = '[PASS]' if count == 0 else '[FAIL]'
        print(f"{status} {name}: {count} occurrences")
    
    # Phase 3: Frontend Check
    print("\n[Phase 3] Frontend Check")
    print("-"*40)
    
    try:
        r = urllib.request.urlopen('http://127.0.0.1:3000/dashboard', timeout=10)
        if r.status == 200:
            print("[PASS] Frontend loading")
        else:
            print(f"[FAIL] Frontend status: {r.status}")
    except Exception as e:
        print(f"[WARN] Frontend not reachable: {e}")
        print("  Note: Start frontend with: cd web && npm run dev")
    
    # Phase 4: Database Check
    print("\n[Phase 4] Database Schema Check")
    print("-"*40)
    
    # Check schema file
    schema_path = 'infra/db/schema.sql'
    if os.path.exists(schema_path):
        with open(schema_path, 'r') as f:
            schema = f.read()
        
        # Check for biased columns
        biased_columns = ['lon', 'lat', 'geometry', 'geography', 'srid']
        found_bias = False
        for col in biased_columns:
            if col in schema.lower():
                print(f"[FAIL] Schema contains biased column: {col}")
                found_bias = True
        
        if not found_bias:
            print("[PASS] Schema has no biased columns")
    else:
        print("[WARN] Schema file not found")
    
    # Summary
    print("\n" + "="*60)
    print("AUDIT SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in RESULTS.values() if v.get('passed'))
    total = len(RESULTS)
    print(f"API Tests: {passed}/{total} passed")
    
    bias_pass = sum(1 for v in bias_results.values() if v == 0)
    bias_total = len(bias_results)
    print(f"Bias Checks: {bias_pass}/{bias_total} passed")
    
    overall = "✅ COMPLETE" if passed == total and bias_pass == bias_total else "⚠️ PARTIAL"
    print(f"\nOverall Status: {overall}")
    
    return passed == total and bias_pass == bias_total


if __name__ == '__main__':
    success = run_audit()
    sys.exit(0 if success else 1)
