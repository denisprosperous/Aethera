"""Agent 2 — Intrinsic Geometer (Python wrapper)."""
import numpy as np
from ..core import EdgeGraph, Scalar, IntrinsicManifold, Point3
from .._smacof import smacof, discrete_gaussian_curvature

class IntrinsicGeometer:
    def __init__(self, max_iter=500, tol=1e-12, precision_bits=256):
        self.max_iter = max_iter; self.tol = tol
    def solve_2d(self, graph):
        nodes = graph.nodes; n = len(nodes)
        if n < 3: raise ValueError(f"need >= 3 nodes, got {n}")
        delta, weight = self._build(graph, nodes)
        coords, stress = smacof(delta, weight, dim=2, max_iter=self.max_iter, tol=self.tol)
        cm = {nodes[i]: Point3(coords[i,0], coords[i,1], 0.0) for i in range(n)}
        adj = self._adj(graph, nodes)
        curv = discrete_gaussian_curvature(coords, adj)
        return IntrinsicManifold("2D", cm, stress,
            {nodes[i]: float(curv[i]) for i in range(n)}, "Agent 2")
    def solve_3d(self, graph):
        nodes = graph.nodes; n = len(nodes)
        if n < 4: raise ValueError(f"need >= 4 nodes, got {n}")
        delta, weight = self._build(graph, nodes)
        coords, stress = smacof(delta, weight, dim=3, max_iter=self.max_iter, tol=self.tol)
        cm = {nodes[i]: Point3(coords[i,0], coords[i,1], coords[i,2]) for i in range(n)}
        return IntrinsicManifold("3D", cm, stress, {}, "Agent 2 (3D)")
    @staticmethod
    def _build(graph, nodes):
        n = len(nodes); idx = {name: i for i, name in enumerate(nodes)}
        delta = np.zeros((n, n)); weight = np.zeros((n, n))
        for e in graph.edges:
            i, j = idx[e.a], idx[e.b]
            d = e.weight.to_f64(); delta[i,j] = d; delta[j,i] = d
            w = 1.0 / e.sigma.to_f64()**2 if e.sigma and e.sigma.to_f64() > 0 else 1.0
            weight[i,j] = w; weight[j,i] = w
        return delta, weight
    @staticmethod
    def _adj(graph, nodes):
        idx = {name: i for i, name in enumerate(nodes)}
        adj = [[] for _ in nodes]
        for e in graph.edges:
            i, j = idx[e.a], idx[e.b]
            adj[i].append(j); adj[j].append(i)
        return adj
