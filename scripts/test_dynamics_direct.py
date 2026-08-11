import sys
sys.path.insert(0, 'python')
from aethera.api import dynamics_simulate
from aethera.api import DynamicsSimulateRequest
import asyncio

# Test directly
req = DynamicsSimulateRequest(
    start=[0, 0, 0],
    initial_velocity=[1, 0, 0],
    force_law='uniform',
    mu=1.0,
    uniform_accel=[0, 0, -9.81],
    dt=0.1,
    t_max=5.0
)
result = asyncio.run(dynamics_simulate(req))
print('Result:', result)
