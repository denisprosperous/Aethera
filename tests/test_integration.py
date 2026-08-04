"""AETHERA integration tests."""
import sys, math
sys.path.insert(0, "/home/z/my-project/aethera-core/python")
import pytest
from aethera import EdgeGraph, Scalar
from aethera.agents import (
    GhostResolver, IntrinsicGeometer, AcifNavigator, AlienGeometer, DynamicsModule,
)
from aethera.agents.ghost import Polygon as GhostPolygon
from aethera.agents.acif import AcifSnapshot
from aethera.agents.dynamics import (
    ForceFieldConfig, simulate_particle, inertial_field, inverse_square_field, uniform_field,
)
from aethera.modules import (
    TransparencyComparator, StrainVisualizer, AnomalyDaemon,
    MaritimeChokepoint, HallOfShame, TerraformationSimulator, StellarPositioning,
)
from aethera.modules.transparency import RangeClaim
from aethera.modules.seismic import SeismicEvent
from aethera.modules.maritime import Chokepoint
from aethera.modules.hall_of_shame import Polygon as HSPolygon
from aethera.modules.terraformation import VolumeTransfer
from aethera.modules.stellar import QuasarObservation

def test_smacof_flat_square():
    g = EdgeGraph()
    g.add_edge("A","B", Scalar(1.0)); g.add_edge("B","C", Scalar(1.0))
    g.add_edge("C","D", Scalar(1.0)); g.add_edge("A","D", Scalar(1.0))
    g.add_edge("A","C", Scalar(1.41421356)); g.add_edge("B","D", Scalar(1.41421356))
    mf = IntrinsicGeometer().solve_2d(g)
    assert mf.residual < 1e-6
    for a, b, t in [("A","B",1.0),("A","C",1.41421356),("A","D",1.0)]:
        assert abs(mf.coords[a].dist(mf.coords[b]) - t) < 1e-6

def test_ghost_red_flag():
    polys = [
        GhostPolygon(name="G", area=Scalar(100.0)),
        GhostPolygon(name="A", area=Scalar(30.0)),
        GhostPolygon(name="B", area=Scalar(40.0)),
        GhostPolygon(name="C", area=None, claimed_area=Scalar(0.1)),
    ]
    rep = GhostResolver().solve(polys, "G", Scalar(100.0))
    c = next(p for p in rep.polygons if p.name == "C")
    assert abs(c.area.to_f64() - 30.0) < 0.1
    assert len(rep.red_flags) >= 1

def test_alien_flat():
    g = EdgeGraph()
    g.add_edge("A","B", Scalar(1.0)); g.add_edge("B","C", Scalar(1.0))
    g.add_edge("C","D", Scalar(1.0)); g.add_edge("A","D", Scalar(1.0))
    g.add_edge("A","C", Scalar(1.41421356)); g.add_edge("B","D", Scalar(1.41421356))
    _, r = AlienGeometer().analyse(g)
    assert r.shape == "Flat"

def test_transparency():
    tc = TransparencyComparator()
    c = tc.evaluate(RangeClaim("A","B",(0,0,0),(10000,0,0),15000.0))
    assert c.is_exaggerated

def test_strain_visualizer():
    events = [SeismicEvent(f"S{i}", i*10.0) for i in range(4)]
    sv = StrainVisualizer()
    sm = sv.build_strain_manifold(events)
    rv = sv.visualize_minimal_rupture_path(sm)
    assert len(rv.path) >= 2
    assert "visualization tool" in rv.disclaimer.lower()

def test_anomaly_local():
    s0 = AcifSnapshot(0.0, [("A","B",1000.0),("C","D",2000.0)])
    s1 = AcifSnapshot(86400.0, [("A","B",1000.05),("C","D",2000.0)])
    alerts = AnomalyDaemon(1.0).run([s0, s1])
    assert len(alerts) == 1

def test_maritime():
    cp = Chokepoint("Strait", 33000, 40, 20, 68)
    mc = MaritimeChokepoint(10)
    assert mc.evaluate(cp, 0.0).navigable
    assert not mc.evaluate(cp, -15.0).navigable

def test_hall_of_shame():
    polys = [
        HSPolygon("A", [(-20,-35),(50,-35),(50,37),(-20,37)], 30_370_000, False),  # AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
        HSPolygon("E", [(-10,36),(40,36),(40,71),(-10,71)], 10_180_000, True),  # AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
    ]
    scores = HallOfShame(polys).all_scores()
    assert len(scores) == 4

def test_terraformation():
    polys = [
        HSPolygon("Greenland", [(-50,60),(-20,60),(-20,80),(-50,80)], 2_166_086, False),  # AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
        HSPolygon("Ocean", [(-180,-90),(180,-90),(180,90),(-180,90)], 361_000_000, False),  # AETHERA-GUARD: ALLOW DOCUMENTATION (measured area)
    ]
    rep = TerraformationSimulator(polys).simulate([VolumeTransfer("Greenland","Ocean",2_850_000)])  # AETHERA-GUARD: ALLOW DOCUMENTATION (Greenland ice volume estimate)
    g = next(c for c in rep.coastline_changes if c.nation == "Greenland")
    assert g.area_change_km2 < 0

def test_stellar():
    obs = [QuasarObservation(f"Q{i}", 0.001*i, 8_000_000) for i in range(4)]  # AETHERA-GUARD: ALLOW DOCUMENTATION (test baseline)
    pos = StellarPositioning().solve(obs)
    assert pos.reference_count == 4

def test_agent7_mode_a():
    g = EdgeGraph()
    g.add_edge("A","B", Scalar(1.0)); g.add_edge("B","C", Scalar(1.0))
    g.add_edge("A","C", Scalar(5.0)); g.add_edge("A","D", Scalar(1.0))
    g.add_edge("D","C", Scalar(1.0)); g.add_edge("A","E", Scalar(1.0))
    g.add_edge("E","D", Scalar(1.0)); g.add_edge("B","E", Scalar(1.0))
    g.add_edge("B","D", Scalar(1.0))
    mf = IntrinsicGeometer().solve_2d(g)
    r = DynamicsModule().shortest_path(g, mf, "A", "C")
    assert r.path_length < 3.0
    assert "Targeting solutions" in r.note

def test_agent7_mode_b_inertial():
    r = simulate_particle((0,0,0), (1,0,0), inertial_field(),
        ForceFieldConfig(dt=0.1, t_max=10.0, force_law_note="inertial"))
    assert abs(r.final_position[0] - 10.0) < 1e-3
    assert "Targeting solutions" in r.note

def test_agent7_mode_b_orbit():
    r = simulate_particle((1,0,0), (0,1,0), inverse_square_field(1.0),
        ForceFieldConfig(dt=0.001, t_max=6.2832, force_law_note="inverse-square"))
    assert abs(r.final_position[0] - 1.0) < 0.05

def test_agent7_api_no_target():
    import inspect
    from aethera.agents.dynamics import simulate_particle
    params = list(inspect.signature(simulate_particle).parameters.keys())
    assert "target" not in params
    assert "azimuth" not in params
    assert "elevation" not in params

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
