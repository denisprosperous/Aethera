import sys
sys.path.insert(0, 'python')
from aethera.api import ghost_resolve
import inspect
src = inspect.getsource(ghost_resolve)
print(src[:2000])
