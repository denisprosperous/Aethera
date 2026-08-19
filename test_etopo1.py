import sys
sys.path.insert(0, 'C:/Users/PROSPERO/Aethera/python')
from aethera.ingest.ingest_global_etopo1 import ETOPO1Ingestor, DATABASE_URL
from aethera.ingest.db import Database
import json

with Database(DATABASE_URL) as db:
    ingestor = ETOPO1Ingestor(db, 'data')
    
    # Create synthetic data
    print('Creating synthetic ETOPO1 data...')
    ingestor._create_synthetic_etopo1('data/test.nc')
    
    # Load it
    print('Loading ETOPO1 data...')
    ingestor.load_etopo1('data/test.npz')
    
    # Process a single region first
    print('Testing with France...')
    result = ingestor.compute_region_area('France', 42.0, 51.0, -5.0, 8.0)
    print(f'Result: {result}')
    
    # Store it
    print('Storing result...')
    ingestor.store_physical_truth('France', result, 'Europe')
    
    print('Done!')
