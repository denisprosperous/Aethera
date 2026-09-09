"""AETHERA v35.0 — local unit tests for Features 5 & 6.

Feature 5: maritime median line between two nations on the intrinsic manifold.
Feature 6: territorial verification of a KNOWN polygon (square whose Newell
           area exactly equals the official area must verify valid).
"""
import sys
sys.path.insert(0, "/home/z/my-project/aethera/python")

import math

print("=== Feature 5 & 6 local tests ===")

# ---- Feature 6 first (no solver needed for the pure math check) ----
from aethera.modules.territory import compute_area_on_manifold, verify_claim

# Square of side 3000 -> area 9,000,000 (km²-equivalent manifold units).
side = 3000.0
cx, cy = 100.0, -50.0
sq = [
    [cx - side / 2, cy - side / 2, 0.0],
    [cx + side / 2, cy - side / 2, 0.0],
    [cx + side / 2, cy + side / 2, 0.0],
    [cx - side / 2, cy + side / 2, 0.0],
]
area = compute_area_on_manifold(sq)
print(f"Newell area of {side:.0f}x{side:.0f} square: {area:,.1f} (expected 9,000,000)")
assert abs(area - 9_000_000.0) < 1e-6, "Newell area wrong"

# Skewed non-convex order-invariance check: reverse the vertex order.
area_rev = compute_area_on_manifold(sq[::-1])
assert abs(area_rev - 9_000_000.0) < 1e-6, "vertex order invariance broken"
print("PASS: Newell area exact + order invariant")

# Full verify_claim against the registry (needs the manifold for spec
# signature compliance; registry lookup needs REGIONS_PHYSICAL_TRUTH).
from aethera.modules.physical_truth_manifold import REGIONS_PHYSICAL_TRUTH, solve_physical_truth_manifold

sample_name, _verts, sample_area, _col = REGIONS_PHYSICAL_TRUTH[0]
print(f"Registry sample: {sample_name} official area {sample_area:,.0f} km2")

# Known polygon: square centred on origin with area == official area.
k = math.sqrt(sample_area)
known_poly = [
    [-k / 2, -k / 2, 0.0], [k / 2, -k / 2, 0.0],
    [k / 2, k / 2, 0.0], [-k / 2, k / 2, 0.0],
]

# Inflated polygon: 20% larger -> must be invalid.
k2 = k * math.sqrt(1.2)
inflated_poly = [
    [-k2 / 2, -k2 / 2, 0.0], [k2 / 2, -k2 / 2, 0.0],
    [k2 / 2, k2 / 2, 0.0], [-k2 / 2, k2 / 2, 0.0],
]

print("Solving physical truth manifold (SMACOF)...")
mf, _area_map = solve_physical_truth_manifold()
print(f"  manifold solved: residual={mf.residual:.6f}, regions={len(mf.coords)}")

r_valid = verify_claim(known_poly, sample_name, mf)
print(f"verify_claim(known):  true={r_valid['true_area']:,.1f} "
      f"official={r_valid['official_area']:,.1f} "
      f"dev={r_valid['deviation_percent']:.6f}% valid={r_valid['valid']}")
assert r_valid["valid"] is True, "known polygon must verify valid"
assert abs(r_valid["deviation_percent"]) < 1e-6
assert r_valid["certificate"].startswith("sha256:")

r_invalid = verify_claim(inflated_poly, sample_name, mf)
print(f"verify_claim(inflated): dev={r_invalid['deviation_percent']:.2f}% valid={r_invalid['valid']}")
assert r_invalid["valid"] is False, "inflated polygon must be invalid"
print("PASS: Feature 6 territorial verification")

# ---- Feature 5: median line ----
from aethera.modules.physical_truth_manifold import build_physical_truth_edge_graph
from aethera.modules.maritime import get_coastline, equidistant_set, compute_median_line

graph, _areas = build_physical_truth_edge_graph()
# Pick an adjacent pair from the graph.
e0 = graph.edges[0]
a, b = e0.a, e0.b
print(f"Adjacent test pair: {a} <-> {b}")

res = compute_median_line(a, b, mf, graph)
print(f"coastline sizes: {res['coastline_a_points']} / {res['coastline_b_points']}")
print(f"median line: {res['median_line_points']} points, length {res['median_line_length_units']:.3f} units")
print(f"first point: {res['median_line'][0] if res['median_line'] else None}")
assert res["median_line_points"] >= 1, "median line must be non-empty for adjacent nations"
assert res["adjacent_on_manifold"] is True

# Equidistance property: each median point is equidistant (within tol) to
# both coastlines.
coast_a = get_coastline(a, mf, graph)
coast_b = get_coastline(b, mf, graph)
for m in res["median_line"][:10]:
    da = min(math.dist(m, (p.x, p.y, p.z) if hasattr(p, 'x') else p) for p in coast_a)
    db = min(math.dist(m, (p.x, p.y, p.z) if hasattr(p, 'x') else p) for p in coast_b)
    assert abs(da - db) <= 0.05 * max(da, db, 1e-12), f"equidistance broken: {da} vs {db}"
print("PASS: median points equidistant from both coastlines")

# Unknown nation must raise KeyError.
try:
    compute_median_line("Atlantis", b, mf, graph)
    raise AssertionError("Atlantis must not resolve")
except KeyError:
    print("PASS: unknown nation rejected")
print("ALL FEATURE 5+6 LOCAL CHECKS PASSED")
