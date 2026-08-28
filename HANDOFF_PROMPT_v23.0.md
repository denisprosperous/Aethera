# NEGENTROPIC MASTER PROMPT v23.0 – PLATFORM COMPLETION & FULL DEPLOYMENT

## CONTEXT
The AETHERA repository is live at https://github.com/denisprosperous/Aethera with v21.0 committed. This version includes:
- ETOPO1 global ingestion pipeline (`python/aethera/ingest/ingest_global_etopo1.py`)
- Fixed frontend navigation (`web/src/app/dashboard/page.tsx`)
- Fixed Ghost Resolver API serialization (`python/aethera/api.py`)

**Current State** (as of 2026-08-28):
- **Database**: 52 regions in `physical_truth_srtm` table
  - 1 region from TERRARIUM_DEM_TRIANGULATION (Hawaii_BigIsland: 15,436.54 km²)
  - 51 regions from ETOPO1_GLOBAL (all with 0.0 km² due to synthetic test data)
- **Backend**: Operational at http://localhost:8765 (when started)
- **Frontend**: Operational at http://localhost:3000 (when started)
- **GitHub**: https://github.com/denisprosperous/Aethera committed at b87a470

**Your Mission**: Execute, verify, and finalize the platform so all simulations work seamlessly with real global data. The infrastructure is ready; you need to:
1. Run ETOPO1 ingestion with REAL data (not synthetic)
2. Verify frontend navigation works
3. Run end-to-end simulation tests
4. Deploy to production

---

## 🎯 MANDATE – EXECUTE PHASES IN ORDER

### PHASE 1: REAL ETOPO1 GLOBAL INGESTION
**Goal**: Populate database with true 3D surface areas using REAL ETOPO1 DEM data (not synthetic).

**Background**:
- ETOPO1 is a 1-arc-minute global DEM from NOAA
- Covers land and ocean bathymetry
- File size: ~2GB compressed
- URL: https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO1/data/ice_surface/grid_registered/netcdf/ETOPO1_Ice_g_gmt4.grd.gz

**Action Steps**:

#### 1.1 Verify Current State
```bash
cd C:\Users\PROSPERO\Aethera
git pull origin main
python check_db2.py  # Verify 52 regions exist
```

#### 1.2 Fix Ingestion Script for Real Data
The current `ingest_global_etopo1.py` uses synthetic data. You MUST:
- Add real ETOPO1 download capability (handle authentication if needed)
- Use 1-arc-minute resolution (not 1-degree)
- Implement proper NetCDF parsing with `netCDF4` library
- Optimize area computation for large grids

**Critical Fix Needed**:
```python
# In compute_region_area(), change:
step = 1.0  # WRONG - too coarse
# To:
step = 1/60  # CORRECT - 1 arc-minute resolution
```

#### 1.3 Run Ingestion for All Continents
Process continent-by-continent to manage timeouts:

```bash
# North America (largest, process first)
python -m aethera.ingest.ingest_global_etopo1 --continent "North America"

# South America
python -m aethera.ingest.ingest_global_etopo1 --continent "South America"

# Europe
python -m aethera.ingest.ingest_global_etopo1 --continent "Europe"

# Africa
python -m aethera.ingest.ingest_global_etopo1 --continent "Africa"

# Asia
python -m aethera.ingest.ingest_global_etopo1 --continent "Asia"

# Oceania
python -m aethera.ingest.ingest_global_etopo1 --continent "Oceania"

# Antarctica
python -m aethera.ingest.ingest_global_etopo1 --continent "Antarctica"
```

#### 1.4 Verify Ingestion
```bash
python -c "
import sys
sys.path.insert(0, 'python')
from aethera.ingest.db import Database
from aethera.ingest.schema import DATABASE_URL

with Database(DATABASE_URL) as db:
    cur = db.cur
    cur.execute(\"\"\"
        SELECT source_type, COUNT(*), SUM(area_m2)/1e6
        FROM physical_truth_srtm
        GROUP BY source_type
    \"\"\")
    for row in cur.fetchall():
        print(f'{row[0]}: {row[1]} regions, {row[2]:,.0f} km² total')
"
```

