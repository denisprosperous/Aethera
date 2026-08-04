#!/bin/bash
set -e
ROOT=/home/z/my-project/aethera-core

# Python package files
cat > $ROOT/python/pyproject.toml << 'TOML'
[project]
name = "aethera"
version = "0.2.0"
description = "AETHERA — first objective geometric substrate."
requires-python = ">=3.10"
dependencies = ["numpy>=2.0", "scipy>=1.14", "networkx>=3.0", "mpmath>=1.3"]

[project.scripts]
aethera = "aethera.cli.main:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
TOML

cat > $ROOT/python/aethera/__init__.py << 'PY'
"""AETHERA — first objective geometric substrate."""
__version__ = "0.2.0"
try:
    from . import _rust  # type: ignore
    HAS_RUST = True
except ImportError:
    HAS_RUST = False
from .core import EdgeGraph, Scalar, IntrinsicManifold, Point3
from .agents import (
    GhostResolver, IntrinsicGeometer, AcifNavigator, AlienGeometer, DynamicsModule,
)
from .modules import (
    TransparencyComparator, StrainVisualizer, AnomalyDaemon,
    MaritimeChokepoint, HallOfShame, TerraformationSimulator, StellarPositioning,
)
__all__ = [
    "EdgeGraph", "Scalar", "IntrinsicManifold", "Point3",
    "GhostResolver", "IntrinsicGeometer", "AcifNavigator", "AlienGeometer",
    "DynamicsModule",
    "TransparencyComparator", "StrainVisualizer", "AnomalyDaemon",
    "MaritimeChokepoint", "HallOfShame", "TerraformationSimulator",
    "StellarPositioning", "HAS_RUST",
]
PY

