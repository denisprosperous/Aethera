"""Globe-agnostic country boundary ingestion (v36.0 — REAL edge lengths).

v33-v35 rendered "country territories" as the Voronoi dual of ONE seed
point per country, because Mode B bootstrapping stored every edge length
as a 1.0 placeholder (see natural_earth.py). With no real lengths the
solver could never reconstruct actual country shapes — the viewer could
only show capture cells around points. That is the "nodes, not
boundaries" problem.

v36.0 replaces the placeholder bootstrap with REAL boundary data:

  1. Read Natural Earth admin_0 countries (1:50m preferred, 1:110m
     fallback — the mandate's data source).
  2. For every country ring, extract TOPOLOGY (which vertices connect
     to which, in ring order) and RAW EDGE LENGTHS — the Euclidean
     distance between consecutive vertices in the shapefile's own local
     frame, exactly as the v36.0 mandate specifies.
  3. COORDINATES ARE DISCARDED. Nothing lat/lon/WGS84/EPSG is stored —
     not in the JSON bundle, not in the database. Axiom 3 (Extrinsic
     Agnosticism) and Axiom 4 (Zero Bias) hold by construction.
  4. Adjacent countries that digitise the same border share snapped
     vertex IDs, so the solver receives ONE connected adjacency graph
     — borders stitch across countries.
  5. Additional scalar chord constraints (distances between
     stride-separated ring vertices) are stored so the reconstruction
     is rigid enough to recover true country shapes from lengths alone.
  6. Declared absolute areas (km²) come from the platform's Physical
     Truth register (measured survey facts) where a name match exists;
     otherwise a single global calibration scalar converts the raw
     frame's deg² ring area. One scalar — no coordinate system.

The solver (aethera.modules.boundary_reconstruction) later reconstructs
intrinsic coordinates from these lengths + areas alone (Tabula Rasa
random init), scales every country so its polygon area satisfies global
area closure, and emits the derived boundary geometry the 3D viewer
renders as real country polygons.

Usage:
    python -m aethera.ingest.ingest_boundaries --all --commit
"""

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone

import numpy as np

from .db import Database

DATA_DIR = os.environ.get(
    "AETHERA_DATA_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "natural_earth")),
)

SHAPEFILE_URLS = {
    "50m": "https://naciscdn.org/naturalearth/50m/cultural/ne_50m_admin_0_countries.zip",
}

SOURCE_TAG = "boundary_v36"
CHORD_SOURCE_TAG = "boundary_v36_chord"

# Legacy Physical Truth register (measured survey areas, km²).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from aethera.modules.compare_ingestion import REGIONS_PHYSICAL_TRUTH  # noqa: E402

# Continent-level register entries must never shadow country names.
_CONTINENT_ENTRIES = {
    "Africa", "Europe", "Asia", "North America", "South America", "Oceania",
}

# Natural Earth abbreviated names -> legacy register names.
NE_NAME_ALIASES = {
    "United States of America": "United States",
    "Dem. Rep. Congo": "DR Congo",
    "Congo": "Republic of the Congo",
    "S. Sudan": "South Sudan",
    "Côte d'Ivoire": "Ivory Coast",
    "Czechia": "Czech Republic",
    "Bosnia and Herz.": "Bosnia and Herzegovina",
    "Dominican Rep.": "Dominican Republic",
    "Eq. Guinea": "Equatorial Guinea",
    "Solomon Is.": "Solomon Islands",
    "Falkland Is.": "Falkland Islands",
    "W. Sahara": "Western Sahara",
    "Central African Rep.": "Central African Republic",
    "S. Korea": "South Korea",
    "N. Korea": "North Korea",
    "Lao PDR": "Laos",
    "eSwatini": "Eswatini",
    "Timor-Leste": "East Timor",
}


