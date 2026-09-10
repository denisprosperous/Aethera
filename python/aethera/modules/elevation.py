"""Elevation lookup on the intrinsic manifold (v37.2).

Serves elevation-on-click for the Intrinsic Manifold Viewer: given a
point in the solver's intrinsic frame, return the height above sea level
sampled from ETOPO1 at ingestion time.

Design notes:
  • The lookup table is the bundled artifact
    boundaries_elevation_v37.json — intrinsic (x, y) pairs with the
    elevation SCALAR per vertex. No coordinates outside the solver's own
    intrinsic frame exist in this module (Axiom 3).
  • Nearest neighbour is an exact O(n) numpy scan over ~98k points
    (~1 ms). scipy is deliberately NOT imported so the serverless
    bundle stays lean; the result is identical to a cKDTree query.
  • The whole artifact loads once per process (~2 MB) and is cached.
  • v37.2: the scale-aware COVERAGE GUARD is enforced HERE, inside the
    lookup itself. A click whose nearest boundary vertex lies farther
    than the coverage radius returns None — honestly reporting that the
    point is outside the ingested world — instead of silently returning
    a far-away vertex's scalar (Axiom 5).
"""

import json
import os
from typing import Optional, Tuple

import numpy as np

_ARTIFACT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "data", "boundaries_elevation_v37.json"))

_CACHE: dict = {}


def _load() -> Tuple[np.ndarray, np.ndarray, str]:
    """Load + cache the elevation lookup table."""
    if not _CACHE:
        with open(_ARTIFACT) as f:
            data = json.load(f)
        samples = np.asarray(data["samples"], dtype=np.float64)
        _CACHE["xy"] = np.ascontiguousarray(samples[:, :2])
        _CACHE["elev"] = np.ascontiguousarray(samples[:, 2])
        _CACHE["source"] = data["meta"]["source_dem"]
    return _CACHE["xy"], _CACHE["elev"], _CACHE["source"]


def coverage_radius() -> float:
    """Scale-aware coverage radius for the honest out-of-manifold guard.

    The intrinsic solution spans tens of thousands of display units, so
    a fixed threshold is meaningless. 25% of the world's largest span
    (min 4,000 units) covers every click inside the world's bounding box
    (measured max random-point distance ≈ 3,431 units) while clicks far
    outside the ingested world report honestly.
    """
    xy, _elev, _src = _load()
    span = max(xy[:, 0].max() - xy[:, 0].min(), xy[:, 1].max() - xy[:, 1].min())
    return max(4000.0, 0.25 * span)


def is_available() -> bool:
    """True when the elevation lookup table loads cleanly."""
    try:
        _load()
        return True
    except Exception:
        return False


def lookup_elevation_by_intrinsic(x: float, y: float) -> Optional[dict]:
    """Return elevation (m) for the nearest intrinsic vertex.

    v37.2 coverage guard: returns None when (a) the lookup table is
    unavailable, or (b) the nearest boundary vertex lies outside the
    scale-aware coverage radius — i.e. the point is not on the ingested
    manifold and inventing a scalar for it would be dishonest.
    Otherwise a dict with the scalar, the nearest vertex distance and
    coverage stats.
    """
    try:
        xy, elev, source = _load()
    except Exception:
        return None
    d2 = (xy[:, 0] - x) ** 2 + (xy[:, 1] - y) ** 2
    idx = int(np.argmin(d2))
    dist = float(np.sqrt(d2[idx]))
    guard = coverage_radius()
    if dist > guard:
        return None  # outside the known manifold (scale-aware guard)
    return {
        "elevation_m": float(elev[idx]),
        "nearest_distance_units": dist,
        "coverage_radius_units": guard,
        "source": source,
    }


def stats() -> dict:
    """Coverage stats for transparency endpoints."""
    try:
        xy, elev, source = _load()
    except Exception as e:
        return {"available": False, "error": str(e)}
    return {
        "available": True,
        "samples": int(len(elev)),
        "min_elevation_m": float(elev.min()),
        "max_elevation_m": float(elev.max()),
        "mean_elevation_m": round(float(elev.mean()), 2),
        "above_sea_level": int((elev >= 0).sum()),
        "below_sea_level": int((elev < 0).sum()),
        "source": source,
        "no_coordinates": True,
    }
