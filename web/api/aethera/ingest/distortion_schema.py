"""Distortion analysis schema — stores per-region comparison metrics between
physical truth (true geographic area) and legacy cartographic projections.

The distortion_metrics table quantifies how much each scholarly projection
deviates from the physical baseline for each region.

Physical truth = the actual surface area of the region (a physical fact).
Legacy = the area as distorted by a map projection (Mercator, Robinson, etc.).
"""

import os
import psycopg2

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_i7I6oGlzgpmu@ep-small-fire-awt6hp2b.c-12.us-east-1.aws.neon.tech/neondb?sslmode=require",
)

DISTORTION_SCHEMA_SQL = """
-- Distortion metrics: per-region comparison between physical truth and
-- legacy projection areas.
CREATE TABLE IF NOT EXISTS distortion_metrics (
    id SERIAL PRIMARY KEY,
    region_name TEXT NOT NULL,
    projection TEXT NOT NULL,  -- 'Mercator', 'Robinson', 'AuthaGraph', 'Equirectangular', 'Winkel_Tripel'
    area_physical_m2 DOUBLE PRECISION NOT NULL,  -- true geographic area
    area_legacy_m2 DOUBLE PRECISION NOT NULL,    -- projection-distorted area
    absolute_error_m2 DOUBLE PRECISION NOT NULL,
    relative_error_percent DOUBLE PRECISION NOT NULL,
    distortion_category TEXT NOT NULL,  -- 'overreported', 'underreported', 'within_tolerance'
    source_physical TEXT DEFAULT 'geographic_survey',
    source_legacy TEXT DEFAULT 'projection_computed',
    computed_timestamp TIMESTAMP DEFAULT NOW(),
    UNIQUE (region_name, projection)
);

-- Global distortion index: the headline metric.
CREATE TABLE IF NOT EXISTS global_distortion_index (
    projection TEXT PRIMARY KEY,
    global_distortion_percent DOUBLE PRECISION NOT NULL,
    total_physical_area_m2 DOUBLE PRECISION NOT NULL,
    total_legacy_area_m2 DOUBLE PRECISION NOT NULL,
    region_count INTEGER NOT NULL,
    computed_timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_distortion_region ON distortion_metrics(region_name);
CREATE INDEX IF NOT EXISTS idx_distortion_projection ON distortion_metrics(projection);
CREATE INDEX IF NOT EXISTS idx_distortion_category ON distortion_metrics(distortion_category);
"""


def create_distortion_schema():
    """Create the distortion_metrics and global_distortion_index tables."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(DISTORTION_SCHEMA_SQL)
    cur.close()
    conn.close()
    print("Distortion schema created (distortion_metrics + global_distortion_index).")


if __name__ == "__main__":
    create_distortion_schema()
