# AETHERA Ingestion Pipeline (v10.2 — Tabula Rasa)

## Overview

The AETHERA ingestion pipeline populates a PostgreSQL database with
**raw edge lengths** between survey points — NO coordinates, NO lon/lat,
NO projections, NO sphere/ellipsoid assumptions.

## Two ingestion modes

### Mode A — User Survey (absolute distances)

The user provides a CSV of measured distances:

```csv
point_A, point_B, 1234.56
point_A, point_C, 5678.90
point_B, point_C, 9012.34
```

These are stored directly as `length_mode='measured'`. The solver
respects these absolute values.

### Mode B — Topology Bootstrapping (placeholder lengths)

We extract ONLY the adjacency topology from Natural Earth shapefiles
(which points are connected to which). All edge lengths are stored as
`1.0` placeholders. The solver (Agent 2) infers true lengths from
global area closure by minimising:

```
E = Σ_edges (l_e - l_true)² + λ (Σ_areas - Global_Total)²
```

This simultaneously finds the correct scale and curvature — entirely
from the topology and the global area invariant.

## Database schema

| Table | Columns | Purpose |
|-------|---------|---------|
| `points` | `id, label, region, source` | Point IDs (NO coordinates) |
| `edges` | `id, source_point_id, target_point_id, length_raw, length_mode, region, source` | Raw edge lengths |
| `faces` | `id, name, type, region, edge_ids[], point_ids[], properties` | Polygons (NO area column) |
| `region_status` | `region, status, edge_count, face_count, point_count, last_commit_hash` | Ingestion progress |
| `global_area_invariants` | `name, total_area_m2, source, notes` | User-supplied closure totals |

## Environment variables

```bash
export DATABASE_URL="postgresql://neondb_owner:***@ep-***.aws.neon.tech/neondb?sslmode=require"
export AETHERA_DATA_DIR="/path/to/natural_earth/shapefiles"  # optional
```

## Usage

```bash
# Ingest a single region (Mode B topology)
cd python
python -m aethera.ingest.pipeline --region Europe

# Ingest all regions
python -m aethera.ingest.pipeline --all

# Ingest Mode A user survey
python -m aethera.ingest.pipeline --survey /path/to/survey.csv

# Commit and push after each region
python -m aethera.ingest.pipeline --region Europe --push
```

## CRITICAL rule

**No pre-computed areas are ever imported.** The pipeline stores only:
1. Adjacency topology (which points connect to which).
2. Raw edge lengths (1.0 placeholders or user-supplied metres).
3. Global area totals (user-supplied scalars, used as closure constraints).

All areas are derived by Agent 0 (Ghost Resolver) and Agent 2
(Intrinsic Geometer) from these raw inputs.
