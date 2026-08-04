"""Tests for the v10.2 ingestion pipeline — verifies no coordinates,
placeholder lengths, and solver-consumable output."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import pytest

from aethera.ingest.geometry import placeholder_length, parse_survey_csv, validate_survey_distance
from aethera.ingest.natural_earth import get_region_topology

def test_placeholder_length_is_1():
    assert placeholder_length() == 1.0

def test_validate_survey_distance_rejects_negative():
    with pytest.raises(ValueError):
        validate_survey_distance(-1.0)

def test_validate_survey_distance_rejects_zero():
    with pytest.raises(ValueError):
        validate_survey_distance(0.0)

def test_validate_survey_distance_accepts_positive():
    assert validate_survey_distance(42.5) == 42.5

def test_parse_survey_csv():
    csv = "A,B,100.0\nB,C,200.5\n"
    edges = parse_survey_csv(csv)
    assert len(edges) == 2
    assert edges[0] == ("A", "B", 100.0)
    assert edges[1] == ("B", "C", 200.5)

def test_parse_survey_csv_skips_comments():
    csv = "# comment\nA,B,100.0\n\n# another\nB,C,200.0\n"
    edges = parse_survey_csv(csv)
    assert len(edges) == 2

def test_topology_extraction_no_coordinates():
    """Verify that topology extraction returns ONLY adjacency — no coordinates."""
    polys = get_region_topology("Antarctica")
    assert len(polys) > 0
    for name, face_type, rings in polys:
        assert face_type in ("land", "ocean")
        for ring in rings:
            # Each ring is a list of point labels (strings), NOT coordinates.
            assert all(isinstance(label, str) for label in ring)
            assert len(ring) >= 3

def test_topology_extraction_returns_labels_not_coords():
    """CRITICAL: topology must return labels, not (lon,lat) tuples."""
    polys = get_region_topology("Antarctica")
    for _, _, rings in polys:
        for ring in rings:
            for label in ring:
                # Must be a string label, not a tuple of coordinates.
                assert isinstance(label, str)
                assert not isinstance(label, tuple)
                assert not isinstance(label, list)

def test_square_reconstruction_from_placeholders():
    """Given a square graph with 1.0 placeholder lengths, the solver
    must reconstruct a flat square."""
    from aethera.core import EdgeGraph, Scalar
    from aethera.agents import IntrinsicGeometer

    g = EdgeGraph()
    g.add_edge("A", "B", Scalar(1.0))  # placeholder
    g.add_edge("B", "C", Scalar(1.0))
    g.add_edge("C", "D", Scalar(1.0))
    g.add_edge("A", "D", Scalar(1.0))
    g.add_edge("A", "C", Scalar(1.41421356))  # diagonal
    g.add_edge("B", "D", Scalar(1.41421356))  # diagonal

    geo = IntrinsicGeometer()
    mf = geo.solve_2d(g)

    # The solver should reconstruct a flat square with low residual.
    assert mf.residual < 1e-6, f"residual too high: {mf.residual}"

    # All edges should be reconstructed to their input lengths.
    for a, b, target in [("A","B",1.0), ("A","C",1.41421356), ("A","D",1.0)]:
        d = mf.coords[a].dist(mf.coords[b])
        assert abs(d - target) < 1e-6, f"{a}-{b}: got {d}, want {target}"

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
