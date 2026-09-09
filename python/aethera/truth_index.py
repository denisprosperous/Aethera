"""AETHERA v35.0 — Feature 7: Global Truth Index (GTI).

The GTI measures how far the world's legacy maps deviate, in aggregate,
from AETHERA's Physical Truth:

    GTI = sum(|physical_area - legacy_area|) / sum(physical_area) * 100

The legacy reference is the Mercator projection (the canonical legacy
world map): per-region legacy areas come from the platform's distortion
engine, which computes each region's projected area from its measured
boundary geometry. Physical areas come from the Physical Truth registry
(absolute measured scalars only).
"""
from __future__ import annotations

from typing import Any, Dict, List

DEFAULT_LEGACY_PROJECTION = "AuthaGraph"


def get_all_physical_truth() -> Dict[str, float]:
    """All Physical Truth registry areas, km², keyed by region name."""
    from aethera.modules.physical_truth_manifold import REGIONS_PHYSICAL_TRUTH
    out: Dict[str, float] = {}
    for entry in REGIONS_PHYSICAL_TRUTH:
        name, _verts, area_true, _coloniser = entry
        out[name] = float(area_true)
    return out


def get_all_legacy_areas(projection: str = DEFAULT_LEGACY_PROJECTION) -> Dict[str, float]:
    """All legacy (projected) areas, km², keyed by region name.

    Uses the platform distortion engine: each region's boundary geometry is
    run through the requested projection and scaled to km², exactly as the
    Consensus Hall of Shame does. The default reference is AuthaGraph —
    the most area-faithful legacy world map — so the GTI measures how far
    even the BEST legacy cartography deviates from Physical Truth.
    """
    from aethera.modules.compare_ingestion import compute_distortion_metrics
    metrics, _global_idx = compute_distortion_metrics()
    out: Dict[str, float] = {}
    for m in metrics:
        if m.get("projection") == projection:
            out[m["region_name"]] = float(m["area_legacy_m2"]) / 1e6  # m² → km²
    return out


def compute_gti(projection: str = DEFAULT_LEGACY_PROJECTION) -> Dict[str, Any]:
    """Compute the Global Truth Index per the v35.0 spec formula.

    Returns the GTI plus the physical/legacy totals, the per-region
    absolute deviations and the matched region count.
    """
    physical = get_all_physical_truth()
    legacy = get_all_legacy_areas(projection)

    total_physical = 0.0
    total_legacy = 0.0
    total_abs_dev = 0.0
    per_region: List[Dict[str, Any]] = []
    for name, p in physical.items():
        if name not in legacy:
            continue
        l = legacy[name]
        dev = abs(p - l)
        total_physical += p
        total_legacy += l
        total_abs_dev += dev
        per_region.append({
            "region": name,
            "physical_area_km2": round(p, 3),
            "legacy_area_km2": round(l, 3),
            "absolute_deviation_km2": round(dev, 3),
            "deviation_percent": round((dev / p * 100.0) if p else 0.0, 4),
        })

    gti = (total_abs_dev / total_physical * 100.0) if total_physical else 0.0
    per_region.sort(key=lambda r: r["absolute_deviation_km2"], reverse=True)

    # Full transparency (Axiom 5): report the GTI for EVERY supported
    # legacy map, not just the reference projection.
    from aethera.modules.compare_ingestion import compute_distortion_metrics
    _metrics, global_idx = compute_distortion_metrics()
    per_projection = [
        {
            "projection": proj,
            "gti": round(float(g["global_distortion_percent"]), 4),
            "total_physical_area": round(float(g["total_physical_area_m2"]) / 1e6, 3),
            "total_legacy_area": round(float(g["total_legacy_area_m2"]) / 1e6, 3),
        }
        for proj, g in sorted(global_idx.items())
    ]

    return {
        "gti": round(gti, 4),
        "total_physical_area": round(total_physical, 3),
        "total_legacy_area": round(total_legacy, 3),
        "total_absolute_deviation_km2": round(total_abs_dev, 3),
        "matched_regions": len(per_region),
        "projection": projection,
        "formula": "GTI = Σ|physical − legacy| / Σphysical × 100",
        "per_projection": per_projection,
        "per_region": per_region,
        "note": "Reference legacy map: AuthaGraph (most area-faithful world "
                "map) — the GTI is how far even the best legacy cartography "
                "deviates from Physical Truth. Mercator's own GTI is far "
                "worse; every projection is reported in per_projection. "
                "No coordinates are consumed by AETHERA itself.",
    }