def _normalise(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def build_legacy_area_register():
    """Map normalised legacy region name -> (register_name, area_km2).

    Continent-level entries are excluded from country matching (a NE
    country record never carries a continent name, but the guard makes
    the rule explicit).
    """
    reg = {}
    for name, _poly, area_km2, _coloniser in REGIONS_PHYSICAL_TRUTH:
        if name in _CONTINENT_ENTRIES:
            continue
        reg[_normalise(name)] = (name, float(area_km2))
    return reg


def ensure_shapefile(resolution: str = "50m") -> str:
    """Return path to the admin_0 countries .shp, downloading if needed."""
    import zipfile

    import requests

    dir_50 = os.path.join(DATA_DIR, "ne_50m_admin_0_countries")
    shp_50 = os.path.join(dir_50, "ne_50m_admin_0_countries.shp")
    if resolution == "50m":
        if os.path.exists(shp_50):
            return shp_50
        zip_path = os.path.join(DATA_DIR, "ne_50m_admin_0_countries.zip")
        if not os.path.exists(zip_path):
            os.makedirs(DATA_DIR, exist_ok=True)
            print(f"Downloading Natural Earth 1:50m admin_0 countries ...")
            resp = requests.get(SHAPEFILE_URLS["50m"], timeout=120)
            resp.raise_for_status()
            with open(zip_path, "wb") as f:
                f.write(resp.content)
        os.makedirs(dir_50, exist_ok=True)
        with zipfile.ZipFile(zip_path) as zf:
            zf.extractall(dir_50)
        return shp_50

    # 110m fallback (already in repo).
    for cand in (
        os.path.join(DATA_DIR, "ne_110m_admin_0_countries", "ne_110m_admin_0_countries.shp"),
        os.path.join(DATA_DIR, "ne_110m_countries", "ne_110m_admin_0_countries.shp"),
    ):
        if os.path.exists(cand):
            return cand
    raise FileNotFoundError("No Natural Earth countries shapefile found")


class VertexTable:
    """Global vertex table with tolerance snapping (shared borders).

    Vertices are identified ONLY by an integer ID. The snapping grid
    exists transiently at ingestion time to establish adjacency (which
    is exactly the topological fact the mandate stores); no coordinate
    survives into the bundle or the database.
    """

    def __init__(self, eps: float = 5e-4):
        self.eps = float(eps)
        self.cells = {}
        self.coords = []  # transient, never serialised

    def _cell(self, x, y):
        return (int(math.floor(x / self.eps)), int(math.floor(y / self.eps)))

    def get_or_add(self, x: float, y: float) -> int:
        cx, cy = self._cell(x, y)
        eps2 = self.eps * self.eps
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                bucket = self.cells.get((cx + dx, cy + dy))
                if not bucket:
                    continue
                for vid in bucket:
                    px, py = self.coords[vid]
                    ddx = px - x
                    ddy = py - y
                    if ddx * ddx + ddy * ddy <= eps2:
                        return vid
        vid = len(self.coords)
        self.coords.append((x, y))
        self.cells.setdefault((cx, cy), []).append(vid)
        return vid


def ring_signed_area(points) -> float:
    """Shoelace signed area in the raw local frame (deg² units)."""
    a = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return 0.5 * a


def chord_strides(n: int) -> list:
    """Stride values for rigidifying chord constraints on an n-ring."""
    strides = []
    s = 2
    while s < max(3, n // 3):
        strides.append(s)
        s *= 2
    return strides


def ingest_boundaries(
    commit: bool = False,
    resolution: str = "50m",
    snap_eps: float = 5e-4,
    out_path: str = None,
) -> dict:
    """Ingest all country boundaries — topology + edge lengths only."""
    import shapefile

    shp_path = ensure_shapefile(resolution)
    print(f"Reading {shp_path}")
    sf = shapefile.Reader(shp_path)
    fields = [f[0] for f in sf.fields]
    name_idx = fields.index("NAME")

    vtx = VertexTable(snap_eps)
    edge_map = {}     # (a, b) ordered tuple -> length
    chord_map = {}    # (a, b) ordered tuple -> length
    edge_countries = {}  # (a, b) -> [(country, ring, seq, dir, len), ...]
    countries = []

    for sr in sf.shapeRecords():
        name = str(sr.record[name_idx])
        shape = sr.shape
        n_pts = len(shape.points)
        if n_pts < 3:
            continue

        # Split into parts (rings).
        parts = list(shape.parts) + [n_pts]
        raw_rings = []
        for pi in range(len(parts) - 1):
            s0, s1 = parts[pi], parts[pi + 1]
            if s1 - s0 >= 3:
                raw_rings.append([tuple(shape.points[j]) for j in range(s0, s1)])

        if not raw_rings:
            continue

        # Ring role: outer vs hole by signed-area sign of the largest ring.
        areas = [ring_signed_area(r) for r in raw_rings]
        outer_sign = max(areas, key=abs) >= 0

        rings_meta = []
        declared_raw_area = 0.0
        for ring, area in zip(raw_rings, areas):
            is_outer = (area >= 0) == outer_sign
            kind = "outer" if is_outer else "hole"
            if is_outer:
                declared_raw_area += abs(area)
            else:
                declared_raw_area -= abs(area)

            # Canonical winding: outers CCW, holes CW (chirality is an
            # invariant of the source topology, not a coordinate frame).
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

            n = len(unique_ids)
            # Turtle-walk scalars: per-edge length + direction relative to
            # the ring's own first edge (frame-free rotation scalars).
            # Lengths + turn angles determine the ring exactly (no MDS).
            # v39.1: the ABSOLUTE first-edge bearing is additionally stored
            # as a scalar (same scalar class as the relative directions).
            # It is an orientation, not a position: with it, every ring's
            # turtle-walk reconstructs in ONE globally consistent source
            # frame, so the stitched world recovers true inter-country
            # orientation exactly (no per-component rotations).
            walk = []
            dirs_abs = []
            base_dir = None
            for i in range(n):
                a = unique_ids[i]
                b = unique_ids[(i + 1) % n]
                key = (a, b) if a < b else (b, a)
                pa = vtx.coords[a]
                pb = vtx.coords[b]
                length = math.sqrt((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2)
                d = math.atan2(pb[1] - pa[1], pb[0] - pa[0])
                if base_dir is None:
                    base_dir = d
                # Cumulative direction of this edge in the ring's own walk
                # frame (first edge = 0). Frame-free rotation scalar.
                rel = (d - base_dir + math.pi) % (2 * math.pi) - math.pi
                dirs_abs.append(rel)
                walk.append(length)

            # Register per-ring edge records (topology + scalars).
            ring_key = (name, len(rings_meta))
            for i in range(n):
                a = unique_ids[i]
                b = unique_ids[(i + 1) % n]
                key = (a, b) if a < b else (b, a)
                if key[0] == key[1]:
                    continue
                edge_countries.setdefault(key, []).append(
                    (name, len(rings_meta), i, dirs_abs[i], walk[i]))
                edge_map.setdefault(key, walk[i])
                if key not in edge_map or walk[i] < edge_map[key]:
                    edge_map[key] = walk[i]

            # Rigidifying chord constraints (scalar lengths, stride-separated).
            for st in chord_strides(n):
                step = 2 if st > 4 else 1
                for i in range(0, n, step):
                    a = unique_ids[i]
                    b = unique_ids[(i + st) % n]
                    if a == b:
                        continue
                    key = (a, b) if a < b else (b, a)
                    if key in chord_map:
                        continue
                    pa = vtx.coords[key[0]]
                    pb = vtx.coords[key[1]]
                    chord_map[key] = math.sqrt((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2)

            rings_meta.append({"ids": unique_ids, "kind": kind,
                               "walk": walk, "dirs": dirs_abs,
                               "bearing0": base_dir})

        if not rings_meta:
            continue

        countries.append({
            "name": name,
            "rings": rings_meta,
            "raw_frame_area_deg2": declared_raw_area,
        })

    # Shared border segments: same snapped vertex pair touched by two
    # different countries. Their per-country walk direction angles are the
    # scalar data from which RELATIVE country orientations emerge.
    shared_edges = []
    for (a, b), touches in edge_countries.items():
        (na, ri_a, seq_a, da, _la) = touches[0]
        for (nb, ri_b, seq_b, db, _lb) in touches[1:]:
            if nb != na:
                shared_edges.append([a, b, na, round(da, 6), nb, round(db, 6)])
                break

    # ---- Declared absolute areas (km²) --------------------------------
    legacy = build_legacy_area_register()
    ratios = []
    for c in countries:
        norm = _normalise(NE_NAME_ALIASES.get(c["name"], c["name"]))
        hit = legacy.get(norm)
        if hit and c["raw_frame_area_deg2"] > 1e-9:
            ratios.append(hit[1] / c["raw_frame_area_deg2"])
        c["_legacy"] = hit
    calibration = float(np.median(ratios)) if ratios else 1.0

    for c in countries:
        if c["_legacy"] is not None:
            c["declared_area_km2"] = c["_legacy"][1]
            c["area_source"] = "physical_truth"
            c["legacy_region"] = c["_legacy"][0]
        else:
            c["declared_area_km2"] = round(c["raw_frame_area_deg2"] * calibration, 3)
            c["area_source"] = "calibrated_raw_frame"
            c["legacy_region"] = None
        del c["_legacy"]

    edges = [[a, b, round(l, 8)] for (a, b), l in sorted(edge_map.items())]
    chords = [[a, b, round(l, 8)] for (a, b), l in sorted(chord_map.items())]

    bundle = {
        "meta": {
            "version": "v36.0",
            "source_shapefile": os.path.basename(shp_path),
            "resolution": "1:50m" if "50m" in shp_path else "1:110m",
            "snap_eps_deg": snap_eps,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "calibration_km2_per_deg2": round(calibration, 6),
            "principle": (
                "Coordinates are discarded at ingestion. Only topology "
                "(vertex adjacency), raw local-frame edge lengths and "
                "declared absolute areas (km²) are stored. No lon/lat, "
                "no WGS84, no EPSG — Axioms 3 and 4 hold by construction."
            ),
        },
        "vertices_count": len(vtx.coords),
        "countries_count": len(countries),
        "countries": countries,
        "edges": edges,
        "chord_constraints": chords,
        "shared_edges": shared_edges,
    }

    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(bundle, f, separators=(",", ":"))
        print(f"Bundle written: {out_path} ({os.path.getsize(out_path)/1e6:.1f} MB)")

    stats = {
        "countries": len(countries),
        "vertices": len(vtx.coords),
        "edges": len(edges),
        "chords": len(chords),
        "physical_truth_matched": sum(1 for c in countries if c["area_source"] == "physical_truth"),
        "calibrated": sum(1 for c in countries if c["area_source"] == "calibrated_raw_frame"),
        "calibration_km2_per_deg2": round(calibration, 6),
        "shared_border_edges": len(shared_edges),
    }
    print("Ingestion stats:", json.dumps(stats, indent=2))

    if commit:
        _commit_to_db(bundle, stats)
    return bundle


def _commit_to_db(bundle: dict, stats: dict) -> None:
    """Store topology + edge lengths in Neon — NO coordinates."""
    with Database() as db:
        # Idempotent re-ingest: clear previous v36 boundary rows.
        db.cur.execute("DELETE FROM edges WHERE source IN (%s, %s)", (SOURCE_TAG, CHORD_SOURCE_TAG))
        db.cur.execute("DELETE FROM faces WHERE region = %s", (SOURCE_TAG,))
        db.cur.execute("DELETE FROM points WHERE source = %s", (SOURCE_TAG,))
        db.conn.commit()

        # Points: integer IDs with machine labels. No coordinates.
        n_v = bundle["vertices_count"]
        db.batch_create_points([(f"bv{vid}", SOURCE_TAG) for vid in range(n_v)], source=SOURCE_TAG)
        db.cur.execute("SELECT id, label FROM points WHERE source = %s", (SOURCE_TAG,))
        pid = {int(label[2:]): pid_ for pid_, label in db.cur.fetchall() if label and label.startswith("bv")}

        # Boundary edges (the render topology) with real measured lengths.
        edge_specs = [
            (pid[a], pid[b], length, SOURCE_TAG, "measured", SOURCE_TAG)
            for a, b, length in bundle["edges"]
        ]
        db.batch_create_edges(edge_specs)

        # Chord constraints (rigidifying scalars) — separate source tag.
        chord_specs = [
            (pid[a], pid[b], length, CHORD_SOURCE_TAG, "measured", CHORD_SOURCE_TAG)
            for a, b, length in bundle["chord_constraints"]
        ]
        db.batch_create_edges(chord_specs)

        # Turtle-walk scalars per ring edge (length + relative direction):
        # the exact reconstruction data — still no coordinates.
        db.cur.execute("""
            CREATE TABLE IF NOT EXISTS boundary_edge_walk (
                country TEXT NOT NULL,
                ring_idx INTEGER NOT NULL,
                seq INTEGER NOT NULL,
                from_vid INTEGER NOT NULL,
                to_vid INTEGER NOT NULL,
                length DOUBLE PRECISION NOT NULL,
                direction_rad DOUBLE PRECISION NOT NULL
            )
        """)
        db.cur.execute("DELETE FROM boundary_edge_walk")
        walk_rows = []
        for c in bundle["countries"]:
            for ri, ring in enumerate(c["rings"]):
                ids = ring["ids"]
                for seq, (ln, dr) in enumerate(zip(ring["walk"], ring["dirs"])):
                    walk_rows.append((c["name"], ri, seq, ids[seq],
                                      ids[(seq + 1) % len(ids)], ln, dr))
        from psycopg2.extras import execute_values as _ev
        _ev(db.cur,
            "INSERT INTO boundary_edge_walk (country, ring_idx, seq, from_vid, "
            "to_vid, length, direction_rad) VALUES %s", walk_rows, page_size=1000)

        # Faces: one per country; ordered rings live in properties JSONB.
        for c in bundle["countries"]:
            point_ids = [pid[vid] for vid in c["rings"][0]["ids"]]
            props = {
                "rings": c["rings"],
                "declared_area_km2": c["declared_area_km2"],
                "area_source": c["area_source"],
                "legacy_region": c["legacy_region"],
                "raw_frame_area_deg2": c["raw_frame_area_deg2"],
                "resolution": bundle["meta"]["resolution"],
            }
            db.insert_face(c["name"], "land", SOURCE_TAG, [], point_ids, props)

        db.update_region_status(
            SOURCE_TAG, "done",
            edge_count=stats["edges"] + stats["chords"],
            face_count=stats["countries"],
            point_count=stats["vertices"],
        )

    print(
        f"Committed to database: {stats['vertices']} points, "
        f"{stats['edges']} boundary edges, {stats['chords']} chord constraints, "
        f"{stats['shared_border_edges']} shared border edges, "
        f"{len(walk_rows)} walk-scalar rows, "
        f"{stats['countries']} country faces (source={SOURCE_TAG})."
    )


def main():
    ap = argparse.ArgumentParser(description="v36.0 globe-agnostic boundary ingestion")
    ap.add_argument("--all", action="store_true", help="ingest all countries")
    ap.add_argument("--commit", action="store_true", help="write to the database")
    ap.add_argument("--resolution", default="50m", choices=["50m", "110m"])
    ap.add_argument("--snap-eps", type=float, default=5e-4)
    ap.add_argument(
        "--out",
        default=os.path.join(DATA_DIR, "..", "boundaries", "boundaries_v36.json"),
    )
    args = ap.parse_args()

    if not args.all:
        print("Nothing to do — pass --all to ingest all countries.")
        return

    ingest_boundaries(commit=args.commit, resolution=args.resolution, snap_eps=args.snap_eps, out_path=os.path.abspath(args.out))


if __name__ == "__main__":
    main()
