import sys
sys.path.insert(0, 'python')
from aethera.api import dynamics_simulate
import inspect
src = inspect.getsource(dynamics_simulate)
src = src.encode('ascii', 'replace').decode('ascii')
print(src[:1500])
