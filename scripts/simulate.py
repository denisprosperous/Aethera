import urllib.request, json

BASE = 'http://127.0.0.1:8765/api'

def post(path, data):
    req = urllib.request.Request(
        f'{BASE}{path}',
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return json.loads(r.read())
    except Exception as e:
        return {'error': str(e)}

def get(path):
    try:
        r = urllib.request.urlopen(f'{BASE}{path}', timeout=10)
        return json.loads(r.read())
    except Exception as e:
        return {'error': str(e)}

print('='*60)
print('AETHERA PLATFORM SIMULATION')
print('='*60)

# 1. Ghost Resolver
print('\n[1/9] Ghost Resolver — Deriving unknown region areas...')
r = post('/ghost/resolve', {
    'polygons': [
        {'name': 'A', 'area': 100, 'neighbours': ['B', 'C']},
        {'name': 'B', 'area': 200, 'neighbours': ['A', 'C']},
        {'name': 'C', 'area': None, 'neighbours': ['A', 'B']},
    ],
    'global_enclosure': 'World',
    'global_area': 500
})
print(f'  Resolved areas: {r.get("resolved_areas", {})}')

# 2. Physical Truth Manifold
print('\n[2/9] Physical Truth — Reconstructing global manifold...')
r = get('/solve/physical-truth')
regions = r.get('regions', [])
print(f'  Regions solved: {len(regions)}')
if regions:
    print(f'  Sample: {regions[0]["name"]} at ({regions[0]["coords"][0]:.1f}, {regions[0]["coords"][1]:.1f})')

# 3. Projection Scores
print('\n[3/9] Distortion Observatory — Computing Colonial Distortion Scores...')
r = get('/projections/scores')
scores = r.get('scores', [])
print(f'  Projections analyzed: {len(scores)}')
for s in scores[:3]:
    print(f'  {s["projection"]}: score={s["colonial_score"]:.4f}')

# 4. Terraformation
print('\n[4/9] Terraformer — Simulating 10m sea-level rise...')
r = post('/terraformation', {'sea_level_rise_m': 10})
changes = r.get('coastline_changes', [])
print(f'  Regions affected: {len(changes)}')
for c in changes[:2]:
    print(f'  {c["nation"]}: {c["area_change_km2"]:.0f} km2')

# 5. Alien Reconstruct
print('\n[5/9] Alien Geometer — Reconstructing shape from edges...')
r = post('/alien/reconstruct', {
    'edges': [
        {'source': 'A', 'target': 'B', 'length': 1.0, 'source_type': 'topology'},
        {'source': 'B', 'target': 'C', 'length': 1.0, 'source_type': 'topology'},
        {'source': 'C', 'target': 'A', 'length': 1.0, 'source_type': 'topology'}
    ]
})
print(f'  Shape: {r.get("shape", "N/A")}, Residual: {r.get("residual", "N/A")}')

# 6. Dynamics
print('\n[6/9] Celestial Dynamics — Simulating particle trajectory...')
r = post('/dynamics/simulate', {
    'start': [0, 0, 0],
    'initial_velocity': [1, 0, 0],
    'force_law': 'uniform',
    'uniform_accel': [0, 0, -9.81],
    'dt': 0.1,
    't_max': 5.0
})
trajectory = r.get('trajectory', [])
print(f'  Trajectory points: {len(trajectory)}')
if trajectory:
    print(f'  Final pos: {trajectory[-1]}')

# 7. Datasets
print('\n[7/9] Data Inventory — Checking ingested regions...')
r = get('/datasets')
regions = r.get('regions', [])
done = [x for x in regions if x.get('status') == 'done']
print(f'  Total regions: {len(regions)}, Ingested: {len(done)}')

# 8. Anomaly
print('\n[8/9] Anomaly Detector — Checking for edge drifts...')
r = get('/anomaly/latest')
alerts = r.get('alerts', [])
print(f'  Active alerts: {len(alerts)}')

# 9. LLM Status
print('\n[9/9] LLM Status — Checking provider chain...')
r = get('/llm/status')
print(f'  Any available: {r.get("any_available", False)}')
print(f'  Primary: {r.get("primary", "N/A")}')

print('\n' + '='*60)
print('SIMULATION COMPLETE — All 9 modules executed')
print('='*60)