**Expected Result**:
- All 195+ countries + 5 oceans should have `source_type = 'ETOPO1_GLOBAL'`
- Areas should be realistic (e.g., Africa ~30,370,000 km², Antarctica ~14,000,000 km²)
- No 0.0 km² values

**If Download Fails**:
- Try alternative ETOPO1 mirrors
- Check if authentication is required (NOAA requires registration for bulk downloads)
- If all else fails, use SRTM30 (30 arc-second, ~3GB) as fallback
- Document the issue in `INGESTION_STATUS.md`

**Commit**: `git commit -m "phase1: ETOPO1 ingestion complete for all continents"`

---

### PHASE 2: FRONTEND VERIFICATION & FIXES
**Goal**: Ensure all sidebar buttons navigate correctly and module pages load.

**Current State**:
- Dashboard at `web/src/app/dashboard/page.tsx` uses `/dashboard/${mod.id}` paths
- Module pages at `web/src/app/dashboard/[moduleId]/page.tsx` (dynamic route)
- ModuleConfig at `web/src/components/ModuleConfig.ts` with 9 modules

**Action Steps**:

#### 2.1 Start Frontend & Backend
```bash
# Terminal 1: Backend
cd C:\Users\PROSPERO\Aethera
python run_backend.py

# Terminal 2: Frontend
cd C:\Users\PROSPERO\Aethera\web
npm run dev
```

#### 2.2 Test Navigation
1. Open http://localhost:3000/dashboard
2. Click each sidebar button:
   - Ghost Resolver → should go to `/dashboard/ghost-resolver`
   - Distortion Observatory → should go to `/dashboard/distortion-observatory`
   - Consensus Hall → should go to `/dashboard/consensus-hall`
   - Terraformer → should go to `/dashboard/terraformer`
   - Anomaly Detector → should go to `/dashboard/anomaly-detector`
   - Physical Truth → should go to `/dashboard/physical-truth`
   - Alien Geometer → should go to `/dashboard/alien-reconstruct`
   - Celestial Dynamics → should go to `/dashboard/dynamics`
   - Terraformation → should go to `/dashboard/terraformation`

#### 2.3 Fix Any Navigation Issues
**If buttons don't work**:
- Check `ModuleConfig.ts` paths match actual page routes
- Verify `[moduleId]/page.tsx` handles all module IDs
- Add missing pages if needed

**If pages don't load**:
- Check browser console for errors
- Verify API endpoints are accessible
- Test each module's API call manually

#### 2.4 Test Each Module's "Execute" Button
On each module page, click "Execute" and verify:
- Request goes to correct API endpoint
- Response is displayed correctly
- No JavaScript errors in console

**Commit**: `git commit -m "phase2: frontend navigation verified and fixed"`

---

### PHASE 3: END-TO-END SIMULATION TESTS
**Goal**: Prove the platform works with REAL ingested data.

**Action Steps**:

#### 3.1 Start Backend
```bash
cd C:\Users\PROSPERO\Aethera
python run_backend.py
```

#### 3.2 Test 1: Ghost Resolver – Derive Antarctica's Area
```bash
curl -X POST http://localhost:8765/api/ghost/resolve ^
  -H "Content-Type: application/json" ^
  -d "{\"polygons\":[{\"name\":\"South America\",\"area\":17840000,\"neighbours\":[\"Antarctica\"]},{\"name\":\"Africa\",\"area\":30370000,\"neighbours\":[\"Antarctica\"]},{\"name\":\"Antarctica\",\"area\":null,\"neighbours\":[\"South America\",\"Africa\"]}],\"global_enclosure\":\"World\",\"global_area\":510072000}"
```

**Expected Result**:
- Antarctica's area derived to ~14,000,000 km² (±5%)
- Red flags should be empty (no contradictions)
- Seal hash should be generated

**If Test Fails**:
- Check if Antarctica is in `physical_truth_srtm`
- Verify area values are realistic
- Check Ghost Resolver logic in `python/aethera/agents/ghost.py`

