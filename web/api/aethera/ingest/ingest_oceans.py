"""Ocean & sea ingestion from ETOPO1 (v39.0, globe-agnostic).

Computes TRUE surface areas for the five ocean basins and major seas
from the ETOPO1 Ice Surface DEM (1 arc-minute), using the mandate's
segmentation convention (priority: Southern lat<-60, Arctic lat>66,
then Pacific/Atlantic/Indian longitude boxes) and stores:

  * true per-basin areas (km2, cos(lat)-corrected cell integration),
  * coarse coastline polygons per basin (6-arc-minute contours),
  * polygons mapped into the platform's intrinsic DISPLAY frame via the
    disclosed lon/lat -> display affine fitted on the stitched solution.

Coordinates are consumed at INGESTION only and never stored in the
solver chain (Axioms 2-4). The segmentation convention is disclosed
(Axiom 5). Run:  python -m aethera.ingest.ingest_oceans [--no-db]
"""

import argparse
import json
import math
import os
from datetime import datetime, timezone

import numpy as np

SOLUTION_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "data", "boundaries_solution_v39.json"))
OUT_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "boundaries",
    "oceans_v39.json"))
ETOPO_PATH = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "etopo1",
    "ETOPO1_Ice_g_gmt4.grd.gz"))

KM_PER_DEG = 6371.0 * math.pi / 180.0
ARCMIN = 1.0 / 60.0
CELL_KM = 111.194 * ARCMIN          # 1 arc-minute meridional (~1.853 km)

# Mandate segmentation (priority order matters: earlier masks claim cells)
BASIN_BOXES = [
    # name, lon_min, lon_max, lat_min, lat_max, priority
    ("Southern Ocean", -180.0, 180.0, -90.0, -60.0, 0),
    ("Arctic Ocean", -180.0, 180.0, 66.0, 90.0, 0),
    ("Pacific Ocean", -180.0, -70.0, -60.0, 66.0, 1),
    ("Pacific Ocean", 120.0, 180.0, -60.0, 66.0, 1),
    ("Atlantic Ocean", -70.0, 20.0, -60.0, 66.0, 1),
    ("Indian Ocean", 20.0, 120.0, -60.0, 66.0, 1),
]

SEA_BOXES = [
    ("Mediterranean Sea", -5.5, 36.0, 30.0, 46.0),
    ("Caribbean Sea", -105.0, -60.0, 8.0, 25.0),
    ("Gulf of Mexico", -105.0, -75.0, 18.5, 31.0),
    ("South China Sea", 100.0, 122.0, 0.0, 25.0),
    ("Bering Sea", 160.0, -165.0, 50.0, 66.0),
    ("Sea of Japan", 127.0, 142.0, 33.0, 52.0),
    ("Red Sea", 32.0, 44.0, 12.0, 30.0),
    ("Black Sea", 27.0, 42.0, 40.5, 48.0),
    ("Baltic Sea", 10.0, 30.0, 53.5, 66.0),
    ("Hudson Bay", -95.0, -70.0, 51.0, 66.0),
    ("Persian Gulf", 47.5, 57.0, 23.5, 30.5),
    ("Bay of Bengal", 80.0, 95.0, 5.0, 22.0),
    ("Arabian Sea", 57.0, 75.0, 5.0, 25.0),
]

REFERENCE_AREAS_KM2 = {
    "Pacific Ocean": 165250000.0,
    "Atlantic Ocean": 106460000.0,
    "Indian Ocean": 70560000.0,
    "Southern Ocean": 21960000.0,
    "Arctic Ocean": 14060000.0,
}


def _lon_in_box(lon, lo, hi):
    if lo <= hi:
        return (lon >= lo) & (lon < hi)
    return (lon >= lo) | (lon < hi)   # antimeridian-crossing box


