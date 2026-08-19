import sys
sys.path.insert(0, 'C:/Users/PROSPERO/Aethera/python')
from aethera.ingest.db import Database
from aethera.ingest.schema import DATABASE_URL

# Connect and check tables
with Database(DATABASE_URL) as db:
    cur = db.cur
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")
    tables = cur.fetchall()
    print("Existing tables:")
    for t in tables:
        print(f"  - {t[0]}")
    
    # Check if physical_truth_srtm exists
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'physical_truth_srtm';")
    cols = cur.fetchall()
    if cols:
        print("\nphysical_truth_srtm columns:")
        for c in cols:
            print(f"  - {c[0]}")
    else:
        print("\nphysical_truth_srtm table does not exist")
