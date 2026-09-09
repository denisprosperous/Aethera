"""AETHERA v35.0 — Feature 4: Ghost Resolver with Geometric Red Flags.

When a region has a NULL area, the Ghost Resolver (Agent 0) derives its
area via topological residual closure against the global enclosure total.
If the derived area deviates more than 5% from the official claimed value,
the region is flagged "CENSORED" and a Geometric Red Flag report is
issued containing:

    * the derived area,
    * the official (claimed) area,
    * the deviation percentage,
    * a cryptographic seal (SHA-256 over the canonical report payload),
    * the Rationale Engine log.

This module is a transparency tool. It computes ONLY from absolute scalar
inputs (areas + adjacency). No coordinates, no projections, no datums —
Axiom 3 (Extrinsic Agnosticism) and Axiom 4 (Zero Bias).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from aethera.agents.ghost import GhostResolver, Polygon as GhostPolygon
from aethera.core import Scalar

CENSOR_THRESHOLD = 0.05  # 5% deviation triggers the CENSORED flag


@dataclass
class GhostRegion:
    """Normalized region record consumed by resolve_with_red_flag."""
    name: str
    area_known: Optional[float]          # NULL when the area is censored/unknown
    claimed_area: Optional[float]        # officially claimed value (km²)
    neighbours: List[str] = field(default_factory=list)
    security_level: str = "N/A"
    # Filled by the resolver:
    area_derived: Optional[float] = None
    flag: Optional[str] = None
    red_flag_report: Optional[Dict[str, Any]] = None


def _report_seal(payload: Dict[str, Any]) -> str:
    """Cryptographic seal: SHA-256 over the canonical (sorted-keys) JSON."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_report(region: GhostRegion, global_total: float,
                    enclosure: str = "Earth") -> Dict[str, Any]:
    """Geometric Red Flag report for a single CENSORED region."""
    derived = float(region.area_derived or 0.0)
    official = float(region.area_known or region.claimed_area or 0.0)
    deviation = abs(derived - official) / official if official else 0.0
    log_entry = (
        f"RationaleEngine: region '{region.name}' had NULL area; derived "
        f"{derived:,.0f} km² via Topological Residual Closure against "
        f"{enclosure} total {global_total:,.0f} km² using adjacency "
        f"[{', '.join(region.neighbours) if region.neighbours else 'none'}]; "
        f"official claim {official:,.0f} km² deviates {deviation * 100:.2f}% "
        f"(> {CENSOR_THRESHOLD * 100:.0f}% threshold) — flagged CENSORED."
    )
    payload = {
        "region": region.name,
        "derived_area_km2": round(derived, 3),
        "official_area_km2": round(official, 3),
        "deviation_percent": round(deviation * 100.0, 4),
        "flag": "CENSORED",
        "security_level": region.security_level,
        "global_total_km2": round(float(global_total), 3),
        "rationale": log_entry,
    }
    return {
        **payload,
        "seal": _report_seal(payload),
        "rationale_log": [log_entry],
        "note": "Geometric Red Flag — transparency tool for public oversight. "
                "Computed from absolute scalars only; no coordinates involved.",
    }


def resolve_with_red_flag(polygons: List[Dict[str, Any]],
                          global_total: float,
                          enclosure: str = "Earth") -> List[GhostRegion]:
    """Resolve NULL-area polygons via topological closure and flag CENSORED.

    Parameters
    ----------
    polygons : list of dicts with keys {name, area (NULL if unknown),
               claimed_area, neighbours, security_level}.
    global_total : the global enclosure area (km²) used as the closure sum.

    Returns the list of GhostRegion records; every region whose derived
    area deviates more than 5% from its official claimed value carries
    flag == "CENSORED" and a full red_flag_report dict.
    """
    ghost_polygons: List[GhostPolygon] = []
    for p in polygons:
        area = Scalar(p["area"]) if p.get("area") is not None else None
        claimed = Scalar(p["claimed_area"]) if p.get("claimed_area") is not None else None
        ghost_polygons.append(GhostPolygon(
            name=p["name"],
            area=area,
            neighbours=p.get("neighbours", []),
            claimed_area=claimed,
            security_level=p.get("security_level", "N/A"),
        ))

    resolver = GhostResolver()
    report = resolver.solve(ghost_polygons, enclosure, Scalar(global_total))
    derived_map = {p.name: (p.area.to_f64() if p.area else 0.0)
                   for p in report.polygons}

    regions: List[GhostRegion] = []
    for p in polygons:
        known = p.get("area")
        claimed = p.get("claimed_area")
        reg = GhostRegion(
            name=p["name"],
            area_known=known,
            claimed_area=claimed,
            neighbours=p.get("neighbours", []),
            security_level=p.get("security_level", "N/A"),
            area_derived=derived_map.get(p["name"]),
        )
        # Deviation check against the official claimed value.
        reference = claimed if claimed is not None else known
        if reg.area_derived is not None and reference:
            deviation = abs(reg.area_derived - reference) / abs(reference)
            if deviation > CENSOR_THRESHOLD:
                reg.flag = "CENSORED"
                reg.area_known = reference
                reg.red_flag_report = generate_report(reg, global_total, enclosure)
        regions.append(reg)
    return regions
