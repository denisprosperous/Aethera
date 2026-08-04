"""AETHERA database schema (v10.2 — Tabula Rasa correction).

CRITICAL CORRECTION: This schema stores NO coordinates (no x/y/z, no
lon/lat). Only:
- Point IDs (with optional human-readable labels).
- Raw scalar edge lengths between connected points.
  - Mode A (user survey): absolute distance in metres.
  - Mode B (topology bootstrapping): placeholder 1.0 — the solver infers
    true lengths from global area closure.
- Faces (polygons) as ordered lists of edge IDs.

The solver (Agent 2) reads the adjacency graph + edge lengths and
reconstructs the intrinsic manifold. If all lengths are 1.0, it treats
them as unknown variables and solves for their true values by minimising:
    E = Σ_edges (l_e - l_true)² + λ (Σ_areas - Global_Total)²

This is true Tabula Rasa — no coordinates, no projections, no sphere,
no ellipsoid.
"""

import os
import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_i7I6oGlzgpmu@ep-small-fire-awt6hp2b.c-12.us-east-1.aws.neon.tech/neondb?sslmode=require",
)

SCHEMA_SQL = """
-- Points: identified by ID only. No coordinates stored.
-- Optional label for human readability (e.g. "Berlin", "vertex_42").
-- The solver reconstructs positions purely from edge lengths.
CREATE TABLE IF NOT EXISTS points (
    id SERIAL PRIMARY KEY,
    label TEXT,
    region TEXT,
    source TEXT DEFAULT 'topology',  -- 'topology' (Mode B) or 'survey' (Mode A)
    created_at TIMESTAMP DEFAULT NOW()
);
-- Unique constraint on (label, region) for deduplication.
CREATE UNIQUE INDEX IF NOT EXISTS idx_points_label_region ON points(label, region) WHERE label IS NOT NULL;

-- Edges: raw scalar lengths between connected points.
-- length_raw is either:
--   - Mode A (user survey): absolute distance in metres.
--   - Mode B (topology bootstrapping): placeholder 1.0 — solver infers
--     true lengths from global area closure.
-- NO coordinates stored. NO lon/lat. NO x/y/z.
CREATE TABLE IF NOT EXISTS edges (
    id SERIAL PRIMARY KEY,
    source_point_id INTEGER NOT NULL REFERENCES points(id),
    target_point_id INTEGER NOT NULL REFERENCES points(id),
    length_raw DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    length_mode TEXT NOT NULL DEFAULT 'placeholder',  -- 'placeholder' or 'measured'
    region TEXT,
    source TEXT DEFAULT 'topology',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (source_point_id, target_point_id)
);

-- Faces: polygons (countries, islands, ocean basins).
-- Ordered list of edge IDs forming the polygon boundary.
-- NO area column — areas are derived by Agent 0/Agent 2.
CREATE TABLE IF NOT EXISTS faces (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,  -- 'land' or 'ocean'
    region TEXT NOT NULL,
    edge_ids INTEGER[] NOT NULL DEFAULT '{}',
    point_ids INTEGER[] NOT NULL DEFAULT '{}',
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Region status: ingestion progress tracking with Git commit hash.
CREATE TABLE IF NOT EXISTS region_status (
    region TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'processing', 'done'
    edge_count INTEGER DEFAULT 0,
    face_count INTEGER DEFAULT 0,
    point_count INTEGER DEFAULT 0,
    last_commit_hash TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Global area invariants: user-supplied scalar totals per region/group.
-- The solver uses these as closure constraints. NO pre-computed areas
-- from shapefile attributes — only user-supplied scalars.
CREATE TABLE IF NOT EXISTS global_area_invariants (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,  -- e.g. 'earth_total', 'africa_total'
    total_area_m2 DOUBLE PRECISION NOT NULL,
    source TEXT DEFAULT 'user-supplied',
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_point_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_point_id);
CREATE INDEX IF NOT EXISTS idx_edges_region ON edges(region);
CREATE INDEX IF NOT EXISTS idx_faces_region ON faces(region);
CREATE INDEX IF NOT EXISTS idx_points_region ON points(region);
"""


def create_schema():
    """Create all tables if they don't exist. Does NOT drop existing data."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    # Use CREATE TABLE IF NOT EXISTS — preserve existing data.
    # Only drop legacy vertices table if it exists (from v10.0 schema).
    cur.execute("DROP TABLE IF EXISTS vertices CASCADE;")
    cur.execute(SCHEMA_SQL)
    cur.close()
    conn.close()
    print("Schema ready (v10.2 — no coordinates, Tabula Rasa). Existing data preserved.")


if __name__ == "__main__":
    create_schema()
