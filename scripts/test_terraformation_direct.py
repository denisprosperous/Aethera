import sys
sys.path.insert(0, 'python')
from aethera.api import terraformation
from aethera.api import TerraformationRequest
import asyncio

# Test directly
req = TerraformationRequest(sea_level_rise_m=10)
result = asyncio.run(terraformation(req))
print('Result:', result)
