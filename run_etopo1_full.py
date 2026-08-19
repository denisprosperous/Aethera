import sys
sys.path.insert(0, 'C:/Users/PROSPERO/Aethera/python')
from aethera.ingest.ingest_global_etopo1 import ETOPO1Ingestor, DATABASE_URL
from aethera.ingest.db import Database
import json

print("=" * 60)
print("AETHERA ETOPO1 Global Ingestion Pipeline v21.0")
print("=" * 60)

with Database(DATABASE_URL) as db:
    ingestor = ETOPO1Ingestor(db, 'data')
    
    # Create synthetic data
    print("\n1. Creating synthetic ETOPO1 data...")
    ingestor._create_synthetic_etopo1('data/test.nc')
    
    # Load it
    print("\n2. Loading ETOPO1 data...")
    ingestor.load_etopo1('data/test.npz')
    
    # Process all continents
    print("\n3. Processing all continents...")
    results = ingestor.process_all()
    
    print("\n4. Results:")
    for continent, result in results.items():
        if 'error' in result:
            print(f"  {continent}: FAILED - {result['error']}")
        else:
            print(f"  {continent}: {result['regions_processed']} regions, "
                  f"{result['total_area_km2']:,.0f} km² total")
    
    # Cleanup
    print("\n5. Cleaning up...")
    ingestor.cleanup()

print("\n" + "=" * 60)
print("ETOPO1 ingestion complete!")
print("=" * 60)
