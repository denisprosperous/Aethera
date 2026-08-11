import sys
sys.path.insert(0, 'python')
with open('python/aethera/api.py', 'r') as f:
    content = f.read()

# Find the import section
import_start = content.find('from aethera.modules import (')
import_end = content.find(')', import_start) + 1
import_stmt = content[import_start:import_end]
print('Current import:')
print(import_stmt)
