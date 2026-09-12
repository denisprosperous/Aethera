#!/usr/bin/env python3
"""
v39.1 display-frame artifact builder.

Re-projects the two frame-dependent artifacts (oceans + elevation) into
the v39.1 canonical anamorphic kilometre frame:

    x = KM_PER_DEG * lon * cos(lat)
    y = KM_PER_DEG * lat

Ocean rings: the v39.0 bundle stores the raw lon/lat segmentation rings
(`coastline_ring`) alongside their affine display projection; the lon/lat
rings are authoritative and are re-projected exactly. Areas are
recomputed as the shoelace area of the re-projected rings (which, in the
anamorphic frame, equal the true geodesic areas of the polygons).

Elevation artifact: the v39.0 npz stores the original lon/lat of every
sample alongside its old-frame display position; the samples are
re-projected from their stored lon/lat (elevations untouched).
"""
import json
import math
import os
from datetime import datetime, timezone

import numpy as np

BASE = "/home/z/my-project/aethera/python/aethera/data"
KM_PER_DEG = 6371.0 * math.pi / 180.0


def to_display(lon, lat):
    return (lon * math.cos(math.radians(lat)) * KM_PER_DEG,
            lat * KM_PER_DEG)


def shoelace(P):
    x, y = P[:, 0], P[:, 1]
    return 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


def build_oceans():
    src = json.load(open(os.path.join(BASE, "oceans_v39.json")))
    out = {"meta": {
        "version": "v39.1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": src["meta"].get("source", "NOAA ETOPO1 Ice Surface"),
        "segmentation": src["meta"].get("segmentation", ""),
        "display_frame": {
            "type": "anamorphic_cylindrical_km",
            "x": "KM_PER_DEG * lon * cos(lat)",
            "y": "KM_PER_DEG * lat",
            "km_per_deg": round(KM_PER_DEG, 6),
        },
        "note": ("lon/lat segmentation rings re-projected exactly into the "
                 "v39.1 canonical display frame; areas recomputed as ring "
                 "shoelace areas (true geodesic areas in this frame)"),
    }, "stats": dict(src.get("stats", {})), "oceans": []}

    total_declared = 0.0
    for o in src["oceans"]:
        ring_ll = np.asarray(o["coastline_ring"], dtype=float)
        disp = np.column_stack([
            ring_ll[:, 0] * np.cos(np.radians(ring_ll[:, 1])) * KM_PER_DEG,
            ring_ll[:, 1] * KM_PER_DEG])
        area_km2 = abs(float(shoelace(disp)))
        cx, cy = to_display(*np.mean(ring_ll, axis=0))
        total_declared += area_km2
        out["oceans"].append({
            "name": o["name"],
            "kind": o.get("kind", "ocean"),
            "area_km2": round(area_km2, 1),
            "reference_area_km2": o.get("reference_area_km2"),
            "coastline_ring": o["coastline_ring"],
            "coastline_ring_display": [[round(float(x), 4), round(float(y), 4)]
                                       for x, y in disp],
            "centroid_lonlat": o.get("centroid_lonlat"),
            "centroid_display": [round(float(cx), 4), round(float(cy), 4)],
        })
    out["stats"]["total_area_km2"] = round(total_declared, 1)
    dst = os.path.join(BASE, "oceans_v391.json")
    with open(dst, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    print(f"oceans_v391.json: {len(out['oceans'])} water bodies, "
          f"total {total_declared/1e6:.1f}M km2 "
          f"({os.path.getsize(dst)/1e6:.1f} MB)")


def build_elevation():
    z = np.load(os.path.join(BASE, "elevation_artifact.npz"))
    lonlat = z["lonlat"]
    elev = z["elevation_m"]
    lon, lat = lonlat[:, 0], lonlat[:, 1]
    x = lon * np.cos(np.radians(lat)) * KM_PER_DEG
    y = lat * KM_PER_DEG
    np.savez_compressed(
        os.path.join(BASE, "elevation_artifact.npz"),
        x=x, y=y, elevation_m=elev, lonlat=lonlat,
        meta=np.array([
            391.0,                       # artifact schema marker (v39.1)
            KM_PER_DEG,
            float(len(x)),
            float(x.min()), float(x.max()),
            float(y.min()), float(y.max()),
        ]))
    meta = {
        "version": "v39.1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "samples": int(len(x)),
        "step_deg": 0.5,
        "source": "NOAA ETOPO1 Ice Surface (re-projected from stored lon/lat)",
        "display_frame": {
            "type": "anamorphic_cylindrical_km",
            "x": "KM_PER_DEG * lon * cos(lat)",
            "y": "KM_PER_DEG * lat",
            "km_per_deg": round(KM_PER_DEG, 6),
        },
    }
    with open(os.path.join(BASE, "elevation_artifact.npz.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(f"elevation_artifact.npz: {len(x)} samples re-projected "
          f"x[{x.min():.0f},{x.max():.0f}] y[{y.min():.0f},{y.max():.0f}]")


if __name__ == "__main__":
    build_oceans()
    build_elevation()
