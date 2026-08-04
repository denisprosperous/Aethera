"""Tests for the distortion analysis pipeline (v10.5)."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import pytest

from aethera.modules.compare_ingestion import (
    compute_distortion_metrics, compute_projection_area, REGIONS_PHYSICAL_TRUTH,
)
from aethera.modules.hall_of_shame import PROJECTIONS


def test_regions_data_has_100_plus():
    """Success criterion: at least 100 regions."""
    assert len(REGIONS_PHYSICAL_TRUTH) >= 100, f"Only {len(REGIONS_PHYSICAL_TRUTH)} regions"


def test_all_regions_have_4_tuple():
    """Each region must be (name, vertices, area, coloniser)."""
    for i, entry in enumerate(REGIONS_PHYSICAL_TRUTH):
        assert isinstance(entry, tuple), f"Entry {i} is not a tuple: {type(entry)}"
        assert len(entry) == 4, f"Entry {i} has {len(entry)} elements, expected 4"


def test_projection_area_computes_nonzero():
    """The projection area function must return a positive value for a valid polygon."""
    verts = [(-20, -35), (50, -35), (50, 37), (-20, 37)]  # Africa bounding box
    for name, proj_fn in PROJECTIONS.items():
        area = compute_projection_area(verts, proj_fn)
        assert area > 0, f"{name} projection returned zero area"


def test_distortion_metrics_computed():
    """The full pipeline must produce metrics for all regions × projections."""
    metrics, global_idx = compute_distortion_metrics()
    # 4 projections × 149 regions = 596 metrics.
    assert len(metrics) == len(REGIONS_PHYSICAL_TRUTH) * len(PROJECTIONS)
    # Global index must have all 4 projections.
    assert len(global_idx) == 4


def test_global_distortion_index_above_5_percent():
    """Success criterion: GDI > 5% for at least one projection."""
    metrics, global_idx = compute_distortion_metrics()
    max_gdi = max(idx["global_distortion_percent"] for idx in global_idx.values())
    assert max_gdi > 5.0, f"GDI too low: {max_gdi}"


def test_mercator_has_highest_gdi():
    """Mercator should have the highest GDI (massive polar inflation)."""
    metrics, global_idx = compute_distortion_metrics()
    mercator_gdi = global_idx["Mercator"]["global_distortion_percent"]
    for proj, idx in global_idx.items():
        if proj != "Mercator":
            assert mercator_gdi >= idx["global_distortion_percent"], \
                f"Mercator GDI ({mercator_gdi}) < {proj} GDI ({idx['global_distortion_percent']})"


def test_antarctica_is_top_deviation():
    """Antarctica should be among the top 3 deviations (Mercator inflates it massively)."""
    metrics, global_idx = compute_distortion_metrics()
    mercator_metrics = sorted(
        [m for m in metrics if m["projection"] == "Mercator"],
        key=lambda m: abs(m["relative_error_percent"]),
        reverse=True,
    )
    top3_names = [m["region_name"] for m in mercator_metrics[:3]]
    assert "Antarctica" in top3_names, f"Antarctica not in top 3: {top3_names}"


def test_distortion_categories_are_valid():
    """Each metric must have a valid distortion category."""
    metrics, _ = compute_distortion_metrics()
    valid = {"overreported", "underreported", "within_tolerance"}
    for m in metrics:
        assert m["distortion_category"] in valid, \
            f"Invalid category: {m['distortion_category']}"


def test_relative_error_sign():
    """Overreported regions should have negative relative error (legacy > physical)."""
    metrics, _ = compute_distortion_metrics()
    for m in metrics:
        if m["distortion_category"] == "overreported":
            assert m["relative_error_percent"] < 0, \
                f"{m['region_name']} overreported but error is positive"
        elif m["distortion_category"] == "underreported":
            assert m["relative_error_percent"] > 0, \
                f"{m['region_name']} underreported but error is negative"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
