"""AETHERA ingestion package (v10.2 — Tabula Rasa, no coordinates).

Two ingestion modes:
- Mode A (user survey): absolute distances in metres. No coordinates.
- Mode B (topology bootstrapping): 1.0 placeholders. Solver infers lengths.

CRITICAL: No lon/lat, no x/y/z, no projections, no sphere, no ellipsoid.
"""

from .schema import create_schema, DATABASE_URL
from .db import Database
from .natural_earth import download_shapefiles, get_region_topology, REGIONS
from .geometry import placeholder_length, parse_survey_csv, validate_survey_distance
from .pipeline import ingest_region, ingest_all, ingest_survey_csv

__all__ = [
    "create_schema", "DATABASE_URL", "Database",
    "download_shapefiles", "get_region_topology", "REGIONS",
    "placeholder_length", "parse_survey_csv", "validate_survey_distance",
    "ingest_region", "ingest_all", "ingest_survey_csv",
]
