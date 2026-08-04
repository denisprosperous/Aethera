# AETHERA — Project Terra Incognita Ex Machina (TIEM)

**The first objective geometric substrate.** AETHERA reconstructs the
intrinsic geometry of a manifold from raw edge-length measurements
**without assuming any consensus prior** — no coordinates, no lon/lat,
no projections, no sphere, no ellipsoid, no planetary radius, no
gravitational constant, no ephemeris.

**v10.2 (current):** Tabula Rasa correction. The platform stores ONLY
adjacency topology and raw edge lengths (1.0 placeholders or user-
supplied metres). All areas are derived by the solvers from topology +
global area closure. No coordinates anywhere.

## What's in this repository

| Component | Status | Description |
|-----------|--------|-------------|
| `rust/` | ✅ 18 tests | Rust workspace: guard, core, ghost, geometer, acif, alien, dynamics, ffi |
| `python/aethera/` | ✅ 23 tests | Python orchestration: agents, modules, ingest, FastAPI backend |
| `python/aethera/ingest/` | ✅ | v10.2 ingestion pipeline (Mode A survey + Mode B topology) |
| `python/aethera/api.py` | ✅ | FastAPI backend with live endpoints |
| `web/` | ✅ | Next.js 16 frontend with 4 dashboard pages |
| `tests/` | ✅ 23 passing | Integration + ingest tests |

## Database (Neon PostgreSQL)

- **Project:** `raspy-cherry-57547334`
- **Schema:** v10.2 (no coordinates — Tabula Rasa)
- **Tables:** `points`, `edges`, `faces`, `region_status`, `global_area_invariants`
- **Data ingested:** 43,882 edges, 46,555 points, 502 faces across 12 regions
- **All edge lengths:** 1.0 placeholders (Mode B topology bootstrapping)

## Two ingestion modes

### Mode A — User Survey (absolute distances)
```csv
point_A, point_B, 1234.56
point_A, point_C, 5678.90
```
Stored directly as `length_mode='measured'`. Solver respects these.

### Mode B — Topology Bootstrapping (placeholder lengths)
Extract ONLY adjacency from Natural Earth. All lengths = 1.0. Solver
infers true lengths from global area closure:
```
E = Σ_edges (l_e - l_true)² + λ (Σ_areas - Global_Total)²
```

## Quick start

### Rust core
```bash
cd rust && cargo test --release --workspace --exclude aethera-ffi
```

### Python + API
```bash
cd python && pip install -r requirements.txt
export DATABASE_URL="postgresql://neondb_owner:***@ep-***.neon.tech/neondb?sslmode=require"
python -m aethera.ingest.pipeline --region Europe
uvicorn aethera.api:app --reload --port 8000
```

### Web frontend
```bash
cd web && npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

## API endpoints

- `GET /api/health` — health check
- `GET /api/datasets` — list ingested regions
- `GET /api/regions/{region}/edges` — raw edges for a region
- `POST /api/solve/manifold` — run SMACOF solver
- `POST /api/ghost/resolve` — resolve NULL areas (Agent 0)
- `POST /api/alien/reconstruct` — shape classification (Agent 8)
- `POST /api/dynamics/simulate` — user-force-field sim (Agent 7, no targeting)
- `POST /api/terraformation` — sea-level rise simulation
- `GET /api/anomaly/latest` — anomaly alerts
- `GET /api/projections/scores` — Colonial Distortion Scores

## Ethical safeguards

The platform is a **geometry provider**, not a weapons controller.
- `simulate_particle()` does NOT accept `target` parameter
- Does NOT return azimuth/elevation/impact_point
- Force field is always user-supplied; G is never hardcoded

## License

MIT.
