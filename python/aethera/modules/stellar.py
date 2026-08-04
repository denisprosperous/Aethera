"""Module 5G — Stellar Positioning Grid."""
import math
from dataclasses import dataclass
from typing import List, Tuple
from ..core import EdgeGraph, Scalar
from ..agents.geometer import IntrinsicGeometer

@dataclass
class QuasarObservation:
    quasar_name: str
    probe_to_quasar_angular_sep_rad: float
    baseline_m: float

@dataclass
class StellarPosition:
    probe_coords: Tuple[float, float, float]
    residual: float
    reference_count: int
    note: str

class StellarPositioning:
    def __init__(self, max_iter=500, tol=1e-12):
        self.geometer = IntrinsicGeometer(max_iter=max_iter, tol=tol)
    def solve(self, observations, probe_name="Probe"):
        g = EdgeGraph()
        for obs in observations:
            chord = 2.0 * obs.baseline_m * math.sin(obs.probe_to_quasar_angular_sep_rad / 2.0)
            g.add_edge(probe_name, f"qsr:{obs.quasar_name}", Scalar(chord), source="VLBI-stellar")
        for i, o1 in enumerate(observations):
            for o2 in observations[i+1:]:
                theta = math.pi / 2  # default 90°
                chord = 2.0 * o1.baseline_m * math.sin(theta / 2)
                g.add_edge(f"qsr:{o1.quasar_name}", f"qsr:{o2.quasar_name}", Scalar(chord), source="VLBI-interquasar")
        mf = self.geometer.solve_3d(g)
        probe = mf.coords.get(probe_name)
        if probe is None:
            return StellarPosition((0,0,0), mf.residual, len(observations), "Probe not found.")
        return StellarPosition((probe.x, probe.y, probe.z), mf.residual, len(observations),
            f"Solved from {len(observations)} quasars. Residual {mf.residual:.2e}. No ephemeris used.")
