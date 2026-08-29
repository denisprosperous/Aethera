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
