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
