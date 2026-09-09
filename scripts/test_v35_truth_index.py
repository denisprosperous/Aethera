"""AETHERA v35.0 — local unit test for Feature 7 (Global Truth Index)."""
import sys
sys.path.insert(0, "/home/z/my-project/aethera/python")

from aethera.truth_index import compute_gti, get_all_physical_truth

print("=== Feature 7: Global Truth Index (local) ===")
result = compute_gti()
print(f"GTI:                    {result['gti']}%")
print(f"Total physical area:    {result['total_physical_area']:,.0f} km2")
print(f"Total legacy area:      {result['total_legacy_area']:,.0f} km2")
print(f"Total abs deviation:    {result['total_absolute_deviation_km2']:,.0f} km2")
print(f"Matched regions:        {result['matched_regions']}")
print(f"Formula:                {result['formula']}")
top = result["per_region"][:3]
for r in top:
    print(f"  top deviation: {r['region']}: physical {r['physical_area_km2']:,.0f} "
          f"vs legacy {r['legacy_area_km2']:,.0f} ({r['deviation_percent']}%)")

assert result["gti"] > 0, "GTI must be positive"
assert result["total_physical_area"] > 0
assert result["matched_regions"] > 100, "must match the full registry"
# Recompute manually per spec formula and compare.
pairs = [(r["physical_area_km2"], r["legacy_area_km2"]) for r in result["per_region"]]
manual = sum(abs(p - l) for p, l in pairs) / sum(p for p, _ in pairs) * 100
assert abs(manual - result["gti"]) < 0.01, f"formula mismatch: {manual} vs {result['gti']}"
print("PASS: GTI formula verified end-to-end")
print(f"INFO: headline GTI (AuthaGraph reference) = {result['gti']}% (spec expected range ~20-30%)")
assert 20.0 <= result["gti"] <= 30.0, "headline GTI must land in the spec-expected band"
pp = {p["projection"]: p["gti"] for p in result["per_projection"]}
print(f"INFO: per-projection GTIs: {pp}")
assert pp["Mercator"] > pp["AuthaGraph"], "Mercator must distort more than AuthaGraph"
print("ALL FEATURE 7 LOCAL CHECKS PASSED")
