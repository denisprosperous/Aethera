"""ETOPO1 elevation ingestion as per-vertex physical scalars (v37.1).

The 3D viewer supports elevation-on-click: click any point on the
intrinsic manifold and read the height above sea level at that location.
Elevation is a PHYSICAL SCALAR of a vertex (like edge length or area) —
it is not a coordinate. Nothing lat/lon/WGS84/EPSG is stored anywhere:
the DEM's grid coordinates are used transiently at ingestion time to
SAMPLE the scalar, then discarded (Axiom 3 - Extrinsic Agnosticism,
Axiom 4 - Zero Bias).

Pipeline (offline, deterministic):
  1. Re-run the v36.0 vertex snapping phase verbatim (same shapefile,
     same snap grid, same iteration order) so vertex IDs match the
     bundle's ring `ids` exactly. Coordinates stay in memory only.
  2. Sample ETOPO1 (1 arc-minute, ice surface) at each snapped vertex.
  3. Join bundle ring ids with the intrinsic solution rings (the
     reconstruction preserves ring vertex order 1:1) and emit:
       - python/aethera/data/boundaries_elevation_v37.json
         {meta, samples: [[x, y, elev_m], ...]}  (intrinsic x/y + scalar)
  4. Commit the scalar to Neon:
       - boundary_vertex_elevation (vid, elevation_m)
       - boundary_solution.elevation_m (per rendered solution vertex)

Usage:
    python -m aethera.ingest.ingest_elevation --all --commit
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

DATA_DIR = os.environ.get(
    "AETHERA_DATA_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "natural_earth")),
)
BUNDLE_PATH = os.environ.get(
    "AETHERA_BOUNDARY_BUNDLE",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "boundaries", "boundaries_v36.json")),
)
SOLUTION_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "data", "boundaries_solution_v36.json"))
OUT_ARTIFACT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "data", "boundaries_elevation_v37.json"))
ETOPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "dem"))

ETOPO_URL = ("https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO1/data/"
             "ice_surface/grid_registered/netcdf/ETOPO1_Ice_g_gmt4.grd.gz")
ETOPO_FILENAME = "ETOPO1_Ice_g_gmt4.grd"


def ensure_etopo() -> str:
    """Download + decompress ETOPO1 if not cached locally."""
    import gzip
    import shutil

    import requests

    os.makedirs(ETOPO_DIR, exist_ok=True)
    path = os.path.join(ETOPO_DIR, ETOPO_FILENAME)
    if os.path.exists(path):
        return path
    gz = path + ".gz"
    if not os.path.exists(gz):
        print("Downloading ETOPO1 (ice surface, 1 arc-minute, ~158 MB) ...")
        resp = requests.get(ETOPO_URL, timeout=600)
        resp.raise_for_status()
        with open(gz, "wb") as f:
            f.write(resp.content)
    print("Decompressing ETOPO1 ...")
    with gzip.open(gz, "rb") as src, open(path, "wb") as dst:
        shutil.copyfileobj(src, dst, length=1 << 24)
    return path


def rebuild_vertex_coords(resolution: str = "50m", snap_eps: float = 5e-4):
    """VERBATIM re-run of the v36.0 snapping phase (keep in sync!).

    This replicates ingest_boundaries.ingest_boundaries() lines from the
    shapefile read through the per-ring `ids = [vtx.get_or_add(x, y)]`
    pass, in the same order, with the same winding normalisation and the
    same dedupe. The VertexTable coordinates are TRANSIENT — used here
    only to sample the DEM, never stored.
    """
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from aethera.ingest.ingest_boundaries import VertexTable, ensure_shapefile, ring_signed_area

    import shapefile

    shp_path = ensure_shapefile(resolution)
    print(f"Reading {shp_path}")
    sf = shapefile.Reader(shp_path)
    fields = [f[0] for f in sf.fields]
    name_idx = fields.index("NAME")

    vtx = VertexTable(snap_eps)
    ring_ids = []  # (country, [ring ids in ingestion order]) mirror

    for sr in sf.shapeRecords():
        name = str(sr.record[name_idx])
        shape = sr.shape
        n_pts = len(shape.points)
        if n_pts < 3:
            continue

        parts = list(shape.parts) + [n_pts]
        raw_rings = []
        for pi in range(len(parts) - 1):
            s0, s1 = parts[pi], parts[pi + 1]
            if s1 - s0 >= 3:
                raw_rings.append([tuple(shape.points[j]) for j in range(s0, s1)])

        if not raw_rings:
            continue

        areas = [ring_signed_area(r) for r in raw_rings]
        outer_sign = max(areas, key=abs) >= 0

        rings_meta = []
        for ring, area in zip(raw_rings, areas):
            is_outer = (area >= 0) == outer_sign
            kind = "outer" if is_outer else "hole"
            if is_outer and area < 0:
                ring = list(reversed(ring))
            elif (not is_outer) and area > 0:
                ring = list(reversed(ring))

            ids = [vtx.get_or_add(x, y) for x, y in ring]
            unique_ids = []
            seen = set()
            for vid in ids:
                if vid not in seen:
                    seen.add(vid)
                    unique_ids.append(vid)
            if len(unique_ids) < 3:
                continue
            rings_meta.append({"ids": unique_ids, "kind": kind})

        if rings_meta:
            ring_ids.append((name, rings_meta))

    return vtx, ring_ids


def verify_against_bundle(vtx, ring_ids, bundle: dict) -> None:
    """Hard identity checks: same rings, same ids, same edge lengths."""
    b_countries = bundle["countries"]
    assert len(b_countries) == len(ring_ids), (
        f"country count mismatch: bundle {len(b_countries)} vs resnap {len(ring_ids)}")
    for (name_r, rings_r), c_b in zip(ring_ids, b_countries):
        assert name_r == c_b["name"], f"country order mismatch: {name_r} vs {c_b['name']}"
        rings_b = c_b["rings"]
        assert len(rings_r) == len(rings_b), f"ring count mismatch for {name_r}"
        for rr, rb in zip(rings_r, rings_b):
            assert rr["ids"] == rb["ids"], f"ring ids mismatch for {name_r}"
    assert bundle["vertices_count"] == len(vtx.coords), (
        f"vertex count mismatch: bundle {bundle['vertices_count']} vs resnap {len(vtx.coords)}")
    # Edge-length fingerprint: resampled coords must reproduce stored lengths.
    max_dev = 0.0
    for a, b, length in bundle["edges"][:5000]:
        pa, pb = vtx.coords[a], vtx.coords[b]
        d = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
        max_dev = max(max_dev, abs(d - length))
    assert max_dev < 1e-6, f"edge-length fingerprint deviates: {max_dev}"
    print("Vertex-table identity verified against the v36.0 bundle "
          f"({len(vtx.coords)} vertices, edge-length deviation < 1e-6).")


def load_etopo_grid(path: str):
    """Read the ETOPO1 NetCDF grid (transient — used only for sampling).

    Memory-mapped: the file is ~933 MB; fancy indexing below touches only
    the cells we need (78,529 of 58.3M).
    """
    from scipy.io import netcdf_file

    sf = netcdf_file(path, "r", mmap=True)
    xv = np.array(sf.variables["x"][:], dtype=np.float64)
    yv = np.array(sf.variables["y"][:], dtype=np.float64)
    zv = sf.variables["z"]
    zz = zv[:]  # lazy view over the mmap (dtype int16 or float)
    # GMT4 integer grids may carry scale_factor / add_offset attributes.
    scale = float(getattr(zv, "scale_factor", 1.0) or 1.0)
    offset = float(getattr(zv, "add_offset", 0.0) or 0.0)
    if zz.shape != (len(yv), len(xv)):
        # Some writers store (x, y); transpose to (y, x).
        zz = zz.reshape(len(yv), len(xv))
    return xv, yv, zz, scale, offset


def sample_elevations(xv, yv, zz, scale, offset, coords) -> np.ndarray:
    """Nearest-cell DEM sample per (lon, lat) — scalar output only."""
    half_dx = (xv[1] - xv[0]) / 2.0 if len(xv) > 1 else 0.0
    half_dy = (yv[1] - yv[0]) / 2.0 if len(yv) > 1 else 0.0
    cols = np.searchsorted(xv - half_dx, [c[0] for c in coords], side="right") - 1
    rows = np.searchsorted(yv - half_dy, [c[1] for c in coords], side="right") - 1
    cols = np.clip(cols, 0, len(xv) - 1)
    rows = np.clip(rows, 0, len(yv) - 1)
    return zz[rows, cols].astype(np.float64) * scale + offset


ELEV_CACHE = os.path.join(ETOPO_DIR, "elev_cache_v37.npy")


def ingest_elevation(commit: bool = False, resolution: str = "50m", snap_eps: float = 5e-4) -> dict:
    print("Phase 1 — verbatim vertex re-snap (transient coordinates) ...")
    vtx, ring_ids = rebuild_vertex_coords(resolution, snap_eps)

    with open(BUNDLE_PATH) as f:
        bundle = json.load(f)
    verify_against_bundle(vtx, ring_ids, bundle)

    print("Phase 2 — ETOPO1 sampling (scalar output only) ...")
    if os.path.exists(ELEV_CACHE):
        elev = np.load(ELEV_CACHE)
        print(f"Loaded cached elevation scalars: {len(elev)} values")
    else:
        dem_path = ensure_etopo()
        xv, yv, zz, scale, offset = load_etopo_grid(dem_path)
        print(f"ETOPO1 grid: {zz.shape[1]} x {zz.shape[0]} cells")
        elev = sample_elevations(xv, yv, zz, scale, offset, vtx.coords)
        del xv, yv, zz  # transient grid discarded
        os.makedirs(ETOPO_DIR, exist_ok=True)
        np.save(ELEV_CACHE, elev.astype(np.float32))
        elev = elev.astype(np.float32)
        print(f"Sampled {len(elev)} scalars, range [{elev.min():.0f}, {elev.max():.0f}] m (cached)")
    print(f"z stats: min {elev.min():.0f} m, max {elev.max():.0f} m, mean {elev.mean():.1f} m")

    print("Phase 3 — join with the intrinsic solution (identity: ring order) ...")
    with open(SOLUTION_PATH) as f:
        solution = json.load(f)
    sol_by_name = {c["name"]: c for c in solution["countries"]}

    samples = []            # [x, y, elev_m] — intrinsic coords + scalar
    solution_rows = []      # (elev, country, ring_idx, seq) for the DB update
    per_vertex = []         # (vid, elevation) — full table for the DB
    ring_mismatches = 0
    for ci, (name, rings_r) in enumerate(ring_ids):
        c_sol = sol_by_name.get(name)
        if c_sol is None:
            continue
        for ri, rr in enumerate(rings_r):
            if ri >= len(c_sol["rings"]):
                ring_mismatches += 1
                continue
            ring_xy = c_sol["rings"][ri]
            if len(ring_xy) != len(rr["ids"]):
                ring_mismatches += 1
                continue
            for k, vid in enumerate(rr["ids"]):
                x, y = ring_xy[k]
                e = round(float(elev[vid]), 1)
                samples.append([x, y, e])
                solution_rows.append((e, name, ri, k))
    for vid in range(len(vtx.coords)):
        per_vertex.append((vid, round(float(elev[vid]), 1)))

    land = int(np.sum(elev >= 0))
    artifact = {
        "meta": {
            "version": "v37.1",
            "source_dem": "ETOPO1 Ice Surface (1 arc-minute, NGDC/NOAA)",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "vertices_sampled": len(vtx.coords),
            "samples": len(samples),
            "dem_cells_above_sea_level": land,
            "principle": (
                "Elevation is ingested as a per-vertex physical scalar "
                "(metres above sea level) sampled transiently from the "
                "ETOPO1 grid. The DEM's coordinates are discarded — the "
                "artifact stores intrinsic solver coordinates plus the "
                "scalar. No lon/lat, no WGS84, no EPSG (Axioms 3-4)."
            ),
        },
        "samples": samples,
    }
    os.makedirs(os.path.dirname(OUT_ARTIFACT), exist_ok=True)
    with open(OUT_ARTIFACT, "w") as f:
        json.dump(artifact, f, separators=(",", ":"))
    size_mb = os.path.getsize(OUT_ARTIFACT) / 1e6
    print(f"Artifact written: {OUT_ARTIFACT} ({size_mb:.1f} MB, {len(samples)} samples)")

    stats = {
        "vertices_sampled": len(vtx.coords),
        "samples": len(samples),
        "ring_mismatches": ring_mismatches,
        "min_elevation_m": round(float(elev.min()), 1),
        "max_elevation_m": round(float(elev.max()), 1),
        "mean_elevation_m": round(float(elev.mean()), 1),
    }
    print("Elevation stats:", json.dumps(stats, indent=2))

    if commit:
        _commit_to_db(per_vertex, solution_rows)
    return stats


def _commit_to_db(per_vertex, solution_rows) -> None:
    """Store the elevation SCALAR in Neon (no coordinates added)."""
    from psycopg2.extras import execute_values

    from aethera.ingest.db import Database

    with Database() as db:
        db.cur.execute("""
            CREATE TABLE IF NOT EXISTS boundary_vertex_elevation (
                vid INTEGER PRIMARY KEY,
                elevation_m DOUBLE PRECISION NOT NULL
            )
        """)
        db.cur.execute("DELETE FROM boundary_vertex_elevation")
        execute_values(db.cur,
                       "INSERT INTO boundary_vertex_elevation (vid, elevation_m) VALUES %s",
                       per_vertex, page_size=2000)

        # Attach the scalar to the rendered solution vertices (auditable).
        db.cur.execute("ALTER TABLE boundary_solution ADD COLUMN IF NOT EXISTS elevation_m DOUBLE PRECISION")
        execute_values(db.cur,
                       "UPDATE boundary_solution AS b SET elevation_m = data.elev "
                       "FROM (VALUES %s) AS data (elev, country, ring_idx, seq) "
                       "WHERE b.country = data.country AND b.ring_idx = data.ring_idx "
                       "AND b.seq = data.seq",
                       solution_rows, page_size=2000, template="(%s, %s, %s, %s)")
        db.cur.execute("SELECT COUNT(*) FROM boundary_solution WHERE elevation_m IS NOT NULL")
        n_updated = db.cur.fetchone()[0]
        db.update_region_status(
            "boundary_elevation_v37", "done",
            point_count=len(per_vertex),
        )

    print(f"Committed to database: {len(per_vertex)} vertex elevation scalars, "
          f"{n_updated} boundary_solution rows tagged with elevation_m.")


def main():
    ap = argparse.ArgumentParser(description="v37.1 ETOPO1 elevation scalar ingestion")
    ap.add_argument("--all", action="store_true", help="sample all boundary vertices")
    ap.add_argument("--commit", action="store_true", help="write scalars to the database")
    ap.add_argument("--resolution", default="50m", choices=["50m", "110m"])
    ap.add_argument("--snap-eps", type=float, default=5e-4)
    args = ap.parse_args()

    if not args.all:
        print("Nothing to do — pass --all to sample all boundary vertices.")
        return

    ingest_elevation(commit=args.commit, resolution=args.resolution, snap_eps=args.snap_eps)


if __name__ == "__main__":
    main()