def load_etopo1(path=ETOPO_PATH):
    """Read the ETOPO1 NetCDF classic grid (decompressing .gz if needed)."""
    import gzip
    import tempfile
    from scipy.io import netcdf_file

    open_path = path
    tmp = None
    if path.endswith(".gz"):
        tmp = tempfile.NamedTemporaryFile(suffix=".grd", delete=False)
        with gzip.open(path, "rb") as f:
            while True:
                chunk = f.read(1 << 22)
                if not chunk:
                    break
                tmp.write(chunk)
        tmp.close()
        open_path = tmp.name
    try:
        with netcdf_file(open_path, "r", mmap=False) as nc:
            z = nc.variables["z"][:].astype(np.int16)
            x = nc.variables["x"][:].astype(np.float64)
            y = nc.variables["y"][:].astype(np.float64)
    finally:
        if tmp is not None:
            os.unlink(tmp.name)
    return x, y, z


def compute_areas_and_masks(x, y, z, coarse_step=8):
    """Basin/sea areas + coarse water masks (priority segmentation)."""
    nlat, nlon = z.shape
    lats = y + ARCMIN / 2.0
    lons = x + ARCMIN / 2.0
    cell_area = CELL_KM ** 2        # km2 at the equator, scaled by cos(lat)

    basin_area = {}
    basin_mask = {}     # coarse bool grids
    sea_area = {}
    sea_mask = {}

    owner = np.full(z.shape, -1, dtype=np.int8)
    names = []
    for name, lo, hi, la, lb, _pri in BASIN_BOXES:
        if name not in names:
            names.append(name)
    idx_of = {n: i for i, n in enumerate(names)}
    # priority claim: iterate basins in priority order
    ordered = sorted(BASIN_BOXES, key=lambda b: b[5])
    for name, lo, hi, la, lb, _pri in ordered:
        lat_ok = (lats >= la) & (lats < lb)
        lon_ok = _lon_in_box(lons, lo, hi)
        box = lat_ok[:, None] & lon_ok[None, :]
        water = (z <= 0) & box & (owner == -1)
        owner[water] = idx_of[name]
        chunk = water.sum(dtype=np.int64)
        cosl = np.cos(np.radians(lats))
        basin_area[name] = basin_area.get(name, 0.0) + float(
            (water * cosl[:, None]).sum()) * cell_area

    # coarse masks per basin
    zs = z[::coarse_step, ::coarse_step]
    os_ = owner[::coarse_step, ::coarse_step]
    slats = lats[::coarse_step]
    slons = lons[::coarse_step]
    for name in names:
        basin_mask[name] = (os_ == idx_of[name]) & (zs <= 0)

    # seas (independent boxes, may overlap basins - disclosed)
    for name, lo, hi, la, lb in SEA_BOXES:
        lat_ok = (lats >= la) & (lats < lb)
        lon_ok = _lon_in_box(lons, lo, hi)
        water = (z <= 0) & lat_ok[:, None] & lon_ok[None, :]
        cosl = np.cos(np.radians(lats))
        sea_area[name] = float((water * cosl[:, None]).sum()) * cell_area
        sw = water[::coarse_step, ::coarse_step]
        sea_mask[name] = sw & (zs <= 0)

    return names, basin_area, basin_mask, sea_area, sea_mask, slats, slons


