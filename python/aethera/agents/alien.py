"""Agent 8 — Alien Geometer."""
from dataclasses import dataclass
from typing import Tuple
from ..core import EdgeGraph, IntrinsicManifold
from .geometer import IntrinsicGeometer

@dataclass
class AlienReport:
    shape: str
    embedding: str
    residual: float
    mean_curvature: float
    max_curvature: float
    min_curvature: float
    node_count: int
    edge_count: int

class AlienGeometer:
    def __init__(self, max_iter=500, tol=1e-12):
        self.geometer = IntrinsicGeometer(max_iter=max_iter, tol=tol)
    def analyse(self, graph):
        m2 = self.geometer.solve_2d(graph)
        if m2.residual < 1e-4: mf, emb = m2, "2D"
        else:
            try:
                m3 = self.geometer.solve_3d(graph)
                if m3.residual < m2.residual: mf, emb = m3, "3D"
                else: mf, emb = m2, "2D"
            except Exception: mf, emb = m2, "2D"
        curvs = list(mf.gaussian_curvature.values())
        if mf.residual < 1e-6: shape = "Flat"
        elif mf.residual < 1e-2:
            if not curvs: shape = "Ellipsoidal"
            else:
                import statistics
                mean = sum(curvs) / len(curvs)
                std = statistics.pstdev(curvs) if len(curvs) > 1 else 0.0
                shape = "Ellipsoidal" if abs(mean) < 1e-9 or std / max(abs(mean), 1e-12) < 0.3 else "Potato"
        else: shape = "Potato"
        mean_c = sum(curvs) / len(curvs) if curvs else 0.0
        return mf, AlienReport(shape, emb, mf.residual, mean_c,
            max(curvs) if curvs else 0.0, min(curvs) if curvs else 0.0,
            graph.node_count, graph.edge_count)
    def safest_touchdown_ellipse(self, manifold, radius_m):
        if not manifold.coords: return None
        coords = list(manifold.coords.items())
        best_score = float("inf"); best = None
        for i, (_, p_i) in enumerate(coords):
            sum_dev = 0.0; cnt = 0
            for j, (_, p_j) in enumerate(coords):
                if i == j: continue
                d = p_i.dist(p_j)
                if d > radius_m * 2: continue
                sum_dev += d; cnt += 1
            if cnt == 0: continue
            score = abs(sum_dev / cnt - radius_m)
            if score < best_score: best_score = score; best = (p_i.x, p_i.y)
        return best
