"""Build the intrinsic elevation artifact (v39.0).

Samples ETOPO1 on a regular lon/lat grid, maps every sample into the
platform's display frame with the SAME disclosed affine as the ocean
ingestion, and stores a pure-numpy KD-tree-ready npz:

    x, y           display-frame sample positions
    elevation_m    ETOPO1 ice-surface elevation, metres (sea level = 0)

Run AFTER the stitched solution + ocean ingestion exist:
    python -m aethera.ingest.ingest_elevation_intrinsic
"""

import json
import os
from datetime import datetime, timezone

import numpy as np

from aethera.ingest.ingest_oceans import (
    ETOPO_PATH, SOLUTION_PATH, fit_display_affine, load_etopo1)

OUT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "data", "elevation_artifact.npz"))
STEP_DEG = 0.5


def main():
    print("loading ETOPO1 ...", flush=True)
    x, y, z = load_etopo1(ETOPO_PATH)
    nlat, nlon = z.shape
    lat0, lat1 = float(y[0]), float(y[-1])
    lon0, lon1 = float(x[0]), float(x[-1])
    print(f"grid {z.shape} lat {lat0}..{lat1} lon {lon0}..{lon1}", flush=True)

    # regular lon/lat sample grid (row-step to ~STEP_DEG)
    step = max(1, int(round(STEP_DEG / (1.0 / 60.0))))
    lats = y[::step]
    lons = x[::step]
    Z = z[::step, ::step].astype(np.float32)
    LA, LO = np.meshgrid(lats, lons, indexing="ij")
    print(f"samples: {Z.size}", flush=True)

    with open(SOLUTION_PATH) as f:
        solution = json.load(f)
    (a, b, c, d, e, f_), rms = fit_display_affine(solution)
    print(f"display affine rms {rms:.0f} km", flush=True)
    DX = (a * LO + b * LA + c).astype(np.float64)
    DY = (d * LO + e * LA + f_).astype(np.float64)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    np.savez_compressed(
        OUT,
        x=DX.reshape(-1), y=DY.reshape(-1),
        elevation_m=Z.reshape(-1),
        lonlat=np.stack([LO.reshape(-1), LA.reshape(-1)], axis=1),
        meta=np.array([a, b, c, d, e, f_, rms]))
    print(f"elevation artifact: {OUT} "
          f"({os.path.getsize(OUT)/1e6:.1f} MB)", flush=True)

    meta = {
        "version": "v39.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "samples": int(Z.size),
        "step_deg": STEP_DEG,
        "source": "NOAA ETOPO1 Ice Surface",
        "display_affine_rms_km": round(rms, 1),
    }
    with open(OUT + ".json", "w") as f:
        json.dump(meta, f, indent=1)
    print("meta written", flush=True)


if __name__ == "__main__":
    main()
