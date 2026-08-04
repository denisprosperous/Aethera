"""Module 5B — Strain Visualizer (v6.0 renamed, not a predictor)."""
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple
from ..core import EdgeGraph, Scalar
from .._smacof import smacof

@dataclass
class SeismicEvent:
    station: str
    p_wave_arrival_s: float
    location_xyz: Tuple[float, float, float] = (0.0, 0.0, 0.0)

@dataclass
class StrainManifold:
    coords: dict
    strain_field: dict
    edges: List[Tuple[str, str, float]]

@dataclass
class RuptureVisualization:
    path: List[str]
    path_length: float
    strain_concentration: float
    note: str
    @property
    def disclaimer(self):
        return ("This is a strain visualization tool. Prediction accuracy "
                "depends on user-provided rupture models. Not sufficient "
                "for earthquake prediction.")

class StrainVisualizer:
    def __init__(self, p_wave_speed_m_per_s=6000.0):
        self.speed = p_wave_speed_m_per_s
    def build_strain_manifold(self, events, reference_station=None):
        if len(events) < 3: raise ValueError(f"need >= 3, got {len(events)}")
        if reference_station is None:
            reference_station = min(events, key=lambda e: e.p_wave_arrival_s).station
        g = EdgeGraph()
        for i, a in enumerate(events):
            for b in events[i+1:]:
                dt = abs(a.p_wave_arrival_s - b.p_wave_arrival_s)
                g.add_edge(a.station, b.station, Scalar(dt * self.speed), source="P-wave")
        delta = np.zeros((len(events), len(events)))
        weight = np.zeros((len(events), len(events)))
        names = [e.station for e in events]
        idx = {n: i for i, n in enumerate(names)}
        for e in g.edges:
            i, j = idx[e.a], idx[e.b]
            d = e.weight.to_f64()
            delta[i,j] = d; delta[j,i] = d
            weight[i,j] = 1.0; weight[j,i] = 1.0
        coords, _ = smacof(delta, weight, dim=2, max_iter=500, tol=1e-12)
        strain_field = {n: 0.0 for n in names}
        for e in g.edges:
            d = e.weight.to_f64()
            strain_field[e.a] += d; strain_field[e.b] += d
        edges_list = [(e.a, e.b, e.weight.to_f64()) for e in g.edges]
        return StrainManifold(
            {names[i]: (float(coords[i,0]), float(coords[i,1])) for i in range(len(names))},
            strain_field, edges_list)
    def visualize_minimal_rupture_path(self, sm):
        if not sm.coords: raise ValueError("empty")
        adj = {n: [] for n in sm.coords}
        for a, b, s in sm.edges:
            adj[a].append((b, s)); adj[b].append((a, s))
        for n in adj: adj[n].sort(key=lambda x: -x[1])
        start = max(sm.strain_field.items(), key=lambda x: x[1])[0]
        path = [start]; visited = {start}; total_s = 0.0; total_l = 0.0
        while True:
            cur = path[-1]
            nxt = None; ns = 0.0
            for n, s in adj.get(cur, []):
                if n not in visited and s > ns: nxt = n; ns = s
            if nxt is None: break
            path.append(nxt); visited.add(nxt); total_s += ns
            x1, y1 = sm.coords[cur]; x2, y2 = sm.coords[nxt]
            total_l += float(np.hypot(x2-x1, y2-y1))
        return RuptureVisualization(path, total_l, total_s,
            f"Path through {len(path)} stations. Strain: {total_s:.0f}. {self._disclaimer()}")
    @staticmethod
    def _disclaimer():
        return ("Strain visualization tool. Not sufficient for earthquake prediction.")

SeismicForecaster = StrainVisualizer  # backward compat
