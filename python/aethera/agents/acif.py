"""Agent 6 — ACIF Navigator."""
import math
from dataclasses import dataclass
from typing import Optional, List
from ..core import EdgeGraph, Scalar, IntrinsicManifold
from .geometer import IntrinsicGeometer

@dataclass
class AcifSnapshot:
    epoch: float
    edge_lengths: List[tuple]
    frame: Optional[IntrinsicManifold] = None

class AcifNavigator:
    def __init__(self, max_iter=500, tol=1e-12):
        self.geometer = IntrinsicGeometer(max_iter=max_iter, tol=tol)
    def solve_frame(self, graph):
        return self.geometer.solve_2d(graph)
    def snapshot(self, epoch, graph):
        frame = self.solve_frame(graph)
        edges = [(e.a, e.b, e.weight.to_f64()) for e in graph.edges]
        return AcifSnapshot(epoch, edges, frame)
    @staticmethod
    def import_interferometric_csv(csv):
        g = EdgeGraph()
        for i, line in enumerate(csv.splitlines()):
            line = line.strip()
            if not line or line.startswith("#"): continue
            cols = [c.strip() for c in line.split(",")]
            if len(cols) < 3: raise ValueError(f"line {i}: expected >=3 columns")
            phase = float(cols[2])
            sigma = float(cols[3]) if len(cols) > 3 else None
            g.add_edge(cols[0], cols[1], Scalar(phase), Scalar(sigma) if sigma else None, source="ACIF-phase")
        return g
    @staticmethod
    def import_vlbi_angular_csv(csv):
        g = EdgeGraph()
        for i, line in enumerate(csv.splitlines()):
            line = line.strip()
            if not line or line.startswith("#"): continue
            cols = [c.strip() for c in line.split(",")]
            if len(cols) < 4: raise ValueError(f"line {i}: expected 4 columns")
            theta = float(cols[2]); baseline = float(cols[3])
            chord = 2 * baseline * math.sin(theta / 2)
            g.add_edge(cols[0], cols[1], Scalar(chord), None, source="VLBI-chord")
        return g
