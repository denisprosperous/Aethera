import sys
sys.path.insert(0, 'python')

from aethera.ingest.priority_regions import get_all_regions, get_priority_regions
from aethera.ingest.queue_manager import IngestionQueue
from aethera.ingest.terrarium import ingest_region
import asyncio
import json
from datetime import datetime

async def ingest_all_regions():
    """Ingest all remaining regions."""
    queue = IngestionQueue()
    
    # Get all regions
    regions = get_all_regions()
    print(f"Total regions to ingest: {len(regions)}")
    
    # Get already ingested
    completed = queue.get_stats().get('completed', 0)
    print(f"Already completed: {completed}")
    
    # Process priority 1 regions first
    priority_1 = get_priority_regions(1)
    print(f"\nProcessing {len(priority_1)} priority 1 regions...")
    
    for i, region in enumerate(priority_1):
        name = region['name']
        bbox = region['bbox']
        
        print(f"\n[{i+1}/{len(priority_1)}] Ingesting {name}...")
        
        try:
            result = await ingest_region(name, bbox)
            print(f"  ✓ Area: {result.area_computed:,.0f} m²")
            print(f"  ✓ Tiles: {result.tile_count}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
            continue
        
        # Commit to Git after every 5 regions
        if (i + 1) % 5 == 0:
            print(f"\n  Committing after {i+1} regions...")
            import subprocess
            subprocess.run(['git', 'add', '.'], cwd='..', capture_output=True)
            subprocess.run(['git', 'commit', '-m', f'Ingested {i+1} regions'], 
                          cwd='..', capture_output=True)
            subprocess.run(['git', 'push'], cwd='..', capture_output=True)
    
    # Show final stats
    stats = queue.get_stats()
    print(f"\n{'='*60}")
    print(f"INGESTION COMPLETE")
    print(f"{'='*60}")
    print(f"Pending: {stats.get('pending', 0)}")
    print(f"Completed: {stats.get('completed', 0)}")
    print(f"Failed: {stats.get('failed', 0)}")
    print(f"Total: {stats.get('total', 0)}")

if __name__ == "__main__":
    asyncio.run(ingest_all_regions())
