"""Module 5D — Maritime Chokepoint Reconstructor."""
import math
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Chokepoint:
    name: str
    width_m: float
    depth_m: float
    draft_m: float
    beam_m: float

@dataclass
class NavigabilityReport:
    name: str
    tide_offset_m: float
    effective_width_m: float
    effective_depth_m: float
    navigable: bool
    max_vessel_beam_m: float
    max_vessel_draft_m: float
    navigability_index: float
    note: str

class MaritimeChokepoint:
    def __init__(self, safety_margin_m=50.0):
        self.safety = safety_margin_m
    def evaluate(self, cp, tide_offset_m=0.0):
        ed = cp.depth_m + tide_offset_m
        ew = cp.width_m
        md = ed - self.safety
        mb = ew
        nav = md >= cp.draft_m and mb >= cp.beam_m
        di = min(1.0, max(0.0, md / max(cp.draft_m, 1e-12))) * min(1.0, mb / max(cp.beam_m, 1e-12))
        note = f"{cp.name}: tide {tide_offset_m:+.2f}m, eff depth {ed:.2f}m. {'Navigable' if nav else 'NOT navigable'}."
        return NavigabilityReport(cp.name, tide_offset_m, ew, ed, nav, mb, md, di, note)
    def evaluate_over_tide_range(self, cp, tide_range):
        return [self.evaluate(cp, t) for t in tide_range]
    def shortest_transit_path(self, chokes, tide_offset_m):
        nav = [c for c in chokes if self.evaluate(c, tide_offset_m).navigable]
        if not nav: return ([], 0.0)
        return ([c.name for c in nav], sum(c.width_m for c in nav))


# ---------------------------------------------------------------------------
# AETHERA v35.0 — Feature 5: Maritime Arbitration Engine (intrinsic median
# line). The absolute median line between two nations is computed on the
# INTRINSIC MANIFOLD — no sphere, no datum, no lat/lon, no WGS84. The
# coastline of each nation is discretized from the solved manifold embedding:
# the nation's vertex plus the midpoints of its boundary edges to every
# graph neighbour. The median line is the discrete equidistant set between
# the two coastlines (the Voronoi boundary on the manifold).
# ---------------------------------------------------------------------------

from math import sqrt
from typing import Tuple


def _midpoint(p, q) -> Tuple[float, float, float]:
    return ((p.x + q.x) / 2.0, (p.y + q.y) / 2.0, (p.z + q.z) / 2.0)


def _dist_point_tuple(p, t: Tuple[float, float, float]) -> float:
    return sqrt((p.x - t[0]) ** 2 + (p.y - t[1]) ** 2 + (p.z - t[2]) ** 2)


def get_coastline(nation: str, manifold, graph=None) -> list:
    """Discrete coastline of `nation` on the intrinsic manifold.

    The nation is a single solved vertex; its boundary is represented by
    the vertex itself plus the midpoints of its edges to every adjacent
    region in the Physical Truth edge graph. Purely intrinsic — derived
    from the solver embedding, never from geographic coordinates.
    """
    if nation not in manifold.coords:
        raise KeyError(f"Region '{nation}' is not part of the solved manifold.")
    own = manifold.coords[nation]
    points = [(own.x, own.y, own.z)]

    if graph is not None:
        neighbours = set()
        for e in graph.edges:
            if e.a == nation:
                neighbours.add(e.b)
            elif e.b == nation:
                neighbours.add(e.a)
        for nb in sorted(neighbours):
            q = manifold.coords.get(nb)
            if q is not None:
                points.append(_midpoint(own, q))
    return points


def equidistant_set(coast_a: list, coast_b: list, rel_tol: float = 0.05) -> list:
    """Discrete median line: the equidistant set between two coastlines.

    A point m (midpoint of a cross-pair p∈A, q∈B) lies on the median line
    when its distances to both coastlines are equal within `rel_tol`
    (discrete Voronoi boundary). The resulting points are ordered along
    their principal direction so the output forms a coherent polyline.
    """
    if not coast_a or not coast_b:
        return []

    def dmin(t, coast):
        best = None
        for p in coast:
            d = _dist_point_tuple(p, t) if hasattr(p, "x") else sqrt(
                (p[0] - t[0]) ** 2 + (p[1] - t[1]) ** 2 + (p[2] - t[2]) ** 2)
            if best is None or d < best:
                best = d
        return best if best is not None else 0.0

    candidates = []
    for p in coast_a:
        px, py, pz = (p.x, p.y, p.z) if hasattr(p, "x") else p
        for q in coast_b:
            qx, qy, qz = (q.x, q.y, q.z) if hasattr(q, "x") else q
            m = ((px + qx) / 2.0, (py + qy) / 2.0, (pz + qz) / 2.0)
            da = dmin(m, coast_a)
            db = dmin(m, coast_b)
            scale = max(da, db, 1e-12)
            if abs(da - db) <= rel_tol * scale:
                candidates.append(m)

    # Deduplicate near-identical points (grid rounding).
    deduped = []
    for m in candidates:
        if not any(
            (m[0] - u[0]) ** 2 + (m[1] - u[1]) ** 2 + (m[2] - u[2]) ** 2
            < 1e-12 for u in deduped
        ):
            deduped.append(m)

    # Order along the principal direction (variance-maximising axis).
    if len(deduped) > 1:
        n = len(deduped)
        mx = sum(p[0] for p in deduped) / n
        my = sum(p[1] for p in deduped) / n
        mz = sum(p[2] for p in deduped) / n
        var = [0.0, 0.0, 0.0]
        for p in deduped:
            var[0] += (p[0] - mx) ** 2
            var[1] += (p[1] - my) ** 2
            var[2] += (p[2] - mz) ** 2
        axis = max(range(3), key=lambda i: var[i])
        deduped.sort(key=lambda p: p[axis])
    return deduped


def compute_median_line(nation_a: str, nation_b: str, manifold, graph=None,
                        max_points: int = 512) -> dict:
    """Compute the absolute median line between two nations on the manifold.

    Returns a dict with the ordered median line coordinates, coastline
    provenance and the intrinsic length of the line (manifold units).
    If more than `max_points` points qualify, the line is uniformly
    subsampled for transport (the full count is reported).
    """
    if graph is None:
        from aethera.modules.physical_truth_manifold import (
            build_physical_truth_edge_graph,
        )
        graph, _areas = build_physical_truth_edge_graph()

    coast_a = get_coastline(nation_a, manifold, graph)
    coast_b = get_coastline(nation_b, manifold, graph)
    median_line = equidistant_set(coast_a, coast_b)

    length_units = 0.0
    for i in range(1, len(median_line)):
        length_units += sqrt(sum(
            (median_line[i][k] - median_line[i - 1][k]) ** 2 for k in range(3)
        ))

    full_count = len(median_line)
    if max_points and full_count > max_points:
        step = full_count / max_points
        median_line = [median_line[int(i * step)] for i in range(max_points)]

    adjacent = any(
        {e.a, e.b} == {nation_a, nation_b} for e in graph.edges
    )

    return {
        "coastline_a_points": len(coast_a),
        "coastline_b_points": len(coast_b),
        "median_line": [[round(float(p[0]), 6), round(float(p[1]), 6),
                         round(float(p[2]), 6)] for p in median_line],
        "median_line_points": full_count,
        "median_line_returned": len(median_line),
        "median_line_length_units": round(float(length_units), 6),
        "adjacent_on_manifold": adjacent,
    }
