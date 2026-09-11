"""Intrinsic elevation lookup (v39.0) - ETOPO1 in the display frame.

Serves POST /api/elevation: a display-frame point (x, y) is matched to
the nearest ETOPO1 sample (mapped into the same display frame at
ingestion time by the disclosed lon/lat -> display affine) and its
bathymetric/topographic elevation in metres is returned, referenced to
sea level (Axiom 5 disclosure: the samples carry the disclosed affine's
residual, ~hundreds of km worst case).

Pure numpy KD-tree over the npz artifact - serverless-safe, no database
at query time, no coordinates in the platform's solver chain (the
artifact is a disclosed ingestion product).
"""

import math
import os
from functools import lru_cache

import numpy as np

ARTIFACT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "data", "elevation_artifact.npz"))

SOURCE = "ETOPO1_GLOBAL"
REFERENCE = "sea_level"


@lru_cache(maxsize=1)
def _load():
    if not os.path.exists(ARTIFACT):
        return None, None, None
    with np.load(ARTIFACT) as z:
        xs = z["x"]
        ys = z["y"]
        el = z["elevation_m"]
    pts = np.stack([xs, ys], axis=1)
    from scipy.spatial import cKDTree
    tree = cKDTree(pts)
    return tree, el, (float(xs.min()), float(xs.max()),
                      float(ys.min()), float(ys.max()))


def world_span():
    bbox = _load()[2]
    if bbox is None:
        return 0.0
    return math.hypot(bbox[1] - bbox[0], bbox[3] - bbox[2])


def coverage_guard():
    """Scale-aware coverage guard (v37.2 spec): 25% of world span,
    minimum 4000 display units."""
    return max(4000.0, world_span() * 0.25)


def lookup_elevation_by_intrinsic(x: float, y: float):
    """Elevation (m) at a display-frame point, or None outside coverage."""
    tree, values, _bbox = _load()
    if tree is None:
        return None
    dist, idx = tree.query([float(x), float(y)], k=1)
    if dist > coverage_guard():
        return None
    return float(values[idx])


def sample_count():
    tree, values, _ = _load()
    return 0 if values is None else int(len(values))
