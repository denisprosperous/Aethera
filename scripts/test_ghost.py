import sys
sys.path.insert(0, 'python')
from aethera.api import ghost_resolve, GhostResolveRequest

# Test the endpoint directly
req = GhostResolveRequest(
    polygons=[
        {'name': 'A', 'area': 100, 'neighbours': ['B', 'C']},
        {'name': 'B', 'area': 200, 'neighbours': ['A', 'C']},
        {'name': 'C', 'area': None, 'neighbours': ['A', 'B']},
    ],
    global_enclosure='World',
    global_area=500
)

import asyncio
result = asyncio.run(ghost_resolve(req))
print('Result:', result)