def mask_to_rings(mask, lons, lats, max_pts=420):
    """Extract the largest closed contour of a mask as [lon, lat] ring."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if not mask.any():
        return []
    g = np.zeros((mask.shape[0] + 2, mask.shape[1] + 2), dtype=float)
    g[1:-1, 1:-1] = mask.astype(float)
    cs = plt.contour(g, levels=[0.5])
    plt.close(cs.figure)
    paths = cs.get_paths() if hasattr(cs, "get_paths") else cs.collections[0].get_paths()
    if not paths:
        return []
    largest = max(paths, key=lambda p: p.vertices.shape[0])
    v = largest.vertices
    # decimate to max_pts
    if len(v) > max_pts:
        step = max(1, len(v) // max_pts)
        v = v[::step]
    rings = []
    for px, py in v:
        cx = px - 1
        cy = py - 1
        cx = min(max(cx, 0), len(lons) - 1)
        cy = min(max(cy, 0), len(lats) - 1)
        rings.append([float(lons[int(round(cx))]), float(lats[int(round(cy))])])
    return rings


def fit_display_affine(solution):
    """Least-squares affine lon/lat -> display frame from country centroids.

    Uses the NE label centroids (disclosed convention) against the solved
    display centroids. Returns (a..f, rms) so that
        [dx, dy] = A @ [lon, lat] + t,  A = [[a, b], [d, e]], t = [c, f].
    """
    import shapefile

    ne = os.path.abspath(os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "data", "natural_earth",
        "ne_50m_admin_0_countries"))
    sf = shapefile.Reader(os.path.join(ne, "ne_50m_admin_0_countries.shp"))
    fields = [f[0] for f in sf.fields]
    adj = {f: i - 1 for i, f in enumerate(fields) if f != "DeletionFlag"}
    ix, iy, inm = adj["LABEL_X"], adj["LABEL_Y"], adj["NAME"]
    lonlat = {}
    for i in range(sf.numRecords):
        r = sf.record(i)
        lonlat[str(r[inm]).strip()] = (float(r[ix]), float(r[iy]))

    from aethera.modules.boundary_reconstruction import (
        DISPLAY_ALIASES, _ne_alias)
    norm = lambda s: "".join(ch for ch in s.lower() if ch.isalnum())
    disp = {}
    for c in solution["countries"]:
        nm = c["name"]
        key = None
        for cand in (nm, DISPLAY_ALIASES.get(nm), _ne_alias(nm),
                     DISPLAY_ALIASES.get(_ne_alias(nm))):
            if cand and norm(cand) in {norm(k) for k in lonlat}:
                key = next(k for k in lonlat if norm(k) == norm(cand))
                break
        if key is None:
            continue
        pts = np.asarray([p for r in c["rings"] for p in r], dtype=float)
        disp[key] = pts.mean(axis=0)

    A_rows, b_x, b_y = [], [], []
    for key, (lon, lat) in lonlat.items():
        if key not in disp:
            continue
        A_rows.append([lon, lat, 1.0])
        b_x.append(disp[key][0])
        b_y.append(disp[key][1])
    M = np.asarray(A_rows)
    bx = np.asarray(b_x)
    by = np.asarray(b_y)
    sol_x, *_ = np.linalg.lstsq(M, bx, rcond=None)
    sol_y, *_ = np.linalg.lstsq(M, by, rcond=None)
    a, b, c = sol_x
    d, e, f = sol_y
    pred_x = M @ sol_x
    pred_y = M @ sol_y
    rms = float(np.sqrt(((pred_x - bx) ** 2 + (pred_y - by) ** 2).mean()))
    return (a, b, c, d, e, f), rms


def main():
    ap = argparse.ArgumentParser(description="v39.0 ocean ingestion")
    ap.add_argument("--etopo", default=ETOPO_PATH)
    ap.add_argument("--out", default=OUT_PATH)
    ap.add_argument("--no-db", action="store_true")
    args = ap.parse_args()

    print("loading ETOPO1 ...", flush=True)
    x, y, z = load_etopo1(args.etopo)
    print(f"grid {z.shape}", flush=True)

    names, basin_area, basin_mask, sea_area, sea_mask, slats, slons = \
        compute_areas_and_masks(x, y, z)
    for n in names:
        ref = REFERENCE_AREAS_KM2.get(n)
        dev = (basin_area[n] / ref - 1.0) * 100.0 if ref else float("nan")
        print(f"  {n:16s} {basin_area[n]:>16,.0f} km2 "
              f"(reference {ref:,.0f}, {dev:+.1f}%)" if ref else
              f"  {n:16s} {basin_area[n]:>16,.0f} km2", flush=True)
    for n, a in sea_area.items():
        print(f"  {n:16s} {a:>16,.0f} km2", flush=True)

    with open(SOLUTION_PATH) as f:
        solution = json.load(f)
    (a, b, c, d, e, f_), aff_rms = fit_display_affine(solution)
    print(f"display affine rms: {aff_rms:.0f} km", flush=True)

    def to_display(ring):
        out = []
        for lon, lat in ring:
            dx = a * lon + b * lat + c
            dy = d * lon + e * lat + f_
            out.append([round(float(dx), 2), round(float(dy), 2)])
        return out

    oceans = []
    for n in names:
        ring = mask_to_rings(basin_mask[n], slons, slats)
        pts = np.asarray(ring) if ring else np.zeros((0, 2))
        cen = [float(pts[:, 0].mean()), float(pts[:, 1].mean())] \
            if len(pts) else None
        oceans.append({
            "name": n,
            "kind": "ocean",
            "area_km2": round(basin_area[n], 1),
            "reference_area_km2": REFERENCE_AREAS_KM2.get(n),
            "coastline_ring": ring,
            "coastline_ring_display": to_display(ring),
            "centroid_lonlat": [
                round(cen[0], 3), round(cen[1], 3)] if cen else None,
            "centroid_display": [
                round(a * cen[0] + b * cen[1] + c, 2),
                round(d * cen[0] + e * cen[1] + f_, 2)] if cen else None,
        })
    for n, ar in sea_area.items():
        ring = mask_to_rings(sea_mask[n], slons, slats)
        oceans.append({
            "name": n,
            "kind": "sea",
            "area_km2": round(ar, 1),
            "coastline_ring": ring,
            "coastline_ring_display": to_display(ring),
        })

    total = sum(o["area_km2"] for o in oceans if o["kind"] == "ocean")
    bundle = {
        "meta": {
            "version": "v39.0",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "NOAA ETOPO1 Ice Surface (1 arc-minute)",
            "segmentation": (
                "priority boxes: Southern lat<-60, Arctic lat>66, then "
                "Pacific/Atlantic/Indian longitude boxes (mandate "
                "convention, disclosed); seas by named boxes"),
            "display_affine_lonlat_to_display": {
                "a": a, "b": b, "c": c, "d": d, "e": e, "f": f_,
                "rms_display_units": round(aff_rms, 1)},
            "principle": (
                "True ocean surface areas integrated from ETOPO1 "
                "bathymetry with cos(lat) cell correction; coastline "
                "polygons are 8-arc-minute disclosed conventions mapped "
                "into the intrinsic display frame. No coordinates enter "
                "the solver chain."),
        },
        "stats": {
            "basins": len(names),
            "seas": len(sea_area),
            "total_ocean_area_km2": round(total, 1),
        },
        "oceans": oceans,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as fo:
        json.dump(bundle, fo, separators=(",", ":"))
    print(f"oceans bundle written: {args.out} "
          f"({os.path.getsize(args.out)/1e6:.1f} MB)", flush=True)

    if not args.no_db:
        from aethera.ingest.db import Database
        with Database() as db:
            db.cur.execute("""
                CREATE TABLE IF NOT EXISTS ocean_areas (
                    name TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    area_km2 DOUBLE PRECISION NOT NULL,
                    reference_area_km2 DOUBLE PRECISION,
                    version TEXT NOT NULL
                )
            """)
            db.cur.execute("DELETE FROM ocean_areas")
            for o in oceans:
                db.cur.execute(
                    "INSERT INTO ocean_areas (name, kind, area_km2, "
                    "reference_area_km2, version) VALUES (%s,%s,%s,%s,%s)",
                    (o["name"], o["kind"], o["area_km2"],
                     o.get("reference_area_km2"), "v39.0"))
        print(f"ocean_areas table: {len(oceans)} rows", flush=True)


if __name__ == "__main__":
    main()
