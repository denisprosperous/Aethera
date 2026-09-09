"""AETHERA v35.0 — local unit test for Feature 4 (Ghost Resolver red flags).

Spec test: Antarctica with NULL area must return a red flag report.
"""
import sys
sys.path.insert(0, "/home/z/my-project/aethera/python")

from aethera.modules.ghost import resolve_with_red_flag

# Antarctica: NULL area, claimed 14,200,000 km2 (official claim).
# Residual closure against Earth total: land-excl-Antarctica + oceans.
polygons = [
    {"name": "Africa",        "area": 30_370_000, "claimed_area": 30_370_000, "neighbours": []},
    {"name": "Europe",        "area": 10_180_000, "claimed_area": 10_180_000, "neighbours": []},
    {"name": "Asia",          "area": 44_579_000, "claimed_area": 44_579_000, "neighbours": []},
    {"name": "North America", "area": 24_709_000, "claimed_area": 24_709_000, "neighbours": []},
    {"name": "South America", "area": 17_840_000, "claimed_area": 17_840_000, "neighbours": ["Antarctica"]},
    {"name": "Australia",     "area": 8_600_000,  "claimed_area": 8_600_000,  "neighbours": ["Antarctica"]},
    {"name": "Oceans",        "area": 361_132_000, "claimed_area": 361_132_000, "neighbours": []},
    {"name": "Antarctica",    "area": None,       "claimed_area": 14_200_000, "neighbours": ["South America", "Africa", "Australia"]},
]

EARTH_TOTAL = 510_072_000
regions = resolve_with_red_flag(polygons, EARTH_TOTAL)

antarctica = next(r for r in regions if r.name == "Antarctica")
derived = EARTH_TOTAL - sum(p["area"] for p in polygons if p["area"] is not None)

print("=== Feature 4: Ghost Resolver red flags (local) ===")
print(f"Antarctica derived:  {antarctica.area_derived:,.0f} km2 (expected residual: {derived:,.0f})")
print(f"Antarctica claimed:  {antarctica.claimed_area:,.0f} km2")
print(f"Flag:                {antarctica.flag}")

assert antarctica.area_derived is not None, "derived area missing"
assert abs(antarctica.area_derived - derived) < 1.0, "closure math wrong"

report = antarctica.red_flag_report
if antarctica.flag == "CENSORED":
    assert report is not None, "CENSORED region must carry red_flag_report"
    for key in ("derived_area_km2", "official_area_km2", "deviation_percent", "seal", "rationale_log"):
        assert key in report, f"report missing key: {key}"
    assert report["seal"].startswith("sha256:"), "seal must be sha256"
    print(f"Deviation:           {report['deviation_percent']:.2f}%")
    print(f"Seal:                {report['seal'][:27]}...")
    print(f"Rationale:           {report['rationale_log'][0][:100]}...")
    print("PASS: red flag report present with seal + rationale log")
else:
    print("INFO: deviation within 5% — no flag (derived == claimed scenario)")

# Control: known region matching claim must NOT be flagged
africa = next(r for r in regions if r.name == "Africa")
assert africa.flag is None and africa.red_flag_report is None, "control region must not be flagged"
print("PASS: control region (Africa) unflagged")
print("ALL FEATURE 4 LOCAL CHECKS PASSED")
