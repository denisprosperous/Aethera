"""
AETHERA Deep Platform Audit
"""
import os
import sys
import importlib
from pathlib import Path

def audit():
    print("=" * 70)
    print("AETHERA PLATFORM DEEP AUDIT")
    print("=" * 70)
    
    # 1. Check project structure
    print("\n[1/5] Project Structure...")
    root = Path(__file__).parent.parent
    print(f"Root: {root}")
    
    dirs = ['python', 'backend', 'frontend', 'web', 'rust']
    for d in dirs:
        p = root / d
        exists = p.exists()
        status = "[OK]" if exists else "[MISSING]"
        print(f"  {status} {d}/")
    
    # 2. Check Python package
    print("\n[2/5] Python Package (aethera)...")
    sys.path.insert(0, str(root / 'python'))
    try:
        import aethera
        print(f"  [OK] aethera imported successfully")
        print(f"    Version: {getattr(aethera, '__version__', 'N/A')}")
    except ImportError as e:
        print(f"  [FAIL] Import failed: {e}")
        return
    
    # 3. Check modules
    print("\n[3/5] Core Modules...")
    modules = [
        'aethera.core',
        'aethera.ingest',
        'aethera.agents',
        'aethera.modules',
        'aethera.llm',
        'aethera.rust_bridge',
    ]
    for mod in modules:
        try:
            importlib.import_module(mod)
            print(f"  [OK] {mod}")
        except ImportError as e:
            print(f"  [FAIL] {mod}: {e}")
    
    # 4. Check API endpoints
    print("\n[4/5] API Endpoints...")
    api_file = root / 'python' / 'aethera' / 'api.py'
    if api_file.exists():
        content = api_file.read_text()
        endpoints = [line.strip().split('(')[0].replace('@app.', '') for line in content.split('\n') if '@app.' in line and 'async def' in line]
        print(f"  Found {len(endpoints)} endpoint(s):")
        for ep in endpoints:
            print(f"    - {ep}")
    else:
        print("  [FAIL] api.py not found")
    
    # 5. Check database schema
    print("\n[5/5] Database Schema...")
    schema_file = root / 'python' / 'aethera' / 'ingest' / 'schema.py'
    if schema_file.exists():
        print(f"  [OK] Schema defined in: {schema_file}")
        content = schema_file.read_text()
        key_tables = ['points', 'edges', 'faces', 'region_status', 'global_area_invariants']
        for table in key_tables:
            if f'CREATE TABLE {table}' in content:
                print(f"  [OK] {table}")
            else:
                print(f"  [FAIL] {table}")
    else:
        print(f"  [FAIL] Schema file not found")
    
    # 6. Check Rust engine
    print("\n[6/5] Rust Engine...")
    rust_dir = root / 'rust'
    if rust_dir.exists():
        cargo_toml = rust_dir / 'Cargo.toml'
        if cargo_toml.exists():
            print(f"  [OK] Rust workspace found")
            # Check for module crates
            crates = ['aethera-core', 'aethera-ghost', 'aethera-geometer', 'aethera-dynamics', 'aethera-ffi']
            for crate in crates:
                crate_dir = rust_dir / crate
                if crate_dir.exists():
                    print(f"  [OK] {crate}/")
                else:
                    print(f"  [FAIL] {crate}/")
        else:
            print(f"  [FAIL] Cargo.toml not found")
    else:
        print(f"  [FAIL] Rust directory not found")
    
    # 7. Check web frontend
    print("\n[7/7] Web Frontend...")
    web_dir = root / 'web'
    if web_dir.exists():
        package_json = web_dir / 'package.json'
        if package_json.exists():
            print(f"  [OK] Web frontend found")
            # Check for node_modules
            node_modules = web_dir / 'node_modules'
            if node_modules.exists():
                print(f"  [OK] Dependencies installed")
            else:
                print(f"  [WARN] Dependencies not installed - run: cd web && npm install")
        else:
            print(f"  [FAIL] package.json not found")
    else:
        print(f"  [FAIL] Web directory not found")
    
    # Summary
    print("\n" + "=" * 70)
    print("AUDIT COMPLETE")
    print("=" * 70)
    
    # Check backend API
    print("\n[BACKEND API STATUS]")
    backend_dir = root / 'backend'
    if backend_dir.exists():
        print(f"  Backend directory exists: {backend_dir}")
        app_dir = backend_dir / 'app'
        if app_dir.exists():
            print(f"  App directory exists: {app_dir}")
            # Check for main.py
            main_py = app_dir / 'main.py'
            if main_py.exists():
                print(f"  [OK] main.py found")
            else:
                print(f"  [INFO] Using Python package API (python/aethera/api.py)")
        else:
            print(f"  [FAIL] app/ directory not found")
    else:
        print(f"  [FAIL] Backend directory not found")
    
    print("\n" + "=" * 70)
    print("RECOMMENDED ACTIONS")
    print("=" * 70)
    print("""
1. Start backend API:
   cd python && python -m aethera.cli.main serve --port 8765

2. Start web frontend:
   cd web && npm run dev

3. Run ingestion:
   python -m aethera.cli.main ingest --regions hawaii,luxembourg

4. Deploy to Railway:
   - Create Railway project
   - Set DATABASE_URL from Neon
   - Connect GitHub repo
   - Auto-deploys on push
""")

if __name__ == "__main__":
    audit()
