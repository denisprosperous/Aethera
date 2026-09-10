"""AETHERA v35.0 — Feature 6: Territorial Integrity Verifier.

Given a nation's official territorial claim (a polygon in the intrinsic
manifold embedding), verify whether the claimed area matches AETHERA's
Physical Truth.

The polygon's true area is computed DIRECTLY ON THE MANIFOLD via Newell's
method (the magnitude of the summed cross products of consecutive vertex
pairs is the exact planar polygon area in the embedding space). No
projection, no datum, no lat/lon — the embedding produced by the solver
IS the ground truth representation (Axiom 2 · Intrinsic Emergence).
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Dict, List, Optional, Sequence

VALID_DEVIATION_THRESHOLD = 0.05  # 5% — a claim within 5% of truth is valid


def compute_area_on_manifold(polygon: Sequence[Sequence[float]], manifold=None) -> float:
    """Compute the area of a polygon on the intrinsic manifold.

    Newell's method for a 3D polygon:
        2A = | sum_i (v_i x v_{i+1}) |
    This is the exact planar polygon area in the embedding space and is
    invariant under the choice of starting vertex. If `manifold` is given
    and the polygon vertices are integer indices, they are resolved to the
    manifold coordinates of the corresponding regions (so callers may pass
    either explicit [[x, y, z], ...] vertices or region index loops).
    """
    verts: List[List[float]] = []
    for v in polygon:
        if manifold is not None and len(v) == 1 and isinstance(v[0], int) \
                and not isinstance(v[0], bool):
            # Index form [i]: resolve against the manifold coordinate list.
            coords = list(manifold.coords.values())
            idx = v[0]
            if idx < 0 or idx >= len(coords):
                raise ValueError(f"polygon vertex index {idx} out of range")
            p = coords[idx]
            verts.append([p.x, p.y, p.z])
        else:
            # Accept 2D [[x, y], ...] or 3D [[x, y, z], ...] claims.
            # Missing components are treated as planar (z = 0), consistent
            # with the intrinsic embedding where region coordinates live
            # in the z = 0 plane.
            x = float(v[0])
            y = float(v[1]) if len(v) > 1 else 0.0
            z = float(v[2]) if len(v) > 2 else 0.0
            verts.append([x, y, z])

    n = len(verts)
    if n < 3:
        raise ValueError("polygon must contain at least 3 vertices")

    nx = ny = nz = 0.0
    for i in range(n):
        a = verts[i]
        b = verts[(i + 1) % n]
        nx += a[1] * b[2] - a[2] * b[1]
        ny += a[2] * b[0] - a[0] * b[2]
        nz += a[0] * b[1] - a[1] * b[0]
    return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)


def get_official_area(nation: str) -> Optional[float]:
    """Official Physical Truth area of a nation (km²) from the registry."""
    try:
        from aethera.modules.physical_truth_manifold import get_region_area
        return get_region_area(nation)
    except Exception:
        return None


def generate_certificate(nation: str, true_area: float,
                         official_area: float) -> str:
    """Standalone cryptographic seal over the verification payload.

    (The API layer additionally issues a full HMAC-SHA256 Truth
    Certificate via issue_certificate(); this seal makes the report
    independently verifiable without platform keys.)
    """
    payload = {
        "nation": nation,
        "true_area_km2": round(true_area, 6),
        "official_area_km2": round(official_area, 6),
        "method": "newell_on_intrinsic_manifold",
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_claim(claimed_polygon: Sequence[Sequence[float]], nation: str,
                 manifold=None) -> Dict[str, Any]:
    """Verify a nation's territorial claim against Physical Truth.

    Returns true_area, official_area, deviation_percent, valid flag and a
    cryptographic seal. `valid` is True when the deviation is below 5%.
    """
    true_area = compute_area_on_manifold(claimed_polygon, manifold)
    official_area = get_official_area(nation)
    if not official_area:
        raise ValueError(f"Region '{nation}' not found in Physical Truth registry.")

    deviation = abs(true_area - official_area) / official_area
    return {
        "true_area": true_area,
        "official_area": official_area,
        # Explicit km-squared aliases (the embedding is km-scaled via
        # area-derived edge lengths, so the Newell area is already km²).
        "true_area_km2": true_area,
        "official_area_km2": official_area,
        "deviation_percent": deviation * 100.0,
        "valid": deviation < VALID_DEVIATION_THRESHOLD,
        "certificate": generate_certificate(nation, true_area, official_area),
        "method": "Newell's method on the intrinsic manifold embedding — "
                  "no projection, no datum, no coordinates consulted",
        "note": "The polygon area is computed in the solver embedding; the "
                "official area comes from the Physical Truth registry "
                "(absolute measured scalars only).",
    }
