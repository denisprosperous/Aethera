import sys
sys.path.insert(0, 'python')

with open('python/aethera/api.py', 'r') as f:
    content = f.read()

# Fix the dynamics_simulate function
content = content.replace(
    'result = simulate_particle(\n        start=tuple(req.start),\n        initial_velocity=tuple(req.initial_velocity),\n        accel_fn=accel_fn,\n        config=config,\n    )',
    'result = simulate_particle(\n        start=tuple(req.start),\n        vel0=tuple(req.initial_velocity),\n        accel_fn=accel_fn,\n        config=config,\n    )'
)

with open('python/aethera/api.py', 'w') as f:
    f.write(content)

print('Fixed')