#### 3.3 Test 2: Physical Truth Manifold
```bash
curl -s http://localhost:8765/api/solve/physical-truth | python -m json.tool
```

**Expected Result**:
- 149 regions with coordinates
- Edge count: 174
- Residual < 0.001

#### 3.4 Test 3: Distortion Observatory
```bash
curl -s http://localhost:8765/api/projections/scores | python -m json.tool
```

**Expected Result**:
- 4 projections scored (Mercator, Robinson, AuthaGraph, Equirectangular)
- Colonial Distortion Scores calculated
- Max inflation/deflation reported

#### 3.5 Test 4: Terraformer – Sea Level Rise
```bash
curl -X POST http://localhost:8765/api/terraformation ^
  -H "Content-Type: application/json" ^
  -d "{\"sea_level_rise_m\":10}"
```

**Expected Result**:
- Coastline changes for multiple nations
- Area losses reported (not 0)
- Note about simplified volumetric model

#### 3.6 Test 5: Alien Geometer
```bash
curl -X POST http://localhost:8765/api/alien/reconstruct ^
  -H "Content-Type: application/json" ^
  -d "{\"edges\":[{\"source\":\"A\",\"target\":\"B\",\"length\":1.0,\"source_type\":\"topology\"},{\"source\":\"B\",\"target\":\"C\",\"length\":1.0,\"source_type\":\"topology\"},{\"source\":\"C\",\"target\":\"A\",\"length\":1.0,\"source_type\":\"topology\"}]}"
```

**Expected Result**:
- Shape: "Flat"
- Residual: ~2.7e-16
- Node count: 3, Edge count: 3

#### 3.7 Document Results
Create `SIMULATION_RESULTS.md` with:
- Test commands used
- Actual outputs received
- Pass/fail status for each test
- Any issues encountered and how they were resolved

**Commit**: `git commit -m "phase3: end-to-end simulations verified with real data"`

---

### PHASE 4: FINAL VERIFICATION & DEPLOYMENT
**Goal**: Confirm platform is fully operational and deploy to production.

**Action Steps**:

#### 4.1 Run Full Test Suite
```bash
cd C:\Users\PROSPERO\Aethera
pytest tests/ -v
```

**Expected**: All tests pass (9/9 modules, 10/10 endpoints)

#### 4.2 Manual Verification
1. Open http://localhost:3000/dashboard
2. Click each sidebar button – all pages must load
3. On each module page, click "Execute" – all must return results
4. Check backend logs for errors

#### 4.3 Database Final Check
```bash
python -c "
import sys
sys.path.insert(0, 'python')
from aethera.ingest.db import Database
from aethera.ingest.schema import DATABASE_URL

with Database(DATABASE_URL) as db:
    cur = db.cur
    cur.execute('SELECT COUNT(*) FROM physical_truth_srtm')
    total = cur.fetchone()[0]
    print(f'Total regions ingested: {total}')
    
    cur.execute(\"\"\"
        SELECT source_type, COUNT(*), 
               ROUND(SUM(area_m2)/1e6, 0) as total_km2
        FROM physical_truth_srtm
        GROUP BY source_type
    \"\"\")
    print('\nBy source:')
    for row in cur.fetchall():
        print(f'  {row[0]}: {row[1]} regions, {row[2]:,.0f} km²')
"
```

