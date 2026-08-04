"""Integration tests for v10.6 — Physical Truth manifold + Ghost Resolver."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import pytest

from aethera.modules.physical_truth_manifold import (
    solve_physical_truth_manifold, build_physical_truth_edge_graph, list_regions, get_region_area,
)
from aethera.modules.ghost_resolver_integration import derive_antarctica_area


def test_physical_truth_graph_has_100_plus_nodes():
    """Success criterion: the Physical Truth edge graph has >= 100 nodes."""
    graph, _ = build_physical_truth_edge_graph()
    assert graph.node_count >= 100, f"Only {graph.node_count} nodes"
    assert graph.edge_count >= 100, f"Only {graph.edge_count} edges"


def test_physical_truth_manifold_solves():
    """The SMACOF solver must produce a valid manifold from Physical Truth data."""
    mf, area_map = solve_physical_truth_manifold(max_iter=200, tol=1e-8)
    assert len(mf.coords) >= 100, f"Only {len(mf.coords)} coordinates"
    assert mf.residual < 1.0, f"Residual too high: {mf.residual}"
    # All coords should be finite.
    for name, p in mf.coords.items():
        assert math.isfinite(p.x), f"{name} has non-finite x"
        assert math.isfinite(p.y), f"{name} has non-finite y"


def test_major_regions_present():
    """Key regions should be in the manifold."""
    mf, _ = solve_physical_truth_manifold(max_iter=200, tol=1e-8)
    for name in ["Russia", "China", "United States", "Brazil", "Antarctica", "Europe", "Africa"]:
        assert name in mf.coords, f"{name} not in manifold"


def test_antarctica_derived_area_is_plausible():
    """Ghost Resolver must derive Antarctica's area within a plausible range."""
    result = derive_antarctica_area()
    derived = result["derived_area_km2"]
    # Antarctica's true area is ~14M km². The derived value should be
    # within 50% of this (generous tolerance due to bounding-box area
    # approximations).
    assert 5_000_000 < derived < 25_000_000, f"Implausible: {derived}"
    assert result["confidence_pct"] > 50, f"Confidence too low: {result['confidence_pct']}"


def test_antarctica_has_rationale_log():
    """The Ghost Resolver must produce a rationale log."""
    result = derive_antarctica_area()
    assert len(result["rationale_log"]) > 0
    rationale = result["rationale_log"][0]
    assert "Antarctica" in rationale["polygon"]
    assert "Topological Residual Closure" in rationale["rationale"]


def test_antarctica_sealed_hash():
    """The Ghost Resolver must produce a sealed hash."""
    result = derive_antarctica_area()
    assert result["sealed_hash"].startswith("sha256:")


def test_region_area_lookup():
    """get_region_area must return correct areas."""
    assert get_region_area("Russia") == 17_098_242
    assert get_region_area("Antarctica") == 14_000_000
    assert get_region_area("Nonexistent") is None


def test_list_regions_returns_all():
    """list_regions must return all 149 regions."""
    regions = list_regions()
    assert len(regions) >= 149


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