cat > $ROOT/python/aethera/core.py << 'PY'
"""Core types — mirrors the Rust aethera-core crate."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import json
import mpmath
from mpmath import mpf, sqrt as mpsqrt
mpmath.mp.prec = 256

class Scalar:
    __slots__ = ("val",)
    def __init__(self, val):
        if isinstance(val, Scalar): self.val = val.val
        elif isinstance(val, (mpf, int, float, str)): self.val = mpf(val)
        else: raise TypeError(f"cannot construct Scalar from {type(val)}")
    @classmethod
    def from_str(cls, s): return cls(mpf(s))
    def to_f64(self): return float(self.val)
    def __add__(self, o): return Scalar(self.val + Scalar(o).val)
    def __radd__(self, o): return Scalar(Scalar(o).val + self.val)
    def __sub__(self, o): return Scalar(self.val - Scalar(o).val)
    def __rsub__(self, o): return Scalar(Scalar(o).val - self.val)
    def __mul__(self, o): return Scalar(self.val * Scalar(o).val)
    def __rmul__(self, o): return Scalar(Scalar(o).val * self.val)
    def __truediv__(self, o): return Scalar(self.val / Scalar(o).val)
    def __neg__(self): return Scalar(-self.val)
    def __eq__(self, o): return self.val == Scalar(o).val
    def __lt__(self, o): return self.val < Scalar(o).val
    def __le__(self, o): return self.val <= Scalar(o).val
    def __gt__(self, o): return self.val > Scalar(o).val
    def __ge__(self, o): return self.val >= Scalar(o).val
    def __hash__(self): return hash(self.val)
    def __str__(self): return mpmath.nstr(self.val, 30)
    def __repr__(self): return f"Scalar({self})"

def sqrt(s): return Scalar(mpsqrt(s.val))
def sq(s): return s * s

@dataclass
class Edge:
    a: str
    b: str
    weight: Scalar
    sigma: Optional[Scalar] = None
    source: Optional[str] = None
    epoch: Optional[float] = None

@dataclass
class EdgeGraph:
    edges: list = field(default_factory=list)
    def add_edge(self, a, b, weight, sigma=None, source=None, epoch=None):
        if not isinstance(weight, Scalar): weight = Scalar(weight)
        if sigma is not None and not isinstance(sigma, Scalar): sigma = Scalar(sigma)
        e = Edge(a=a, b=b, weight=weight, sigma=sigma, source=source, epoch=epoch)
        self.edges.append(e); return e
    @property
    def nodes(self):
        seen = set(); out = []
        for e in self.edges:
            if e.a not in seen: seen.add(e.a); out.append(e.a)
            if e.b not in seen: seen.add(e.b); out.append(e.b)
        return out
    @property
    def node_count(self): return len(self.nodes)
    @property
    def edge_count(self): return len(self.edges)
    def node_id(self, name):
        for i, n in enumerate(self.nodes):
            if n == name: return i
        return None

@dataclass
class Point3:
    x: float; y: float; z: float = 0.0
    def dist(self, o): return ((self.x-o.x)**2 + (self.y-o.y)**2 + (self.z-o.z)**2)**0.5

@dataclass
class IntrinsicManifold:
    embedding: str
    coords: dict
    residual: float
    gaussian_curvature: dict = field(default_factory=dict)
    origin: str = ""
PY

cat > $ROOT/python/aethera/_smacof.py << 'PY'
"""Pure-Python SMACOF solver (matches Rust aethera-geometer/smacof.rs)."""
import numpy as np

def classical_mds(delta, dim=2):
    n = delta.shape[0]
    d2 = delta ** 2
    row_mean = d2.mean(axis=1, keepdims=True)
    col_mean = d2.mean(axis=0, keepdims=True)
    total = d2.mean()
    B = -0.5 * (d2 - row_mean - col_mean + total)
    eigvals, eigvecs = np.linalg.eigh(B)
    order = np.argsort(eigvals)[::-1]
    eigvals = eigvals[order]; eigvecs = eigvecs[:, order]
    coords = np.zeros((n, dim))
    for k in range(dim):
        if eigvals[k] > 0: coords[:, k] = eigvecs[:, k] * np.sqrt(eigvals[k])
    coords -= coords.mean(axis=0)
    return coords

def smacof(delta, weight=None, dim=2, max_iter=500, tol=1e-12):
    n = delta.shape[0]
    if weight is None:
        weight = np.ones((n, n)); np.fill_diagonal(weight, 0)
    V = -weight.copy(); np.fill_diagonal(V, weight.sum(axis=1))
    J = np.ones((n, n)) / n
    Vp = np.linalg.inv(V + J) - J
    X = classical_mds(delta, dim)
    X -= X.mean(axis=0)
    prev = float("inf"); stress = float("inf")
    for it in range(max_iter):
        dis = np.linalg.norm(X[:, None, :] - X[None, :, :], axis=2)
        dis_safe = np.where(dis < 1e-30, 1e-30, dis)
        c = weight * delta / dis_safe; np.fill_diagonal(c, 0)
        B = -c; np.fill_diagonal(B, c.sum(axis=1))
        X = Vp @ (B @ X); X -= X.mean(axis=0)
        new_dis = np.linalg.norm(X[:, None, :] - X[None, :, :], axis=2)
        diff = new_dis - delta
        num = float((weight * diff * diff).sum() / 2)
        denom = float((weight * delta * delta).sum() / 2)
        stress = float(np.sqrt(num / max(denom, 1e-30)))
        rel = abs(prev - stress) / max(prev, 1e-30)
        prev = stress
        if rel < tol: break
    return X, stress

def discrete_gaussian_curvature(coords, adj):
    n = len(adj); curv = np.zeros(n)
    for i in range(n):
        neigh = adj[i]
        if len(neigh) < 3: continue
        diffs = coords[neigh] - coords[i]
        angles = np.arctan2(diffs[:, 1], diffs[:, 0])
        order = np.argsort(angles)
        sorted_n = [neigh[j] for j in order]
        sum_a = 0.0; m = len(sorted_n)
        for k in range(m):
            k1 = (k + 1) % m
            a = sorted_n[k]; b = sorted_n[k1]
            r_a = np.linalg.norm(coords[a] - coords[i])
            r_b = np.linalg.norm(coords[b] - coords[i])
            c_ab = np.linalg.norm(coords[a] - coords[b])
            if r_a < 1e-12 or r_b < 1e-12: continue
            cos_t = (r_a**2 + r_b**2 - c_ab**2) / (2 * r_a * r_b)
            sum_a += np.arccos(float(np.clip(cos_t, -1.0, 1.0)))
        curv[i] = 2 * np.pi - sum_a
    return curv
PY

mkdir -p $ROOT/python/aethera/{agents,modules,io,cli}
cat > $ROOT/python/aethera/agents/__init__.py << 'PY'
from .ghost import GhostResolver
from .geometer import IntrinsicGeometer
from .acif import AcifNavigator
from .alien import AlienGeometer
from .dynamics import DynamicsModule
__all__ = ["GhostResolver", "IntrinsicGeometer", "AcifNavigator", "AlienGeometer", "DynamicsModule"]
PY

cat > $ROOT/python/aethera/agents/geometer.py << 'PY'
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
PY

cat > $ROOT/python/aethera/agents/ghost.py << 'PY'
"""Agent 0 — Ghost Resolver. v6.0: 5% threshold + rationale log."""
import hashlib, json
from dataclasses import dataclass, field
from typing import Optional, List
from ..core import Scalar

@dataclass
class Polygon:
    name: str
    area: Optional[Scalar] = None
    neighbours: List[str] = field(default_factory=list)
    claimed_area: Optional[Scalar] = None
    security_level: str = "N/A"

@dataclass
class RedFlag:
    zone: str
    official_claimed_area: Scalar
    derived_residual_area: Scalar
    ratio: float
    note: str

@dataclass
class RationaleEntry:
    polygon: str
    confidence_pct: float
    rationale: str

@dataclass
class GhostReport:
    polygons: List[Polygon]
    red_flags: List[RedFlag]
    global_enclosure: str
    global_area: Scalar
    sealed_hash: str
    rationale_log: list = field(default_factory=list)

class GhostResolver:
    def solve(self, polygons, global_enclosure, global_area):
        unknowns = [i for i, p in enumerate(polygons) if p.area is None and p.name != global_enclosure]
        if not unknowns:
            return GhostReport(polygons, [], global_enclosure, global_area,
                self._hash(polygons, [], global_enclosure, global_area), [])
        known_sum = sum((p.area.val for p in polygons if p.area is not None and p.name != global_enclosure), Scalar(0).val)
        residual = global_area.val - known_sum
        total_n = sum(max(len(polygons[i].neighbours), 1) for i in unknowns)
        for i in unknowns:
            share = max(len(polygons[i].neighbours), 1) / total_n
            polygons[i].area = Scalar(residual * share)
        red_flags = []
        for p in polygons:
            if p.name == global_enclosure: continue
            if p.claimed_area is not None and p.area is not None:
                c = abs(p.claimed_area.to_f64()); d = abs(p.area.to_f64())
                if c > 0:
                    discp = abs(d - c) / c * 100.0
                    if discp > 5.0:
                        red_flags.append(RedFlag(p.name, p.claimed_area, p.area, d/c,
                            f"Deviation: {discp:.2}%. Transparency tool for public oversight."))
        rationale_log = []
        for p in polygons:
            if p.name == global_enclosure: continue
            neigh = ", ".join(p.neighbours) if p.neighbours else "none"
            if p.area is not None and p.claimed_area is not None:
                d = p.area.to_f64(); c = p.claimed_area.to_f64()
                conf = max(0.0, 100.0 * (1.0 - min(abs(d-c)/max(abs(c),1e-12), 1.0))) if abs(c) > 0 else 99.99
            else: conf = 99.99
            rationale_log.append(RationaleEntry(p.name, conf,
                f"Derived via Topological Residual Closure. Confidence: {conf:.2f%. Adjacency: [{neigh}]."))
        return GhostReport(polygons, red_flags, global_enclosure, global_area,
            self._hash(polygons, red_flags, global_enclosure, global_area), rationale_log)
    @staticmethod
    def _hash(polygons, red_flags, enclosure, global_area):
        payload = json.dumps({
            "polygons": [{"name": p.name, "area": str(p.area) if p.area else None, "claimed": str(p.claimed_area) if p.claimed_area else None} for p in polygons],
            "red_flags": [{"zone": r.zone, "ratio": r.ratio} for r in red_flags],
            "enclosure": enclosure, "global_area": str(global_area),
        }, sort_keys=True)
        return f"sha256:{hashlib.sha256(payload.encode()).hexdigest()}"
PY

cat > $ROOT/python/aethera/agents/acif.py << 'PY'
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
PY

cat > $ROOT/python/aethera/agents/alien.py << 'PY'
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
PY

cat > $ROOT/python/aethera/agents/dynamics.py << 'PY'
"""Agent 7 — Dynamics Module (v6.0 reformulated). Dual-mode, no targeting."""
import heapq
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple
from ..core import EdgeGraph, IntrinsicManifold

ETHICS_NOTE = ("This is a geometric simulation. Targeting solutions "
    "(azimuth, elevation, impact point) are not provided. "
    "The platform is a geometry provider, not a weapons controller.")

@dataclass
class PathResult:
    path: List[str]
    path_length: float
    waypoints: List[Tuple[float, float, float]]
    note: str

class InertialGeodesic:
    def shortest_path(self, graph, manifold, start, end):
        if start == end: raise ValueError("start == end")
        adj = {}
        for e in graph.edges:
            d = e.weight.to_f64()
            adj.setdefault(e.a, []).append((e.b, d))
            adj.setdefault(e.b, []).append((e.a, d))
        dist = {start: 0.0}; prev = {}; visited = set(); heap = [(0.0, start)]
        while heap:
            d, u = heapq.heappop(heap)
            if u in visited: continue
            visited.add(u)
            if u == end: break
            for v, w in adj.get(u, []):
                if v in visited: continue
                nd = d + w
                if nd < dist.get(v, float('inf')):
                    dist[v] = nd; prev[v] = u
                    heapq.heappush(heap, (nd, v))
        if end not in dist: raise ValueError(f"no path {start}→{end}")
        path = [end]; cur = end
        while cur != start:
            cur = prev[cur]; path.append(cur)
        path.reverse()
        waypoints = [(manifold.coords[n].x, manifold.coords[n].y, manifold.coords[n].z)
                     for n in path if n in manifold.coords]
        return PathResult(path, dist[end], waypoints,
            f"Inertial geodesic. Length: {dist[end]:.6f}. {ETHICS_NOTE}")

AccelerationFn = Callable[[Tuple[float,float,float], Tuple[float,float,float], float], Tuple[float,float,float]]

@dataclass
class ForceFieldConfig:
    dt: float = 0.01
    t_max: float = 100.0
    force_law_note: str = "user-supplied"

@dataclass
class SimulationResult:
    trajectory: List[Tuple[float, float, float]]
    times: List[float]
    total_path_length: float
    total_time: float
    final_position: Tuple[float, float, float]
    final_velocity: Tuple[float, float, float]
    note: str

def simulate_particle(start, vel0, accel_fn, config=ForceFieldConfig()):
    if config.dt <= 0: raise ValueError("dt must be > 0")
    trajectory = [start]; times = [0.0]
    pos = start; vel = vel0; t = 0.0; total = 0.0
    n_steps = min(int(config.t_max / config.dt) + 1, 10_000_000)  # AETHERA-GUARD: ALLOW DOCUMENTATION (iteration cap)
    for _ in range(n_steps):
        if t >= config.t_max - 1e-12: break
        np, nv, nt = _rk4_step(pos, vel, t, config.dt, accel_fn)
        if nt > config.t_max:
            frac = (config.t_max - t) / (nt - t)
            np = tuple(pos[i] + frac * (np[i] - pos[i]) for i in range(3))
            nv = tuple(vel[i] + frac * (nv[i] - vel[i]) for i in range(3))
            nt = config.t_max
        dx = np[0]-pos[0]; dy = np[1]-pos[1]; dz = np[2]-pos[2]
        total += (dx*dx + dy*dy + dz*dz) ** 0.5
        pos = np; vel = nv; t = nt
        trajectory.append(pos); times.append(t)
        if t >= config.t_max: break
    return SimulationResult(trajectory, times, total, t, pos, vel,
        f"Force law: {config.force_law_note}. Path: {total:.6f}. Time: {t:.6f}s. {ETHICS_NOTE}")

def _rk4_step(pos, vel, t, dt, fn):
    a1 = fn(pos, vel, t); k1p = vel; k1v = a1
    p2 = tuple(pos[i] + 0.5*dt*k1p[i] for i in range(3))
    v2 = tuple(vel[i] + 0.5*dt*k1v[i] for i in range(3))
    a2 = fn(p2, v2, t + 0.5*dt); k2p = v2; k2v = a2
    p3 = tuple(pos[i] + 0.5*dt*k2p[i] for i in range(3))
    v3 = tuple(vel[i] + 0.5*dt*k2v[i] for i in range(3))
    a3 = fn(p3, v3, t + 0.5*dt); k3p = v3; k3v = a3
    p4 = tuple(pos[i] + dt*k3p[i] for i in range(3))
    v4 = tuple(vel[i] + dt*k3v[i] for i in range(3))
    a4 = fn(p4, v4, t + dt); k4p = v4; k4v = a4
    np = tuple(pos[i] + dt/6.0 * (k1p[i] + 2*k2p[i] + 2*k3p[i] + k4p[i]) for i in range(3))
    nv = tuple(vel[i] + dt/6.0 * (k1v[i] + 2*k2v[i] + 2*k3v[i] + k4v[i]) for i in range(3))
    return np, nv, t + dt

def inertial_field(): return lambda p, v, t: (0.0, 0.0, 0.0)
def inverse_square_field(mu, center=(0,0,0)):
    cx, cy, cz = center
    def fn(pos, vel, t):
        dx, dy, dz = pos[0]-cx, pos[1]-cy, pos[2]-cz
        r2 = dx*dx + dy*dy + dz*dz
        r = max(r2 ** 0.5, 1e-12)
        a = -mu / max(r2, 1e-12)
        return (a*dx/r, a*dy/r, a*dz/r)
    return fn
def uniform_field(accel):
    ax, ay, az = accel
    return lambda p, v, t: (ax, ay, az)

class DynamicsModule:
    def __init__(self): self.geodesic = InertialGeodesic()
    def shortest_path(self, graph, manifold, start, end):
        return self.geodesic.shortest_path(graph, manifold, start, end)
    def simulate(self, start, vel0, accel_fn, config=None):
        return simulate_particle(start, vel0, accel_fn, config or ForceFieldConfig())
PY

cat > $ROOT/python/aethera/modules/__init__.py << 'PY'
from .transparency import TransparencyComparator
from .seismic import StrainVisualizer
from .anomaly import AnomalyDaemon
from .maritime import MaritimeChokepoint
from .hall_of_shame import HallOfShame
from .terraformation import TerraformationSimulator
from .stellar import StellarPositioning
__all__ = ["TransparencyComparator", "StrainVisualizer", "AnomalyDaemon",
    "MaritimeChokepoint", "HallOfShame", "TerraformationSimulator", "StellarPositioning"]
PY

cat > $ROOT/python/aethera/modules/transparency.py << 'PY'
"""Module 5A — Transparency Comparator. No targeting — just chord vs claimed range."""
import math
from dataclasses import dataclass
from typing import Tuple

@dataclass
class RangeClaim:
    launch_name: str
    target_name: str
    launch_xyz: Tuple[float, float, float]
    target_xyz: Tuple[float, float, float]
    claimed_range_m: float

@dataclass
class ExaggerationCertificate:
    launch: str; target: str
    claimed_range_m: float
    geometric_chord_m: float
    ratio: float
    is_exaggerated: bool
    note: str

class TransparencyComparator:
    def __init__(self, exaggeration_threshold=1.01):
        self.threshold = exaggeration_threshold
    def chord_distance(self, a, b):
        return math.sqrt(sum((x-y)**2 for x, y in zip(a, b)))
    def evaluate(self, claim):
        chord = self.chord_distance(claim.launch_xyz, claim.target_xyz)
        if chord <= 0:
            return ExaggerationCertificate(claim.launch_name, claim.target_name,
                claim.claimed_range_m, chord, float("inf"), True, "Zero chord.")
        ratio = claim.claimed_range_m / chord
        is_ex = ratio > self.threshold
        note = (f"Claimed {claim.claimed_range_m:.0f}m vs chord {chord:.0f}m (ratio {ratio:.3f}). "
                f"{'Exaggerated' if is_ex else 'Consistent'}. Transparency tool, no targeting.")
        return ExaggerationCertificate(claim.launch_name, claim.target_name,
            claim.claimed_range_m, chord, ratio, is_ex, note)
    def evaluate_many(self, claims): return [self.evaluate(c) for c in claims]
PY

cat > $ROOT/python/aethera/modules/seismic.py << 'PY'
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
PY

cat > $ROOT/python/aethera/modules/anomaly.py << 'PY'
"""Module 5C — Anomaly Daemon (v6.0 civil-scientific)."""
from dataclasses import dataclass
from typing import List, Tuple
from ..agents.acif import AcifSnapshot

@dataclass
class AnomalyAlert:
    edge: Tuple[str, str]
    epochs: Tuple[float, float]
    delta_per_day_cm: float
    note: str

class AnomalyDaemon:
    def __init__(self, threshold_cm_per_day=1.0):
        self.threshold = threshold_cm_per_day
    def run(self, snapshots: List[AcifSnapshot]) -> List[AnomalyAlert]:
        if len(snapshots) < 2: return []
        alerts = []
        for i in range(len(snapshots) - 1):
            s0, s1 = snapshots[i], snapshots[i+1]
            dt = (s1.epoch - s0.epoch) / 86400.0
            if dt <= 0: continue
            map0 = {(a,b): d for a,b,d in s0.edge_lengths}
            map1 = {(a,b): d for a,b,d in s1.edge_lengths}
            deltas = []
            for (a,b), d1 in map1.items():
                d0 = map0.get((a,b)) or map0.get((b,a))
                if d0 is None: continue
                deltas.append((a, b, (d1 - d0) * 100.0))
            if not deltas: continue
            sum_abs = sum(abs(d) for _,_,d in deltas); n = len(deltas)
            for a, b, dc in deltas:
                pd = dc / dt
                if abs(pd) < self.threshold: continue
                loo = (sum_abs - abs(dc)) / max(n-1, 1)
                is_local = abs(dc) > 1e-9 if loo < 1e-12 else (abs(dc)/loo) > 2.0
                if not is_local: continue
                alerts.append(AnomalyAlert((a,b), (s0.epoch, s1.epoch), pd,
                    f"Edge {a}-{b} {pd:+.3} cm/day. Possible: groundwater, glacial, volcanic, geothermal."))
        return alerts
PY

cat > $ROOT/python/aethera/modules/maritime.py << 'PY'
"""Module 5D — Maritime Chokepoint Reconstructor."""
import math
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class Chokepoint:
    name: str
    width_m: float
    depth_m: float
    draft_m: float
    beam_m: float

@dataclass
class NavigabilityReport:
    name: str
    tide_offset_m: float
    effective_width_m: float
    effective_depth_m: float
    navigable: bool
    max_vessel_beam_m: float
    max_vessel_draft_m: float
    navigability_index: float
    note: str

class MaritimeChokepoint:
    def __init__(self, safety_margin_m=50.0):
        self.safety = safety_margin_m
    def evaluate(self, cp, tide_offset_m=0.0):
        ed = cp.depth_m + tide_offset_m
        ew = cp.width_m
        md = ed - self.safety
        mb = ew
        nav = md >= cp.draft_m and mb >= cp.beam_m
        di = min(1.0, max(0.0, md / max(cp.draft_m, 1e-12))) * min(1.0, mb / max(cp.beam_m, 1e-12))
        note = f"{cp.name}: tide {tide_offset_m:+.2f}m, eff depth {ed:.2f}m. {'Navigable' if nav else 'NOT navigable'}."
        return NavigabilityReport(cp.name, tide_offset_m, ew, ed, nav, mb, md, di, note)
    def evaluate_over_tide_range(self, cp, tide_range):
        return [self.evaluate(cp, t) for t in tide_range]
    def shortest_transit_path(self, chokes, tide_offset_m):
        nav = [c for c in chokes if self.evaluate(c, tide_offset_m).navigable]
        if not nav: return ([], 0.0)
        return ([c.name for c in nav], sum(c.width_m for c in nav))
PY

cat > $ROOT/python/aethera/modules/hall_of_shame.py << 'PY'
"""Module 5E — Consensus Hall of Shame. Projection strain tensor + Colonial Distortion Score."""
import math
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

def mercator(lon, lat):
    lr = math.radians(max(-89.999, min(89.999, lat)))
    return (math.radians(lon), math.log(math.tan(math.pi/4 + lr/2)))
def robinson(lon, lat):
    lr = math.radians(lat)
    return (math.radians(lon) * math.cos(lr * 0.7), lr * (1.0 - 0.1 * lr**2))
def authagraph(lon, lat):
    lr = math.radians(lat)
    return (math.radians(lon) * math.cos(lr), math.sin(lr))
def equirectangular(lon, lat):
    return (math.radians(lon), math.radians(lat))

PROJECTIONS = {"Mercator": mercator, "Robinson": robinson,
    "AuthaGraph": authagraph, "Equirectangular": equirectangular}

@dataclass
class Polygon:
    name: str
    vertices_lonlat: List[Tuple[float, float]]
    area_km2_true: float
    coloniser: bool = False

@dataclass
class StrainField:
    polygon_name: str
    centroid: Tuple[float, float]
    area_projected: float
    area_true: float
    scale_factor: float
    log_strain: float
    colour: Tuple[float, float, float]

@dataclass
class DistortionScore:
    projection: str
    mean_log_strain: float
    std_log_strain: float
    max_inflation: float
    max_deflation: float
    colonial_distortion_score: float
    note: str

def _shoelace(v):
    if len(v) < 3: return 0.0
    s = 0.0
    for i in range(len(v)):
        x1, y1 = v[i]; x2, y2 = v[(i+1) % len(v)]
        s += x1*y2 - x2*y1
    return abs(s) / 2.0

def _centroid(v):
    n = len(v)
    return (sum(p[0] for p in v)/n, sum(p[1] for p in v)/n)

def strain_field(polys, proj, name):
    out = []
    for p in polys:
        verts = [proj(lon, lat) for lon, lat in p.vertices_lonlat]
        ap = _shoelace(verts)
        scale = ap / max(p.area_km2_true, 1e-12)
        ls = math.log(max(scale, 1e-12))
        cent = _centroid(verts)
        if ls > 0:
            t = min(1.0, ls / 2.0); col = (1.0, 1.0-t, 1.0-t)
        else:
            t = min(1.0, -ls / 2.0); col = (1.0-t, 1.0-t, 1.0)
        out.append(StrainField(p.name, cent, ap, p.area_km2_true, scale, ls, col))
    return out

def colonial_distortion_score(polys, proj, name):
    sfs = strain_field(polys, proj, name)
    cs = [s.log_strain for s, p in zip(sfs, polys) if p.coloniser]
    ds = [s.log_strain for s, p in zip(sfs, polys) if not p.coloniser]
    mc = sum(cs) / max(len(cs), 1); md = sum(ds) / max(len(ds), 1)
    alls = [s.log_strain for s in sfs]
    ma = sum(alls) / max(len(alls), 1)
    std = math.sqrt(sum((x-ma)**2 for x in alls) / max(len(alls), 1)) if alls else 0.0
    score = mc - md
    return DistortionScore(name, ma, std,
        max(alls) if alls else 0.0, min(alls) if alls else 0.0, score,
        f"{name}: coloniser mean {mc:+.3f}, colonised mean {md:+.3f}. Score {score:+.3f}.")

class HallOfShame:
    def __init__(self, polys): self.polys = polys
    def all_scores(self):
        return [colonial_distortion_score(self.polys, p, n) for n, p in PROJECTIONS.items()]
PY

cat > $ROOT/python/aethera/modules/terraformation.py << 'PY'
"""Module 5F — Terraformation Simulator."""
from dataclasses import dataclass, field
from typing import Dict, List
from .hall_of_shame import Polygon

@dataclass
class VolumeTransfer:
    source: str
    target: str
    volume_km3: float

@dataclass
class CoastlineChange:
    nation: str
    area_change_km2: float
    habitable_area_km2_before: float
    habitable_area_km2_after: float
    note: str

@dataclass
class ReparationsReport:
    transfers: List[VolumeTransfer]
    coastline_changes: List[CoastlineChange]
    reparations_index: Dict[str, float]
    note: str

class TerraformationSimulator:
    def __init__(self, polys):
        self.polys = {p.name: p for p in polys}
    def simulate(self, transfers):
        changes = {n: 0.0 for n in self.polys}
        for t in transfers:
            avg_depth_km = 0.1  # AETHERA-GUARD: ALLOW DOCUMENTATION (assumed avg depth)
            ac = t.volume_km3 / avg_depth_km
            changes[t.source] = changes.get(t.source, 0.0) - ac
            changes[t.target] = changes.get(t.target, 0.0) + ac
        cc = []; ri = {}
        for name, delta in changes.items():
            poly = self.polys.get(name)
            if poly is None: continue
            before = poly.area_km2_true
            after = max(0.0, before + delta)
            cc.append(CoastlineChange(name, delta, before, after,
                f"{name}: {delta:+.0f} km² ({before:.0f} → {after:.0f})."))
            ri[name] = delta
        return ReparationsReport(transfers, cc, ri,
            f"Simulated {len(transfers)} transfers. Net: {sum(changes.values()):+.0f} km².")
PY

cat > $ROOT/python/aethera/modules/stellar.py << 'PY'
"""Module 5G — Stellar Positioning Grid."""
import math
from dataclasses import dataclass
from typing import List, Tuple
from ..core import EdgeGraph, Scalar
from .geometer import IntrinsicGeometer

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
PY

# CLI + IO stubs
cat > $ROOT/python/aethera/cli/__init__.py << 'PY'
PY
cat > $ROOT/python/aethera/cli/main.py << 'PY'
"""AETHERA CLI — minimal entry point."""
import sys, json
def main():
    if len(sys.argv) < 2:
        print("AETHERA v0.2.0 — usage: aethera <command>")
        print("Commands: solve, ghost, alien, dynamics")
        return
    cmd = sys.argv[1]
    if cmd == "version":
        from aethera import __version__
        print(__version__)
    else:
        print(f"Unknown command: {cmd}")
PY
cat > $ROOT/python/aethera/io/__init__.py << 'PY'
PY

echo "Python package written"