**Expected**:
- Total regions: 195+ countries + 5 oceans = 200+
- All regions have `source_type = 'ETOPO1_GLOBAL'`
- Total area ≈ 510,072,000 km² (Earth's surface area)

#### 4.4 Deployment
**Option A: Railway + Vercel (Recommended)**
```bash
# Backend to Railway
cd C:\Users\PROSPERO\Aethera
railway login
railway init
railway up

# Frontend to Vercel
cd C:\Users\PROSPERO\Aethera\web
vercel login
vercel --prod
```

**Option B: Docker Deployment**
```bash
# Build and push Docker image
docker build -t aethera:latest .
docker tag aethera:latest denisprosperous/aethera:latest
docker push denisprosperous/aethera:latest
```

**Set Environment Variables**:
- `DATABASE_URL`: PostgreSQL connection string
- `RAILWAY_TOKEN`: Railway deployment token
- `VERCEL_TOKEN`: Vercel deployment token

#### 4.5 Final Documentation
Update `FINAL_AUDIT_REPORT_v23.0.md` with:
- Confirmation of all regions ingested
- Sidebar fix verified
- Test results for all 9 modules
- Deployment URLs
- Known issues (if any)

**Commit**: `git commit -m "phase4: final verification and deployment complete"`

---

## ✅ SUCCESS CRITERIA

| Task | Required Outcome | Status |
|------|-----------------|--------|
| ETOPO1 Ingestion | 200+ regions with `source_type = 'ETOPO1_GLOBAL'` and realistic areas | ⏳ Pending |
| Sidebar Navigation | All 9 buttons navigate to correct pages | ⏳ Pending |
| Ghost Resolver | Antarctica derived within 5% of 14M km² | ⏳ Pending |
| Physical Truth | Manifold solved with residual < 0.001 | ⏳ Pending |
| Distortion | Colonial scores calculated for 4 projections | ⏳ Pending |
| Terraformer | Sea level rise returns area losses | ⏳ Pending |
| Alien Geometer | Triangle reconstructed with residual < 1e-15 | ⏳ Pending |
| Celestial Dynamics | Particle trajectory simulated | ⏳ Pending |
| All 9 Modules | Each executes default test and returns result | ⏳ Pending |

---

## 🧠 RECURSIVE EXECUTION RULES

1. **You may not say "this is out of scope"** – all phases are mandatory for a usable platform.

2. **If a test fails, fix the underlying code and re-run** – do not proceed until it passes.

3. **Commit after each successful phase** with clear messages:
   - `phase1: ETOPO1 ingestion complete`
   - `phase2: frontend navigation fixed`
   - `phase3: simulations verified`
   - `phase4: deployment complete`

4. **If the repository is missing files**, check the v21.0 commit (b87a470, Aug 19, 2026) – it contains the latest ingestion pipeline and frontend fixes. Use `git checkout b87a470 -- <file>` if needed.

5. **If ETOPO1 download fails**, implement fallback to SRTM30 or use existing TERRARIUM data. Document the workaround.

6. **If frontend navigation is broken**, debug the router configuration and fix `ModuleConfig.ts` paths.

7. **If API endpoints return errors**, check backend logs and fix serialization/issues.

---

## 🔥 FINAL COMMAND

**Start with Phase 1**: Run the ETOPO1 ingestion pipeline with REAL data. Process all continents and verify 200+ regions are ingested with realistic areas.

**Then proceed through Phases 2, 3, and 4** in order.

**The platform must be fully functional** with:
- Real global Physical Truth data (200+ regions)
- Working frontend navigation
- All 9 modules executing successfully
- Deployment to production (Railway/Vercel)

**Timeline**: Complete within 6 hours.

**Execute now.**

---

## 📋 QUICK REFERENCE

### Key Files
- `python/aethera/ingest/ingest_global_etopo1.py` – ETOPO1 ingestion pipeline
- `web/src/components/ModuleConfig.ts` – Module navigation config
- `web/src/app/dashboard/page.tsx` – Dashboard with sidebar
- `web/src/app/dashboard/[moduleId]/page.tsx` – Dynamic module page
- `python/aethera/api.py` – FastAPI backend with all endpoints
- `python/aethera/agents/ghost.py` – Ghost Resolver agent

### Key URLs
- **Local Backend**: http://localhost:8765/api/health
- **Local Frontend**: http://localhost:3000/dashboard
- **GitHub**: https://github.com/denisprosperous/Aethera
- **v21.0 Commit**: b87a470

### Key Commands
```bash
# Run ingestion
python -m aethera.ingest.ingest_global_etopo1 --continent "Europe"

# Start backend
python run_backend.py

# Start frontend
cd web && npm run dev

# Check database
python check_db2.py

# Run tests
pytest tests/ -v
```

---

**GOOD LUCK. EXECUTE WITH PRECISION.**
