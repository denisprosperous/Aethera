"""Natural Earth shapefile topology extractor (v10.2 — Tabula Rasa).

CRITICAL CORRECTION: This module extracts ONLY the adjacency topology
from Natural Earth shapefiles. It DISCARDS all lon/lat coordinates.
Edge lengths are stored as 1.0 placeholders (Mode B bootstrapping) —
the solver (Agent 2) infers true lengths from global area closure.

We use the shapefile geometry ONLY to determine:
1. Which vertices exist (as abstract point IDs).
2. Which vertices are connected by edges (adjacency).
3. The order of edges around each polygon (face).

No coordinates, no projections, no sphere, no ellipsoid.
"""

import os
import zipfile
import shapefile

DATA_DIR = os.environ.get(
    "AETHERA_DATA_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "natural_earth"),
)
DATA_DIR = os.path.abspath(DATA_DIR)

SHAPEFILE_URLS = {
    "countries": "https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip",
    "land": "https://naciscdn.org/naturalearth/110m/physical/ne_110m_land.zip",
    "ocean": "https://naciscdn.org/naturalearth/110m/physical/ne_110m_ocean.zip",
}

# 7 continents + 5 ocean basins + miscellaneous.
REGIONS = [
    "Africa", "Antarctica", "Asia", "Europe",
    "North America", "Oceania", "South America",
    "Pacific Ocean", "Atlantic Ocean", "Indian Ocean",
    "Southern Ocean", "Arctic Ocean",
    "Miscellaneous",
]

SOUTH_AMERICAN_COUNTRIES = {
    "Argentina", "Bolivia", "Brazil", "Chile", "Colombia", "Ecuador",
    "Falkland Islands", "French Guiana", "Guyana", "Paraguay", "Peru",
    "Suriname", "Uruguay", "Venezuela",
}

# Default placeholder edge length for Mode B (topology bootstrapping).
# The solver infers true lengths from global area closure.
PLACEHOLDER_LENGTH = 1.0


def download_shapefiles():
    """Download and extract all Natural Earth shapefiles if not present."""
    import requests
    os.makedirs(DATA_DIR, exist_ok=True)
    for name, url in SHAPEFILE_URLS.items():
        zip_path = os.path.join(DATA_DIR, f"ne_110m_{name}.zip")
        extract_dir = os.path.join(DATA_DIR, f"ne_110m_{name}")
        if os.path.exists(extract_dir) and os.listdir(extract_dir):
            continue
        print(f"Downloading {name}...")
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        with open(zip_path, "wb") as f:
            f.write(resp.content)
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(extract_dir)
        os.remove(zip_path)
    print(f"Shapefiles ready in {DATA_DIR}")


def _continent_from_record(rec, fields) -> str:
    """Map a Natural Earth country record to a continent name."""
    field_list = [f[0] for f in fields]
    continent_idx = field_list.index("CONTINENT")
    name_idx = field_list.index("NAME")
    continent = rec[continent_idx]
    name = rec[name_idx]
    if continent == "Americas":
        if name in SOUTH_AMERICAN_COUNTRIES:
            return "South America"
        return "North America"
    return continent


def get_region_topology(region: str) -> list:
    """Extract adjacency topology for a region.

    Returns a list of (name, face_type, adjacency_rings) where
    adjacency_rings is a list of rings, each ring being a list of
    point labels in order around the polygon. NO coordinates.

    Each point label is unique within a face (e.g., "Germany_v0",
    "Germany_v1", ...). The ingest pipeline will assign integer IDs.
    """
    download_shapefiles()
    results = []

    if "Ocean" in region:
        # Ocean basins — Natural Earth 1:110m ocean has limited polygons.
        # We label the whole ocean as the requested basin.
        ocean_shp = os.path.join(DATA_DIR, "ne_110m_ocean", "ne_110m_ocean.shp")
        if os.path.exists(ocean_shp):
            sf = shapefile.Reader(ocean_shp)
            for i, shape in enumerate(sf.shapes()):
                n_points = len(shape.points)
                if n_points < 3:
                    continue
                # Create adjacency ring as abstract point labels.
                # We DO NOT use the coordinates — only the count and order.
                ring = [f"{region}_p{j}" for j in range(n_points)]
                results.append((region, "ocean", [ring]))
        return results

    if region == "Miscellaneous":
        land_shp = os.path.join(DATA_DIR, "ne_110m_land", "ne_110m_land.shp")
        if os.path.exists(land_shp):
            sf = shapefile.Reader(land_shp)
            for i, shape in enumerate(sf.shapes()):
                n_points = len(shape.points)
                if n_points < 3:
                    continue
                ring = [f"Landmass_{i}_p{j}" for j in range(n_points)]
                results.append((f"Landmass_{i}", "land", [ring]))
        return results

    # Continents — from the countries shapefile.
    countries_shp = os.path.join(DATA_DIR, "ne_110m_countries", "ne_110m_admin_0_countries.shp")
    if not os.path.exists(countries_shp):
        return results

    sf = shapefile.Reader(countries_shp)
    fields = sf.fields
    for rec, shape in zip(sf.records(), sf.shapes()):
        continent = _continent_from_record(rec, fields)
        if continent != region:
            continue
        name_idx = [f[0] for f in fields].index("NAME")
        name = rec[name_idx]
        # Handle multipart geometries (countries with islands).
        parts = shape.parts
        points = shape.points
        n_points = len(points)
        if n_points < 3:
            continue
        rings = []
        if not parts:
            # Single ring.
            ring = [f"{name}_p{j}" for j in range(n_points)]
            rings.append(ring)
        else:
            for pi, part_start in enumerate(parts):
                part_end = parts[pi + 1] if pi + 1 < len(parts) else n_points
                ring_len = part_end - part_start
                if ring_len < 3:
                    continue
                suffix = "" if pi == 0 else f"_part{pi}"
                ring = [f"{name}{suffix}_p{j}" for j in range(ring_len)]
                rings.append(ring)
        if rings:
            results.append((name, "land", rings))

    return results
