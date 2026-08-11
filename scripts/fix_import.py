import sys
sys.path.insert(0, 'python')

with open('python/aethera/api.py', 'r') as f:
    content = f.read()

# Check if import already exists
if 'from aethera.modules.terraformation import VolumeTransfer' not in content:
    # Add import after the modules import block
    content = content.replace(
        'from aethera.modules import (\n    HallOfShame, TransparencyComparator, StrainVisualizer,\n    AnomalyDaemon, MaritimeChokepoint, TerraformationSimulator, StellarPositioning,\n)',
        'from aethera.modules import (\n    HallOfShame, TransparencyComparator, StrainVisualizer,\n    AnomalyDaemon, MaritimeChokepoint, TerraformationSimulator, StellarPositioning,\n)\nfrom aethera.modules.terraformation import VolumeTransfer'
    )
    with open('python/aethera/api.py', 'w') as f:
        f.write(content)
    print('Import added successfully')
else:
    print('Import already exists')
